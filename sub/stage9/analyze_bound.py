import argparse,json,zlib
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();rows=json.loads((a.directory/'accounting.json').read_bytes())
    lines=['|实例|方法|LB|UB|绝对Gap|相对Gap|E2E秒|状态|及时|','|---|---|---:|---:|---:|---:|---:|---|---|'];details=[]
    def f(v):return 'unknown' if v is None else f'{v:.5f}'
    for s in rows:
        folder=a.directory/(s['case']+'__'+s['method']);r=json.loads(zlib.decompress((folder/'result.json.zlib').read_bytes()))
        lines.append('|'+ '|'.join([s['case'],s['method'],f(r['global_lower_bound']),f(r['global_upper_bound']),f(r['absolute_gap']),f(r.get('relative_gap')),f(s['end_to_end_seconds']),r['status'],str(s['timely'])])+'|')
        d=dict(case=s['case'],method=s['method'],end_to_end_seconds=s['end_to_end_seconds'],persistence_seconds=s['persistence_seconds'])
        if 'base_result' in r:
            b=r['base_result'];d.update(base_upper_bound=b['global_upper_bound'],refined_upper_bound=r['global_upper_bound'],economic_evidence=r['economic_evidence'],cg_seconds=b['cg']['wall_seconds'],cg_timing=b['cg']['timing'],cg_status=b['cg']['status'],profile_calls=b['profile_calls'],query_seconds=sum(q['certificate']['total_seconds'] for q in b['queries'] if q['certificate']))
        details.append(d)
    (a.directory/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');(a.directory/'profiles.json').write_text(json.dumps(details,indent=2),encoding='utf-8');print('\n'.join(lines))

if __name__=='__main__':main()
