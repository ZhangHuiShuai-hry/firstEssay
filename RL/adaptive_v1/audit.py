"""整线列的独立小规模枚举 Oracle 与保存证书重放。

枚举直接遍历每任务的“不选/站点/模式”，不调用生产定价或列构造器。
CPLEX 只用于求解本文件独立组装的完整列 LP/IP；原 Compact 是被测对象。
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"sub"))
sys.path.insert(0,str(ROOT/"RL/reuse_v1"))
from check_screen import check as check_screen
from check_candidates import check as check_candidates
sys.path[:0] = [str(ROOT / 'code/dwcg'), str(ROOT / 'code')]
import pulp
from solver_backend import BackendConfig, make_solver, objective_value, use_backend

TOL = 1e-5


def close(a, b, tol=TOL):
    assert a is not None and b is not None and math.isfinite(a) and math.isfinite(b)
    assert abs(a-b) <= tol, (a, b)


def evaluate_line(line, stations):
    """以原始数据检查所有线内约束，不使用 PuLP 或生产列对象。"""
    tasks = {t['id']: t for t in line['tasks']}
    records = {e['station']: e for e in stations}
    assert len(records) == len(stations) == len(line['stations'])
    assert set(records) == set(range(1, len(line['stations'])+1))
    chosen = {}
    humans = robots = 0
    profit = 0.
    for s, costs in enumerate(line['stations'], 1):
        e = records[s]
        assert e.get('line', line['id']) == line['id']
        assignments = e['assignments']
        assert len({i for i, m in assignments}) == len(assignments)
        duration = fatigue = 0.
        h = int(any(m in ('H', 'J') for i, m in assignments))
        r = int(any(m in ('R', 'J') for i, m in assignments))
        for i, m in assignments:
            assert i in tasks and m in tasks[i]['modes'] and i not in chosen
            chosen[i] = s
            p = tasks[i]['modes'][m]
            duration += p['time']
            fatigue += p['time'] * p['beta']
            profit += tasks[i]['value'] - p['cost']
        assert duration <= line['cycle_time']*bool(assignments) + 1e-8
        assert fatigue <= -math.log1p(-line['fatigue_limit'])*h + 1e-8
        humans += h
        robots += r
        profit -= (costs['fixed_cost']*bool(assignments) +
                   costs['human_cost']*h + costs['robot_cost']*r)
    assert set(line.get('required_tasks', [])).issubset(chosen)
    for i, j in line.get('precedence', []):
        assert j not in chosen or (i in chosen and chosen[i] <= chosen[j])
    recovery = sum(tasks[i].get('weight', 0) for i in chosen)
    assert recovery >= line.get('min_recovery', 0) - 1e-8
    return {'profit': profit, 'human': humans, 'robot': robots,
            'stations': stations}


def enumerate_line(line, max_assignments=2000000):
    choices = [[None] + [(s, m) for s in range(1, len(line['stations'])+1)
                         for m in t['modes']] for t in line['tasks']]
    size = math.prod(map(len, choices))
    if size > max_assignments:
        raise ValueError(f"Independent enumeration guard: {line['id']} has {size} choices")
    result = []
    for selection in itertools.product(*choices):
        stations = [{'line': line['id'], 'station': s, 'assignments': []}
                    for s in range(1, len(line['stations'])+1)]
        for task, selected in zip(line['tasks'], selection):
            if selected is not None:
                s, m = selected
                stations[s-1]['assignments'].append([task['id'], m])
        try:
            result.append(evaluate_line(line, stations))
        except AssertionError:
            pass
    return result


def enumerate_all(data):
    return {line['id']: enumerate_line(line) for line in data['lines']}


def full_problem(data, pool, integer=False, phase=2):
    """独立构造整线完整主问题；只有凸性、人和机器人三类行。"""
    problem = pulp.LpProblem('independent_full_line', pulp.LpMaximize)
    variables = {(l, k): pulp.LpVariable(f'oracle_{b}_{k}', 0,
                  cat='Binary' if integer else 'Continuous')
                 for b, (l, columns) in enumerate(pool.items()) for k in range(len(columns))}
    for b, (l, columns) in enumerate(pool.items()):
        problem += pulp.lpSum(variables[l, k] for k in range(len(columns))) == 1, f'line_{b}'
    elastic = []
    for resource, limit in [('human', 'human_limit'), ('robot', 'robot_limit')]:
        total = pulp.lpSum(c[resource]*variables[l, k]
                           for l, columns in pool.items() for k, c in enumerate(columns))
        if phase == 1:
            a = pulp.LpVariable('slack_'+resource, 0)
            elastic.append(a)
            total -= a
        problem += total <= data[limit], resource
    problem += (-pulp.lpSum(elastic) if phase == 1 else
                pulp.lpSum(c['profit']*variables[l, k]
                           for l, columns in pool.items() for k, c in enumerate(columns)))
    return problem, variables


def solve_full(data, pool, integer=False, phase=2, solver='cplex_py'):
    problem, variables = full_problem(data, pool, integer, phase)
    with use_backend(BackendConfig(name=solver)):
        problem.solve(make_solver(mip=integer, role='verification'))
    info = dict(problem.backend_result)
    assert info['optimal'] or info['status'] == 'infeasible', info
    return dict(status=info['status'], objective=info['objective'],
                optimal=info['optimal'], positive=[{'line': l, 'index': k, 'weight': v.value()}
                for (l, k), v in variables.items() if info['optimal'] and v.value() > 1e-9])


def check_witness(data, witness, expected=None):
    by_line = {line['id']: [] for line in data['lines']}
    for record in witness['stations']:
        assert record['line'] in by_line
        by_line[record['line']].append(record)
    evaluated = [evaluate_line(line, by_line[line['id']]) for line in data['lines']]
    assert sum(c['human'] for c in evaluated) <= data['human_limit']
    assert sum(c['robot'] for c in evaluated) <= data['robot_limit']
    value = sum(c['profit'] for c in evaluated)
    if expected is not None:
        close(value, expected)
    close(value, witness['objective'])
    return value


def signature(column):
    return tuple((e['station'], tuple(sorted(tuple(a) for a in e['assignments'])))
                 for e in sorted(column['stations'], key=lambda e: e['station']))


def check_column(line, column):
    independent = evaluate_line(line, column['stations'])
    for key in ('profit', 'human', 'robot'):
        close(independent[key], column[key])
    return independent


def audit(data, result, *, enumerate_pricing=True, solver='cplex_py'):
    """小规模完全重放；大规模仅核算数据/对偶，明确依赖原生最优状态。"""
    check_candidates(data,result)
    lines = {l['id']: l for l in data['lines']}
    pool = result['pool']
    assert set(pool) == set(lines)
    complete = enumerate_all(data) if enumerate_pricing else None
    for l, columns in pool.items():
        keys = set()
        for column in columns:
            check_column(lines[l], column)
            key = signature(column)
            assert key not in keys, 'Duplicate column'
            keys.add(key)
    bounds = []
    infeasible = False
    pricing_checked = 0

    def pricing(cert, duals=None, phase=None):
        nonlocal pricing_checked
        l = cert['line']
        assert l in lines
        phase = cert['phase'] if phase is None else phase
        assert phase == cert['phase']
        h, r, sigma = cert['human_price'], cert['robot_price'], cert['sigma']
        if duals is not None:
            close(h, duals['human']); close(r, duals['robot'])
            close(sigma, duals['convexity'][l])
        if cert.get('bound_certified'):
            check_screen(lines[l],cert,result['pricing_audit_calls'])
            if complete is not None:
                truth=max(c['profit']-h*c['human']-r*c['robot']-sigma for c in complete[l])
                assert truth<=cert['reduced_cost_upper_bound']+TOL
        if cert['column'] is not None:
            c = check_column(lines[l], cert['column'])
            close(cert['reduced_cost'], (c['profit'] if phase==2 else 0)-h*c['human']-r*c['robot']-sigma)
        if cert['optimal']:
            assert cert['solver']['optimal'] and cert['status']=='optimal'
            assert cert['column'] is not None
        if complete is not None:
            candidates = complete[l]
            if cert.get('caps') is not None:
                hc, rc = cert['caps']
                candidates = [c for c in candidates if c['human']<=hc and c['robot']<=rc]
            if cert['status']=='infeasible':
                assert not candidates
            if cert['optimal']:
                assert candidates
                expected = max((c['profit'] if phase==2 else 0)-h*c['human']-r*c['robot']-sigma for c in candidates)
                close(expected, cert['reduced_cost'])
        pricing_checked += 1

    for idx,c in enumerate(result['pricing_audit_calls']):
        assert c['call_index']==idx
        pricing(c)
    init = result['initialization']
    assert len({c['line'] for c in init})==len(init)
    for cert in init:
        pricing(cert)
        if cert['status']=='infeasible':
            infeasible = True
    if len(init)==len(lines) and all(c['optimal'] for c in init):
        bounds.append(sum(c['column']['profit'] for c in init))
    elif result.get('initial_upper_bound_source')=='sum_native_economic_line_MIP_best_bounds':
        assert len(init)==len(lines)
        components=[]
        for cert in init:
            close(cert['human_price'],0); close(cert['robot_price'],0); close(cert['sigma'],0)
            assert cert['phase']==2
            bound=cert['column']['profit'] if cert['optimal'] else cert['solver']['best_bound']
            assert bound is not None and math.isfinite(bound) and abs(bound)<1e19
            assert bound>=cert['column']['profit']-TOL
            if complete is not None:
                assert bound>=max(c['profit'] for c in complete[cert['line']])-TOL
            components.append(bound)
        assert len(components)==len(result['initial_upper_bound_components'])
        for a,b in zip(components,result['initial_upper_bound_components']):close(a,b)
        bounds.append(sum(components))

    def master(cert):
        phase = cert['phase']
        sizes = cert['pool_sizes']
        assert set(sizes)==set(lines)
        for l, size in sizes.items():
            assert 0<size<=len(pool[l])
        if not cert['solver']['has_incumbent']:
            return
        values = {(e['line'],e['column']):e['weight'] for e in cert['solution']}
        assert len(values)==len(cert['solution'])==sum(sizes.values())
        assert set(values)=={(l,p) for l,size in sizes.items() for p in range(size)}
        assert all(math.isfinite(v) and v>=-TOL for v in values.values())
        for l in lines:
            close(sum(v for (li,p),v in values.items() if li==l),1)
        arts = cert['artificials']
        if phase==1:
            assert set(arts)=={'human','robot'} and all(v>=-TOL for v in arts.values())
        else:
            assert not arts
        for resource in ('human','robot'):
            usage = sum(pool[l][p][resource]*v for (l,p),v in values.items())
            assert usage-arts.get(resource,0)<=data[resource+'_limit']+TOL
        obj = -sum(arts.values()) if phase==1 else sum(pool[l][p]['profit']*v for (l,p),v in values.items())
        close(obj,cert['objective'])
        if cert['integer']:
            assert all(abs(v-round(v))<=TOL for v in values.values())
            check_witness(data,cert['witness'],obj)
        elif cert['solver']['optimal']:
            dual = cert['duals']
            assert dual['human']>=-TOL and dual['robot']>=-TOL
            if phase==1:
                assert dual['human']<=1+TOL and dual['robot']<=1+TOL
            dobj = sum(dual['convexity'].values())+sum(data[k+'_limit']*dual[k] for k in ('human','robot'))
            close(dobj,cert['dual_objective']); close(obj,dobj)
            for (l,p) in values:
                c=pool[l][p]
                rc=(c['profit'] if phase==2 else 0)-dual['human']*c['human']-dual['robot']*c['robot']-dual['convexity'][l]
                assert rc<=TOL

    for record in result['history']:
        m = record['rmp']; master(m)
        certs = record['pricing']
        assert len({c['line'] for c in certs})==len(certs)
        for cert in certs:
            pricing(cert,m['duals'],record['phase'])
        if record['complete_certified_pricing']:
            assert {c['line'] for c in certs}==set(lines), 'Missing complete pricing block'
            assert all(c['optimal'] or c.get('bound_certified',False) for c in certs)
            bound=m['dual_objective']+sum(max(0,c['reduced_cost_upper_bound'] if c.get('bound_certified') else c['reduced_cost']) for c in certs)
            close(bound,record['repaired_upper_bound'])
            if record['phase']==2:
                bounds.append(bound)
            elif bound < -result['policy']['artificial_tolerance']:
                infeasible=True
        else:
            assert record['repaired_upper_bound'] is None
        for added in record['added']:
            c=pool[added['line']][added['column']]
            matching=[p for p in certs if p['line']==added['line'] and p['column'] is not None and signature(p['column'])==signature(c)]
            assert matching and matching[0]['reduced_cost']>result['policy']['reduced_cost_epsilon']
    for recovery in result['integer_recovery']:
        master(recovery)
    lb,ub=result['lower_bound'],result['upper_bound']
    if result['witness'] is not None:
        check_witness(data,result['witness'],lb)
        for line in data['lines']:
            chosen=[s for s in result['witness']['stations'] if s['line']==line['id']]
            assert signature(dict(stations=chosen)) in {signature(c) for c in pool[line['id']]}
    else:
        assert lb is None
    if ub is not None:
        assert bounds, 'Upper bound has no complete pricing/independent-line evidence'
        close(ub,min(bounds))
    if lb is not None and ub is not None:
        assert ub>=lb-TOL
        close(ub-lb,result['absolute_gap'])
    if result['global_integer_optimal_proven']:
        assert lb is not None and ub is not None and ub-lb<=max(result['policy']['global_absolute_tolerance'],result['policy']['global_relative_tolerance']*max(1,abs(lb)))+1e-8
    if result['global_infeasibility_proven']:
        assert infeasible and lb is None
    oracle_results={}
    if complete is not None:
        for integer in (False,True):
            full=solve_full(data,complete,integer,solver=solver)
            oracle_results['IP' if integer else 'LP']=full
        ip=oracle_results['IP']; lp=oracle_results['LP']
        if result['lp_optimal_proven']:
            assert lp['optimal']; close(lp['objective'],result['lp_objective'])
        if result['global_integer_optimal_proven']:
            assert ip['optimal']; close(ip['objective'],lb)
        if result['global_infeasibility_proven']:
            assert ip['status']=='infeasible'
        if lb is not None and ip['optimal']:
            assert lb<=ip['objective']+TOL
        if ub is not None and lp['optimal']:
            assert ub>=lp['objective']-TOL
    return dict(status='PASS',scope='complete_independent_enumeration' if complete is not None else 'data_dual_arithmetic_and_native_status_only',
                columns=sum(map(len,pool.values())),pricing_checked=pricing_checked,
                independent_full_models=oracle_results,
                line_pattern_counts=None if complete is None else {l:len(c) for l,c in complete.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('instance', type=Path)
    parser.add_argument('result', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--no-enumeration', action='store_true',
                        help='只复核数据级证据，不独立证明完整定价最优')
    args = parser.parse_args()
    data = json.loads(args.instance.read_text(encoding='utf-8-sig'))
    result = json.loads(zlib.decompress(args.result.read_bytes()).decode('utf-8')) if args.result.suffix=='.zlib' else json.loads(args.result.read_text(encoding='utf-8-sig'))
    verified = audit(data, result, enumerate_pricing=not args.no_enumeration)
    text = json.dumps(verified, ensure_ascii=False, indent=2, allow_nan=False)
    if args.output:
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(text+'\n')
    print(text)


if __name__ == '__main__':
    main()
