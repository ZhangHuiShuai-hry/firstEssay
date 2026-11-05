"""独立算术重建经济界，不调用生产derive/refine；微例枚举核验每个界。"""
import math,sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'stage7'),str(Path(__file__).resolve().parents[1]/'stage2')]
from verify7 import audit as base_audit
from validate import enumerate_all,check_witness

def audit(data,r,enumerate_profiles=False):
    b=r['base_result'];checks=base_audit(data,b,enumerate_profiles=enumerate_profiles);cg=b['cg'];expected=[];best={l['id']:None for l in data['lines']}
    full=enumerate_all(data) if enumerate_profiles else None
    def check(path,c):
        s=c['solver'];bound=s.get('best_bound')
        if c['phase']!=2 or c['human_price']!=0 or c['robot_price']!=0 or c.get('caps') is not None:return
        if s.get('backend')!='cplex_py' or s.get('native_status') not in (101,102,107,108):return
        if bound is None or not math.isfinite(bound) or abs(bound)>=1e19:return
        value=bound+c['sigma'];lid=c['line']
        if c['column']:assert value>=c['column']['profit']-1e-5
        if full is not None:assert value>=max(col['profit'] for col in full[lid])-1e-5
        expected.append(dict(path=path,line=lid,economic_upper_bound=value));best[lid]=value if best[lid] is None else min(best[lid],value)
    for n,c in enumerate(cg['initialization']):check(f'initialization/{n}',c)
    for n,h in enumerate(cg['history']):
        for j,c in enumerate(h['pricing']):check(f'history/{n}/pricing/{j}',c)
    assert r['economic_evidence']['records']==expected
    assert r['economic_evidence']['line_upper_bounds']==best
    value=sum(best.values()) if all(v is not None for v in best.values()) else None
    assert r['economic_evidence']['upper_bound']==value
    bounds=[v for v in (value,b['global_upper_bound']) if v is not None];ub=min(bounds) if bounds else None
    assert r['global_upper_bound']==ub and r['global_lower_bound']==b['global_lower_bound']
    assert r['witness']==b['witness'] and r['global_infeasibility_proven']==b['global_infeasibility_proven']
    lb=r['global_lower_bound'];p=b['policy'];closed=lb is not None and ub is not None and ub-lb<=max(p['global_absolute_tolerance'],p['global_relative_tolerance']*max(1,abs(lb)))
    assert r['global_integer_optimal_proven']==bool(b['global_integer_optimal_proven'] or closed)
    if lb is not None:check_witness(data,r['witness'],lb);assert ub is None or ub>=lb-1e-5
    if closed:assert r['status']=='optimal_within_tolerance'
    return dict(status='PASS',scope=checks['scope'],economic_records=len(expected))
