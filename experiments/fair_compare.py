"""Equal end-to-end wall budgets: compact CPLEX IP vs exact CG + restricted IP.

Uses existing mathematical builders and exact pricing without modifications.
An interrupted root retains generated columns and bounds from fully priced rounds.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time
import traceback

from generate_instances import write_suite
from run_experiments import save_summary

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code/dwcg'))
import solve as cg_module
from common import compact
from master import build_master,decode_integer
from solver_backend import BackendConfig,make_solver,use_backend,load_cplex
import pulp


def relative_gap(upper,lower):
    return None if upper is None or lower is None else max(0,upper-lower)/(abs(lower)+1e-10)


def arm(data,config,kind,log_dir):
    budget=config['equal_budget_seconds'];events=[]
    settings=BackendConfig(name='cplex_py',seed=config.get('solver_seed',11),threads=1,log_dir=str(log_dir))
    result=dict(kind=kind,budget_seconds=budget,optimal=False,incumbent=None,best_bound=None,relative_gap=None)
    begin=time.perf_counter();end=begin+budget
    settings.deadline=end
    with use_backend(settings,events):
        if kind=='compact_ip':
            try:
                model=compact.build_model(data)
                result['model_build_time']=time.perf_counter()-begin
                model.problem.solve(make_solver(role='compact_ip'))
                native=model.problem.backend_result
                result.update(status=native['status'],optimal=native['optimal'],incumbent=native['objective'],
                              best_bound=native['best_bound'],relative_gap=native['relative_gap'],native=native)
                if native['has_incumbent']:result['solution']=compact.solution_report(model)
            except TimeoutError as error:result.update(status='time_limit',error=str(error))
        else:
            originals={name:getattr(cg_module,name) for name in ('build_master','solve_master','price')}
            held={'pool':None,'master':None,'pricing':[],'phase':1,'iteration':0}
            metrics=dict(rmp_build_time=0.,rmp_solve_time=0.,pricing_wall_time=0.,pricing_calls=0)
            rounds=[];pp=[];best_upper=None
            expected={(l['id'],s) for l in data['lines'] for s in range(1,len(l['stations'])+1)}

            def build(*args,**kwargs):
                phase=args[2] if len(args)>2 else kwargs.get('phase',2)
                if phase!=held['phase']:held['iteration']=0
                held.update(pool=args[1],phase=phase,iteration=held['iteration']+1,pricing=[])
                tick=time.perf_counter()
                try:return originals['build_master'](*args,**kwargs)
                finally:metrics['rmp_build_time']+=time.perf_counter()-tick

            def master(*args,**kwargs):
                tick=time.perf_counter()
                try:
                    m=originals['solve_master'](*args,**kwargs);held['master']=m;return m
                finally:metrics['rmp_solve_time']+=time.perf_counter()-tick

            def price(*args,**kwargs):
                nonlocal best_upper
                tick=time.perf_counter();status='not_proven';rc=None
                try:
                    answer=originals['price'](*args,**kwargs);rc=answer[1];status='optimal'
                    entry=dict(line=args[0]['id'],station=args[1],reduced_cost=rc,
                               assignments=list(answer[0].assignments))
                    held['pricing'].append(entry)
                    if len(held['pricing'])==len(expected):
                        if {(p['line'],p['station']) for p in held['pricing']}!=expected:
                            raise RuntimeError('Incomplete or duplicate exact pricing round')
                        value=held['master'].value();upper=value+sum(max(0,p['reduced_cost']) for p in held['pricing'])
                        rounds.append(dict(phase=held['phase'],iteration=held['iteration'],objective=value,
                                           upper_bound=upper,maximum_reduced_cost=max(p['reduced_cost'] for p in held['pricing']),
                                           duals=[dict(row=list(row),value=value) for row,value in held['master'].duals().items()],
                                           pricing=list(held['pricing'])))
                        if held['phase']==2:best_upper=upper if best_upper is None else min(best_upper,upper)
                    return answer
                finally:
                    elapsed=time.perf_counter()-tick;metrics['pricing_wall_time']+=elapsed;metrics['pricing_calls']+=1
                    pp.append(dict(phase=held['phase'],iteration=held['iteration'],line=args[0]['id'],station=args[1],
                                   status=status,reduced_cost=rc,wall_time=elapsed))

            cg_module.build_master,cg_module.solve_master,cg_module.price=build,master,price
            settings.deadline=begin+budget*config['root_fraction']
            cg=None;pool=None
            try:
                cg,pool=cg_module.run_cg(data,max_iterations=config.get('max_iterations',1000),recover=False)
                result['cg']=cg;result['root_status']=cg['status'];result['root_converged']=cg['lp_converged']
            except (RuntimeError,TimeoutError) as error:
                last=events[-1] if events else {}
                result.update(root_status='time_limit' if isinstance(error,TimeoutError) or last.get('status')=='time_limit'
                              else 'numerical_or_solver_exception',root_converged=False,root_error=repr(error))
            finally:
                result['root_wall_time']=time.perf_counter()-begin
                for name,fn in originals.items():setattr(cg_module,name,fn)
            if pool is None:pool=held['pool']
            result.update(metrics,completed_pricing_rounds=rounds,pricing_calls_detail=pp,
                          best_bound=best_upper,root_lp_objective=cg['lp_objective'] if cg and cg['lp_converged'] else None,
                          columns_generated=sum(map(len,pool.values())) if pool else None)
            result['recovery_status']='not_run'
            result['generated_pool']=[dict(line=l,station=s,patterns=[list(c.assignments) for c in cols])
                                      for (l,s),cols in pool.items()] if pool else []
            settings.deadline=end
            tick=time.perf_counter()
            if pool and tick<end:
                try:
                    m=build_master(data,pool,integer=True)
                    m.problem.solve(make_solver(role='recovery'))
                    native=m.problem.backend_result
                    result['recovery_native']=native;result['recovery_status']=native['status']
                    if native['has_incumbent']:
                        report=decode_integer(data,pool,m);result['solution']=report
                        result['incumbent']=report['objective']
                except TimeoutError as error:result.update(recovery_status='time_limit',recovery_error=str(error))
            result['integer_recovery_time']=time.perf_counter()-tick
            result['relative_gap']=relative_gap(result['best_bound'],result['incumbent'])
            result['status']=('feasible_unproven' if result['incumbent'] is not None else 'no_integer_solution')
            # Restricted-IP optimality is not original-IP optimality. Root convergence
            # is reported separately, even if the two global bounds happen to coincide.
            result['optimal']=False
    result.update(wall_time=time.perf_counter()-begin,events=events)
    result['budget_overrun_seconds']=max(0,result['wall_time']-budget)
    return result


def execute(task):
    data=json.loads(Path(task['instance_path']).read_text());compact.validate_data(data)
    out=Path(task['output']);out.parent.mkdir(parents=True,exist_ok=True)
    result=dict(task=task,start_utc=datetime.now(timezone.utc).isoformat())
    # Identical API warmup before either method; no witness/solution is fed to solvers.
    native=load_cplex().Cplex();native.end()
    for kind in task['order']:
        result['current_stage']=kind
        out.write_text(json.dumps(result,indent=2),encoding='utf-8')
        result[kind]=arm(data,task['config'],kind,out.parent.parent/'logs'/out.stem/kind)
        out.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    # Separately timed diagnostic LP, excluded from both method budgets and not fed
    # to either method. It is not relabelled as a CG-produced bound.
    with use_backend(BackendConfig(name='cplex_py',time_limit=10,log_dir=str(out.parent.parent/'logs'/out.stem/'diagnostic'))):
        tick=time.perf_counter();m=compact.build_model(data)
        for v in m.problem.variables():v.cat=pulp.LpContinuous
        m.problem.solve(make_solver(mip=False,role='compact_lp'))
        result['compact_lp_diagnostic']=dict(m.problem.backend_result)
        result['compact_lp_diagnostic']['end_to_end_wall']=time.perf_counter()-tick
    ip=result['compact_ip'];cg=result['cg_pipeline']
    for upper,lower in ((ip['best_bound'],cg['incumbent']),(cg['best_bound'],ip['incumbent'])):
        if upper is not None and lower is not None and lower>upper+1e-4:
            raise RuntimeError('Independent incumbent/upper-bound comparison violated')
    result['current_stage']='complete';result['finish_utc']=datetime.now(timezone.utc).isoformat()
    out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return result


def summarize(raw):
    e=raw['task']['entry'];r=dict(instance_id=e['instance_id'],seed=e['seed'],tasks_per_line=e['factor'],
        total_tasks=e['metadata']['total_tasks'],lines=e['metadata']['lines'],budget_seconds=raw['task']['config']['equal_budget_seconds'])
    for name,prefix in [('compact_ip','ip'),('cg_pipeline','cg')]:
        for key in ('status','wall_time','optimal','incumbent','best_bound','relative_gap','budget_overrun_seconds'):
            r[prefix+'_'+key]=raw.get(name,{}).get(key)
    c=raw.get('cg_pipeline',{})
    for key in ('root_status','root_converged','root_lp_objective','root_wall_time','recovery_status',
                'integer_recovery_time','columns_generated','rmp_build_time','rmp_solve_time','pricing_wall_time','pricing_calls'):
        r['cg_'+key]=c.get(key)
    if r['ip_incumbent'] is not None and r['cg_incumbent'] is not None:
        r['cg_minus_ip_profit']=r['cg_incumbent']-r['ip_incumbent']
    else:r['cg_minus_ip_profit']=None
    r['compact_lp_diagnostic']=raw.get('compact_lp_diagnostic',{}).get('objective')
    return r


def run(config_path,out,limit=None):
    config=json.loads(config_path.read_text());out.mkdir(parents=True,exist_ok=False)
    for folder in ('raw','logs','tasks','source'):(out/folder).mkdir()
    (out/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    hashes={}
    for path in list((ROOT/'code').glob('**/*.py'))+list((ROOT/'experiments').glob('*.py')):
        relative=path.relative_to(ROOT);dest=out/'source'/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest);hashes[str(relative)]=hashlib.sha256(path.read_bytes()).hexdigest()
    (out/'provenance.json').write_text(json.dumps(dict(python=sys.executable,source_sha256=hashes,
        started_utc=datetime.now(timezone.utc).isoformat(),git='No repository; SHA-256 snapshot used'),indent=2),encoding='utf-8')
    environment=ROOT/'experiments/runs/environment_final/environment.json'
    if environment.exists():shutil.copy2(environment,out/'environment.json')
    manifest=write_suite(config,out/'instances');selected=manifest[:limit] if limit else manifest
    (out/'budget_estimate.json').write_text(json.dumps(dict(pairs=len(selected),
        nominal_algorithm_seconds=2*len(selected)*config['equal_budget_seconds'],
        hard_process_upper_seconds=len(selected)*(2*config['equal_budget_seconds']+30)),indent=2),encoding='utf-8')
    rows=[]
    for index,e in enumerate(selected):
        key=e['instance_id'];order=['compact_ip','cg_pipeline'] if index%2==0 else ['cg_pipeline','compact_ip']
        task=dict(entry=e,config=config,instance_path=str((out/'instances'/e['instance']).resolve()),
                  output=str((out/'raw'/(key+'.json')).resolve()),order=order)
        path=out/'tasks'/(key+'.json');path.write_text(json.dumps(task,indent=2),encoding='utf-8')
        with (out/'logs'/(key+'.stderr')).open('w') as err,(out/'logs'/(key+'.stdout')).open('w') as stdout:
            process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--task',str(path.resolve())],stderr=err,stdout=stdout,cwd=ROOT)
            try:code=process.wait(timeout=2*config['equal_budget_seconds']+30)
            except subprocess.TimeoutExpired:
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                code=process.wait()
        raw=json.loads(Path(task['output']).read_text()) if Path(task['output']).exists() else {'task':task}
        row=summarize(raw);row['process_exit_code']=code;rows.append(row);save_summary(rows,out)
        print(f"[{index+1}/{len(selected)}] n={e['factor']} seed={e['seed']} IP={row['ip_incumbent']} CG={row['cg_incumbent']} root={row['cg_root_status']}",flush=True)
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path);p.add_argument('--out',type=Path)
    p.add_argument('--task',type=Path);p.add_argument('--limit',type=int);args=p.parse_args()
    try:
        if args.task:execute(json.loads(args.task.read_text()))
        else:run(args.config,args.out,args.limit)
    except Exception:traceback.print_exc();raise SystemExit(1)
