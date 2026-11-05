import json,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
    b=HERE/'evidence/paired20';rs=json.loads((b/'accounting.json').read_text(encoding='utf-8'))
    lines=['|输入|方法|LB|UB|E2E秒|查询数|状态|','|---|---|---:|---:|---:|---:|---|']
    def fmt(v):return 'unknown' if v is None else f'{v:.4f}'
    for r in rs:lines.append('|'+ '|'.join([r['case'],r['method'],fmt(r.get('global_lower_bound')),fmt(r.get('global_upper_bound')),fmt(r['end_to_end_seconds']),str(r.get('profile_calls')),r.get('status','missing')])+'|')
    (b/'ALL_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print('\n'.join(lines))
    stats=[]
    for p in b.glob('*demand/result.json.zlib'):
        r=json.loads(zlib.decompress(p.read_bytes()))
        stats.append(dict(run=p.parent.name,cg_seconds=r['cg']['wall_seconds'],profile_calls=r['profile_calls'],queried_profiles=r['queried_profiles'],total_profiles=r['profile_count'],query_seconds=sum(q['certificate']['total_seconds'] for q in r['queries'] if q['certificate']),algorithm_seconds=r['wall_seconds']))
    (b/'profiles.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
if __name__=='__main__':main()
