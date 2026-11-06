"""Read-only comparisons; known optima are derived only after all solver runs."""
import argparse
import json
from pathlib import Path
import zlib

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    a = parser.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    rows, details, refs = [], [], {}
    for batch in ('pilot120', 'formal600'):
        root = HERE/'evidence'/batch
        for rec in json.loads((root/'accounting.json').read_bytes()):
            folder = root/(rec['case']+'__'+rec['method'])
            r = json.loads(zlib.decompress((folder/'result.json.zlib').read_bytes()))
            data = json.loads((folder/'instance.json').read_bytes())
            lb, ub = r['global_lower_bound'], r['global_upper_bound']
            gap = None if lb is None or ub is None else (ub-lb)/max(1, abs(lb))
            assert gap is None or gap >= -1e-5
            row = dict(batch=batch, case=rec['case'], method=rec['method'], lb=lb, ub=ub,
                       relative_gap=gap, seconds=rec['end_to_end_seconds'],
                       proven=r['global_integer_optimal_proven'], status=r['status'],
                       timely=rec['timely'], hard_stop=rec['hard_stop'])
            rows.append(row)
            if row['proven']:
                assert row['timely'], 'Do not treat a late proof as a timely result'
                if rec['case'] in refs:
                    assert abs(refs[rec['case']]-lb) < 1e-5
                refs[rec['case']] = lb
            d = dict(row, total_tasks=sum(len(l['tasks']) for l in data['lines']),
                     lines=len(data['lines']), stations=sum(len(l['stations']) for l in data['lines']),
                     capacity=[data['human_limit'], data['robot_limit']],
                     resources=r['witness']['resources_used'] if r['witness'] else None,
                     evidence_bytes=rec['evidence_bytes'], persistence_seconds=rec['persistence_seconds'],
                     first_optimal_profit_time=None,
                     first_time_scope='Compact no callback; no comparable first-optimum timestamps')
            if 'base_result' in r:
                b = r['base_result']; c = b['cg']; hist = c['history']
                d.update(cg_seconds=c['wall_seconds'], timing=c['timing'], init_calls=len(c['initialization']),
                         rmp_calls=len(hist), phase1_pricing_rounds=sum(bool(h['pricing']) for h in hist if h['phase']==1),
                         phase2_pricing_rounds=sum(bool(h['pricing']) for h in hist if h['phase']==2),
                         complete_rounds=sum(h['complete_exact_pricing'] for h in hist),
                         pp_calls=len(c['initialization'])+sum(len(h['pricing']) for h in hist),
                         final_columns=sum(len(v) for v in c['pool'].values()), profile_calls=len(b['queries']),
                         phase1_artificials=[h['rmp']['artificials'] for h in hist if h['phase']==1],
                         resource_prices=[dict(human=h['rmp']['duals']['human'], robot=h['rmp']['duals']['robot'])
                                          for h in hist if h['phase']==2 and h['rmp']['duals']],
                         phase2_complete=[h['complete_exact_pricing'] for h in hist if h['phase']==2 and h['pricing']],
                         base_upper_bound=b['global_upper_bound'], final_upper_bound=ub)
            details.append(d)
    for row in rows:
        ref = refs.get(row['case'])
        row['reference_optimum'] = ref
        row['posthoc_true_profit_gap'] = None if ref is None or row['lb'] is None else (ref-row['lb'])/max(1,abs(ref))
    pairs=[]
    for case in sorted({r['case'] for r in rows if r['batch']=='formal600'}):
        c = next(r for r in rows if r['batch']=='formal600' and r['case']==case and r['method']=='compact_plain')
        d = next(r for r in rows if r['batch']=='formal600' and r['case']==case and r['method']=='balanced_bound')
        pairs.append(dict(case=case, compact=c, decomposition=d,
                          completion_speed_ratio=c['seconds']/d['seconds'] if c['proven'] and d['proven'] else None,
                          compact_time_censored=not c['proven']))
    for name, value in [('rows.json',rows),('diagnostics.json',details),('reference_optima.json',refs),('pairs.json',pairs)]:
        with (a.output/name).open('x',encoding='utf-8') as f:
            json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)
    for batch in ('pilot120','formal600'):
        md=['|输入|方法|利润LB|有效UB|认证Gap|E2E秒|已证最优|','|---|---|---:|---:|---:|---:|---|']
        tex=[r'\begin{tabular}{llrrrrl}',r'\hline',r'Case & Method & LB & UB & Gap (\%) & Time (s) & Proven \\',r'\hline']
        for r in rows:
            if r['batch']!=batch: continue
            def fmt(v): return '--' if v is None else f'{v:.2f}'
            gap='--' if r['relative_gap'] is None else f"{100*r['relative_gap']:.3f}"
            method='Compact' if r['method']=='compact_plain' else 'Line-DW'
            label=r['case'].replace('tasks','N').replace('_lines','-L').replace('_conflict_candidate_seed','-s')
            md.append(f"|{r['case']}|{method}|{fmt(r['lb'])}|{fmt(r['ub'])}|{gap}%|{r['seconds']:.2f}|{r['proven']}|")
            tex.append(f"{label} & {method} & {fmt(r['lb'])} & {fmt(r['ub'])} & {gap} & {r['seconds']:.2f} & {'Yes' if r['proven'] else 'No'} "+r'\\')
        tex.extend([r'\hline',r'\end{tabular}'])
        (a.output/(batch+'.md')).write_text('\n'.join(md)+'\n',encoding='utf-8')
        (a.output/(batch+'.tex')).write_text('\n'.join(tex)+'\n',encoding='utf-8')
    print('Analyzed',len(rows),'runs;',len(refs),'known optima')


if __name__=='__main__': main()
