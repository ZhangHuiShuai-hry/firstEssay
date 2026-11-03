"""Deterministic exact-pricing Branch-and-Price for ML-HRC-DLBP-CF.

Proofs are numerical, within the recorded solver/primal/duality/optimality tolerances.
No full-column enumeration, compact-IP solve, native cross-node reuse or monkeypatch.
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
import subprocess
import sys
import time
import traceback

from common import compact
from node_state import NumericPolicy,NodeRestrictions,NodeResult,NumericalUncertain,most_fractional
from node_master_v0 import solve_node
from bp_solution import integer_from_x

ROOT=Path(__file__).resolve().parents[2]


def code_version():
    bundled=Path('C:/Users/Hrychang/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
    exe=str(bundled) if bundled.exists() else shutil.which('git')
    head=None
    if exe:
        try:head=subprocess.check_output([exe,'-c','safe.directory='+ROOT.as_posix(),'rev-parse','HEAD'],cwd=ROOT,stderr=subprocess.DEVNULL,text=True).strip()
        except (OSError,subprocess.CalledProcessError):pass
    files=['code/dwcg/'+n+'.py' for n in ('branch_price','node_state','node_master','node_pricing','bp_solution','common','master')]
    files+=['code/milp/model.py','code/solver_backend.py']
    return {'git_head':head,'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}}


def minimum_bound(inherited,computed):
    known=[v for v in (inherited,computed) if v is not None]
    if any(not math.isfinite(v) for v in known):raise NumericalUncertain('Nonfinite node bound')
    return min(known) if known else None


def global_bounds(nodes,lower,policy):
    active=[n for n in nodes.values() if n['node_status']=='open' or n['node_status'].startswith('unresolved_')]
    terminal=[n for n in nodes.values() if n['node_status'] in ('pruned_bound','pruned_integer')]
    if any(n['safe_upper_bound'] is None for n in active):return None,None,None
    candidates=[n['safe_upper_bound'] for n in active+terminal]
    if any(v is None or not math.isfinite(v) for v in candidates):raise NumericalUncertain('Invalid frontier bound')
    upper=max(candidates) if candidates else lower
    if lower is None or upper is None:return upper,None,None
    if upper<lower-policy.bound_consistency_tolerance:raise NumericalUncertain('Global upper bound below integer lower bound')
    # Record only an outward correction for a tolerated floating-point residual.
    upper=max(upper,lower)
    absolute=upper-lower;relative=max(0.,absolute)/max(1.,abs(lower))
    return upper,absolute,relative


def run_branch_price(data, *, solver='cbc', time_limit=300., node_limit=10000,
                     max_cg_iterations=1000, policy=None, output_dir=None, verbose=False,
                     _node_solver=None):
    compact.validate_data(data);policy=policy or NumericPolicy()
    compact.number(time_limit,'time_limit',0,strict=True);compact.integer(node_limit,'node_limit',0)
    compact.integer(max_cg_iterations,'max_cg_iterations',1)
    if solver not in ('cbc','cplex_py'):raise ValueError('Unsupported B&P solver')
    if output_dir:
        output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=False)
    node_solver=_node_solver or solve_node
    started=time.perf_counter();deadline=started+time_limit
    nodes={};stack=[];pools={};lower=None;incumbent=None;incumbent_node=None;processed=[]
    status=None;reason=None;pricing_calls=0;generated=0
    version=code_version()

    def create(parent,restrictions,inherited,branch=None,value=None):
        node_id=len(nodes)
        nodes[node_id]={'node_id':node_id,'parent_id':parent,'depth':0 if parent is None else nodes[parent]['depth']+1,
            'branching_variable':branch,'branching_value':value,'restrictions':restrictions.to_records(),
            'inherited_upper_bound':inherited,'node_lp_upper_bound':None,'safe_upper_bound':inherited,
            'upper_bound_source':'unknown' if inherited is None else 'parent_inherited',
            'phase1_status':'not_run','phase2_status':'not_run','node_status':'open',
            'termination_reason':'not_visited','children':[],'columns_generated':0,'pricing_calls':0,'solve_seconds':0.}
        return node_id

    root=create(None,NodeRestrictions(),None);stack.append(root)

    def save_node(n):
        if output_dir:
            path=output_dir/f'node_{n["node_id"]:06d}.json'
            with path.open('x',encoding='utf-8') as f:json.dump(n,f,ensure_ascii=False,indent=2,allow_nan=False)
            n['certificate_file']=str(path)

    try:
        while stack:
            if time.perf_counter()>=deadline:status='time_limit';reason='Global wall-clock limit';break
            if len(processed)>=node_limit:status='node_limit';reason='Processed node limit';break
            node_id=stack.pop();n=nodes[node_id];processed.append(node_id)
            n['process_index']=len(processed)-1;n['lower_bound_before']=lower
            safe=n['safe_upper_bound']
            if lower is not None and safe is not None and safe<=lower+policy.allowance(lower):
                n.update(node_status='pruned_bound',termination_reason='Inherited valid upper bound dominated by verified incumbent',
                         pruning={'kind':'bound','upper_bound':safe,'integer_lower_bound':lower,'allowance':policy.allowance(lower)},lower_bound_after=lower)
                save_node(n);continue
            restrictions=NodeRestrictions.from_records(data,n['restrictions'])
            parent_pool=pools[n['parent_id']] if n['parent_id'] is not None else None
            logs=output_dir/f'node_{node_id:06d}_logs' if output_dir else None
            try:
                answer=node_solver(data,restrictions,parent_pool,policy=policy,solver=solver,deadline=deadline,
                                   max_iterations=max_cg_iterations,log_dir=logs,verbose=verbose)
                if not isinstance(answer,NodeResult):raise NumericalUncertain('Explicit NodeResult certificate required')
            except Exception as error:
                n.update(node_status='unresolved_solver_error',termination_reason=repr(error),
                         error={'traceback':traceback.format_exc()},lower_bound_after=lower)
                stack.append(node_id);status='solver_error';reason='Node solver raised an exception';save_node(n);break
            pricing_calls+=answer.pricing_calls;generated+=answer.columns_generated
            n.update(node_result=answer.to_dict(),certificate=asdict(answer.certificate),
                     phase1_status=answer.certificate.phase1_status,phase2_status=answer.certificate.phase2_status,
                     columns_generated=answer.columns_generated,pricing_calls=answer.pricing_calls,
                     solve_seconds=answer.solve_seconds,node_lp_upper_bound=answer.lp_upper_bound)
            n['safe_upper_bound']=minimum_bound(n['inherited_upper_bound'],answer.lp_upper_bound)
            n['upper_bound_source']=('complete_node_pricing_and_parent' if answer.lp_upper_bound is not None and n['inherited_upper_bound'] is not None
                                     else 'complete_node_pricing' if answer.lp_upper_bound is not None else n['upper_bound_source'])
            safe=n['safe_upper_bound']
            if answer.status in ('local_infeasible_proven','phase1_infeasible_proven'):
                n.update(node_status='pruned_'+('local_infeasible' if answer.status=='local_infeasible_proven' else 'phase1_infeasible'),
                         termination_reason=answer.termination_reason,pruning={'kind':'infeasible','proof':answer.status})
            elif answer.status!='node_lp_optimal_proven':
                n.update(node_status='unresolved_'+answer.status,termination_reason=answer.termination_reason)
                stack.append(node_id)
                status=answer.status if answer.status in ('time_limit','solver_error') else 'numerical_uncertain'
                reason='Node left unresolved: '+answer.termination_reason
                n['lower_bound_after']=lower;save_node(n);break
            else:
                if safe is None or answer.lp_objective is None or safe<answer.lp_objective-policy.bound_consistency_tolerance:
                    raise NumericalUncertain('Invalid inherited/computed node upper bound')
                if lower is not None and safe<=lower+policy.allowance(lower):
                    n.update(node_status='pruned_bound',termination_reason='Node LP upper bound dominated by verified incumbent',
                             pruning={'kind':'bound','upper_bound':safe,'integer_lower_bound':lower,'allowance':policy.allowance(lower)})
                else:
                    branch=most_fractional(answer.x_values,restrictions,policy)
                    if branch is None:
                        solution=integer_from_x(data,answer.x_values,restrictions,policy,answer.lp_objective)
                        value=solution['objective']
                        if value>safe+policy.bound_consistency_tolerance:
                            raise NumericalUncertain('Integer witness exceeds safe node upper bound')
                        n['integer_witness']=solution
                        if lower is None or value>lower:
                            lower=value;incumbent=solution;incumbent_node=node_id
                            n['incumbent_update']={'objective':value,'solution':solution}
                        if safe>value+policy.allowance(value):
                            raise NumericalUncertain('Integer-looking LP has not closed its repaired bound')
                        n.update(node_status='pruned_integer',termination_reason='Verified integer witness closes node bound',
                                 pruning={'kind':'integer','upper_bound':safe,'integer_objective':value,'allowance':policy.allowance(value)})
                    else:
                        q=tuple(branch['variable'])
                        left=restrictions.add(data,q,0);right=restrictions.add(data,q,1)
                        if not left.is_child_of(restrictions) or not right.is_child_of(restrictions):
                            raise NumericalUncertain('Child restrictions do not extend parent')
                        a=create(node_id,left,safe,list(q),0);b=create(node_id,right,safe,list(q),1)
                        pools[node_id]={key:list(cols) for key,cols in answer.pool.items()}
                        n.update(node_status='branched',children=[a,b],branch_decision=branch,
                                 termination_reason='Most fractional original x; disjoint 0/1 children')
                        stack.extend([b,a])
            n['lower_bound_after']=lower;save_node(n)
        if status is None:
            if stack:raise NumericalUncertain('Unfinished stack at normal termination')
            if lower is None:
                status='infeasible_proven';reason='Every leaf has a proven infeasibility certificate'
            else:
                upper,absolute,relative=global_bounds(nodes,lower,policy)
                if absolute is None or absolute>policy.allowance(lower):
                    raise NumericalUncertain('Completed tree bounds do not close')
                status='optimal_within_tolerance';reason='All tree leaves safely fathomed with verified integer incumbent'
    except NumericalUncertain as error:
        status='numerical_uncertain';reason=str(error)
        if processed:
            n=nodes[processed[-1]]
            if not n['node_status'].startswith('pruned_') and n['node_status']!='branched':
                n.update(node_status='unresolved_numerical_uncertain',termination_reason=str(error),lower_bound_after=lower)
                if n['node_id'] not in stack:stack.append(n['node_id'])
    except Exception as error:
        status='solver_error';reason=repr(error)
        if processed:
            n=nodes[processed[-1]]
            if n['node_status']=='open':n['node_status']='unresolved_solver_error'
            if n['node_status'].startswith('unresolved_') and n['node_id'] not in stack:stack.append(n['node_id'])
            n['error']={'traceback':traceback.format_exc()}
            n['lower_bound_after']=lower
    active=[n for n in nodes.values() if n['node_status']=='open' or n['node_status'].startswith('unresolved_')]
    try:upper,absolute,relative=global_bounds(nodes,lower,policy)
    except NumericalUncertain as error:
        status='numerical_uncertain';reason=str(error);upper=absolute=relative=None
    root_result=nodes[0].get('node_result',{})
    proved=status=='optimal_within_tolerance' and not active and lower is not None
    infeasible=status=='infeasible_proven' and not active and lower is None
    result={'algorithm':'deterministic_DFS_exact_Branch_and_Price','certificate_version':1,
        'code_version':version,'solver_backend':solver,'proof_scope':'MILP_global_integer_optimality_with_recorded_floating_point_tolerances',
        'status':status,'numeric_policy':asdict(policy),'search_config':{'time_limit':time_limit,'node_limit':node_limit,'max_cg_iterations':max_cg_iterations,'node_order':'DFS_0_before_1'},
        'has_integer_incumbent':incumbent is not None,'integer_incumbent_objective':lower,'integer_incumbent_solution':incumbent,
        'integer_incumbent_node':incumbent_node,'global_lower_bound':lower,'global_upper_bound':upper,
        'absolute_gap':absolute,'relative_gap':relative,'global_integer_optimal_proven':proved,'global_infeasibility_proven':infeasible,
        'root_lp_status':root_result.get('status','not_run'),'root_lp_objective':root_result.get('lp_objective'),
        'root_lp_upper_bound':root_result.get('lp_upper_bound'),'total_nodes_created':len(nodes),'total_nodes_processed':len(processed),
        'total_nodes_pruned':sum(n['node_status'].startswith('pruned_') for n in nodes.values()),
        'total_pricing_calls':pricing_calls,'total_columns_generated':generated,'wall_time':time.perf_counter()-started,
        'open_nodes':[{'node_id':n['node_id'],'status':n['node_status'],'safe_upper_bound':n['safe_upper_bound'],
                       'restrictions':n['restrictions']} for n in active],
        'node_history':list(nodes.values()),'processing_order':processed,'termination_reason':reason,
        'input_sha256':hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('instance',type=Path);parser.add_argument('--solver',choices=('cbc','cplex_py'),default='cbc')
    parser.add_argument('--time-limit',type=float,default=300.);parser.add_argument('--node-limit',type=int,default=10000)
    parser.add_argument('--max-cg-iterations',type=int,default=1000);parser.add_argument('--numeric-policy',type=Path)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--verbose',action='store_true')
    args=parser.parse_args()
    try:
        if args.output.exists():raise FileExistsError(f'Output already exists: {args.output}')
        detail=args.output.parent/(args.output.stem+'_files')
        if detail.exists():raise FileExistsError(f'Output details already exist: {detail}')
        data=json.loads(args.instance.read_text(encoding='utf-8-sig'))
        policy=NumericPolicy(**json.loads(args.numeric_policy.read_text(encoding='utf-8-sig'))) if args.numeric_policy else NumericPolicy()
        compact.validate_data(data)
        compact.number(args.time_limit,'time_limit',0,strict=True)
        compact.integer(args.node_limit,'node_limit',0)
        compact.integer(args.max_cg_iterations,'max_cg_iterations',1)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8') as f:json.dump({'status':'running','algorithm':'Branch-and-Price'},f)
        result=run_branch_price(data,solver=args.solver,time_limit=args.time_limit,node_limit=args.node_limit,
                                max_cg_iterations=args.max_cg_iterations,policy=policy,output_dir=detail,verbose=args.verbose)
        (detail/'instance.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
        (detail/'run_config.json').write_text(json.dumps({'argv':sys.argv,'python':sys.executable,
            'started_or_completed_utc':datetime.now(timezone.utc).isoformat(),'numeric_policy':asdict(policy),
            'code_version':result['code_version']},indent=2),encoding='utf-8')
        args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
        print(json.dumps({k:result[k] for k in ('status','integer_incumbent_objective','global_upper_bound','absolute_gap','total_nodes_processed','total_pricing_calls','wall_time')},indent=2))
        return 0 if result['status'] in ('optimal_within_tolerance','infeasible_proven') else 1 if result['status']=='solver_error' else 2
    except Exception as error:
        parser.exit(1,f'Error: {error}\n')


if __name__=='__main__':raise SystemExit(main())
