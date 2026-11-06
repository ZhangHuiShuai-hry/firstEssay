"""Post-experiment tables and fixed-dual probe summary, with no solver calls."""
import argparse,json,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    batch=HERE/'evidence/robust180';rows=json.loads((batch/'accounting.json').read_bytes());table=['|输入|方法|LB|UB|E2E秒|已证|','|---|---|---:|---:|---:|---|'];diag=[]
    for s in rows:
        r=json.loads(zlib.decompress((batch/(s['case']+'__'+s['method'])/'result.json.zlib').read_bytes()));d=json.loads((batch/(s['case']+'__'+s['method'])/'instance.json').read_bytes())
        def f(v):return '--' if v is None else f'{v:.2f}'
        table.append(f"|{s['case']}|{s['method']}|{f(r['global_lower_bound'])}|{f(r['global_upper_bound'])}|{s['end_to_end_seconds']:.2f}|{r['global_integer_optimal_proven']}|")
        item=dict(case=s['case'],method=s['method'],lb=r['global_lower_bound'],ub=r['global_upper_bound'],seconds=s['end_to_end_seconds'],proven=r['global_integer_optimal_proven'],status=r['status'],timely=s['timely'],resources=r['witness']['resources_used'] if r['witness'] else None,caps=[d['human_limit'],d['robot_limit']])
        if 'base_result' in r:
            c=r['base_result']['cg'];h=c['history'];item.update(timing=c['timing'],phase1_rounds=sum(bool(v['pricing']) for v in h if v['phase']==1),phase2_rounds=sum(bool(v['pricing']) for v in h if v['phase']==2),phase2_complete=[v['complete_exact_pricing'] for v in h if v['phase']==2 and v['pricing']],profile_calls=r['profile_calls'],cg_status=c['status'],lp_explicit=c['lp_optimal_proven'])
        diag.append(item)
    (a.output/'ROBUSTNESS.md').write_text('\n'.join(table)+'\n',encoding='utf-8')
    for case in {r['case'] for r in diag}:
        pair=[r for r in diag if r['case']==case]
        assert len(pair)==2
        for x in pair:
            for y in pair:
                if x['lb'] is not None and y['ub'] is not None:assert x['lb']<=y['ub']+1e-5
    probe=json.loads((HERE/'evidence/probe/results.json').read_bytes());summ=[]
    for seed in (32,33,34,31):
        for variant in ('rebuild','persistent_no_explicit_start','persistent_explicit_start'):
            rs=[v for v in probe['rows'] if v['seed']==seed and v['variant']==variant];assert len(rs)==2
            summ.append(dict(seed=seed,variant=variant,proven=sum(v['optimal'] for v in rs),at_optimum_unproven=sum(v['at_known_optimum_but_unproven'] for v in rs),mean_target_seconds=sum(v['target_seconds'] for v in rs)/2,mean_setup_target_seconds=sum(v['total_seconds'] for v in rs)/2,incumbents=[v['incumbent'] for v in rs],bounds=[v['best_bound'] for v in rs]))
    for name,value in [('diagnostics.json',diag),('probe_summary.json',summ)]:
        with (a.output/name).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)
    lines=['|seed|设置|证明次数/2|已到最优但未证|平均target秒|平均setup+target秒|','|---|---|---:|---:|---:|---:|']
    for v in summ:lines.append(f"|{v['seed']}|{v['variant']}|{v['proven']}|{v['at_optimum_unproven']}|{v['mean_target_seconds']:.3f}|{v['mean_setup_target_seconds']:.3f}|")
    (a.output/'PROBE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8');print('PASS 8 paired results and 24 probe trials')
if __name__=='__main__':main()
