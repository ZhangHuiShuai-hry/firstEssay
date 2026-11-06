"""Post-hoc one-step LP/IP response; never a full CG or RL performance claim."""
import argparse,json,zlib,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'sub'))
from validate import solve_full,check_witness
def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    states={s['id']:s for s in json.loads((a.folder/'states.json').read_bytes())};rows=json.loads((a.folder/'results.json').read_bytes())['rows'];out=[]
    for s in states.values():
        src=ROOT/s['source'];original=json.loads((src/'instance.json').read_bytes());cg=json.loads(zlib.decompress((src/'result.json.zlib').read_bytes()))['base_result']['cg'];h=cg['history'][s['history_index']]
        assert s['data']==original and s['rmp']==h['rmp']
        assert s['pool']=={l:cg['pool'][l][:n] for l,n in h['rmp']['pool_sizes'].items()}
    for i,r in enumerate(rows):
        s=states[r['state']];pool=deepcopy(s['pool'])
        for c in r['certificates']:
            col=c['column']
            if col:
                rc=col['profit']-s['current'][0]*col['human']-s['current'][1]*col['robot']-s['rmp']['duals']['convexity'][c['line']]
                if rc>1e-7 and not any(v['stations']==col['stations'] for v in pool[c['line']]):pool[c['line']].append(col)
        lp=solve_full(s['data'],pool);ip=solve_full(s['data'],pool,integer=True);assert lp['optimal'] and lp['objective']>=s['rmp']['objective']-1e-5
        witness=None
        if ip['optimal']:
            stations=[v for x in ip['positive'] for v in pool[x['line']][x['index']]['stations']];witness=dict(stations=stations,objective=ip['objective']);check_witness(s['data'],witness,ip['objective'])
        out.append(dict(state=r['state'],alpha=r['alpha'],repeat=r['repeat'],baseline_rmp=s['rmp']['objective'],rmp_improvement=lp['objective']-s['rmp']['objective'],lp=lp,restricted_ip=ip,witness=witness,action_seconds=r['total_seconds']))
    with (a.output/'results.json').open('x',encoding='utf-8') as f:json.dump(dict(status='PASS',rows=out,scope='source-state prefix integrity and independent one-step restricted LP/IP; posthoc compute outside probe budget'),f,indent=2)
    print('PASS',len(out),'one-step LP/IP responses and source-state integrity')
if __name__=='__main__':main()
