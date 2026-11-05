import json,statistics,zlib,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def main():
    base=Path(sys.argv[1]) if len(sys.argv)>1 else HERE/'evidence/paired30'
    rows=json.loads((base/'accounting.json').read_text(encoding='utf-8'))
    profiles=[]
    text=['|运行|方法|LB|UB|Gap|首次验证秒（算法）|E2E秒|已证最优|状态|',
          '|---|---|---:|---:|---:|---:|---:|---|---|']
    def fmt(x):return '—' if x is None else f'{x:.4f}'
    for s in rows:
        text.append('|'+ '|'.join([s['case'],s['method'],fmt(s.get('global_lower_bound')),fmt(s.get('global_upper_bound')),
                    fmt(s.get('absolute_gap')),fmt(s.get('first_integer_seconds')),fmt(s['end_to_end_seconds']),
                    str(s.get('global_integer_optimal_proven')),str(s.get('status'))])+'|')
        # accounting case字段不含重复编号，从实际目录按worker method/summary匹配。
    for path in sorted(base.glob('*/result.json.zlib')):
        r=json.loads(zlib.decompress(path.read_bytes()))
        if r.get('algorithm')=='compact':continue
        pp=r['initialization']+r['initialization_fallback']+[c for h in r['history'] for c in h['pricing']]
        masters=[h['rmp'] for h in r['history']]+r['integer_recovery']
        p=dict(run=path.parent.name,pricing_calls=len(pp),columns=r['columns'],
            init_seconds=sum(c['total_seconds'] for c in pp if c['purpose']=='initialization'),
            exact_pricing_seconds=sum(c['total_seconds'] for c in pp if c['purpose']=='pricing'),
            pp_seconds=sum(c['total_seconds'] for c in pp),pp_native_seconds=sum(c['solver']['solver_time'] for c in pp),
            master_seconds=sum(c['total_seconds'] for c in masters),algorithm_seconds=r['wall_seconds'],
            objective_updates=r['incumbent_history'],rounds=len(r['history']))
        p['other_seconds']=p['algorithm_seconds']-p['pp_seconds']-p['master_seconds']
        p['pp_components']={k:sum(c['profile'][k] for c in pp if 'profile' in c)
                            for k in ('create_seconds','objective_start_update_seconds','pre_solve_seconds','native_seconds','read_seconds','validate_seconds')}
        assert p['other_seconds']>=-1e-5
        profiles.append(p)
    (base/'ALL_RESULTS.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    (base/'profiles.json').write_text(json.dumps(profiles,indent=2),encoding='utf-8')
    print('\n'.join(text))

if __name__=='__main__':main()
