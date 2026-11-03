"""根节点诊断：固定模型，比较空池、可行解注列、周期性受限整数恢复。

这是根LP与整数LB实验入口，不进行分支搜索。仅当验证整数witness与完整
定价产生的安全UB闭合时才证明整数最优；受限IP不可行不代表原IP不可行。
所有建模/求解/验证/逐轮持久化均消耗同一软预算，最终落盘另报E2E时间。
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib,json,math,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import blocks,compact,empty_pool,make_column
from node_state import NumericPolicy,NodeRestrictions,NumericalUncertain
from bp_solution import verify_integer_assignments
from solver_backend import BackendConfig,use_backend,make_solver
from master import build_master
from node_master_optimized import solve_node,recover_x
from incremental_evidence import materialize,certificate_fields
from evidence_store import EvidenceStore


def pool_from_records(data,records):
    records=materialize(records)
    lines={l['id']:l for l in data['lines']}
    return {(e['line'],e['station']):[make_column(lines[e['line']],e['station'],a)
             for a in e['patterns']] for e in records}


def inject_witness(data,witness,policy=None):
    """验证原模型可行性后，逐站添加列；不修改调用者方案或共享列池。"""
    checked=verify_integer_assignments(data,witness['stations'],policy=policy,expected=witness['objective'])
    pool=empty_pool(data);lines={l['id']:l for l in data['lines']}
    for e in checked['stations']:
        c=make_column(lines[e['line']],e['station'],e['assignments'])
        if c.assignments:pool[e['line'],e['station']].append(c)
    return pool,checked


def acquire_compact(data,solver,deadline,policy):
    started=time.perf_counter();record={'scope':'compact_initial_incumbent','witness':None}
    try:
        with use_backend(config(solver,deadline,policy)):
            m=compact.build_model(data);m.problem.solve(make_solver(role='compact_ip'))
        record['solver_result']=dict(m.problem.backend_result)
        if record['solver_result']['has_incumbent']:
            stations=[dict(line=l['id'],station=s,assignments=[(i,mode)
                      for (li,i,ss,mode),v in m.x.items() if li==l['id'] and ss==s and v.value()>.5])
                      for l,s in blocks(data)]
            record['witness']=verify_integer_assignments(data,stations,policy=policy,
                                                       expected=record['solver_result']['objective'])
    except TimeoutError:record['status']='time_limit'
    record['seconds']=time.perf_counter()-started
    return record


def config(solver,deadline,policy):
    return BackendConfig(name=solver,threads=1,seed=11,deadline=deadline,
        primal_tolerance=policy.lp_primal_tolerance,dual_tolerance=policy.lp_dual_tolerance,
        mip_integrality_tolerance=policy.pricing_integrality_tolerance)


def restricted_recovery(data,pool,solver,deadline,policy=None):
    policy=policy or NumericPolicy();started=time.perf_counter()
    result=dict(scope='restricted_pool_only',witness=None)
    try:
        with use_backend(config(solver,deadline,policy)):
            m=build_master(data,pool,integer=True)
            m.problem.solve(make_solver(role='recovery'))
        info=dict(m.problem.backend_result);result['solver_result']=info
        if info['has_incumbent']:
            if not m.problem.valid(policy.primal_validation_tolerance):
                raise NumericalUncertain('Restricted integer primal invalid')
            if any(v.value() is None or not math.isfinite(v.value()) or
                   abs(v.value()-round(v.value()))>policy.pricing_integrality_tolerance
                   for v in m.variables.values()):
                raise NumericalUncertain('Restricted lambda is not integer')
            stations=[]
            for l,s in blocks(data):
                chosen=[c for p,c in enumerate(pool[l['id'],s]) if m.variables[l['id'],s,p].value()>.5]
                if len(chosen)!=1:raise NumericalUncertain('Expected exactly one selected station column')
                stations.append(dict(line=l['id'],station=s,assignments=chosen[0].assignments))
            result['witness']=verify_integer_assignments(data,stations,policy=policy,expected=info['objective'])
    except TimeoutError:result['status']='time_limit'
    result['seconds']=time.perf_counter()-started
    return result


def round_diagnostics(data,row,policy,previous=None):
    out={k:row.get(k) for k in ('phase','iteration','objective','artificial_sum',
         'maximum_reduced_cost','repaired_upper_bound','complete_pricing')}
    out['pool_columns']=sum(n for k,n in row['pool'].counts) if hasattr(row['pool'],'counts') else sum(len(e['patterns']) for e in row['pool'])
    out['pricing_seconds']=sum(p['solve_seconds'] for p in row['pricing'])
    out['artificials_by_row_type']={}
    for a in row.get('artificials',[]):
        k=a['row'][0];out['artificials_by_row_type'][k]=out['artificials_by_row_type'].get(k,0)+a['value']
    if previous and previous['phase']==row['phase']:
        old={tuple(e['row']):e['value'] for e in previous.get('duals',[])}
        out['dual_change_l1']=sum(abs(e['value']-old[tuple(e['row'])]) for e in row.get('duals',[]))
    if row['phase']==2 and 'solution' in row:
        x=recover_x(data,row['solution']);tol=policy.branch_integrality_tolerance
        out['fractional_x_count']=sum(tol<e['value']<1-tol for e in x)
        out['positive_lambda_count']=sum(e['weight']>tol for e in row['solution'])
        out['structure']=solution_structure(data,row['solution'])
    return out


def solution_structure(data,solution):
    """以真实权重统计利润、站容量余量及共享资源；分数配置不解释为整数方案。"""
    lines={l['id']:l for l in data['lines']};usage={(l['id'],s):dict(active=0.,human=0.,robot=0.,duration=0.,fatigue=0.) for l,s in blocks(data)}
    parts=dict(revenue=0.,execution_cost=0.,station_cost=0.,human_cost=0.,robot_cost=0.)
    recovery={l['id']:0. for l in data['lines']}
    for e in solution:
        weight=e['weight']
        if abs(weight)<1e-12:continue
        line=lines[e['line']];s=e['station'];col=make_column(line,s,e['assignments']);cost=line['stations'][s-1]
        for k in usage[e['line'],s]:usage[e['line'],s][k]+=weight*getattr(col,k)
        recovery[e['line']]+=weight*col.recovery
        tasks={t['id']:t for t in line['tasks']}
        for i,m in col.assignments:
            parts['revenue']+=weight*tasks[i]['value'];parts['execution_cost']+=weight*tasks[i]['modes'][m]['cost']
        for k,attribute in [('station_cost','active'),('human_cost','human'),('robot_cost','robot')]:
            parts[k]+=weight*cost['fixed_cost' if k=='station_cost' else k]*getattr(col,attribute)
    stations=[]
    for (l,s),u in usage.items():
        line=lines[l]
        stations.append(dict(line=l,station=s,**u,time_slack=line['cycle_time']*u['active']-u['duration'],
                             fatigue_slack=-math.log1p(-line['fatigue_limit'])*u['human']-u['fatigue']))
    return dict(profit_parts=parts,net_profit=parts['revenue']-sum(v for k,v in parts.items() if k!='revenue'),
                human_slack=data['human_limit']-sum(u['human'] for u in usage.values()),
                robot_slack=data['robot_limit']-sum(u['robot'] for u in usage.values()),
                recovery_slack={l:recovery[l]-lines[l].get('min_recovery',0) for l in lines},stations=stations)


def run_root(data,*,mode='baseline',solver='cplex_py',time_limit=30.,initial_seconds=1.,
             recovery_every=10,recovery_seconds=.5,store=None,seed_witness=None):
    """mode三组共享初始解获取预算。baseline仅将初始解用于LB；seed注列；recover再周期恢复。"""
    if mode not in ('baseline','seed','recover'):raise ValueError('Unknown root experiment mode')
    compact.validate_data(data)
    for name,v in [('time_limit',time_limit),('recovery_seconds',recovery_seconds)]:compact.number(v,name,0,strict=True)
    compact.number(initial_seconds,'initial_seconds',0);compact.integer(recovery_every,'recovery_every',1)
    policy=NumericPolicy();started=time.perf_counter();deadline=started+time_limit
    acquisition=acquire_compact(data,solver,min(deadline,started+initial_seconds),policy) if seed_witness is None else dict(scope='provided_verified_seed',seconds=0.,witness=verify_integer_assignments(data,seed_witness['stations'],policy=policy,expected=seed_witness['objective']))
    incumbent=acquisition['witness'];first=time.perf_counter()-started if incumbent else None
    pool=None
    if mode!='baseline' and incumbent:pool,incumbent=inject_witness(data,incumbent,policy)
    summaries=[];recoveries=[];previous=None;observer_seconds=0.
    class Observer:
        def put(self,payload,kind):
            nonlocal incumbent,first,previous,observer_seconds
            tick=time.perf_counter();row=payload['record']
            summaries.append(round_diagnostics(data,row,policy,previous));previous=row
            # A completed real RMP is sufficient for heuristic IP, independently of LP convergence.
            if mode=='recover' and row['phase']==2 and row.get('complete_pricing') and (
                row['iteration']==1 or row['iteration']%recovery_every==0 or
                row.get('maximum_reduced_cost',math.inf)<=policy.reduced_cost_epsilon):
                if time.perf_counter()<deadline:
                    attempt=restricted_recovery(data,pool_from_records(data,row['pool']),solver,
                              min(deadline,time.perf_counter()+recovery_seconds),policy)
                    attempt.update(iteration=row['iteration'],elapsed=time.perf_counter()-started)
                    recoveries.append(attempt)
                    w=attempt['witness']
                    if w and (incumbent is None or w['objective']>incumbent['objective']):
                        incumbent=w
                        if first is None:first=time.perf_counter()-started
            if store:store.put(payload,kind)
            observer_seconds+=time.perf_counter()-tick
    answer=solve_node(data,parent_pool=pool,solver=solver,deadline=deadline,policy=policy,
                      version='V2',incremental_evidence=True,round_sink=Observer())
    lower=incumbent['objective'] if incumbent else None;upper=answer.lp_upper_bound
    if lower is not None and upper is not None and upper<lower-policy.bound_consistency_tolerance:
        raise NumericalUncertain('Verified integer LB exceeds complete-pricing root UB')
    if lower is not None and upper is not None:upper=max(lower,upper)
    gap=None if lower is None or upper is None else upper-lower
    result=dict(algorithm='root_CG_diagnostics_with_verified_integer_recovery',schema_version=1,
        proof_scope='root_complete_pricing_upper_bound_and_verified_original_integer_witness',mode=mode,
        settings=dict(solver=solver,time_limit=time_limit,initial_seconds=initial_seconds,
                      recovery_every=recovery_every,recovery_seconds=recovery_seconds,threads=1,seed=11),
        numeric_policy=asdict(policy),acquisition=acquisition,recoveries=recoveries,round_diagnostics=summaries,
        integer_incumbent_solution=incumbent,global_lower_bound=lower,global_upper_bound=upper,absolute_gap=gap,
        integer_structure=None if incumbent is None else solution_structure(data,[dict(e,weight=1.) for e in incumbent['stations']]),
        relative_gap=None if gap is None else gap/max(1,abs(lower)),
        global_integer_optimal_proven=gap is not None and gap<=policy.allowance(lower),
        global_infeasibility_proven=answer.status in ('local_infeasible_proven','phase1_infeasible_proven'),
        first_integer_seconds=first,algorithm_seconds=time.perf_counter()-started,
        observer_seconds=observer_seconds,root_status=answer.status,
        node=dict(node_id=0,restrictions=[],node_result=answer.to_dict(),certificate=certificate_fields(answer.certificate)))
    # Not additive: observer time and its suboperations are included in node_total.
    result['timings']=answer.certificate.timings
    if store:store.put(result,'result')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('instance',type=Path)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=('baseline','seed','recover'),default='recover')
    p.add_argument('--time-limit',type=float,default=30);p.add_argument('--initial-seconds',type=float,default=1)
    p.add_argument('--recovery-every',type=int,default=10);p.add_argument('--recovery-seconds',type=float,default=.5)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);raw=a.instance.read_bytes()
    (a.output/'instance.json').write_bytes(raw);store=EvidenceStore(a.output/'certificate.sqlite');tick=time.perf_counter()
    try:
        r=run_root(json.loads(raw.decode('utf-8-sig')),mode=a.mode,time_limit=a.time_limit,
            initial_seconds=a.initial_seconds,recovery_every=a.recovery_every,recovery_seconds=a.recovery_seconds,store=store)
        summary={k:v for k,v in r.items() if k not in ('node',)}
        summary['input_sha256']=hashlib.sha256(raw).hexdigest()
        summary['evidence_seconds']=store.seconds;summary['end_to_end_before_summary_seconds']=time.perf_counter()-tick
        (a.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        print(json.dumps({k:r[k] for k in ('mode','root_status','global_lower_bound','global_upper_bound','absolute_gap','algorithm_seconds')}))
    finally:store.close()
if __name__=='__main__':main()
