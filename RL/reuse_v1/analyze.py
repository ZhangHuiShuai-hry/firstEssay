import hashlib,json,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent

def main():
    rows=json.loads((HERE/'evidence/paired/summary.json').read_bytes());table=[];metrics=[]
    for name in dict.fromkeys(r['case'] for r in rows):
        pair=[r for r in rows if r['case']==name];base=next(r for r in pair if not r['reuse']);reuse=next(r for r in pair if r['reuse'])
        assert base['status']==reuse['status'] and base['lower_bound']==reuse['lower_bound']
        assert abs(base['upper_bound']-reuse['upper_bound'])<1e-5
        table.append(f"|{name}|{base['lower_bound']}|{base['upper_bound']:.8f}|{base['online_wall_seconds']:.4f}|{reuse['online_wall_seconds']:.4f}|{base['native_pricing_calls']}→{reuse['native_pricing_calls']}|{reuse['status']}|")
        for r in pair:
            folder=HERE/'evidence/paired'/f"{name}_{'reuse' if r['reuse'] else 'base'}";v=json.loads(zlib.decompress((folder/'result.json.zlib').read_bytes()))
            m=dict(case=name,reuse=r['reuse'],PP_native_seconds=sum(e['solver_time'] for e in v['pricing_native_events']),
                   algorithm_seconds=v['online_wall_seconds'],accounting=json.loads((folder/'accounting.json').read_bytes()))
            metrics.append(m)
        # Actual algorithm files are identical across both configurations.
        a=json.loads((HERE/'evidence/paired'/f'{name}_base/sources.json').read_bytes());b=json.loads((HERE/'evidence/paired'/f'{name}_reuse/sources.json').read_bytes())
        for f in ('engine.py','online.py','proof_cache.py'):assert a[str(Path('RL/reuse_v1')/f)]==b[str(Path('RL/reuse_v1')/f)]
    with (HERE/'evidence/metrics.json').open('x') as f:json.dump(metrics,f,indent=2)
    with (HERE/'RESULTS.md').open('x',encoding='utf-8') as f:
        f.write('# 在线同引擎对照\n\n每项一次开发运行，不是显著性实验；中例60秒软预算，两种配置实际均在预算内结束。LB/UB使用未格式化原值核验，表格仅显示8位。\n\n|实例|整数LB|对照UB|对照算法秒|复用算法秒|原生PP次数|状态|\n|---|---:|---:|---:|---:|---|---|\n'+'\n'.join(table)+'\n\n原结果的timing.PP_native_seconds与pricing_strategy来自被price_override绕过的旧工厂，不能作为实际PP耗时和策略；实际为逐线persistent warm，完整事件见pricing_native_events，正确分项见evidence/metrics.json。algorithm_seconds含会话释放，最终持久化及accounting另存。没有把微小耗时波动解释为确定的机制收益。\n')
    print('PASS paired status/bounds and identical core source hashes')
if __name__=='__main__':main()
