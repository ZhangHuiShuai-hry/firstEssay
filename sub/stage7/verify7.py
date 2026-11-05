"""独立核对CG来源、逐查询资源档、乐观路径及整数主问题界。"""
import sys,math
from pathlib import Path
from copy import deepcopy
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/'stage2'),str(HERE.parent)]
from stage2_verify import audit as cg_audit
from validate import enumerate_all,solve_full,check_column,check_witness,close

def audit(data,r,enumerate_profiles=True):
    cg=r['cg'];cg_audit(data,cg,enumerate_pricing=enumerate_profiles)
    full=enumerate_all(data) if enumerate_profiles else None
    sources={l['id']:[] for l in data['lines']}
    for c in cg['initialization']:
        b=c['column']['profit'] if c['optimal'] else c['solver'].get('best_bound')
        if b is not None and math.isfinite(b) and abs(b)<1e19:sources[c['line']].append(dict(kind='economic_initialization',constant=b,human=0.,robot=0.))
    for h in cg['history']:
        if h['phase']!=2 or not h['complete_exact_pricing']:continue
        d=h['rmp']['duals']
        for c in h['pricing']:sources[c['line']].append(dict(kind='complete_phase2_pricing',iteration=h['iteration'],constant=d['convexity'][c['line']]+max(0,c['reduced_cost']),human=d['human'],robot=d['robot']))
    assert sources==r['bound_sources']
    table={}
    for l in data['lines']:
        rows=[];lid=l['id']
        for h in range(min(len(l['stations']),data['human_limit'])+1):
            for robot in range(min(len(l['stations']),data['robot_limit'])+1):
                candidates=[c for c in cg['pool'][lid] if c['human']==h and c['robot']==robot]
                col=deepcopy(max(candidates,key=lambda c:c['profit'])) if candidates else None
                bs=[s['constant']+s['human']*h+s['robot']*robot for s in sources[lid]]
                rows.append(dict(human=h,robot=robot,status='seeded' if col else 'not_run',upper_bound=min(bs) if bs else None,column=col,attempts=0))
        table[lid]=rows
    def upper_ip():
        pool={l:[dict(human=e['human'],robot=e['robot'],profit=e['upper_bound'] or 0) for e in es if e['status']!='infeasible'] for l,es in table.items()}
        unknown={l:[dict(human=e['human'],robot=e['robot'],profit=int(e['upper_bound'] is None)) for e in es if e['status']!='infeasible'] for l,es in table.items()}
        u=solve_full(data,unknown,True)
        if u['status']=='infeasible':return False,None
        return True,None if u['objective']>.5 else solve_full(data,pool,True)['objective']
    for q in r['queries']:
        possible,bound=upper_ip();assert possible
        if bound is None:assert q['upper_value'] is None
        else:close(bound,q['upper_value'])
        path=q['upper_path'];assert len(path)==len(data['lines']) and {x['line'] for x in path}==set(table)
        es=[table[x['line']][x['index']] for x in path]
        assert all(e['status']!='infeasible' for e in es)
        assert sum(e['human'] for e in es)<=data['human_limit'] and sum(e['robot'] for e in es)<=data['robot_limit']
        if bound is not None:close(sum(e['upper_bound'] for e in es),bound)
        choice=q['choice'];assert choice in path;e=table[choice['line']][choice['index']]
        assert e['status'] not in ('optimal','infeasible')
        c=q['certificate']
        if c is None:continue
        assert c['line']==choice['line'] and c['profile']==[e['human'],e['robot']] and c['phase']==2
        assert c['human_price']==c['robot_price']==c['sigma']==0 and c['restrictions']==[]
        col=c['column']
        if col:
            check_column(next(l for l in data['lines'] if l['id']==c['line']),col)
            assert col['human']==e['human'] and col['robot']==e['robot'];close(c['reduced_cost'],col['profit'])
        candidates=None if full is None else [p for p in full[c['line']] if p['human']==e['human'] and p['robot']==e['robot']]
        if c['optimal']:
            assert c['solver']['optimal'] and col
            if candidates is not None:assert candidates;close(col['profit'],max(p['profit'] for p in candidates))
        if c['status']=='infeasible':
            assert e['column'] is None
            if candidates is not None:assert not candidates
            e.update(status='infeasible',upper_bound=None)
        else:
            if col and (e['column'] is None or col['profit']>e['column']['profit']):e['column']=col
            b=col['profit'] if c['optimal'] else c['solver'].get('best_bound')
            if b is not None and math.isfinite(b) and abs(b)<1e19:
                if candidates:assert b>=max(p['profit'] for p in candidates)-1e-5
                e['upper_bound']=b if e['upper_bound'] is None else min(b,e['upper_bound'])
            e['status']=c['status']
        e['attempts']+=1
    assert table==r['table']
    low={l:[e['column'] for e in es if e['column']] for l,es in table.items()}
    lp=solve_full(data,low,True);possible,ub=upper_ip()
    assert r['upper_dp']['feasible']==possible
    if ub is None:assert r['upper_dp']['value'] is None
    else:close(ub,r['upper_dp']['value'])
    if cg['upper_bound'] is not None:ub=cg['upper_bound'] if ub is None else min(ub,cg['upper_bound'])
    if ub is None:assert r['global_upper_bound'] is None
    else:close(ub,r['global_upper_bound'])
    if lp['optimal']:close(lp['objective'],r['global_lower_bound']);check_witness(data,r['witness'],lp['objective'])
    else:assert r['global_lower_bound'] is None and r['witness'] is None
    if r['global_integer_optimal_proven']:
        assert lp['optimal'] and ub is not None and ub-lp['objective']<=max(r['policy']['global_absolute_tolerance'],r['policy']['global_relative_tolerance']*max(1,abs(lp['objective'])))+1e-8
    if r['global_infeasibility_proven']:assert cg['global_infeasibility_proven'] or not possible
    return dict(status='PASS',scope='complete_enum_and_independent_IP' if full else 'native_bound_and_independent_IP',queries=len(r['queries']))
