"""Summaries for paired, equal-budget comparisons; no failed attempt exclusion."""
from collections import Counter
import argparse
import csv
import json
from pathlib import Path
import statistics

from analyze_results import distribution


def display(value,percent=False):
    return '—' if value is None else f'{100*value:.2f}%' if percent else f'{value:.4g}'


def report(run):
    rows=json.loads((run/'summary.json').read_text());config=json.loads((run/'config.json').read_text())
    summaries=[]
    for n in sorted({r['tasks_per_line'] for r in rows}):
        selected=[r for r in rows if r['tasks_per_line']==n]
        item=dict(tasks_per_line=n,attempts=len(selected),
            ip_feasible=sum(r['ip_incumbent'] is not None for r in selected),
            ip_optimal=sum(r['ip_optimal'] is True for r in selected),
            cg_feasible=sum(r['cg_incumbent'] is not None for r in selected),
            cg_root_converged=sum(r['cg_root_converged'] is True for r in selected),
            ip_statuses=dict(Counter(r['ip_status'] for r in selected)),
            cg_root_statuses=dict(Counter(r['cg_root_status'] for r in selected)),
            recovery_statuses=dict(Counter(r['cg_recovery_status'] for r in selected)),
            both_feasible=0,ip_better=0,cg_better=0,tied=0,only_ip_feasible=0,only_cg_feasible=0)
        item['cg_tighter_upper_bound']=sum(r.get('cg_best_bound') is not None and r.get('ip_best_bound') is not None
                                          and r['cg_best_bound']<r['ip_best_bound']-1e-5 for r in selected)
        for field in ('ip_incumbent','cg_incumbent','ip_best_bound','cg_best_bound',
                      'ip_relative_gap','cg_relative_gap','ip_wall_time','cg_wall_time',
                      'cg_rmp_build_time','cg_rmp_solve_time','cg_pricing_wall_time'):
            item[field]=distribution([r.get(field) for r in selected])
        differences=[]
        for r in selected:
            a,b=r['ip_incumbent'],r['cg_incumbent']
            if a is not None and b is not None:
                item['both_feasible']+=1;differences.append((b-a)/(abs(a)+1e-10))
                item['cg_better' if b>a+1e-5 else 'ip_better' if a>b+1e-5 else 'tied']+=1
            elif a is not None:item['only_ip_feasible']+=1
            elif b is not None:item['only_cg_feasible']+=1
        item['paired_relative_profit_difference']=distribution(differences)
        summaries.append(item)
    (run/'group_statistics.json').write_text(json.dumps(summaries,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    lines=['# 较大规模实例：同预算 CPLEX-IP 与 CPLEX-CG 配对比较','',
        '## 设计与公平性','',
        f"固定两条线，每线任务数{config['sizes']}，随机种子{config['seeds']}。同一实例分别运行两种方法，每种名义总墙钟预算均为{config['equal_budget_seconds']}秒，计入模型构造、转换、原生求解和解码，不计共同导入/预热及最终报告序列化。单线程、CPLEX 22.1.1 Python API、种子11、relative/absolute MIP gap=0、原始/对偶容差1e-8。两种方法交替先后顺序，原输入、数学模型和求解器参数相同。",
        '',f"CG方案预先固定：最多{config['equal_budget_seconds']*config['root_fraction']:.2f}秒用于标准两阶段根节点CG，剩余总预算用于一次受限列整数恢复；根节点提前结束时，恢复可使用剩余时间。根节点超时时保留已经生成的合法列，但不使用未证最优的PP结果。恢复不可行后不追加新列或进行新启发式。未使用完预算不等于提前证明最优；本实验比较的是这一明确的标准CG加恢复流程，而不是所有可能的时间分配政策。",
        '', 'CPLEX原MILP可以证明全局整数最优；CG根节点只能证明完整列LP最优。受限IP自身的最优性不等于原MILP最优性。输出区分两类证据，不用不同求解目标的时间宣布算法优越。',
        '', '完整定价轮次的对偶、各站最优检验数与列配置均保存在raw；只有所有PP均证明最优的一整轮Phase II才能产生有效利润上界。CG上界取这些已完成轮次的最小修复上界，即使根节点尚未收敛也可以有效。Phase I目标不能作为利润界。原始紧凑LP另行求解，仅作独立诊断，不计入两种方法的预算，也不混入CG界或作为热启动。',
        '', '同名义预算通过动态剩余时间传给每次原生求解。Python构造不可抢占、求解器退出也有开销，因此记录实际墙钟及overrun，不能把30秒理解为操作系统硬实时边界。父进程另有保护上限。所有失败与空值保留，缺少整数解不填写0，也不等同于原问题不可行。',
        '', '## 实际结果','',
        '| 每线/总任务数 | 配对数 | IP可行/已证最优 | CG恢复可行 | CG根LP收敛 | IP Gap中位数 | CG全局界差中位数 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        lines.append(f"| {s['tasks_per_line']}/{2*s['tasks_per_line']} | {s['attempts']} | {s['ip_feasible']}/{s['ip_optimal']} | {s['cg_feasible']} | {s['cg_root_converged']} | {display(s['ip_relative_gap']['median'],True)} | {display(s['cg_relative_gap']['median'],True)} (n={s['cg_relative_gap']['count']}) |")
    lines += ['', 'CG全局界差 = (CG有效上界 − 恢复整数利润)/|恢复利润|；只有同时存在有效上界与整数解时才计算，不是受限IP求解器的Gap。IP的Gap为原生CPLEX相对Gap。中位数各自的有效样本数可能不同，不能直接把两列视为完全配对的统计量。',
              '', '两种Gap使用各自方法得到的不同整数下界，因此CG的Gap较大不能单独说明其上界较差。独立逐例比较两个有效上界（最大化时越小越好）：',
              '', '| 每线任务数 | CG上界更紧/配对数 |', '|---|---:|']
    for s in summaries:
        lines.append(f"| {s['tasks_per_line']} | {s['cg_tighter_upper_bound']}/{s['attempts']} |")
    lines += ['', '每线20任务的部分实例即使CG根节点尚未收敛，也可通过完整精确定价轮次取得更紧的有效上界；这是界质量优势，不是整数解质量或完成速度优势。30/40任务的截断根过程尚未得到同样优势。没有把两种方法的上下界合并后冒称为某一种方法在30秒内的成绩。',
              '', '| 每线任务数 | 双方均有解 | IP利润更高 | CG利润更高 | 相同 | 仅IP有解 | 仅CG有解 | 配对CG利润相对差中位数 |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in summaries:
        lines.append(f"| {s['tasks_per_line']} | {s['both_feasible']} | {s['ip_better']} | {s['cg_better']} | {s['tied']} | {s['only_ip_feasible']} | {s['only_cg_feasible']} | {display(s['paired_relative_profit_difference']['median'],True)} |")
    lines += ['', '| 每线任务数 | IP实际墙钟中位数秒 | CG流程实际墙钟中位数秒 | IP平均墙钟秒 | CG平均墙钟秒 |',
              '|---|---:|---:|---:|---:|']
    for s in summaries:
        lines.append(f"| {s['tasks_per_line']} | {display(s['ip_wall_time']['median'])} | {display(s['cg_wall_time']['median'])} | {display(s['ip_wall_time']['mean'])} | {display(s['cg_wall_time']['mean'])} |")
    lines += ['', '流程时间短不能解释为求解同一问题更快：CG可能因为根预算结束、受限列IP不可行而提前停止。上表只是实际观察时间，超时为删失完成时间。完整逐例目标、上下界、状态、时间、恢复状态及所有运行均在summary.csv/json中。',
              '', '## 当前能支持的结论与局限','']
    ip_only=sum(s['only_ip_feasible'] for s in summaries);cg_only=sum(s['only_cg_feasible'] for s in summaries)
    better_ip=sum(s['ip_better'] for s in summaries);better_cg=sum(s['cg_better'] for s in summaries)
    lines += [f"已运行{len(rows)}组配对。双方均有整数解时，IP利润更高{better_ip}组、CG更高{better_cg}组；仅IP有整数解{ip_only}组、仅CG有整数解{cg_only}组。这些是已测实例和固定预算/分配方案下的描述性结果，不是跨所有实例、所有时间预算的普遍优越性证明。",
              '', f"实例为同一生成族的合成数据：每线约20%必拆、35%回收要求、节拍15，H/R/J模式和疲劳参数关系沿用现有v2.1生成器。没有筛选CG有利算例，没有将构造见证传给任一求解器，旧结果不覆盖。每规模{len(config['seeds'])}种子不足以对工业总体或其他DAG/成本分布推广；未做显著性检验。",
              '', '若本组CG结果较弱，应先区分根定价未完成、RMP重建负担和受限列缺少整数可行组合，不能仅通过“找到更多CG有利实例”宣称算法更快。下一步可在公开预先固定的更长预算或不同预设资源/DAG处理下复核，仍需对双方给相同总预算。Branch-and-Price和学习定价均未实现。']
    (run/'FAIR_COMPARISON_CN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps([{k:s[k] for k in ('tasks_per_line','attempts','ip_feasible','ip_optimal','cg_feasible','cg_root_converged','ip_better','cg_better','only_ip_feasible')} for s in summaries],indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();report(a.run)
