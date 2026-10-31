"""One isolated instance/solver-combination run with nonoverlapping timers."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code/dwcg'))
import solve as cg_module
from common import compact
import pulp
from solver_backend import BackendConfig, make_solver, objective_value, use_backend
from verify import cross_validate


def run(task):
    data=json.loads(Path(task['instance_path']).read_text(encoding='utf-8-sig'))
    compact.validate_data(data)
    row=dict(instance_id=task['entry']['instance_id'],seed=task['entry']['seed'],
             group=task['entry']['group'],factor=task['entry']['factor'],solver_combo=task['combo']['label'],
             **{k:v for k,v in task['entry']['metadata'].items() if k in
                ('lines','total_tasks','total_stations','precedence_edges','fatigue_limit','human_limit','robot_limit')})
    for name in ('compact_lp_obj','cg_lp_obj','cg_lp_upper_bound','milp_incumbent','milp_best_bound',
                 'restricted_integer_obj','milp_gap','milp_wall_time','compact_lp_wall_time','cg_wall_time',
                 'phase1_wall_time','phase2_wall_time','rmp_build_time','rmp_solve_time','pricing_wall_time',
                 'integer_recovery_time','cg_iterations','phase1_iterations','phase2_iterations','pricing_calls',
                 'columns_generated','columns_active','max_reduced_cost','final_lp_gap','pricing_ratio'):
        row[name]=None
    row.update(cg_status='not_run',cg_converged=False,milp_status='not_run',
               compact_lp_status='not_run',verification_status='not_run',integer_recovery_status='not_run')
    result={'summary':row,'task':task,'started_utc':datetime.now(timezone.utc).isoformat(),'events':[]}
    destination=Path(task['output']);destination.parent.mkdir(parents=True,exist_ok=True)

    def save(stage):
        result['current_stage']=stage
        destination.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')

    config=BackendConfig(name=task['combo']['name'],
                         overrides={k:task['combo'][k] for k in ('rmp','pricing') if k in task['combo']},
                         seed=task['config'].get('solver_seed',11),threads=1,
                         role_limits=task['config']['role_limits'],
                         log_dir=str(destination.parent.parent/'logs'/destination.stem))
    result['solver_settings']=asdict(config)
    with use_backend(config,result['events']):
        for kind in ('compact_ip','compact_lp'):
            save(kind);begin=time.perf_counter();build=time.perf_counter()
            model=compact.build_model(data);build=time.perf_counter()-build
            if kind=='compact_lp':
                for variable in model.problem.variables(): variable.cat=pulp.LpContinuous
            model.problem.solve(make_solver(mip=kind=='compact_ip',role=kind))
            duration=time.perf_counter()-begin;info=model.problem.backend_result
            result[kind]={'backend':info,'build_wall_time':build,'wall_time':duration}
            if kind=='compact_ip':
                report=compact.solution_report(model);result[kind]['solution']=report
                row.update(milp_status=info['status'],milp_incumbent=info['objective'],
                           milp_best_bound=info['best_bound'],milp_gap=info['relative_gap'],
                           milp_wall_time=duration,milp_optimal=info['optimal'])
            else:
                row.update(compact_lp_status=info['status'],compact_lp_obj=info['objective'] if info['optimal'] else None,
                           compact_lp_wall_time=duration)
            save(kind+'_done')
        # Instrument only the original root CG call. Recovery and verification are
        # separate, so their master builds/solver calls never enter these timers.
        metrics={'rmp_build_time':0.,'rmp_solve_time':0.,'pricing_wall_time':0.,'pricing_calls':0,
                 'phase1_wall_time':0.,'phase2_wall_time':0.}
        pp_calls=[];state={'phase':1,'iteration':0};root_begin=time.perf_counter();phase_begin=root_begin
        originals={name:getattr(cg_module,name) for name in ('build_master','solve_master','price')}

        def build(*args,**kwargs):
            nonlocal phase_begin
            phase=args[2] if len(args)>2 else kwargs.get('phase',2)
            if phase!=state['phase']:
                now=time.perf_counter();metrics['phase1_wall_time']+=now-phase_begin;phase_begin=now
                state['phase']=phase;state['iteration']=0
            state['iteration']+=1
            begin=time.perf_counter()
            try: return originals['build_master'](*args,**kwargs)
            finally: metrics['rmp_build_time']+=time.perf_counter()-begin

        def master(*args,**kwargs):
            begin=time.perf_counter()
            try: return originals['solve_master'](*args,**kwargs)
            finally: metrics['rmp_solve_time']+=time.perf_counter()-begin

        def pricing(*args,**kwargs):
            begin=time.perf_counter();status='exception';rc=None
            try:
                answer=originals['price'](*args,**kwargs);status='optimal';rc=answer[1];return answer
            finally:
                elapsed=time.perf_counter()-begin;metrics['pricing_wall_time']+=elapsed;metrics['pricing_calls']+=1
                pp_calls.append(dict(phase=state['phase'],iteration=state['iteration'],line=args[0]['id'],
                                     station=args[1],wall_time=elapsed,status=status,reduced_cost=rc))

        cg_module.build_master, cg_module.solve_master,cg_module.price=build,master,pricing
        save('cg');config.deadline=root_begin+task['config']['cg_root_limit']
        pool=None;cg=None
        try:
            cg,pool=cg_module.run_cg(data,max_iterations=task['config']['max_iterations'],recover=False)
            result['cg']=cg;row.update(cg_status=cg['status'],cg_converged=cg['lp_converged'],
                                       cg_lp_obj=cg['lp_objective'],cg_lp_upper_bound=cg['lp_upper_bound'])
        except (RuntimeError,TimeoutError) as error:
            last=result['events'][-1] if result['events'] else {}
            row['cg_status']='time_limit' if isinstance(error,TimeoutError) or last.get('status')=='time_limit' else 'numerical_or_solver_exception'
            result['cg_error']=repr(error);result['cg_traceback']=traceback.format_exc()
        finally:
            now=time.perf_counter();row['cg_wall_time']=now-root_begin
            metrics[f"phase{state['phase']}_wall_time"]+=now-phase_begin
            config.deadline=None
            for name,value in originals.items():setattr(cg_module,name,value)
        row.update(metrics);result['pricing_calls']=pp_calls
        row['cg_other_time']=max(0,row['cg_wall_time']-sum(metrics[k] for k in ('rmp_build_time','rmp_solve_time','pricing_wall_time')))
        row['pricing_ratio']=100*metrics['pricing_wall_time']/row['cg_wall_time']
        if cg is not None:
            row.update(cg_iterations=len(cg['history']),phase1_iterations=sum(h['phase']==1 for h in cg['history']),
                       phase2_iterations=sum(h['phase']==2 for h in cg['history']))
            finals=[h for h in cg['history'] if 'maximum_reduced_cost' in h]
            row['max_reduced_cost']=finals[-1]['maximum_reduced_cost'] if finals else None
            if cg['lp_objective'] is not None and cg['lp_upper_bound'] is not None:
                row['final_lp_gap']=max(0,cg['lp_upper_bound']-cg['lp_objective'])
            row['columns_generated']=sum(map(len,pool.values()))
            row['columns_active']=len(cg.get('lp_solution',[]))
        save('cg_done')
        if cg is not None and cg['lp_objective'] is not None:
            save('recovery');begin=time.perf_counter()
            # Unlike the exact pricing path, recovery may legitimately stop with
            # an incumbent. Retain native bounds/status and never assert global IP optimality.
            m=cg_module.build_master(data,pool,integer=True)
            m.problem.solve(make_solver(role='recovery'))
            info=m.problem.backend_result
            result['recovery_backend']=info
            if info['has_incumbent']:
                from master import decode_integer
                recovered=decode_integer(data,pool,m);result['integer_recovery']=recovered
                row['restricted_integer_obj']=recovered['objective']
                stations=[s for l in recovered['lines'] for s in l['stations']]
                row['recovered_humans']=sum(s['human'] for s in stations)
                row['recovered_robots']=sum(s['robot'] for s in stations)
                row['recovered_mode_counts']={mode:sum(a['mode']==mode for s in stations for a in s['assignments_in_order']) for mode in ('H','R','J')}
                row['fatigue_active_stations']=sum(s['human'] and abs(s['fatigue_load']-s['fatigue_budget'])<1e-5 for s in stations)
            row.update(integer_recovery_time=time.perf_counter()-begin,integer_recovery_status=info['status'])
            save('recovery_done')
        # Fair relaxation/incumbent comparisons, never root-LP versus IP speed claims.
        if row['cg_converged']:
            lp=row['cg_lp_obj'];bound=row['compact_lp_obj'];incumbent=row['milp_incumbent']
            if bound is not None and lp>bound+1e-5:raise RuntimeError('DW LP exceeds compact LP')
            if incumbent is not None and incumbent>row['cg_lp_upper_bound']+1e-5:raise RuntimeError('IP incumbent exceeds DW LP upper bound')
            row['relaxation_bound_improvement']=bound-lp if bound is not None else None
        if task.get('verify') and cg is not None:
            save('verification');begin=time.perf_counter()
            result['verification']=cross_validate(data,cg,enumeration_limit=task['config'].get('enumeration_limit',100000))
            row['verification_status']=result['verification']['verification_status']
            row['verification_wall_time']=time.perf_counter()-begin
        result['finished_utc']=datetime.now(timezone.utc).isoformat();save('complete')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--task',type=Path,required=True);args=parser.parse_args()
    task=json.loads(args.task.read_text(encoding='utf-8'))
    try:run(task)
    except Exception:
        traceback.print_exc();raise SystemExit(1)
