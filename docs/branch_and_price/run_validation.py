"""Reproducible tiny B&P runs, full-node oracles and explicit boundary scenarios."""
from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'code'),str(Path(__file__).resolve().parent)]
from branch_price import run_branch_price,code_version
from node_state import NodeRestrictions,NumericPolicy
from node_master import solve_node
from common import make_column,compact
from solver_backend import BackendConfig,use_backend,make_solver
from independent_bp_verify import oracle,verify_tree,verify_node


def dump(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False)


def audit_case(name,data,backend,out,budget):
    folder=out/f'{name}_{backend}';folder.mkdir()
    dump(folder/'instance.json',data)
    config={'solver':backend,'time_limit':budget,'node_limit':1000,'max_cg_iterations':1000,
            'numeric_policy':asdict(NumericPolicy()),'code_version':code_version(),'python':sys.executable,
            'started_utc':datetime.now(timezone.utc).isoformat()}
    dump(folder/'config.json',config)
    answer={'name':name,'solver':backend,'validation':'FAIL'}
    events=[]
    try:
        t=time.perf_counter()
        result=run_branch_price(data,solver=backend,time_limit=budget,node_limit=1000,output_dir=folder/'tree')
        dump(folder/'result.json',result);answer['bp_seconds']=time.perf_counter()-t
        with use_backend(BackendConfig(name=backend,time_limit=30,log_dir=str(folder/'oracle_logs')),events):
            verification=verify_tree(data,result,solve_oracles=True)
            original=compact.build_model(data);original.problem.solve(make_solver(role='verification'))
            direct=dict(original.problem.backend_result)
        dump(folder/'verification.json',verification);dump(folder/'compact.json',direct)
        root=next(n for n in verification['node_oracles'] if n['node_id']==0)
        full_ip=root['full_ip'];full_lp=root['full_lp']
        if result['status']=='optimal_within_tolerance':
            if not direct['optimal'] or not full_ip['optimal']:raise AssertionError('B&P feasible but IP oracle disagrees')
            oracle.close(direct['objective'],result['global_lower_bound']);oracle.close(full_ip['objective'],result['global_lower_bound'])
            if not compact.solution_report(original)['has_feasible_solution']:raise AssertionError('Direct compact incumbent invalid')
        elif result['status']=='infeasible_proven':
            if direct['status']!='infeasible' or full_ip['status']!='infeasible':raise AssertionError('B&P infeasible but IP oracle disagrees')
        else:raise AssertionError('B&P did not complete: '+result['status'])
        answer.update(validation='PASS',compact_status=direct['status'],compact_objective=direct['objective'],
                      full_ip_status=full_ip['status'],full_ip_objective=full_ip['objective'],full_lp_objective=full_lp['objective'],
                      bp_status=result['status'],bp_objective=result['global_lower_bound'],upper=result['global_upper_bound'],
                      absolute_gap=result['absolute_gap'],nodes=result['total_nodes_processed'],created=result['total_nodes_created'],
                      pricing_calls=result['total_pricing_calls'],node_oracles=verification['nodes_checked'],
                      rounds=verification['rounds_checked'])
    except Exception:
        answer['error']=traceback.format_exc();dump(folder/'failure.json',answer)
    dump(folder/'oracle_events.json',events)
    return answer


def node_scenarios():
    from test_node_cg import small
    items=[]
    for name in ('one_no_empty','one_local_time_empty','one_local_fatigue_empty','duplicate_optional_recovery',
                 'required_oversupply_recovery','human_missing_column_recovery','robot_missing_column_recovery',
                 'human_global_infeasible','robot_global_infeasible','AND_global_infeasible','AND_missing_column_recovery'):
        d=small();l=d['lines'][0];r=NodeRestrictions().add(d,('L','a',1,'H'),1);parent=None
        if name=='one_local_time_empty':l['tasks'][0]['modes']['H']['time']=5
        if name=='one_local_fatigue_empty':l['fatigue_limit']=0
        if name in ('duplicate_optional_recovery','required_oversupply_recovery'):
            parent={('L',s):[make_column(l,s,[('a','H')])] for s in (1,2)}
            if name.startswith('required'):l['required_tasks']=['a']
        if name in ('human_missing_column_recovery','robot_missing_column_recovery'):
            mode='H' if name.startswith('human') else 'R';d['human_limit' if mode=='H' else 'robot_limit']=1
            l['required_tasks']=['a','b'];r=NodeRestrictions().add(d,('L','a',1,mode),1)
            parent={('L',1):[make_column(l,1,[('a',mode)])],('L',2):[make_column(l,2,[('b',mode)])]}
        if name in ('human_global_infeasible','robot_global_infeasible'):
            mode='H' if name.startswith('human') else 'R';d['human_limit' if mode=='H' else 'robot_limit']=1
            r=NodeRestrictions().add(d,('L','a',1,mode),1).add(d,('L','b',2,mode),1)
        if name.startswith('AND'):
            l['precedence']=[['a','b']];r=NodeRestrictions().add(d,('L','b',1,'H'),1)
            if name=='AND_global_infeasible':r=r.add(d,('L','a',2,'H'),1)
            else:parent={('L',1):[make_column(l,1,[('b','H')])],('L',2):[make_column(l,2,[('a','H')])]}
        items.append((name,d,r,parent))
    return items


def audit_node_scenarios(out):
    out.mkdir();rows=[]
    for name,d,r,parent in node_scenarios():
        for solver in ('cbc','cplex_py'):
            folder=out/f'{name}_{solver}';folder.mkdir()
            dump(folder/'instance.json',d);dump(folder/'restrictions.json',r.to_records())
            dump(folder/'parent_pool.json',None if parent is None else [{'line':l,'station':s,'patterns':[c.assignments for c in cs]} for (l,s),cs in parent.items()])
            result=solve_node(d,r,parent,solver=solver,deadline=time.perf_counter()+30,log_dir=folder/'logs')
            n={'node_id':0,'node_status':result.status,'restrictions':r.to_records(),
               'node_result':result.to_dict(),'certificate':asdict(result.certificate)}
            dump(folder/'node.json',n)
            row={'name':name,'solver':solver,'status':result.status,'validation':'FAIL'}
            try:
                with use_backend(BackendConfig(name=solver,time_limit=30,log_dir=str(folder/'oracle_logs'))):
                    checked=verify_node(d,n,oracle.enumerate_patterns(d),asdict(NumericPolicy()),True)
                expected=checked['full_lp']
                if expected['status']=='infeasible':
                    if result.status not in ('local_infeasible_proven','phase1_infeasible_proven'):raise AssertionError(result.status)
                elif result.status!='node_lp_optimal_proven':raise AssertionError(result.status)
                row.update(validation='PASS',full_lp=expected['objective'],node_lp=result.lp_objective,
                           initial_artificial_sum=result.certificate.rounds[0].get('artificial_sum') if result.certificate.rounds else None)
                dump(folder/'verification.json',checked)
            except Exception:row['error']=traceback.format_exc();dump(folder/'failure.json',row)
            rows.append(row);print('node',name,solver,row['validation'],flush=True)
    dump(out/'summary.json',rows);return rows


def audit_interruptions(out):
    out.mkdir();d=dict(oracle.cases())['two_lines'];rows=[]
    for name in ('node_limit','root_time_limit','child_time_limit','solver_error','cg_limit'):
        folder=out/name;folder.mkdir();options={'solver':'cplex_py','output_dir':folder/'tree'}
        if name=='node_limit':options['node_limit']=1
        if name=='root_time_limit':options['time_limit']=1e-12
        if name=='cg_limit':options['max_cg_iterations']=1
        if name=='child_time_limit':
            calls=[]
            def expire(*args,**kwargs):
                if calls:kwargs['deadline']=time.perf_counter()-1
                calls.append(True);return solve_node(*args,**kwargs)
            options['_node_solver']=expire
        if name=='solver_error':
            def fail(*args,**kwargs):raise RuntimeError('Explicit test injection: node API exception')
            options['_node_solver']=fail
        result=run_branch_price(d,**options);dump(folder/'instance.json',d);dump(folder/'result.json',result)
        checked=verify_tree(d,result,solve_oracles=False);dump(folder/'verification.json',checked)
        if result['global_integer_optimal_proven'] or result['global_infeasibility_proven']:raise AssertionError('Interrupted run claimed proof')
        if not result['open_nodes']:raise AssertionError('Lost interrupted nodes')
        rows.append({'name':name,'status':result['status'],'validation':'PASS','upper':result['global_upper_bound'],
                     'open_nodes':len(result['open_nodes']),'fault_injection':name in ('child_time_limit','solver_error')})
    dump(out/'summary.json',rows);return rows


def audit_additional(out):
    from test_node_cg import small
    out.mkdir();rows=[]
    d=small();d['lines'][0]['required_tasks']=['a','b']
    for t in d['lines'][0]['tasks']:t['value']=-2
    for backend in ('cbc','cplex_py'):
        rows.append(audit_case('mandatory_negative',d,backend,out,30))
    folder=out/'tiny_rc_unclosed_cplex_py';folder.mkdir();d=small()
    for t in d['lines'][0]['tasks']:
        t['value']=3e-8
        for m in t['modes'].values():m['cost']=0
    for s in d['lines'][0]['stations']:s.update(fixed_cost=0,human_cost=0,robot_cost=0)
    policy=NumericPolicy(lp_dual_tolerance=1e-9,global_absolute_tolerance=1e-12,global_relative_tolerance=0)
    result=run_branch_price(d,solver='cplex_py',policy=policy,output_dir=folder/'tree')
    dump(folder/'instance.json',d);dump(folder/'result.json',result)
    with use_backend(BackendConfig(name='cplex_py',dual_tolerance=1e-9,log_dir=str(folder/'oracle_logs'))):
        checked=verify_tree(d,result,solve_oracles=True)
    dump(folder/'verification.json',checked)
    if result['status']!='numerical_uncertain' or result['global_integer_optimal_proven'] or result['absolute_gap']<=policy.global_absolute_tolerance:
        raise AssertionError('Unclosed tiny-RC integer candidate was incorrectly fathomed')
    rows.append({'name':'tiny_rc_unclosed','solver':'cplex_py','validation':'PASS','bp_status':result['status'],
                 'upper':result['global_upper_bound'],'lower':result['global_lower_bound'],'gap':result['absolute_gap']})
    dump(out/'summary.json',rows);return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--case',action='append')
    p.add_argument('--time-limit',type=float,default=60);p.add_argument('--boundaries',action='store_true')
    args=p.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    dump(args.out/'config.json',{'code_version':code_version(),'python':sys.executable,'argv':sys.argv,
         'started_utc':datetime.now(timezone.utc).isoformat(),'time_limit':args.time_limit,'solvers':['cbc','cplex_py']})
    rows=[]
    for name,data in oracle.cases():
        if args.case and name not in args.case:continue
        for backend in ('cbc','cplex_py'):
            row=audit_case(name,data,backend,args.out,args.time_limit);rows.append(row)
            # This file is an owned checkpoint, not an earlier experiment artifact.
            (args.out/'summary.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
            print(name,backend,row['validation'],row.get('bp_status'),row.get('bp_objective'),row.get('nodes'),flush=True)
    extra=[]
    if args.boundaries:
        extra+=audit_node_scenarios(args.out/'node_scenarios')
        extra+=audit_interruptions(args.out/'interruptions')
        extra+=audit_additional(args.out/'additional')
    return 0 if all(r['validation']=='PASS' for r in rows+extra) else 1


if __name__=='__main__':raise SystemExit(main())
