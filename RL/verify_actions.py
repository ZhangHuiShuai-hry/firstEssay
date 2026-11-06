"""Independent arithmetic replay of action evidence, no optimization calls."""
import argparse,hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'sub'))
from validate import check_column
def verify(folder):
    for name,h in json.loads((folder/'sources.json').read_bytes()).items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    states={s['id']:s for s in json.loads((folder/'states.json').read_bytes())};rows=json.loads((folder/'results.json').read_bytes())['rows'];assert len(rows)==40
    assert {(r['state'],r['repeat'],r['alpha']) for r in rows}=={(s,k,a) for s in states for k in (0,1) for a in (1.,.75,.5,.25)}
    for s in states.values():assert hashlib.sha256((ROOT/s['source']/'result.json.zlib').read_bytes()).hexdigest()==s['source_sha256']
    for r in rows:
        s=states[r['state']];p=[r['alpha']*c+(1-r['alpha'])*h for c,h in zip(s['current'],s['reference'])];assert r['prices']==p and all(math.isfinite(v) and v>=0 for v in p)
        cs=r['certificates'];lines={l['id']:l for l in s['data']['lines']};assert len(cs)==len(lines) and {c['line'] for c in cs}==set(lines);q=[];positive=0
        for c in cs:
            assert c['phase']==2 and c['caps'] is None and c['sigma']==0 and [c['human_price'],c['robot_price']]==p
            if c['column']:
                col=c['column'];v=check_column(lines[c['line']],col);val=v['profit']-p[0]*col['human']-p[1]*col['robot'];assert abs(val-c['reduced_cost'])<=1e-5 and abs(val-c['solver']['objective'])<=1e-5
                assert c['solver']['best_bound'] is None or val<=c['solver']['best_bound']+1e-5
                raw=v['profit']-s['current'][0]*col['human']-s['current'][1]*col['robot']-s['rmp']['duals']['convexity'][c['line']]
                if raw>1e-7 and not any(v['stations']==col['stations'] for v in s['pool'][c['line']]):positive+=1
            if c['optimal']:
                assert c['column'] and c['solver']['native_status']==101 and abs(c['solver']['best_bound']-val)<=1e-5;q.append(val)
        complete=all(c['optimal'] for c in cs);assert r['complete_exact']==complete and r['proven_blocks']==len(q) and r['new_positive_columns']==positive
        expected=p[0]*s['data']['human_limit']+p[1]*s['data']['robot_limit']+sum(q) if complete else None
        if expected is None:assert r['exact_lp_upper_bound'] is None
        else:assert abs(r['exact_lp_upper_bound']-expected)<=1e-5 and expected>=s['rmp']['objective']-1e-5
        assert not r['global_integer_optimal_proven']
    return dict(status='PASS',trials=len(rows),states=len(states),scope='source/coverage/local arithmetic/RC/exact-only Lagrangian bounds; native optimality trust boundary')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=verify(a.folder)
    with a.output.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
    print(r)
