"""从原始 accounting 生成完整配对表，不筛除超时或不利输入。"""
import argparse
import json
from pathlib import Path
import zlib


def number(x):
    return '—' if x is None else f'{x:.4f}'


def analyze(folders, output):
    records=[]; text=['# 自动生成的全部实验结果','','利润/UB 均为最大化口径。时间为父进程端到端实测秒。',
                      'station 是已有根 CG + 周期受限 IP；line 是整线分解 + 受限 IP。',
                      '超时不等于不可行；仅 `证明=True` 表示已闭合整数最优证书。','']
    comparisons=[]; profiles=[]
    for folder in folders:
        rows=json.loads((folder/'accounting.json').read_text(encoding='utf-8'))
        records.extend(dict(experiment=folder.name,**r) for r in rows)
        text.extend(['## '+folder.name,'','|实例|方法|LB|UB|绝对Gap|秒|预算内|整数最优证明|状态|',
                     '|---|---|---:|---:|---:|---:|---|---|---|'])
        for r in rows:
            text.append('|'+ '|'.join([r['case'],r['method'],number(r.get('global_lower_bound')),
                number(r.get('global_upper_bound')),number(r.get('absolute_gap')),number(r['end_to_end_seconds']),
                str(r['timely']),str(r.get('global_integer_optimal_proven',False)),str(r.get('status','missing'))])+'|')
            if r['method']=='line' and r['completed_evidence']:
                result=json.loads(zlib.decompress((folder/(r['case']+'__line')/'result.json.zlib').read_bytes()))
                pp=result['initialization']+[p for h in result['history'] for p in h['pricing']]
                masters=[h['rmp'] for h in result['history']]+result['integer_recovery']
                pp_total=sum(p['total_seconds'] for p in pp)
                master_total=sum(m['total_seconds'] for m in masters)
                profiles.append(dict(experiment=folder.name,case=r['case'],
                    termination=result['termination_reason'],columns=result['columns'],pricing_calls=result['pricing_calls'],
                    phase1_rounds=sum(h['phase']==1 for h in result['history']),
                    phase2_rounds=sum(h['phase']==2 for h in result['history']),
                    complete_pricing_rounds=sum(h['complete_exact_pricing'] for h in result['history']),
                    pp_build_seconds=sum(p['build_seconds'] for p in pp),
                    pp_translation_solve_read_seconds=sum(p['solve_seconds'] for p in pp),
                    pp_validation_seconds=sum(p['validate_seconds'] for p in pp),
                    pp_total_seconds=pp_total,master_total_seconds=master_total,
                    other_algorithm_seconds=result['wall_seconds']-pp_total-master_total,
                    pp_native_seconds=result['timing']['PP_native_seconds'],
                    algorithm_seconds=result['wall_seconds'],
                    upper_bound_source=result.get('initial_upper_bound_source','exact_initialization_if_available'),
                    used_resources=None if not result['witness'] else result['witness']['resources_used']))
        text.append('')
        bycase={}
        for r in rows:bycase.setdefault(r['case'],{})[r['method']]=r
        for case,pair in bycase.items():
            if not {'line','compact'}<=pair.keys():continue
            a,b=pair['line'],pair['compact']
            timely=a['timely'] and b['timely']
            la,lb,ua,ub=[r.get(key) for r,key in ((a,'global_lower_bound'),(b,'global_lower_bound'),(a,'global_upper_bound'),(b,'global_upper_bound'))]
            comparisons.append(dict(experiment=folder.name,case=case,timely_pair=timely,
                line_better_LB=timely and la is not None and lb is not None and la>lb+1e-5,
                line_better_UB=timely and ua is not None and ub is not None and ua<ub-1e-5,
                line_proven=a.get('global_integer_optimal_proven',False),compact_proven=b.get('global_integer_optimal_proven',False),
                speedup_if_both_proven=(b['end_to_end_seconds']/a['end_to_end_seconds']
                    if timely and a.get('global_integer_optimal_proven') and b.get('global_integer_optimal_proven') else None)))
    output.mkdir(parents=True,exist_ok=False)
    (output/'ALL_RESULTS.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    (output/'comparisons.json').write_text(json.dumps(comparisons,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'profiles.json').write_text(json.dumps(profiles,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(runs=len(records),timely=sum(r['timely'] for r in records),
                          hard_stops=sum(r['hard_stop'] for r in records),
                          solver_errors=sum(r.get('status')=='solver_error' for r in records)),ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folders',nargs='+',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();analyze(a.folders,a.output)
