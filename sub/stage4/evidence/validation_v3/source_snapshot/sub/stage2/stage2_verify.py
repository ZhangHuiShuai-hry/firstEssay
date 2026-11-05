"""沿用独立算术Oracle，额外核验fallback及非正RC资源补列，兼容V3证书。"""
from pathlib import Path
import sys,math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate import TOL,close,enumerate_all,check_column,signature,check_witness,solve_full
def audit(data, result, *, enumerate_pricing=True, solver='cplex_py'):
    """小规模完全重放；大规模仅核算数据/对偶，明确依赖原生最优状态。"""
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
            if cert['column'] is not None:assert bound>=cert['column']['profit']-TOL
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
        if record['complete_exact_pricing']:
            assert {c['line'] for c in certs}==set(lines), 'Missing complete pricing block'
            assert all(c['optimal'] for c in certs)
            bound=m['dual_objective']+sum(max(0,c['reduced_cost']) for c in certs)
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
    for cert in result.get('initialization_fallback',[]):
        assert cert['purpose']=='initial_feasibility' and cert['phase']==1
        pricing(cert)
        if cert['status']=='infeasible':infeasible=True
    for event in result.get('quota_repair',[]):
        if 'initial_lp' in event:master(event['initial_lp'])
        for cert in event.get('pricing',[]):
            assert cert['purpose']=='integer_quota_repair' and cert['phase']==2
            assert cert['caps'] is not None
            if cert['column']:
                assert cert['column']['human']<=cert['caps'][0] and cert['column']['robot']<=cert['caps'][1]
            pricing(cert)
        if event.get('restricted_IP'):master(event['restricted_IP'])
        if event.get('witness'):check_witness(data,event['witness'],event['lower_bound'])
        for added in event['added']:
            c=pool[added['line']][added['column']]
            assert added['column']>=event['before_sizes'][added['line']]
            assert any(p['column'] is not None and p['line']==added['line'] and signature(p['column'])==signature(c) for p in event.get('pricing',[]))
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

