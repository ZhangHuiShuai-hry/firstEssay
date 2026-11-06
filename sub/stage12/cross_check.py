"""Post-run same-input cross-model and proof-closure checks; no solver calls."""
import argparse
import json
from pathlib import Path
import zlib

HERE=Path(__file__).resolve().parent


def check(root):
    rows=json.loads((root/'analysis/rows.json').read_bytes())
    checks=[]
    for case in sorted({r['case'] for r in rows if r['batch']=='formal600'}):
        rs=[r for r in rows if r['batch']=='formal600' and r['case']==case]
        assert len(rs)==2
        loaded={r['method']:json.loads(zlib.decompress((root/'formal600'/(case+'__'+r['method'])/'result.json.zlib').read_bytes())) for r in rs}
        raw=[(root/'formal600'/(case+'__'+r['method'])/'instance.json').read_bytes() for r in rs]
        assert raw[0]==raw[1]
        for a in rs:
            for b in rs:
                if a['lb'] is not None and b['ub'] is not None:
                    assert a['lb']<=b['ub']+1e-5,(case,a,b)
        d=loaded['balanced_bound'];c=d['base_result']['cg'];data=json.loads(raw[0]);hist=c['history']
        assert all(h['rmp']['solver']['optimal'] for h in hist)
        priced=[h for h in hist if h['pricing']]
        assert all(h['complete_exact_pricing'] and len(h['pricing'])==len(data['lines'])
                   and all(p['optimal'] for p in h['pricing']) for h in priced)
        switches=[h for h in hist if h['phase_transition']]
        assert switches and all(sum(h['rmp']['artificials'].values())<=1e-7 for h in switches)
        assert d['global_integer_optimal_proven']
        assert abs(d['global_upper_bound']-d['witness']['objective'])<=1e-5
        assert abs(c['lp_objective']-d['global_lower_bound'])<=1e-5
        used=d['witness']['resources_used']
        assert used['humans']<=data['human_limit'] and used['robots']<=data['robot_limit']
        checks.append(dict(case=case,status='PASS',identical_input_bytes=True,bounds_cross_consistent=True,
                           all_pricing_rounds_exact=True,phase1_zero_on_transition=True,last_rmp_lp=c['lp_objective'],
                           verified_integer=d['global_lower_bound'],repaired_upper_bound=c['upper_bound'],
                           root_lp_explicit_stop_flag=c['lp_optimal_proven'],termination=c['termination_reason'],
                           profile_calls=d['profile_calls']))
    return dict(status='PASS',cases=checks,
                scope='same-input cross-method bounds plus exact-pricing/phase-transition/closure checks; independent replay recorded separately')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=check(HERE/'evidence')
    with a.output.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
    print('PASS',len(r['cases']),'cross-model cases')
