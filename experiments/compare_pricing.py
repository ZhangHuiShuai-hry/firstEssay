"""V1/V2 paired root CG: identical incremental RMP; exact PP implementation changes only."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

from pricing_profile import ROOT,PricingOracle
import solve as cg
from common import compact,blocks
from incremental_master import IncrementalMaster
from solver_backend import BackendConfig,use_backend,load_cplex
from generate_instances import write_suite
from run_experiments import save_summary


def execute(task):
    data=json.loads(Path(task['input']).read_text());compact.validate_data(data)
    version=task['version'];events=[];rounds=[];native=None
    config=BackendConfig(name='cplex_py',threads=1,seed=11,log_dir=task['logs'])
    Path(task['logs']).mkdir(parents=True,exist_ok=True)
    original={name:getattr(cg,name) for name in ('build_master','solve_master','price')}
    oracle=PricingOracle(version,config,events)
    state=dict(phase=1,phase_start=0.,phase1_time=0.,phase2_time=0.,pool=None,round=None)
    metrics=dict(rmp_build_time=0.,rmp_interface_time=0.)
    load_cplex();begin=time.perf_counter();deadline=begin+task['budget'];config.deadline=deadline;state['phase_start']=begin
    def build(d,pool,phase=2,**kw):
        nonlocal native
        now=time.perf_counter()
        if phase!=state['phase']:
            state['phase1_time']+=now-state['phase_start'];state['phase_start']=now
        state.update(phase=phase,pool=pool)
        tick=time.perf_counter()
        try:
            if native is None:native=IncrementalMaster(d,config,str(Path(task['logs'])/'rmp.log'))
            return native.sync(pool,phase)
        finally:metrics['rmp_build_time']+=time.perf_counter()-tick
    def master(m,**kw):
        tick=time.perf_counter()
        try:
            answer=m.solve(deadline)
            record=dict(round=len(rounds)+1,phase=state['phase'],objective=m.value(),pricing=[],complete_pricing=False,
                        upper_bound=None,maximum_reduced_cost=None,wall_time=time.perf_counter()-begin,
                        duals=[dict(row=list(k),value=v) for k,v in m.duals().items()])
            rounds.append(record);state['round']=record
            return answer
        finally:metrics['rmp_interface_time']+=time.perf_counter()-tick
    def price(*args,**kw):
        previous=len(oracle.records)
        try:return oracle(*args,**kw)
        finally:
            if len(oracle.records)>previous:
                record=oracle.records[-1];record['round']=state['round']['round']
                current=state['round'];current['pricing'].append(record)
                if len(current['pricing'])==len(blocks(data)) and all(p['status']=='optimal' for p in current['pricing']):
                    rc=[p['rc'] for p in current['pricing']]
                    current.update(complete_pricing=True,upper_bound=current['objective']+sum(max(0,r) for r in rc),
                                   maximum_reduced_cost=max(rc),wall_time=time.perf_counter()-begin)
    result=dict(version=version,instance_id=task['entry']['instance_id'],n=task['entry']['factor'],seed=task['entry']['seed'],
                budget=task['budget'],python_hash_seed=os.environ.get('PYTHONHASHSEED'),status='not_run',converged=False,lp_objective=None,upper_bound=None,lower_bound=None)
    with use_backend(config,events):
        cg.build_master,cg.solve_master,cg.price=build,master,price
        try:
            answer,pool=cg.run_cg(data,recover=False,max_iterations=task.get('max_iterations',1000))
            result.update(status=answer['status'],converged=answer['lp_converged'],
                          lp_objective=answer['lp_objective'] if answer['lp_converged'] else None,cg=answer)
        except (TimeoutError,RuntimeError) as error:
            timed=isinstance(error,TimeoutError) or (oracle.records and oracle.records[-1]['status']=='time_limit')
            result.update(status='time_limit' if timed else 'numerical_or_solver_exception',error=repr(error))
        finally:
            now=time.perf_counter();state[f"phase{state['phase']}_time"]+=now-state['phase_start'];result['wall_time']=now-begin
            for name,fn in original.items():setattr(cg,name,fn)
    result.update(metrics,phase1_time=state['phase1_time'],phase2_time=state['phase2_time'],
                  iterations=len(native.solve_records) if native else 0,pricing_calls=len(oracle.records),
                  columns=sum(map(len,state['pool'].values())) if state['pool'] else 0,
                  rmp_native_time=native.native_solve_seconds if native else 0.,
                  phase1_iterations=sum(r['phase']==1 for r in rounds),phase2_iterations=sum(r['phase']==2 for r in rounds))
    phase2=[r for r in rounds if r['phase']==2]
    bounds=[r['upper_bound'] for r in phase2 if r['complete_pricing']]
    result['upper_bound']=min(bounds) if bounds else None
    result['lower_bound']=max(r['objective'] for r in phase2) if phase2 else None
    result['final_lp_gap']=max(0,result['upper_bound']-result['lower_bound']) if bounds else None
    result['max_reduced_cost']=next((r['maximum_reduced_cost'] for r in reversed(phase2) if r['complete_pricing']),None)
    result['pp_time']=sum(p['wall_time'] for p in oracle.records)
    for name in ('build_time','native_creation_time','translation_time','objective_update_time','native_time','other_time'):
        result['pp_'+name]=sum(p[name] for p in oracle.records)
    result['other_time']=result['wall_time']-result['pp_time']-sum(metrics.values())
    result['basis_records']=native.solve_records if native else []
    result['rounds']=rounds;result['pricing_log']=oracle.records;result['events']=events
    if native:native.close()
    oracle.close()
    Path(task['output']).write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    return result


def run(config_path,out):
    config=json.loads(config_path.read_text());out.mkdir(parents=True,exist_ok=False)
    for name in ('raw','logs','tasks','source'):(out/name).mkdir()
    shutil.copy2(config_path,out/'config.json');hashes={}
    for path in list((ROOT/'code').rglob('*.py'))+list((ROOT/'experiments').glob('*.py')):
        rel=path.relative_to(ROOT);target=out/'source'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        hashes[str(rel)]=hashlib.sha256(path.read_bytes()).hexdigest()
    (out/'provenance.json').write_text(json.dumps(dict(source_sha256=hashes,started_utc=datetime.now(timezone.utc).isoformat(),
        python=sys.executable,worker_python_hash_seed='11'),indent=2),encoding='utf-8')
    manifest=write_suite(config,out/'instances');rows=[]
    (out/'budget_estimate.json').write_text(json.dumps(dict(jobs=2*len(manifest),maximum_root_seconds=2*len(manifest)*config['budget']),indent=2),encoding='utf-8')
    for i,entry in enumerate(manifest):
        for version in (('V1','V2') if i%2==0 else ('V2','V1')):
            key=entry['instance_id']+'_'+version
            task=dict(entry=entry,input=str((out/'instances'/entry['instance']).resolve()),version=version,budget=config['budget'],
                      logs=str((out/'logs'/key).resolve()),output=str((out/'raw'/(key+'.json')).resolve()))
            path=out/'tasks'/(key+'.json');path.write_text(json.dumps(task),encoding='utf-8')
            with (out/'logs'/(key+'.stdout')).open('w') as so,(out/'logs'/(key+'.stderr')).open('w') as se:
                environment=dict(os.environ,PYTHONHASHSEED='11')
                process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--task',str(path.resolve())],cwd=ROOT,stdout=so,stderr=se,env=environment)
                try:code=process.wait(timeout=config['budget']+30)
                except subprocess.TimeoutExpired:
                    subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);code=process.wait()
            result=json.loads(Path(task['output']).read_text()) if Path(task['output']).exists() else dict(version=version,instance_id=entry['instance_id'],n=entry['factor'],seed=entry['seed'],status='process_timeout_or_exception',converged=False)
            row={k:v for k,v in result.items() if k not in ('cg','rounds','pricing_log','events','basis_records')};row['process_exit_code']=code
            rows.append(row);save_summary(rows,out)
            print(f"[{len(rows)}/{2*len(manifest)}] n={entry['factor']} s={entry['seed']} {version}: {row['status']} {row.get('wall_time')} obj={row.get('lp_objective')}",flush=True)
    (out/'finished.json').write_text(json.dumps(dict(finished_utc=datetime.now(timezone.utc).isoformat(),runs=len(rows))),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path);p.add_argument('--out',type=Path);p.add_argument('--task',type=Path);a=p.parse_args()
    try:
        if a.task:execute(json.loads(a.task.read_text()))
        else:run(a.config,a.out)
    except Exception:traceback.print_exc();raise SystemExit(1)
