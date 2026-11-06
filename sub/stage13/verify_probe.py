"""Offline arithmetic replay plus independent audits of saved reference certificates."""
import argparse,hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE.parent/'stage11'),str(HERE.parent)]
from run_plan_v2 import audit
from validate import check_column
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    folder=HERE/'evidence/probe';snaps=json.loads((folder/'snapshots.json').read_bytes());rows=json.loads((folder/'results.json').read_bytes())['rows'];checks=[]
    for s in snaps:
        source=ROOT/s['source'];assert hashlib.sha256((source/'result.json.zlib').read_bytes()).hexdigest()==s['source_sha256']
        checks.append(audit(source));sr=s['certificate'];vals=[]
        for r in [v for v in rows if v['seed']==s['seed']]:
            c=r['certificate'];assert all(c[k]==sr[k] for k in ('line','phase','human_price','robot_price','sigma','caps'))
            assert c['phase']==2 and c['caps'] is None
            if c['column']:
                v=check_column(s['line'],c['column']);expected=v['profit']-c['human_price']*c['column']['human']-c['robot_price']*c['column']['robot']-c['sigma']
                assert abs(expected-c['reduced_cost'])<=1e-5
            inc=c['reduced_cost'];bound=c['solver']['best_bound'];assert inc==r['incumbent'] and bound==r['best_bound']
            if inc is not None and bound is not None:assert inc<=bound+1e-5
            if c['optimal']:assert c['solver']['native_status']==101 and inc is not None
            known=sr['reduced_cost'] if sr['optimal'] else None;assert known==r['known_optimum']
            if known is not None:
                if inc is not None:assert inc<=known+1e-5
                if bound is not None:assert bound>=known-1e-5
                if c['optimal']:assert abs(inc-known)<=1e-5
            assert r['at_known_optimum_but_unproven']==bool(known is not None and inc is not None and abs(known-inc)<=1e-5 and not c['optimal'])
            vals.append((inc,bound))
        assert len(vals)==6
        for inc,_ in vals:
            for _,bound in vals:
                if inc is not None and bound is not None:assert inc<=bound+1e-5
    result=dict(status='PASS',trials=len(rows),reference_replays=checks,scope='saved original certificate replay, independent local arithmetic/RC and cross-variant/native bounds')
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print('PASS',len(rows),'probe trials and',len(checks),'reference replays')
if __name__=='__main__':main()
