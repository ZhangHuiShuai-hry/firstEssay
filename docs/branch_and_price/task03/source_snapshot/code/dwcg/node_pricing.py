"""Rebuilt exact station pricing with explicit immutable branch restrictions."""
from __future__ import annotations

import math
import time

import pulp

from common import make_column, reduced_cost
from node_state import (NodePricingResult, PricingCertificate, NumericPolicy,
                        NodeRestrictions, NumericalUncertain)
from solver_backend import make_solver, objective_value


def validate_column(line, station, column, restrictions, policy):
    checked = make_column(line, station, column.assignments, policy.column_local_tolerance)
    if not restrictions.allows(line['id'], station, column):
        raise ValueError('Column violates node branch restrictions')
    if tuple(column.assignments) != checked.assignments:
        raise ValueError('Column assignments must be canonical')
    for name in ('active','human','robot','duration','fatigue','recovery','profit'):
        value = getattr(column, name)
        if not math.isfinite(value) or abs(value-getattr(checked,name)) > policy.column_local_tolerance:
            raise ValueError(f'Invalid column attribute {name}')
    return column


def fixed_records(restrictions, line_id, station):
    return [{'task':i,'mode':m,'value':b} for (i,m),b in
            sorted(restrictions.block_fixes(line_id,station).items())]


def validate_pricing_evidence(answer,line,station,phase,restrictions,purpose):
    if not isinstance(answer,NodePricingResult) or not isinstance(answer.certificate,PricingCertificate):
        raise NumericalUncertain('Typed pricing certificate required')
    cert=answer.certificate
    if ((cert.line,cert.station,cert.phase,cert.purpose)!=(line['id'],station,phase,purpose)
            or cert.fixed_variables!=fixed_records(restrictions,line['id'],station)):
        raise NumericalUncertain('Pricing certificate has the wrong node/block/phase domain')
    info=cert.solver_result
    if cert.optimal and (info.get('optimal') is not True or info.get('status')!='optimal'):
        raise NumericalUncertain('Pricing optimum lacks solver proof metadata')
    if cert.status=='infeasible' and (info.get('status')!='infeasible' or info.get('optimal') is not False):
        raise NumericalUncertain('Local infeasibility lacks solver proof metadata')
    return cert


def price_node(line, station, duals, phase, restrictions, policy=None, *, feasibility=False,
               verbose=False):
    """A typed certificate is mandatory; time-limited incumbents are never maxima.

    Solver configuration/deadline is explicit at the caller's use_backend scope.
    The feasibility oracle uses objective zero and the identical local domain.
    """
    policy = policy or NumericPolicy()
    if phase not in (1,2) or not isinstance(restrictions, NodeRestrictions):
        raise ValueError('Invalid node pricing arguments')
    cert = PricingCertificate(line['id'],station,phase,'local_feasibility' if feasibility else 'pricing')
    cert.fixed_variables=fixed_records(restrictions,line['id'],station)
    started = time.perf_counter()
    try:
        problem = pulp.LpProblem('node_station_pricing',pulp.LpMaximize)
        z = {(t['id'],m):pulp.LpVariable(f'z_{i}_{m}',cat='Binary')
             for i,t in enumerate(line['tasks']) for m in t['modes']}
        u,h,r = [pulp.LpVariable(v,cat='Binary') for v in ('u','h','r')]
        n = len(line['tasks'])
        duration,load,nh,nr = [pulp.LpAffineExpression() for _ in range(4)]
        for t in line['tasks']:
            problem += pulp.lpSum(z[t['id'],m] for m in t['modes']) <= 1
            for m,p in t['modes'].items():
                v = z[t['id'],m]
                duration += p['time']*v;load += p['time']*p['beta']*v
                nh += int(m in ('H','J'))*v;nr += int(m in ('R','J'))*v
        problem += duration <= line['cycle_time']*u
        for flag,total in ((u,pulp.lpSum(z.values())),(h,nh),(r,nr)):
            problem += flag <= total
            problem += total <= n*flag
        problem += load <= -math.log1p(-line['fatigue_limit'])*h
        for key,b in restrictions.block_fixes(line['id'],station).items():
            if key not in z:
                raise ValueError(f'Unknown fixed pricing variable {key}')
            problem += z[key] == b
        objective = pulp.LpAffineExpression()
        if not feasibility:
            l = line['id'];sigma = dict.fromkeys((t['id'] for t in line['tasks']),0.)
            for e,(i,j) in enumerate(line.get('precedence',[])):
                suffix = sum(duals['precedence',l,e,k] for k in range(station,len(line['stations'])+1))
                sigma[i] += suffix;sigma[j] -= suffix
            for t in line['tasks']:
                for m,p in t['modes'].items():
                    reward = (t['value']-p['cost']) if phase==2 else 0.
                    reward += -duals['task',l,t['id']] + duals['recovery',l]*t.get('weight',0) + sigma[t['id']]
                    objective += reward*z[t['id'],m]
            costs = line['stations'][station-1]
            objective -= (costs['fixed_cost'] if phase==2 else 0.)*u
            objective -= ((costs['human_cost'] if phase==2 else 0.)+duals['human',])*h
            objective -= ((costs['robot_cost'] if phase==2 else 0.)+duals['robot',])*r
            objective -= duals['station',l,station]
        problem += objective
        problem.solve(make_solver(mip=True,role='pricing',msg=verbose,gap=0))
        info = dict(problem.backend_result);cert.solver_result = info
        cert.status = info['status'];cert.optimal = info['optimal'] is True
        cert.has_incumbent=info['has_incumbent'];cert.incumbent=info['objective']
        cert.objective = info['objective'];cert.best_bound = info['best_bound']
        if not cert.optimal:
            return NodePricingResult(cert)
        if not problem.valid(policy.primal_validation_tolerance):
            raise NumericalUncertain('Node PP primal feasibility check failed')
        for v in list(z.values())+[u,h,r]:
            if v.value() is None or not math.isfinite(v.value()) or abs(v.value()-round(v.value())) > policy.pricing_integrality_tolerance:
                raise NumericalUncertain('Node PP has nonintegral/missing binary value')
        col = make_column(line,station,[key for key,v in z.items() if v.value()>.5],policy.column_local_tolerance)
        validate_column(line,station,col,restrictions,policy)
        value = objective_value(problem)
        if value is None:
            raise NumericalUncertain('Missing PP objective')
        rc = 0. if feasibility else reduced_cost(line,station,col,duals,phase)
        if not math.isfinite(rc) or abs(rc-value) > policy.bound_consistency_tolerance:
            raise NumericalUncertain('PP objective disagrees with explicit column reduced cost')
        cert.objective = value;cert.assignments = list(col.assignments)
        cert.reduced_cost = None if feasibility else rc
        return NodePricingResult(cert,col)
    except TimeoutError as error:
        cert.status='time_limit';cert.optimal=False;cert.error=str(error)
        return NodePricingResult(cert)
    except (NumericalUncertain,ValueError,KeyError) as error:
        cert.status='numerical_uncertain';cert.optimal=False;cert.error=str(error)
        return NodePricingResult(cert)
    except Exception as error:
        cert.status='solver_error';cert.optimal=False;cert.error=repr(error)
        return NodePricingResult(cert)
    finally:
        cert.solve_seconds = time.perf_counter()-started
