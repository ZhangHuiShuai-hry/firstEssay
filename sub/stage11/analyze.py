"""Post-run tables and attribution; never passes reference optima to solvers."""
import argparse,json,zlib
from pathlib import Path

HERE=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    allrows=[];refs={};details=[]
    for batch in ('pilot120','confirm600'):
        root=HERE/'evidence'/batch
        for s in json.loads((root/'accounting.json').read_bytes()):
            folder=root/(s['case']+'__'+s['method']);r=json.loads(zlib.decompress((folder/'result.json.zlib').read_bytes()));d=json.loads((folder/'instance.json').read_bytes())
            lb,ub=r['global_lower_bound'],r['global_upper_bound'];gap=None if lb is None or ub is None else max(0,ub-lb)/max(1,abs(lb))
            row=dict(batch=batch,case=s['case'],method=s['method'],lb=lb,ub=ub,relative_gap=gap,
                     seconds=s['end_to_end_seconds'],proven=r['global_integer_optimal_proven'],status=r['status'],timely=s['timely'])
            allrows.append(row)
            if row['proven']:
                if s['case'] in refs:assert abs(refs[s['case']]-lb)<1e-5
                refs[s['case']]=lb
            detail=dict(row,lines=len(d['lines']),tasks_per_line=[len(l['tasks']) for l in d['lines']],
                 stations_per_line=[len(l['stations']) for l in d['lines']],edges=sum(len(l['precedence']) for l in d['lines']),
                 required=sum(len(l['required_tasks']) for l in d['lines']),recovery_total=sum(l['min_recovery'] for l in d['lines']),
                 capacity=[d['human_limit'],d['robot_limit']],resources=r['witness']['resources_used'] if r['witness'] else None,
                 evidence_bytes=s['evidence_bytes'],persistence_seconds=s['persistence_seconds'])
            if 'base_result' in r:
                b=r['base_result'];c=b['cg'];hist=c['history']
                detail.update(cg_seconds=c['wall_seconds'],timing=c['timing'],
                     init_calls=len(c['initialization']),rmp_calls=len(hist),
                     phase1_pricing_rounds=sum(bool(h['pricing']) for h in hist if h['phase']==1),
                     phase2_pricing_rounds=sum(bool(h['pricing']) for h in hist if h['phase']==2),
                     complete_rounds=sum(h['complete_exact_pricing'] for h in hist),
                     pp_calls=len(c['initialization'])+sum(len(h['pricing']) for h in hist),
                     final_columns=sum(len(v) for v in c['pool'].values()),profile_calls=len(b['queries']),
                     phase1_artificials=[h['rmp']['artificials'] for h in hist if h['phase']==1],
                     resource_prices=[dict(human=h['rmp']['duals']['human'],robot=h['rmp']['duals']['robot']) for h in hist if h['phase']==2 and h['rmp']['duals']],
                     phase2_complete=[h['complete_exact_pricing'] for h in hist if h['phase']==2 and h['pricing']],
                     base_upper_bound=b['global_upper_bound'],final_upper_bound=ub)
            details.append(detail)
    for row in allrows:
        ref=refs.get(row['case']);row['reference_optimum']=ref
        row['posthoc_true_profit_gap']=None if ref is None or row['lb'] is None else max(0,ref-row['lb'])/max(1,abs(ref))
    for name,obj in [('rows.json',allrows),('diagnostics.json',details),('reference_optima.json',refs)]:
        (a.output/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    for batch in ('pilot120','confirm600'):
        lines=['|输入|方法|利润LB|有效UB|认证Gap|E2E秒|已证最优|','|---|---|---:|---:|---:|---:|---|']
        tex=[r'\begin{tabular}{llrrrrl}',r'\hline',r'Case & Method & LB & UB & Gap (\%) & Time (s) & Proven \\',r'\hline']
        for r in allrows:
            if r['batch']!=batch:continue
            def f(v):return '--' if v is None else f'{v:.2f}'
            gap='--' if r['relative_gap'] is None else f"{100*r['relative_gap']:.3f}"
            lines.append(f"|{r['case']}|{r['method']}|{f(r['lb'])}|{f(r['ub'])}|{gap}%|{r['seconds']:.2f}|{r['proven']}|")
            label='L'+r['case'].split('lines')[1][:2]+('-A' if '_ample_' in r['case'] else '-C')
            method={'compact_plain':'Compact','balanced_bound':'Line-DW','independent':'Independent'}[r['method']]
            tex.append(f"{label} & {method} & {f(r['lb'])} & {f(r['ub'])} & {gap} & {r['seconds']:.2f} & {'Yes' if r['proven'] else 'No'} "+r'\\')
        tex.extend([r'\hline',r'\end{tabular}'])
        (a.output/(batch+'.md')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
        (a.output/(batch+'.tex')).write_text('\n'.join(tex)+'\n',encoding='utf-8')
    print('Analyzed',len(allrows),'formal runs; reference optima',refs)
if __name__=='__main__':main()
