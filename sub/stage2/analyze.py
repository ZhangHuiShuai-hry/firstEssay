import json,zlib
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent
    rows=json.loads((root/'evidence/paired30/accounting.json').read_text(encoding='utf-8'))
    profiles=[];text=['# 全部五组消融结果','','首次LB秒数是run()算法时钟；总秒为父进程E2E。Compact首次发现时间未知。','',
        '|实例|方法|LB|UB|首次验证LB秒|E2E秒|已证整数最优|预算内|','|---|---|---:|---:|---:|---:|---|---|']
    def fmt(v):return '—' if v is None else f'{v:.4f}'
    for row in rows:
        folder=root/'evidence/paired30'/(row['case']+'__'+row['method'])
        r=json.loads(zlib.decompress((folder/'result.json.zlib').read_bytes()))
        text.append('|'+ '|'.join([row['case'],row['method'],fmt(row['global_lower_bound']),fmt(row['global_upper_bound']),fmt(row['first_integer_seconds']),fmt(row['end_to_end_seconds']),str(row['global_integer_optimal_proven']),str(row['timely'])])+'|')
        if row['method']!='compact':
            init=r['initialization']+r.get('initialization_fallback',[])
            pp=[p for h in r['history'] for p in h['pricing']]
            quota=r.get('quota_repair',[])
            profiles.append(dict(case=row['case'],method=row['method'],status=r['status'],termination=r['termination_reason'],
                initial_native=sum(e['solver'].get('solver_time',0) or 0 for e in init),
                exact_pricing_native=sum(e['solver'].get('solver_time',0) or 0 for e in pp),
                quota_attempts=len(quota),quota_calls=sum(len(e.get('pricing',[])) for e in quota),
                quota_added=sum(len(e['added']) for e in quota),quota_seconds=sum(e.get('seconds',0) for e in quota),
                total_pricing_calls=len(init)+len(pp)+sum(len(e.get('pricing',[])) for e in quota),
                complete_pricing_rounds=sum(h['complete_exact_pricing'] for h in r['history']),
                columns=r['columns'],first_integer_seconds=r['first_integer_seconds'],algorithm_seconds=r['wall_seconds']))
    out=root/'evidence/analysis';out.mkdir(exist_ok=False)
    (out/'ALL_RESULTS.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    (out/'profiles.json').write_text(json.dumps(profiles,indent=2),encoding='utf-8')
    print(json.dumps(dict(runs=len(rows),timely=sum(r['timely'] for r in rows),
                         quota_triggered=sum(p['quota_attempts']>0 for p in profiles))))

if __name__=='__main__':main()
