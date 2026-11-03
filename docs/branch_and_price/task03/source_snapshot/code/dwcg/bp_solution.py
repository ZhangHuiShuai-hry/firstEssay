"""Data-level and original compact-MILP verification of B&P integer witnesses."""
import math

import pulp

from common import compact,blocks
from node_state import NumericalUncertain,NumericPolicy,NodeRestrictions
from solver_backend import objective_value


def verify_integer_assignments(data,station_records,restrictions=None,policy=None,expected=None):
    restrictions=restrictions or NodeRestrictions();policy=policy or NumericPolicy()
    tol=policy.primal_validation_tolerance
    lines={l['id']:l for l in data['lines']};seen_blocks=set();selected={l:{} for l in lines}
    humans=robots=0;profit=0.;columns=[]
    original=compact.build_model(data)
    for v in original.problem.variables():v.varValue=0
    for record in station_records:
        l,s=record['line'],record['station'];key=l,s
        if key in seen_blocks or l not in lines or type(s) is not int or not 1<=s<=len(lines[l]['stations']):
            raise NumericalUncertain('Invalid/duplicate integer station')
        seen_blocks.add(key);line=lines[l];tasks={t['id']:t for t in line['tasks']}
        assignments=tuple(tuple(a) for a in record['assignments']);pairs=set(assignments)
        if len(pairs)!=len(assignments):raise NumericalUncertain('Duplicate integer assignment')
        local_tasks=set();time_used=load=recovery=revenue=execution=0.
        for i,m in assignments:
            if i not in tasks or m not in tasks[i]['modes'] or i in local_tasks or i in selected[l]:
                raise NumericalUncertain('Invalid/duplicate task or mode')
            local_tasks.add(i);selected[l][i]=s;p=tasks[i]['modes'][m]
            time_used+=p['time'];load+=p['time']*p['beta'];recovery+=tasks[i].get('weight',0)
            revenue+=tasks[i]['value'];execution+=p['cost']
            original.x[l,i,s,m].varValue=1;original.y[l,i].varValue=1
        u=int(bool(assignments));h=int(any(m in ('H','J') for i,m in assignments));r=int(any(m in ('R','J') for i,m in assignments))
        if time_used>line['cycle_time']*u+policy.column_local_tolerance:
            raise NumericalUncertain('Integer cycle constraint violated')
        if load>-math.log1p(-line['fatigue_limit'])*h+policy.column_local_tolerance:
            raise NumericalUncertain('Integer fatigue constraint violated')
        for (i,m),b in restrictions.block_fixes(l,s).items():
            if int((i,m) in pairs)!=b:raise NumericalUncertain('Integer solution violates branch')
        original.u[l,s].varValue=u;original.h[l,s].varValue=h;original.r[l,s].varValue=r
        cost=line['stations'][s-1];pvalue=revenue-execution-cost['fixed_cost']*u-cost['human_cost']*h-cost['robot_cost']*r
        profit+=pvalue;humans+=h;robots+=r
        columns.append({'line':l,'station':s,'assignments':[list(a) for a in sorted(assignments)],
                        'active':u,'human':h,'robot':r,'duration':time_used,'fatigue':load,
                        'recovery':recovery,'profit':pvalue})
    if seen_blocks!={(l['id'],s) for l,s in blocks(data)}:
        raise NumericalUncertain('Integer witness does not cover every station')
    for l,line in lines.items():
        chosen=selected[l];tasks={t['id']:t for t in line['tasks']}
        if not set(line.get('required_tasks',[]))<=chosen.keys():raise NumericalUncertain('Missing required integer task')
        for i,j in line.get('precedence',[]):
            if j in chosen and (i not in chosen or chosen[i]>chosen[j]):raise NumericalUncertain('Integer AND precedence violation')
        if sum(tasks[i].get('weight',0) for i in chosen)<line.get('min_recovery',0)-tol:
            raise NumericalUncertain('Integer recovery violation')
    if humans>data['human_limit'] or robots>data['robot_limit']:
        raise NumericalUncertain('Integer shared resource violation')
    if not original.problem.valid(tol):raise NumericalUncertain('Original compact constraints reject integer witness')
    value=objective_value(original.problem)
    if value is None or not math.isfinite(profit) or abs(value-profit)>policy.bound_consistency_tolerance:
        raise NumericalUncertain('Independent integer profit disagrees with compact objective')
    if expected is not None and abs(profit-expected)>policy.bound_consistency_tolerance:
        raise NumericalUncertain('Rounded integer witness profit disagrees with LP objective')
    return {'objective':profit,'stations':columns,'resources_used':{'humans':humans,'robots':robots},
            'data_level_validated':True,'compact_constraints_validated':True,
            'branch_restrictions_validated':True}


def integer_from_x(data,x_values,restrictions,policy,expected):
    assignment={(l['id'],s):[] for l,s in blocks(data)}
    for e in x_values:
        l,i,s,m=e['variable'];value=e['value']
        if not math.isfinite(value) or abs(value-round(value))>policy.branch_integrality_tolerance:
            raise NumericalUncertain('Cannot recover integer witness from fractional x')
        if value>.5:assignment[l,s].append((i,m))
    return verify_integer_assignments(data,[{'line':l,'station':s,'assignments':a} for (l,s),a in assignment.items()],
                                      restrictions,policy,expected)
