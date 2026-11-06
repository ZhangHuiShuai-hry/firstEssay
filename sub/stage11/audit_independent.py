"""Independent arithmetic and tiny enumeration audit of the existing line baseline."""
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate import check_column,check_witness,enumerate_all

def audit(data,r,enumerate_profiles=False):
    lines={l['id']:l for l in data['lines']};init=r['initialization']
    assert len({c['line'] for c in init})==len(init)
    full=enumerate_all(data) if enumerate_profiles else None
    for c in init:
        assert c['line'] in lines and c['phase']==2 and c['caps'] is None
        assert c['human_price']==c['robot_price']==c['sigma']==0
        assert c['optimal']==c['solver']['optimal']
        if c['column']:
            val=check_column(lines[c['line']],c['column'])
            assert abs(val['profit']-c['reduced_cost'])<=1e-5
            assert abs(val['profit']-c['solver']['objective'])<=1e-5
        if c['optimal']:
            assert c['column'] and c['solver']['native_status']==101
        if full is not None:
            cols=full[c['line']]
            if c['status']=='infeasible':assert not cols
            if c['optimal']:assert abs(c['column']['profit']-max(v['profit'] for v in cols))<1e-5
        b=c['solver'].get('best_bound')
        if b is not None:
            assert math.isfinite(b)
            if c['column']:assert b>=c['column']['profit']-1e-5
            if full is not None and full[c['line']]:assert b>=max(v['profit'] for v in full[c['line']])-1e-5
    complete=len(init)==len(lines) and all(c['column'] for c in init)
    expected=None
    if complete:
        bs=[c['column']['profit'] if c['optimal'] else c['solver'].get('best_bound') for c in init]
        if all(b is not None and math.isfinite(b) for b in bs):expected=sum(bs)
    assert r['global_upper_bound']==expected
    cols=[c['column'] for c in init] if complete else []
    compatible=bool(complete and sum(c['human'] for c in cols)<=data['human_limit'] and sum(c['robot'] for c in cols)<=data['robot_limit'])
    lb=r['global_lower_bound']
    if r['witness']:
        assert compatible;check_witness(data,r['witness'],lb)
        assert abs(lb-sum(c['profit'] for c in cols))<1e-5
    else:assert lb is None
    if complete and not compatible:
        assert r['status']=='resource_incompatible_unresolved' and not r['global_infeasibility_proven']
    if r['global_integer_optimal_proven']:
        assert r['witness'] and expected is not None and expected-lb<=1e-5
    if r['global_infeasibility_proven']:
        assert any(c['status']=='infeasible' and c['solver']['native_status']==103 for c in init)
    return dict(status='PASS',scope='independent_arithmetic_and_native_bounds',locally_complete=bool(complete),compatible=compatible)
