import json,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
    base=HERE/'evidence/paired20';rows=json.loads((base/'accounting.json').read_text(encoding='utf-8'))
    table=['|输入|方法|LB|UB|E2E秒|状态|档调用/总数|','|---|---|---:|---:|---:|---|---|']
    def fmt(x):return 'unknown' if x is None else f'{x:.4f}'
    for r in rows:table.append('|'+ '|'.join([r['case'],r['method'],fmt(r.get('global_lower_bound')),fmt(r.get('global_upper_bound')),fmt(r['end_to_end_seconds']),r.get('status','missing'),f"{r.get('profile_calls','—')}/{r.get('profile_count','—')}"])+'|')
    (base/'ALL_RESULTS.md').write_text('\n'.join(table)+'\n',encoding='utf-8');print('\n'.join(table))
    details=[]
    for p in base.glob('*profiles/result.json.zlib'):
        r=json.loads(zlib.decompress(p.read_bytes()));certs=[e['certificate'] for es in r['table'].values() for e in es if e['certificate']]
        total=sum(c['total_seconds'] for c in certs)
        details.append(dict(run=p.parent.name,calls=r['profile_calls'],total=r['profile_count'],PP_seconds=total,
            PP_native_seconds=sum(c['solver']['solver_time'] for c in certs),DP_verification_other_seconds=r['wall_seconds']-total,
            complete_profiles=r['complete_profiles']))
    (base/'profiles.json').write_text(json.dumps(details,indent=2),encoding='utf-8')
if __name__=='__main__':main()
