import hashlib,json,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def main():
    small=json.loads((HERE/'evidence/small/summary.json').read_bytes());medium=json.loads((HERE/'evidence/medium/summary.json').read_bytes());metrics=[]
    for stage,rows in [('small',small),('medium',medium)]:
        for name in dict.fromkeys(r['case'] for r in rows):
            input_hashes=set();core=set()
            for row in (r for r in rows if r['case']==name):
                f=HERE/'evidence'/stage/f"{name}_{row['policy_name']}";input_hashes.add(hashlib.sha256((f/'instance.json').read_bytes()).hexdigest())
                source=json.loads((f/'sources.json').read_bytes())
                for path,sha in source.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,path
                core.add(tuple(source[str(Path('RL/adaptive_v1')/n)] for n in ('engine.py','online.py','check_candidates.py')))
                r=json.loads(zlib.decompress((f/'result.json.zlib').read_bytes()));certs=[c for h in r['history'] for c in h.get('candidate_pricing',[])];lb,ub=r['lower_bound'],r['upper_bound']
                metrics.append(dict(stage=stage,**row,absolute_gap=None if lb is None or ub is None else ub-lb,
                    relative_gap=None if lb is None or ub is None else max(0,ub-lb)/max(1,abs(lb)),
                    unproven_candidate_blocks=sum(not c['optimal'] for c in certs),candidate_blocks=len(certs),columns=r['columns'],
                    accounting=json.loads((f/'accounting.json').read_bytes())))
            assert len(input_hashes)==len(core)==1
    with (HERE/'evidence/metrics.json').open('x') as f:json.dump(metrics,f,indent=2)
    lines=['# 中例四策略开发对照','','每配置一次，60秒软算法预算；最终持久化单列，非硬实时协议。输入字节和核心源码哈希跨策略一致；完整源码与原始证据哈希核验PASS。','','|实例|策略|LB|UB|绝对Gap|算法秒|候选秒|候选加入列|未证候选块|整数最优已证|','|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for r in metrics:
        if r['stage']=='medium':lines.append('|'+ '|'.join(str(r[k]) if not isinstance(r[k],float) else f'{r[k]:.4f}' for k in ('case','policy_name','lower_bound','upper_bound','absolute_gap','online_wall_seconds','candidate_seconds','candidate_added','unproven_candidate_blocks','global_integer_optimal_proven'))+'|')
    with (HERE/'RESULTS.md').open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
    print('PASS',len(metrics),'input/source/accounting records')
if __name__=='__main__':main()
