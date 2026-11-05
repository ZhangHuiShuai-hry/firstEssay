import json,zlib,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
    base=HERE/'evidence/paired15';rows=json.loads((base/'accounting.json').read_text(encoding='utf-8'))
    table=['|输入|方法|LB|UB|Gap|E2E秒|节点|已证最优|状态|','|---|---|---:|---:|---:|---:|---:|---|---|']
    def fmt(v):return '—' if v is None else f'{v:.4f}'
    for r in rows:table.append('|'+ '|'.join([r['case'],r['method'],fmt(r.get('global_lower_bound')),fmt(r.get('global_upper_bound')),fmt(r.get('absolute_gap')),fmt(r['end_to_end_seconds']),str(r.get('total_nodes_processed')),str(r.get('global_integer_optimal_proven')),r.get('status','missing')])+'|')
    (base/'ALL_RESULTS.md').write_text('\n'.join(table)+'\n',encoding='utf-8')
    profiles=[]
    for path in sorted(base.glob('*/result.json.zlib')):
        r=json.loads(zlib.decompress(path.read_bytes()))
        if r.get('algorithm')=='compact':continue
        nodes=[n['result'] for n in r['node_history'] if n['result']]
        pp=[c for n in nodes for c in n['initialization_fallback']+[c for h in n['history'] for c in h['pricing']]]
        masters=[c for n in nodes for c in [h['rmp'] for h in n['history']]+n['integer_recovery']]
        p=dict(run=path.parent.name,pp_calls=len(pp),columns=sum(sum(map(len,n['pool'].values())) for n in nodes),
            pp_total_seconds=sum(c['total_seconds'] for c in pp),native_seconds=sum(c['solver']['solver_time'] for c in pp),
            master_seconds=sum(c['total_seconds'] for c in masters),algorithm_seconds=r['wall_seconds'],
            mip_starts=sum(bool(c.get('mip_start_submitted')) for c in pp),reused_calls=sum(bool(c.get('reused')) for c in pp))
        p['other_seconds']=p['algorithm_seconds']-p['pp_total_seconds']-p['master_seconds']
        p['native_components']={k:sum(c.get('profile',{}).get(k,0) for c in pp) for k in ('create_seconds','objective_start_update_seconds','pre_solve_seconds','native_seconds','read_seconds','validate_seconds')}
        assert p['other_seconds']>=-1e-5
        profiles.append(p)
    (base/'profiles.json').write_text(json.dumps(profiles,indent=2),encoding='utf-8');print('\n'.join(table))
    micro=json.loads((HERE/'evidence/micro/summary.json').read_text(encoding='utf-8'))
    tab=['|节点|策略|三次序列中位总秒|构造|原生求解|','|---|---|---:|---:|---:|']
    for n in sorted({r['node'] for r in micro}):
        for m in ('rebuild','reuse','warm'):
            rs=[r for r in micro if r['node']==n and r['strategy']==m]
            tab.append('|'+ '|'.join([str(n),m]+[f'{statistics.median(r[k] for r in rs):.6f}' for k in ('total_seconds','create_seconds','native_seconds')])+'|')
    (HERE/'evidence/micro/RESULTS.md').write_text('\n'.join(tab)+'\n',encoding='utf-8')
if __name__=='__main__':main()
