import argparse,json,zlib
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
    rows=json.loads((a.directory/'accounting.json').read_bytes());lines=['|实例|方法|LB|UB|Gap|E2E秒|状态|及时落盘|','|---|---|---:|---:|---:|---:|---|---|'];details=[]
    def f(x):return 'unknown' if x is None else f'{x:.4f}'
    for s in rows:
        lines.append('|'+ '|'.join([s['case'],s['method'],f(s.get('global_lower_bound')),f(s.get('global_upper_bound')),f(s.get('absolute_gap')),f(s['end_to_end_seconds']),s.get('status','missing'),str(s['timely'])])+'|')
        folder=a.directory/(s['case']+'__'+s['method']);r=json.loads(zlib.decompress((folder/'result.json.zlib').read_bytes()))
        d=dict(case=s['case'],method=s['method'],progress_events=len(r['progress_trace']),snapshots=[])
        for t in (10,30,60,120):
            seen=[e for e in r['progress_trace'] if e['seconds']<=t]
            lbs=[e['lower_bound'] for e in seen if e['lower_bound'] is not None];ubs=[e['upper_bound'] for e in seen if e['upper_bound'] is not None]
            d['snapshots'].append(dict(at_seconds=t,observed_lower_bound=max(lbs) if lbs else None,observed_upper_bound=min(ubs) if ubs else None,last_observation_seconds=seen[-1]['seconds'] if seen else None))
        if s['method']=='cg':d.update(timing=r['timing'],iterations=len(r['history']),lp_optimal=r['lp_optimal_proven'],termination=r['termination_reason'])
        elif s['method']=='demand':d.update(cg_seconds=r['cg']['wall_seconds'],cg_lp_optimal=r['cg']['lp_optimal_proven'],query_seconds=sum(q['certificate']['total_seconds'] for q in r['queries'] if q['certificate']),queries=r['profile_calls'],incumbents=r['incumbent_history'])
        details.append(d)
    (a.directory/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');(a.directory/'profiles.json').write_text(json.dumps(details,indent=2),encoding='utf-8');print('\n'.join(lines))

if __name__=='__main__':main()
