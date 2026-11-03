"""Node-isolated two-phase CG with generalized elastic coupling rows."""
from __future__ import annotations

from dataclasses import asdict
import math
from pathlib import Path
import time
import traceback

import pulp

from common import blocks, empty_pool, coefficients, compact, reduced_cost
from master import build_master
from node_pricing import price_node, validate_column,validate_pricing_evidence
from node_state import (NodeRestrictions, NumericPolicy, NodeCertificate, NodeResult,
                        NodePricingResult, NumericalUncertain, pool_snapshot)
from solver_backend import BackendConfig, make_solver, use_backend, objective_value


def build_node_master(data, pool, restrictions, phase, policy=None):
    policy = policy or NumericPolicy()
    restrictions.validate(data)
    for line,s in blocks(data):
        cols = pool[line['id'],s]
        if not cols:
            raise ValueError('Hard convexity requires at least one legal local column')
        for c in cols:validate_column(line,s,c,restrictions,policy)
    m = build_master(data,pool,phase=2)
    m.phase = phase;m.elastic = []
    if phase==1:
        for index,(key,row) in enumerate(m.rows.items()):
            if key[0]=='station':continue
            signs = (1,-1) if row.sense==pulp.LpConstraintEQ else (-1,)
            for direction in signs:
                v = pulp.LpVariable(f'elastic_{index}_{"plus" if direction==1 else "minus"}',0)
                row.addInPlace(direction*v)
                m.elastic.append((key,direction,v))
        m.artificials=[v for k,sign,v in m.elastic]
        m.objective=-pulp.lpSum(m.artificials)
        m.problem.setObjective(m.objective)
    elif phase!=2:
        raise ValueError('Node master phase must be 1 or 2')
    return m


def solve_node_master(m, policy, verbose=False):
    m.native_adapter.solve_mirror(m) if hasattr(m,'native_adapter') else m.problem.solve(make_solver(mip=False,role='rmp',msg=verbose))
    info=dict(m.problem.backend_result)
    if not info['optimal']:
        error=NumericalUncertain('Node RMP not proven optimal: '+info['status'])
        error.solver_result=info
        raise error
    if not m.problem.valid(policy.primal_validation_tolerance):
        raise NumericalUncertain('Node RMP primal constraints invalid')
    raw=m.duals();effective={}
    for key,row in m.rows.items():
        value=raw[key]
        if value is None or not math.isfinite(value):
            raise NumericalUncertain('Nonfinite node dual')
        lo = 0. if row.sense==pulp.LpConstraintLE else -math.inf
        hi = math.inf
        if m.phase==1 and key[0]!='station':
            hi=1.
            if row.sense==pulp.LpConstraintEQ:lo=-1.
        if value < lo-policy.lp_dual_tolerance or value > hi+policy.lp_dual_tolerance:
            raise NumericalUncertain('Invalid node dual sign/artificial inequality')
        effective[key]=min(hi,max(lo,value))
    value=objective_value(m.problem)
    if value is None:raise NumericalUncertain('Missing node RMP objective')
    dobj=sum(-m.rows[k].constant*v for k,v in effective.items())
    if not math.isfinite(dobj) or abs(dobj-value)>policy.bound_consistency_tolerance:
        raise NumericalUncertain('Node primal/dual objective mismatch')
    return value,raw,effective,dobj,info


def primal_snapshot(m,pool):
    return [{'line':l,'station':s,'column':p,'assignments':list(pool[l,s][p].assignments),
             'weight':v.value()} for (l,s,p),v in m.variables.items()]


def recover_x(data,solution):
    values={(line['id'],t['id'],s,m):0. for line in data['lines'] for s in range(1,len(line['stations'])+1)
            for t in line['tasks'] for m in t['modes']}
    for e in solution:
        for i,m in e['assignments']:values[e['line'],i,e['station'],m]+=e['weight']
    return [{'variable':list(q),'value':v} for q,v in values.items()]


def _unproven_status(cert):
    if cert.status=='time_limit':return 'time_limit'
    if cert.status=='solver_error':return 'solver_error'
    return 'numerical_uncertain'


def solve_node(data, restrictions=None, parent_pool=None, *, policy=None, solver='cbc',
               deadline=None, max_iterations=1000, log_dir=None, verbose=False, version='V1'):
    """No enumeration, no monkeypatch, no native state shared between nodes."""
    compact.validate_data(data);policy=policy or NumericPolicy()
    restrictions=(restrictions or NodeRestrictions()).validate(data)
    compact.integer(max_iterations,'max_iterations',1)
    cert=NodeCertificate(restrictions.to_records())
    result=NodeResult('numerical_uncertain',cert);started=time.perf_counter()
    config=BackendConfig(name=solver,threads=1,seed=11,deadline=deadline,
        primal_tolerance=policy.lp_primal_tolerance,dual_tolerance=policy.lp_dual_tolerance,
        mip_integrality_tolerance=policy.pricing_integrality_tolerance,
        log_dir=str(log_dir) if log_dir else None)
    if log_dir:Path(log_dir).mkdir(parents=True,exist_ok=True)
    native_pp={};native_master=None
    metrics={'pp_wall':0.,'rmp_build':0.,'rmp_solve_read':0.}
    def node_price(line,s,duals,phase,restrictions,policy,**kwargs):
        tick=time.perf_counter()
        try:
            if solver!='cplex_py':return price_node(line,s,duals,phase,restrictions,policy,**kwargs)
            from node_persistent_pricing import NodePersistentPricing
            key=line['id'],s
            if key not in native_pp:
                path=str(Path(log_dir)/f'pp_{len(native_pp)}.log') if log_dir else None
                native_pp[key]=NodePersistentPricing(line,s,restrictions,policy,config,path)
            return native_pp[key].run(duals,phase,deadline,kwargs.get('feasibility',False))
        finally:metrics['pp_wall']+=time.perf_counter()-tick
    active_phase=0
    try:
        with use_backend(config,cert.solver_events):
            inherited=empty_pool(data) if parent_pool is None else parent_pool
            for line,s in blocks(data):
                key=line['id'],s;legal=[];seen=set()
                for col in inherited.get(key,[]):
                    # Invalid attributes are an input error, not a silent filter.
                    if restrictions.allows(key[0],s,col):
                        validate_column(line,s,col,restrictions,policy)
                        if col.assignments not in seen:legal.append(col);seen.add(col.assignments)
                result.pool[key]=legal
                entry={'line':key[0],'station':s,'inherited_count':len(inherited.get(key,[])),
                       'legal_inherited_count':len(legal)}
                cert.initialization.append(entry)
                if not legal:
                    answer=node_price(line,s,None,1,restrictions,policy,feasibility=True,verbose=verbose)
                    result.pricing_calls+=1
                    pp=validate_pricing_evidence(answer,line,s,1,restrictions,'local_feasibility')
                    entry['feasibility']=asdict(pp)
                    if pp.status=='infeasible':
                        if not any(restrictions.block_fixes(key[0],s).values()):
                            result.status='solver_error';result.termination_reason='Empty column contradicts local infeasibility'
                        else:
                            result.status='local_infeasible_proven';result.termination_reason='Allowed station column set proven empty'
                        return result
                    if not pp.optimal or pp.status!='optimal' or answer.column is None:
                        result.status=_unproven_status(pp);result.termination_reason='Unproven local initialization'
                        return result
                    validate_column(line,s,answer.column,restrictions,policy)
                    legal.append(answer.column);result.columns_generated+=1
            cert.initial_pool=pool_snapshot(result.pool)
            for phase in (1,2):
                active_phase=phase
                for iteration in range(1,max_iterations+1):
                    record={'phase':phase,'iteration':iteration,'complete_pricing':False,
                            'pool':pool_snapshot(result.pool),'pricing':[]}
                    cert.rounds.append(record)
                    tick=time.perf_counter()
                    m=build_node_master(data,result.pool,restrictions,phase,policy)
                    if version=='V2' and solver=='cplex_py':
                        from node_incremental_master import NodeIncrementalMaster
                        if native_master is None:native_master=NodeIncrementalMaster(config,str(Path(log_dir)/'native_rmp.log') if log_dir else None)
                        native_master.sync(m)
                    metrics['rmp_build']+=time.perf_counter()-tick
                    tick=time.perf_counter()
                    value,raw,duals,dobj,info=solve_node_master(m,policy,verbose)
                    metrics['rmp_solve_read']+=time.perf_counter()-tick
                    record.update(rmp_status='optimal',rmp_solver_result=info,objective=value,dual_objective=dobj,
                        raw_duals=[{'row':list(k),'value':v} for k,v in raw.items()],
                        duals=[{'row':list(k),'value':v} for k,v in duals.items()],
                        solution=primal_snapshot(m,result.pool),
                        artificials=[{'row':list(k),'sign':sign,'value':v.value(),'name':v.name} for k,sign,v in m.elastic])
                    if phase==1:
                        artificial_sum=sum(v.value() for k,sign,v in m.elastic)
                        record['artificial_sum']=artificial_sum
                        if artificial_sum < -policy.primal_validation_tolerance:
                            raise NumericalUncertain('Negative artificial total')
                        if artificial_sum<=policy.artificial_tolerance:
                            cert.phase1_status='zero_artificials_pending_real_RMP_check'
                            record['event']='attempt_phase2_without_artificials'
                            break
                    else:
                        # This is the independent real-RMP feasibility confirmation.
                        cert.phase1_status='feasible_real_RMP_confirmed'
                        result.lp_objective=value;result.lp_solution=record['solution']
                        result.x_values=recover_x(data,result.lp_solution)
                    for (l,s,p),v in m.variables.items():
                        line=next(line for line in data['lines'] if line['id']==l)
                        raw_rc=reduced_cost(line,s,result.pool[l,s][p],raw,phase)
                        if v.dj is None or not math.isfinite(v.dj) or abs(v.dj-raw_rc)>policy.bound_consistency_tolerance:
                            raise NumericalUncertain('RMP dj disagrees with row-vector reduced cost')
                    candidates=[]
                    for line,s in blocks(data):
                        answer=node_price(line,s,duals,phase,restrictions,policy,verbose=verbose)
                        result.pricing_calls+=1
                        pp=validate_pricing_evidence(answer,line,s,phase,restrictions,'pricing')
                        record['pricing'].append(asdict(pp))
                        if not pp.optimal or pp.status!='optimal' or answer.column is None:
                            result.status='solver_error' if pp.status=='infeasible' else _unproven_status(pp)
                            result.termination_reason='Unproven pricing; no new round bound'
                            return result
                        col=validate_column(line,s,answer.column,restrictions,policy)
                        rc=reduced_cost(line,s,col,duals,phase)
                        if not math.isfinite(rc) or pp.reduced_cost is None or abs(rc-pp.reduced_cost)>policy.bound_consistency_tolerance:
                            raise NumericalUncertain('Pricing certificate reduced cost mismatch')
                        candidates.append((line,s,col,rc))
                    coverage={(p['line'],p['station']) for p in record['pricing']}
                    if coverage!=set(result.pool) or len(record['pricing'])!=len(result.pool):
                        raise NumericalUncertain('Incomplete/duplicate pricing coverage')
                    correction=sum(max(0.,rc) for l,s,c,rc in candidates)
                    upper=max(value,dobj)+correction;maximum=max(rc for l,s,c,rc in candidates)
                    record.update(complete_pricing=True,maximum_reduced_cost=maximum,
                                  rmp_formula_upper_bound=value+correction,repaired_upper_bound=upper,
                                  upper_bound_base=max(value,dobj),lp_gap=upper-value,columns_added=[])
                    if phase==2:
                        result.lp_upper_bound=upper if result.lp_upper_bound is None else min(result.lp_upper_bound,upper)
                        if result.lp_upper_bound < value-policy.bound_consistency_tolerance:
                            raise NumericalUncertain('Node upper bound below a feasible RMP objective')
                    if maximum<=policy.reduced_cost_epsilon:
                        if phase==1:
                            if upper < -policy.artificial_tolerance:
                                cert.phase1_status='infeasible_proven';result.status='phase1_infeasible_proven'
                                result.termination_reason='Complete Phase I repaired dual bound is strictly negative'
                            else:
                                cert.phase1_status='numerical_uncertain';result.status='numerical_uncertain'
                                result.termination_reason='Phase I certificate insufficient for infeasibility'
                            return result
                        cert.phase2_status='node_lp_optimal_proven';result.status='node_lp_optimal_proven'
                        result.termination_reason='Complete exact pricing in all node blocks'
                        return result
                    if iteration==max_iterations:
                        result.status='cg_iteration_limit';result.termination_reason=f'Phase {phase} CG iteration limit'
                        return result
                    for line,s,col,rc in candidates:
                        if rc>policy.reduced_cost_epsilon:
                            cols=result.pool[line['id'],s]
                            if any(old.assignments==col.assignments for old in cols):
                                raise NumericalUncertain('Positive reduced cost duplicate column')
                            cols.append(col);result.columns_generated+=1
                            record['columns_added'].append({'line':line['id'],'station':s,'assignments':list(col.assignments)})
    except TimeoutError as error:
        result.status='time_limit';result.termination_reason=str(error)
        cert.error={'type':type(error).__name__,'message':str(error)}
    except NumericalUncertain as error:
        info=getattr(error,'solver_result',{})
        result.status='time_limit' if info.get('status')=='time_limit' else 'numerical_uncertain'
        result.termination_reason=str(error)
        cert.error={'type':type(error).__name__,'message':str(error),'solver_result':info}
    except Exception as error:
        result.status='solver_error';result.termination_reason=repr(error)
        cert.error={'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()}
    finally:
        for pp in native_pp.values():pp.close()
        if native_master is not None:native_master.close()
        result.solve_seconds=time.perf_counter()-started
        cert.timings=dict(metrics,other=max(0.,result.solve_seconds-sum(metrics.values())),node_total=result.solve_seconds)
        if active_phase==1 and cert.phase1_status=='not_run':cert.phase1_status=result.status
        if active_phase==2 and cert.phase2_status=='not_run':cert.phase2_status=result.status
    return result
