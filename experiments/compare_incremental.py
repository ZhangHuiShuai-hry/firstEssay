"""Paired CG-V0/V1 root-LP experiments. Same CG loop and unchanged exact PP."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code/dwcg'))
import solve as cg
from common import compact
from incremental_master import IncrementalMaster
from solver_backend import BackendConfig,use_backend,load_cplex
from generate_instances import write_suite
from run_experiments import save_summary


def execute(task):
    data=json.loads(Path(task['input']).read_text());compact.validate_data(data)
    version=task['version'];events=[];history=[];pp_records=[]
    config=BackendConfig(name='cplex_py',threads=1,seed=11,log_dir=task['logs'])
    original={name:getattr(cg,name) for name in ('build_master','solve_master','price')}
    metrics=dict(rmp_build_time=0.,rmp_interface_time=0.,pp_time=0.)
    state=dict(phase=1,phase_start=0.,phase1_time=0.,phase2_time=0.,pool=None,master=None,pricing=[])
    native=None;begin=time.perf_counter();deadline=begin+task['budget'];state['phase_start']=begin

    def build(data,pool,phase=2,**kwargs):
        nonlocal native
        if phase!=state['phase']:
            state['phase1_time']+=time.perf_counter()-state['phase_start'];state['phase_start']=time.perf_counter()
        state.update(phase=phase,pool=pool,pricing=[])
        tick=time.perf_counter()
        try:
            if version=='V0':return original['build_master'](data,pool,phase,**kwargs)
            if native is None:native=IncrementalMaster(data,config,str(Path(task['logs'])/'native_rmp.log'))
            return native.sync(pool,phase)
        finally:metrics['rmp_build_time']+=time.perf_counter()-tick

    def master(m,**kwargs):
        tick=time.perf_counter()
        try:
            value=original['solve_master'](m,**kwargs) if version=='V0' else m.solve(deadline)
            state['master']=value;return value
        finally:metrics['rmp_interface_time']+=time.perf_counter()-tick

    def price(*args,**kwargs):
        tick=time.perf_counter();rc=None;status='unproven'
        try:
            answer=original['price'](*args,**kwargs);rc=answer[1];status='optimal'
            state['pricing'].append(rc)
            if len(state['pricing'])==sum(len(l['stations']) for l in data['lines']):
                m=state['master'];z=m.value();rho=max(state['pricing'])
                history.append(dict(phase=state['phase'],objective=z,upper_bound=z+sum(max(0,x) for x in state['pricing']),
                                    maximum_reduced_cost=rho,wall_time=time.perf_counter()-begin))
            return answer
        finally:
            elapsed=time.perf_counter()-tick;metrics['pp_time']+=elapsed
            pp_records.append(dict(phase=state['phase'],line=args[0]['id'],station=args[1],wall_time=elapsed,status=status,rc=rc))

    # Native API import warmup is outside the measured root budget for both arms.
    load_cplex();begin=time.perf_counter();deadline=begin+task['budget'];state['phase_start']=begin
    config.deadline=deadline
    result=dict(version=version,instance_id=task['entry']['instance_id'],n=task['entry']['factor'],seed=task['entry']['seed'],
                budget=task['budget'],status='not_run',converged=False,lp_objective=None,upper_bound=None)
    Path(task['logs']).mkdir(parents=True,exist_ok=True)
    with use_backend(config,events):
        cg.build_master,cg.solve_master,cg.price=build,master,price
        try:
            answer,pool=cg.run_cg(data,recover=False,max_iterations=1000)
            result.update(status=answer['status'],converged=answer['lp_converged'],lp_objective=answer['lp_objective'] if answer['lp_converged'] else None)
            result['cg']=answer
        except (TimeoutError,RuntimeError) as error:
            result.update(status='time_limit' if isinstance(error,TimeoutError) or (events and events[-1]['status']=='time_limit') else 'numerical_or_solver_exception',error=repr(error))
        finally:
            now=time.perf_counter();state[f"phase{state['phase']}_time"]+=now-state['phase_start']
            result['wall_time']=now-begin
            for name,fn in original.items():setattr(cg,name,fn)
    result.update(metrics,phase1_time=state['phase1_time'],phase2_time=state['phase2_time'],
        iterations=sum(e['role']=='rmp' for e in events) if version=='V0' else len(native.solve_records) if native else 0,
        pricing_calls=len(pp_records),columns=sum(map(len,state['pool'].values())) if state['pool'] else None)
    bounds=[r['upper_bound'] for r in history if r['phase']==2]
    result['upper_bound']=min(bounds) if bounds else None
    if native:
        result.update(rmp_native_time=native.native_solve_seconds,rmp_conversion_time=0.,
                      rmp_read_time=native.read_seconds,basis_records=native.solve_records)
        native.close()
    else:
        rmp=[e for e in events if e['role']=='rmp']
        result.update(rmp_native_time=sum(e['solver_time'] for e in rmp),
                      rmp_conversion_time=sum(e.get('translation_time',0) for e in rmp))
    result['other_time']=result['wall_time']-sum(metrics.values())
    result['iteration_log']=history;result['pricing_log']=pp_records;result['events']=events
    Path(task['output']).write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    return result


def run(config_path,out):
    config=json.loads(config_path.read_text());out.mkdir(parents=True,exist_ok=False)
    for name in ('raw','logs','tasks','source'):(out/name).mkdir()
    (out/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    hashes={}
    for path in list((ROOT/'code').glob('**/*.py'))+list((ROOT/'experiments').glob('*.py')):
        relative=path.relative_to(ROOT);target=out/'source'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target);hashes[str(relative)]=hashlib.sha256(path.read_bytes()).hexdigest()
    (out/'provenance.json').write_text(json.dumps(dict(source_sha256=hashes,started_utc=datetime.now(timezone.utc).isoformat(),python=sys.executable),indent=2),encoding='utf-8')
    manifest=write_suite(config,out/'instances');rows=[]
    (out/'budget_estimate.json').write_text(json.dumps(dict(instances=len(manifest),jobs=2*len(manifest),
        maximum_root_seconds=2*len(manifest)*config['budget']),indent=2),encoding='utf-8')
    for i,entry in enumerate(manifest):
        versions=['V0','V1'] if i%2==0 else ['V1','V0']
        for version in versions:
            key=entry['instance_id']+'_'+version
            task=dict(entry=entry,input=str((out/'instances'/entry['instance']).resolve()),version=version,budget=config['budget'],
                output=str((out/'raw'/(key+'.json')).resolve()),logs=str((out/'logs'/key).resolve()))
            path=out/'tasks'/(key+'.json');path.write_text(json.dumps(task),encoding='utf-8')
            with (out/'logs'/(key+'.stdout')).open('w') as so,(out/'logs'/(key+'.stderr')).open('w') as se:
                p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--task',str(path.resolve())],stdout=so,stderr=se,cwd=ROOT)
                try:code=p.wait(timeout=config['budget']+30)
                except subprocess.TimeoutExpired:
                    subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);code=p.wait()
            result=json.loads(Path(task['output']).read_text()) if Path(task['output']).exists() else dict(version=version,instance_id=entry['instance_id'],n=entry['factor'],seed=entry['seed'],status='process_timeout_or_exception',converged=False)
            row={k:v for k,v in result.items() if k not in ('cg','iteration_log','pricing_log','events','basis_records')};row['process_exit_code']=code
            rows.append(row);save_summary(rows,out)
            print(f"[{len(rows)}/{2*len(manifest)}] n={entry['factor']} s={entry['seed']} {version}: {row['status']} {row.get('wall_time')} obj={row.get('lp_objective')}",flush=True)
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path);p.add_argument('--out',type=Path);p.add_argument('--task',type=Path);a=p.parse_args()
    try:
        if a.task:execute(json.loads(a.task.read_text()))
        else:run(a.config,a.out)
    except Exception:traceback.print_exc();raise SystemExit(1)
