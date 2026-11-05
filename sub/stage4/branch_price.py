"""整线精确B&P：DFS、原x二元分支、完整节点定价及可审计树。

默认单线程CPLEX；软墙钟包含建模/搜索/原方案验证，CLI压缩落盘另计。
不依赖完整枚举、不复用跨节点原生模型、不把受限IP最优作为原问题最优。
"""
import argparse,json,math,sys,time,traceback,zlib
from pathlib import Path
from dataclasses import asdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from line_bp_node import solve_node,NumericPolicy,NumericalUncertain,NodeRestrictions,verify_integer_assignments
from node_state import most_fractional

def run(data,*,time_limit=30,node_limit=1000,max_iterations=100,solver='cplex_py',policy=None,log_dir=None):
    from line_cg import compact
    compact.validate_data(data);compact.number(time_limit,'time_limit',0,strict=True)
    compact.integer(node_limit,'node_limit',0);compact.integer(max_iterations,'max_iterations',1)
    policy=policy or NumericPolicy();started=time.perf_counter();deadline=started+time_limit
    r=dict(algorithm='whole_line_branch_and_price',certificate_version='line-bp-1',
           proof_scope='solver_floating_point_tolerances',policy=asdict(policy),solver_backend=solver,
           status='not_solved',termination_reason='',witness=None,global_lower_bound=None,global_upper_bound=None,
           absolute_gap=None,relative_gap=None,global_integer_optimal_proven=False,global_infeasibility_proven=False,
           node_history=[],open_nodes=[],first_integer_seconds=None,incumbent_history=[],error=None)
    nodes=r['node_history'];stack=[]
    def create(parent,restrictions,bound,branch=None):
        n=dict(node_id=len(nodes),parent_id=parent,depth=0 if parent is None else nodes[parent]['depth']+1,
               restrictions=restrictions.to_records(),inherited_upper_bound=bound,node_lp_upper_bound=None,
               safe_upper_bound=bound,status='pending',children=[],branch_from_parent=branch,
               branching_variable=None,prune_lower_bound=None,prune_witness=None,result=None)
        nodes.append(n);return n['node_id']
    def accept(w):
        if w is None:return
        checked=verify_integer_assignments(data,w['stations'],policy=policy,expected=w['objective'])
        if r['global_lower_bound'] is None or checked['objective']>r['global_lower_bound']:
            r.update(global_lower_bound=checked['objective'],witness=checked)
            elapsed=time.perf_counter()-started
            r['incumbent_history'].append(dict(seconds=elapsed,objective=checked['objective']))
            if r['first_integer_seconds'] is None:r['first_integer_seconds']=elapsed
    def closes(ub):
        return ub is not None and r['global_lower_bound'] is not None and ub<=r['global_lower_bound']+policy.allowance(r['global_lower_bound'])
    stack.append(create(None,NodeRestrictions(),None));processed=0;current=None
    try:
        while stack:
            if time.perf_counter()>=deadline:r.update(status='time_limit',termination_reason='global_deadline');break
            if processed>=node_limit:r.update(status='node_limit',termination_reason='processed_node_limit');break
            current=nodes[stack.pop()];processed+=1
            restrictions=NodeRestrictions.from_records(data,current['restrictions'])
            if closes(current['safe_upper_bound']):
                current.update(status='bound_pruned',prune_lower_bound=r['global_lower_bound'],prune_witness=r['witness']);current=None;continue
            current['status']='processing'
            parent=current['parent_id'];pool=None if parent is None else nodes[parent]['result']['pool']
            nr=solve_node(data,restrictions,pool,time_limit=max(1e-9,deadline-time.perf_counter()),solver=solver,
                          max_iterations=max_iterations,policy=policy,
                          log_dir=Path(log_dir)/f'node_{current["node_id"]}' if log_dir else None)
            current['result']=nr;current['node_lp_upper_bound']=nr['upper_bound']
            if nr['upper_bound'] is not None:
                old=current['safe_upper_bound'];current['safe_upper_bound']=nr['upper_bound'] if old is None else min(old,nr['upper_bound'])
            accept(nr['witness'])
            if nr['global_infeasibility_proven']:
                current['status']='infeasible_pruned';current=None;continue
            ub=current['safe_upper_bound'];lb=r['global_lower_bound']
            # 一个兄弟节点的上界可以低于全局LB；只检查本节点witness与本节点界。
            if nr['lower_bound'] is not None and ub is not None and ub<nr['lower_bound']-policy.bound_consistency_tolerance:
                raise NumericalUncertain('Node bound below its own witness')
            if closes(ub):
                current.update(status='bound_pruned',prune_lower_bound=lb,prune_witness=r['witness']);current=None;continue
            if not nr['lp_optimal_proven']:
                current['status']='unresolved';r.update(status=nr['status'],termination_reason=nr['termination_reason']);break
            branch=most_fractional(nr['x_values'],restrictions,policy)
            if branch is None:
                stations=[]
                for line in data['lines']:
                    candidates=[e for e in nr['solution'] if e['line']==line['id'] and e['weight']>policy.lp_primal_tolerance]
                    if not candidates:raise NumericalUncertain('Integral LP has empty line support')
                    chosen=max(candidates,key=lambda e:e['weight'])
                    stations+=nr['pool'][line['id']][chosen['column']]['stations']
                w=verify_integer_assignments(data,stations,policy=policy,expected=nr['lp_objective'])
                current['integral_witness']=w;accept(w)
                if not closes(ub):raise NumericalUncertain('Integral LP witness does not close repaired UB')
                current.update(status='integral_pruned',prune_lower_bound=w['objective'],prune_witness=w);current=None;continue
            current['status']='branched';current['branching_variable']=branch
            children=[]
            for value in (0,1):
                fix=restrictions.add(data,branch['variable'],value)
                children.append(create(current['node_id'],fix,ub,dict(variable=branch['variable'],value=value)))
            current['children']=children;stack.extend(reversed(children));current=None
    except Exception as error:
        if current:current['status']='unresolved'
        r.update(status='numerical_uncertain' if isinstance(error,NumericalUncertain) else 'solver_error',
                 termination_reason=str(error),error=dict(type=type(error).__name__,traceback=traceback.format_exc()))
    unresolved=[n for n in nodes if n['status'] in ('pending','processing','unresolved')]
    r['open_nodes']=[dict(node_id=n['node_id'],restrictions=n['restrictions'],upper_bound=n['safe_upper_bound']) for n in unresolved]
    bounds=[n['safe_upper_bound'] for n in nodes if n['status'] in ('pending','processing','unresolved','bound_pruned','integral_pruned')]
    if r['global_lower_bound'] is not None:bounds.append(r['global_lower_bound'])
    r['global_upper_bound']=None if not bounds or any(b is None for b in bounds) else max(bounds)
    if not unresolved:
        if r['global_lower_bound'] is None:r.update(status='infeasible_proven',global_infeasibility_proven=True,termination_reason='all_leaves_infeasible')
        elif closes(r['global_upper_bound']):r.update(status='optimal_within_tolerance',global_integer_optimal_proven=True,termination_reason='complete_tree_and_verified_bounds')
        else:r.update(status='numerical_uncertain',termination_reason='closed_tree_bound_gap_not_closed')
    if r['global_lower_bound'] is not None and r['global_upper_bound'] is not None:
        gap=r['global_upper_bound']-r['global_lower_bound'];r.update(absolute_gap=gap,relative_gap=max(0,gap)/max(1,abs(r['global_lower_bound'])))
    r.update(total_nodes_created=len(nodes),total_nodes_processed=processed,
             total_nodes_pruned=sum(n['status'].endswith('_pruned') for n in nodes),
             total_pricing_calls=sum(n['result']['pricing_calls'] for n in nodes if n['result']),wall_seconds=time.perf_counter()-started)
    return r

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('instance',type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--time-limit',type=float,default=30);p.add_argument('--node-limit',type=int,default=1000)
    p.add_argument('--max-iterations',type=int,default=100);p.add_argument('--solver',choices=['cplex_py','cbc'],default='cplex_py')
    a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    a.output.mkdir(parents=True,exist_ok=False);raw=a.instance.read_bytes();(a.output/'instance.json').write_bytes(raw)
    t=time.perf_counter();r=run(json.loads(raw.decode('utf-8-sig')),time_limit=a.time_limit,node_limit=a.node_limit,max_iterations=a.max_iterations,solver=a.solver,log_dir=a.output/'logs')
    encoded=zlib.compress(json.dumps(r,allow_nan=False).encode());(a.output/'result.json.zlib').write_bytes(encoded)
    import hashlib
    summary={k:r[k] for k in ('status','global_lower_bound','global_upper_bound','absolute_gap','global_integer_optimal_proven','global_infeasibility_proven','total_nodes_processed','wall_seconds')}
    summary.update(input_sha256=hashlib.sha256(raw).hexdigest(),evidence_sha256=hashlib.sha256(encoded).hexdigest(),algorithm_plus_persistence_seconds=time.perf_counter()-t)
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
    return 0 if r['global_integer_optimal_proven'] or r['global_infeasibility_proven'] else 2 if r['status']!='solver_error' else 3

if __name__=='__main__':sys.exit(main())
