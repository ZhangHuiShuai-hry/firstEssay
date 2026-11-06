"""Independent checks of candidate prices, raw RC, causal references and fallback."""
import math

def check(data,result):
    history=result['history'];calls=result['pricing_audit_calls'];streak=0;rounds=0;spent=0.
    for idx,h in enumerate(history):
        cs=h.get('candidate_pricing',[]);action=h.get('candidate_action');added=h.get('candidate_added',[])
        if action is not None:
            assert h['phase']==2 and streak==0 and result['policy_name']!='exact'
            expected_alpha=1. if result['policy_name']=='short_raw' or (result['policy_name']=='adaptive' and rounds>0) else .25
            assert action['alpha']==expected_alpha and action['candidate_round']==rounds;rounds+=1
            prev=[(i,v) for i,v in enumerate(history[:idx]) if v['phase']==2 and v['complete_certified_pricing'] and v['repaired_upper_bound'] is not None]
            chosen=min(prev,key=lambda x:x[1]['repaired_upper_bound']) if prev else None
            ref=[chosen[1]['rmp']['duals'][k] for k in ('human','robot')] if chosen else [0.,0.]
            assert action['reference_history_index']==(chosen[0] if chosen else None) and action['reference']==ref
            current=[h['rmp']['duals'][k] for k in ('human','robot')];assert action['current']==current
            p=[expected_alpha*x+(1-expected_alpha)*y for x,y in zip(current,ref)]
            assert action['price']==p and all(math.isfinite(v) and v>=0 for v in p)
            assert action['budget_before']==spent and action['budget_after']>=spent;spent=action['budget_after']
            assert len({c['line'] for c in cs})==len(cs)
            for c in cs:
                assert c==calls[c['call_index']] and c['phase']==2 and c['caps'] is None
                assert [c['human_price'],c['robot_price']]==p and c['sigma']==0 and c['purpose']=='candidate' and not c.get('bound_certified')
            for a in added:
                c=next(c for c in cs if c['call_index']==a['call_index']);col=c['column'];assert col is not None and col['line']==a['line']
                assert result['pool'][a['line']][a['column']]==col
                rc=col['profit']-current[0]*col['human']-current[1]*col['robot']-h['rmp']['duals']['convexity'][col['line']]
                assert abs(rc-a['raw_reduced_cost'])<1e-7 and rc>1e-7
                assert a['column']>=h['rmp']['pool_sizes'][a['line']]
        else:assert not cs and not added
        if h.get('candidate_only'):
            assert added and not h['pricing'] and not h['complete_certified_pricing'] and h['repaired_upper_bound'] is None
            streak=1
        elif h['pricing']:
            # On a failed candidate round or following a successful candidate round,
            # raw-price certification is actually attempted, never inferred from failure.
            streak=0
        if action is not None and not added:assert h['pricing'] or result['status'] in ('time_limit','solver_error','numerical_uncertain')
    assert abs(spent-result['candidate_seconds'])<1e-6 or result['status'] in ('time_limit','solver_error','numerical_uncertain')
