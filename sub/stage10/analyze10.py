"""Read completed evidence; no solver optimization and no modification of raw runs."""
import argparse
import json
from pathlib import Path
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'sub'))
from line_cg import validate_column


def main():
    p = argparse.ArgumentParser()
    p.add_argument('directory', type=Path)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    records = json.loads((a.directory/'accounting.json').read_bytes())
    rows, details = [], []
    for s in records:
        folder = a.directory/(s['case']+'__'+s['method'])
        r = json.loads(zlib.decompress((folder/'result.json.zlib').read_bytes()))
        data = json.loads((folder/'instance.json').read_bytes())
        lb, ub = r['global_lower_bound'], r['global_upper_bound']
        rel = None if lb is None or ub is None else max(0,ub-lb)/max(1,abs(lb))
        row = dict(case=s['case'], method=s['method'], lb=lb, ub=ub,
                   absolute_gap=None if lb is None or ub is None else ub-lb,
                   relative_gap=rel, e2e_seconds=s['end_to_end_seconds'],
                   proven=r['global_integer_optimal_proven'], timely=s['timely'], status=r['status'])
        rows.append(row)
        d = dict(row, resources=r['witness']['resources_used'],
                 resource_limits=dict(human=data['human_limit'],robot=data['robot_limit']),
                 persistence_seconds=s['persistence_seconds'],evidence_bytes=s['evidence_bytes'])
        d['line_plans'] = [validate_column(l,[t for t in r['witness']['stations'] if t['line']==l['id']]) for l in data['lines']]
        if 'base_result' in r:
            b=r['base_result']; c=b['cg']
            d.update(cg_seconds=c['wall_seconds'], cg_timing=c['timing'],
                     initial_calls=len(c['initialization']), rmp_calls=len(c['history']),
                     pricing_rounds=sum(bool(h['pricing']) for h in c['history']),
                     complete_pricing_rounds=sum(h['complete_exact_pricing'] for h in c['history']),
                     round_pp_calls=sum(len(h['pricing']) for h in c['history']),
                     final_columns=sum(len(v) for v in c['pool'].values()),
                     phase2_resource_prices=[{k:h['rmp']['duals'][k] for k in ('human','robot')} for h in c['history'] if h['phase']==2 and h['rmp']['duals']],
                     profile_calls=len(b['queries']),
                     profile_seconds=sum(q['certificate']['total_seconds'] for q in b['queries'] if q['certificate']),
                     profile_first_lb=b['incumbent_history'][0]['objective'] if b['incumbent_history'] else None,
                     base_ub=b['global_upper_bound'], refined_ub=ub,
                     policy=c['policy'])
        details.append(d)
    pairs=[]
    for case in sorted({r['case'] for r in rows}):
        c=next(r for r in rows if r['case']==case and r['method']=='compact_plain')
        d=next(r for r in rows if r['case']==case and r['method']=='balanced_bound')
        pairs.append(dict(case=case, profit_difference=d['lb']-c['lb'], ub_reduction=c['ub']-d['ub'],
                          compact=c, decomposition=d))
    def save(name, obj):
        (a.output/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    save('paired.json',pairs); save('diagnostics.json',details)
    lines=['|输入|方法|利润LB|有效UB|认证Gap|E2E秒|已证整数最优|',
           '|---|---|---:|---:|---:|---:|---|']
    tex=[r'% Generated from stage10 heldout600, 600-second total budget; floating-point proof.',
         r'\begin{tabular}{llrrrrl}',r'\hline',r'Instance & Method & LB & UB & Gap (\%) & Time (s) & Proven \\',r'\hline']
    for pair in pairs:
        for r in (pair['compact'],pair['decomposition']):
            method='Compact' if r['method']=='compact_plain' else 'Line-DW'
            case=r['case'];short=case.split('_')[0]+'-s'+case.split('seed')[-1]
            lines.append(f"|{case}|{method}|{r['lb']:.2f}|{r['ub']:.5f}|{100*r['relative_gap']:.3f}%|{r['e2e_seconds']:.2f}|{'是' if r['proven'] else '否'}|")
            tex.append(f"{short} & {method} & {r['lb']:.2f} & {r['ub']:.5f} & {100*r['relative_gap']:.3f} & {r['e2e_seconds']:.2f} & {'Yes' if r['proven'] else 'No'} "+r'\\')
    tex.extend([r'\hline',r'\end{tabular}'])
    (a.output/'PAPER_RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (a.output/'paper_table.tex').write_text('\n'.join(tex)+'\n',encoding='utf-8')
    print('\n'.join(lines))
    for d in details:
        print(d['case'],d['method'],[(l['line'],l['profit']) for l in d['line_plans']])
    print('total E2E seconds',sum(r['e2e_seconds'] for r in rows))


if __name__=='__main__':main()
