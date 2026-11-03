"""Recompute tables from raw Task03 data; never changes experiment records."""
import collections,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/branch_and_price/task03'
def read(p):return json.loads(p.read_text())
def f(x):return '—' if x is None else f'{x:.4f}' if isinstance(x,(int,float)) else str(x)
def main():
    rows=read(BASE/'evidence/medium/summary.json');small=read(BASE/'evidence/sealed_validation/summary.json')
    lines=['# Task03 实测结果','',
      '中等规模为 15 个输入 × 5 个方法 = 75 次独立进程运行。每臂名义 5 秒，全部为 time_limit，没有已证整数最优；这是短预算诊断，不是性能优势证明。V0/V1/V2 均无整数 incumbent，不能把 RMP 值当 LB。V3 与 Compact 均在 15/15 个输入取得整数 witness。',
      '', '所有方法使用同一软截止政策，但建模、求解器返回、证书写盘无法硬抢占，实际耗时超过 5 秒；不能将这些记录声称为严格相同总墙钟预算的公平胜负。保留 overrun，正式公平性验收为 PARTIAL。',
      '', '本轮中等规模源码保存在 source_snapshot/，在随后补充节点 PP 数值读回检查前冻结。最终源码的小规模正确性单独复跑；尚未对最终源码重跑全部中等规模矩阵。',
      '', '## 汇总（秒；中位数及 Q1/Q3，inclusive 分位数）','',
      '|每线任务|版本|incumbent/5|已证最优/5|秒 中位 [Q1,Q3]|超预算秒中位|内存峰值中位 MiB|',
      '|---|---|---|---|---|---|---|']
    aggregate=[]
    for n in (20,30,40):
        for version in ('V0','V1','V2','V3','Compact'):
            a=[r for r in rows if r['n']==n and r['version']==version]
            ts=[r['seconds'] for r in a];q=statistics.quantiles(ts,n=4,method='inclusive')
            inc=sum(r['lb'] is not None for r in a);proven=sum(r['status']=='optimal' or r['status']=='optimal_within_tolerance' for r in a)
            med=statistics.median(ts);over=statistics.median(r['overrun'] for r in a)
            mem=statistics.median(r['peak_process_memory_bytes']/1048576 for r in a)
            aggregate.append(dict(n=n,version=version,incumbents=inc,proven=proven,median_seconds=med,q1=q[0],q3=q[2],median_overrun=over,median_peak_mib=mem))
            lines.append(f'|{n}|{version}|{inc}/5|{proven}/5|{med:.3f} [{q[0]:.3f},{q[2]:.3f}]|{over:.3f}|{mem:.1f}|')
    lines+=['','## 每次尝试（没有省略失败/无 incumbent）','','|n|seed|版本|状态|整数 LB|有效 UB|绝对 Gap|相对 Gap|秒|首解秒|节点|PP 次数|','|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        vals=[r['n'],r['seed'],r['version'],r['status'],r['lb'],r['ub'],r['absolute_gap'],r['relative_gap'],r['seconds'],r.get('first_integer_seconds'),r.get('nodes'),r.get('pricing')]
        lines.append('|'+'|'.join(str(v) if j<4 or j>=10 else f(v) for j,v in enumerate(vals))+'|')
    lines+=['','Compact 的首个 incumbent 时间未从日志解析（null），不是零秒。各臂 result.json 保存原始 solver 状态、整数方案、列数、逐节点证书与组件计时；summary.json 保存 Windows 进程 peak working set。','',
      '## 最终源码小规模对照','',
      '以下为同输入的完整求解，不使用超时实验计算加速比。独立枚举节点 LP/IP、Compact 与整数 witness 校验见 sealed_validation/ 各实例 verification.json 及 Task02 对照。没有重复随机运行，时间仅是单次观察。','',
      '|实例|版本|状态|整数目标|UB|Gap|秒|节点|PP|','|---|---|---|---|---|---|---|---|---|']
    names=('single_line','two_lines','generator_n6_L1_s13','lp_yes_ip_no','mandatory_negative')
    for r in small:
        if r['case'] not in names:continue
        lines.append('|'+ '|'.join([r['case'],r['version'],r['status'],f(r['lb']),f(r['ub']),f(r['gap']),f(r['seconds']),str(r['nodes']),str(r['pricing'])])+'|')
    lines+=['','## 组件诊断（小规模完整求解，非独立可加的 speedup 证明）','',
      '|实例|版本|PP墙钟|RMP构造/同步|RMP求解/读回|节点剩余|节点总和|','|---|---|---|---|---|---|---|']
    components=[]
    for name in names[:3]:
        for version in ('V0','V1','V2','V3'):
            r=read(BASE/f'evidence/sealed_validation/{name}_{version}/result.json')
            totals={k:sum(m.get(k,0) for m in r['component_timings']) for k in ('pp_wall','rmp_build','rmp_solve_read','other','node_total')}
            components.append(dict(case=name,version=version,**totals))
            lines.append('|'+name+'|'+version+'|'+'|'.join(f(v) for v in totals.values())+'|')
    lines+=['','V0 未细分构造计时，RMP 构造成本计入 other，表中构造 0 代表未测分项，不表示没有建模成本。V1/V2 的 PP 墙钟含首次构造。V3 节点计时不含 acquisition，其时间另存 acquisition.seconds。不同版本可产生不同树与定价次数，不能把总时间比例全部归因于建模优化。',
      '', '## 解释','',
      '持久化 PP 避免同节点重复翻译；增量 native RMP 避免重复创建原生 LP，但 Python 验证镜像仍每轮重建。小规模表可观察完整求解耗时与树大小，受控中等规模只能比较截断进展。V3 更早获得 LB 的直接来源是额外计费的 Compact acquisition；未向根列池注入该 witness 的站点列，因而不保证改善 Phase I 和 UB。',
      '', '全部 75 臂未闭合 Gap。没有 120/150 总任务实验，也没有 RL 实验；本轮 n40×2=80 总任务。']
    (BASE/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (BASE/'RESULTS.json').write_text(json.dumps(dict(aggregate=aggregate,components=components,attempts=rows),indent=2))
if __name__=='__main__':main()
