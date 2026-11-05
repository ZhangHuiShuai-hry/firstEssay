"""整线节点两阶段CG。所有新定价均满足节点硬固定域。"""
import sys,time,traceback,math
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from line_cg import (NumericPolicy,NumericalUncertain,BackendConfig,use_backend,
                     solve_master,column_key,verify_integer_assignments,validate_column)
from line_bp_pricing import solve_line,allows,NodeRestrictions

def solve_node(data,restrictions=None,parent_pool=None,*,time_limit=30,solver='cplex_py',
               max_iterations=100,policy=None,log_dir=None,recovery_seconds=.3):
    started=time.perf_counter();deadline=started+time_limit
    policy=policy or NumericPolicy();restrictions=(restrictions or NodeRestrictions()).validate(data)
    pool={l['id']:[deepcopy(c) for c in (parent_pool or {}).get(l['id'],[]) if allows(c,restrictions)] for l in data['lines']}
    keys={l:{column_key(c) for c in cols} for l,cols in pool.items()}
    events=[]
    r=dict(status='not_solved',termination_reason='',pool=pool,policy=asdict(policy),restrictions=restrictions.to_records(),
           initialization=[],initialization_fallback=[],history=[],integer_recovery=[],quota_repair=[],
           witness=None,lower_bound=None,upper_bound=None,absolute_gap=None,lp_objective=None,
           lp_optimal_proven=False,global_integer_optimal_proven=False,global_infeasibility_proven=False,
           solver_events=events,solution=[],x_values=[],error=None)
    def add(c):
        if not allows(c,restrictions):raise NumericalUncertain('Node received illegal column')
        k=column_key(c);l=c['line']
        if k in keys[l]:return False
        keys[l].add(k);pool[l].append(c);return True
    def accept(w):
        if w and (r['lower_bound'] is None or w['objective']>r['lower_bound']):
            r['lower_bound']=w['objective'];r['witness']=w
    config=BackendConfig(name=solver,threads=1,seed=11,deadline=deadline,
        primal_tolerance=policy.lp_primal_tolerance,dual_tolerance=policy.lp_dual_tolerance,
        mip_integrality_tolerance=policy.pricing_integrality_tolerance,log_dir=str(log_dir) if log_dir else None)
    try:
        with use_backend(config,events):
            for line in data['lines']:
                for c in pool[line['id']]:
                    checked=validate_column(line,c['stations'],policy=policy,expected=c['profit'])
                    if c['line']!=line['id'] or any(c[k]!=checked[k] for k in ('human','robot')):
                        raise NumericalUncertain('Invalid inherited line column')
            for line in data['lines']:
                if pool[line['id']]:continue
                c,cert=solve_line(line,phase=1,purpose='initial_feasibility',restrictions=restrictions,policy=policy)
                r['initialization_fallback'].append(cert)
                if cert['status']=='infeasible':
                    r.update(status='infeasible_proven',global_infeasibility_proven=True,termination_reason='local_domain_empty');return r
                if c is None:
                    r.update(status=cert['status'],termination_reason='local_initialization_unresolved');return r
                add(c)
            phase=1
            for iteration in range(1,max_iterations+1):
                if time.perf_counter()>=deadline:raise TimeoutError('Node deadline')
                m=solve_master(data,pool,phase=phase,policy=policy)
                rec=dict(iteration=iteration,phase=phase,rmp=m,pricing=[],complete_exact_pricing=False,
                         repaired_upper_bound=None,added=[],phase_transition=False)
                r['history'].append(rec)
                if not m['solver']['optimal']:
                    r.update(status='numerical_uncertain' if m['solver']['status']=='infeasible' else m['solver']['status'],
                             termination_reason='restricted_RMP_not_optimal');break
                # CBC的对偶输出会舍入：用已有列的最大违约量向上修复凸性价格。
                # 这是可审计的对偶修复；上界使用修复后真实对偶目标，不放宽epsilon。
                before=deepcopy(m['duals']);old_objective=m['dual_objective'];shifts={}
                for l,cols in pool.items():
                    d=m['duals'];sigma=d['convexity'][l]
                    violation=max((c['profit'] if phase==2 else 0)-d['human']*c['human']-d['robot']*c['robot']-sigma for c in cols)
                    if violation>policy.bound_consistency_tolerance:raise NumericalUncertain('Large RMP dual violation')
                    if violation>0:d['convexity'][l]=math.nextafter(sigma+violation,math.inf)
                    shifts[l]=d['convexity'][l]-sigma
                m['dual_objective']=sum(m['duals']['convexity'].values())+sum(data[k+'_limit']*m['duals'][k] for k in ('human','robot'))
                if abs(m['dual_objective']-m['objective'])>policy.bound_consistency_tolerance:raise NumericalUncertain('Repaired RMP duality gap')
                m['dual_repair']=dict(before=before,before_objective=old_objective,shifts=shifts)
                if phase==1 and sum(m['artificials'].values())<=policy.artificial_tolerance:
                    rec['phase_transition']=True;phase=2;continue
                if phase==2:
                    r['lp_objective']=m['objective']
                    rip=solve_master(data,pool,integer=True,policy=policy,time_limit=min(recovery_seconds,max(.001,deadline-time.perf_counter())))
                    r['integer_recovery'].append(rip);accept(rip['witness'])
                d=m['duals']
                for line in data['lines']:
                    c,cert=solve_line(line,phase=phase,human_price=d['human'],robot_price=d['robot'],
                        sigma=d['convexity'][line['id']],restrictions=restrictions,policy=policy)
                    rec['pricing'].append(cert)
                    if cert['status']=='infeasible':
                        r.update(status='infeasible_proven',global_infeasibility_proven=True,termination_reason='pricing_local_domain_empty');break
                    if c and cert['reduced_cost']>policy.reduced_cost_epsilon:
                        if add(c):rec['added'].append(dict(line=c['line'],column=len(pool[c['line']])-1))
                        elif cert['optimal']:raise NumericalUncertain('Positive RC duplicate column')
                    if not cert['optimal']:
                        r.update(status=cert['status'],termination_reason='pricing_unresolved');break
                if r['global_infeasibility_proven']:break
                rec['complete_exact_pricing']=len(rec['pricing'])==len(data['lines']) and all(c['optimal'] for c in rec['pricing'])
                if not rec['complete_exact_pricing']:
                    if not r['termination_reason']:r.update(status='numerical_uncertain',termination_reason='incomplete_pricing')
                    break
                rho=[c['reduced_cost'] for c in rec['pricing']]
                ub=m['dual_objective']+sum(max(0,x) for x in rho);rec['repaired_upper_bound']=ub
                if phase==1 and ub < -policy.artificial_tolerance:
                    r.update(status='infeasible_proven',global_infeasibility_proven=True,termination_reason='phase1_negative_complete_bound');break
                if phase==2:r['upper_bound']=ub if r['upper_bound'] is None else min(ub,r['upper_bound'])
                if max(rho)<=policy.reduced_cost_epsilon:
                    if phase==1:r.update(status='numerical_uncertain',termination_reason='phase1_ambiguous');break
                    r.update(status='node_lp_optimal_proven',lp_optimal_proven=True,solution=m['solution'],termination_reason='complete_exact_pricing')
                    values={(line['id'],t['id'],s,mode):0. for line in data['lines'] for t in line['tasks']
                            for s in range(1,len(line['stations'])+1) for mode in t['modes']}
                    for e in m['solution']:
                        for station in pool[e['line']][e['column']]['stations']:
                            for i,mode in station['assignments']:values[e['line'],i,station['station'],mode]+=e['weight']
                    r['x_values']=[dict(variable=list(k),value=v) for k,v in sorted(values.items(),key=lambda e:(e[0][0],e[0][2],e[0][1],e[0][3]))]
                    break
                if not rec['added']:raise NumericalUncertain('Positive RC without new column')
            else:r.update(status='iteration_limit',termination_reason='node_CG_iteration_limit')
    except TimeoutError as error:r.update(status='time_limit',termination_reason=str(error))
    except Exception as error:
        r.update(status='numerical_uncertain' if isinstance(error,NumericalUncertain) else 'solver_error',
                 termination_reason=str(error),error=dict(type=type(error).__name__,traceback=traceback.format_exc()))
    finally:
        r['solve_seconds']=time.perf_counter()-started
        r['pricing_calls']=len(r['initialization_fallback'])+sum(len(h['pricing']) for h in r['history'])
        if r['lower_bound'] is not None and r['upper_bound'] is not None:r['absolute_gap']=r['upper_bound']-r['lower_bound']
    return r
