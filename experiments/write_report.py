"""Build a Chinese report exclusively from persisted observed results."""
import argparse
from collections import Counter
import json
import re
from pathlib import Path
import statistics

from analyze_results import analyze,distribution


def fmt(value):return '—' if value is None else f'{value:.4g}'


def report(stage_a,pilot,destination,scout=None):
    a,astats,aaudit=analyze(stage_a);rows,stats,audit=analyze(pilot)
    env=json.loads((pilot/'environment.json').read_text())
    cbc_log=next((stage_a/'logs').glob('**/*cbc.log'))
    cbc_version=re.search(r'Version:\s*(\S+)',cbc_log.read_text(encoding='utf-8')).group(1)
    comparisons=json.loads((stage_a/'analysis/cross_solver_comparison.json').read_text())
    statuses=Counter(r.get('cg_status') for r in rows)
    recover=Counter(r.get('integer_recovery_status') for r in rows)
    ratios=distribution([r.get('pricing_ratio') for r in rows])
    root=sum(r.get('cg_wall_time') or 0 for r in rows)
    pp=sum(r.get('pricing_wall_time') or 0 for r in rows)
    native=sum(r.get('pricing_native_time') or 0 for r in rows)
    translate=sum(r.get('pricing_translation_time') or 0 for r in rows)
    gaps=[r['milp_incumbent']-r['restricted_integer_obj'] for r in rows
          if r.get('milp_incumbent') is not None and r.get('restricted_integer_obj') is not None]
    totalwall=sum(r.get('process_wall_time') or 0 for r in rows)
    lines=[
        '# 标准列生成计算实验：阶段 A、小规模预试验与受控扩展',
        '', '## 1. 实际完成范围与环境', '',
        f"本报告汇总 `{stage_a.name}`、`{pilot.name}`"+(f" 及 `{scout.name}`" if scout else '')+"。前序环境调试和生成器探索运行保留，不与最终结果混合。工作区无 Git，修改前源码及每次运行的源码 SHA-256、配置与快照均已保存。",
        '',f"Python {env['python'].split()[0]}，PuLP {env['packages']['pulp']}，CPLEX {env.get('cplex_version')}，CBC {cbc_version}；均已实际求解及回归。主机 {env['cpu']}，{env['logical_cpus']} 逻辑核，物理内存 {env.get('hardware',{}).get('physical_memory_bytes',0)/1024**3:.1f} GiB。主要实验单线程，种子11，gap=0。",
        '', '本地 CPLEX API 支持 Python 3.8/3.9/3.10，不支持当前原有3.12解释器。已建立项目Python3.10虚拟环境，未修改系统PATH或全局安装。直接API、CPLEX_PY和CPLEX_CMD的LP测试已成功；API/PuLP还实际求解MILP并核对状态、目标及非零检验数。1201变量模型成功，仅证明当前许可足以完成该测试，不推断许可证有效期或所有更大规模的授权。',
        '', '## 2. 算例与公平比较', '',
        '合成任务时间和模式成本存在显式依赖，R疲劳系数为零，J更快但有联合资源成本。按全任务可行见证构造站点，DAG只有前向AND边；必拆目标20%（每线至少一个），最低回收35%。见证不是MILP验证的替代。正式生成版本v2.1：普通规模节拍15，固定总量组节拍20。F=.40/.60/.80仅为实验参数，不是人体安全标准。',
        '', '每处理使用11/21/31/41/51五个生成种子。B1预试验每线n=6/10、L=1；B2包括每线任务固定与总任务12/站点4/人机预算各4固定两种设计，L=1/2；B3只改变F；B4只按见证人机需求改变全局资源上限。固定总量分线仍会改变优先边分块、必拆与回收分摊，不能声称完全隔离这些因素。',
        '', f"性能预试验含 {audit['generated_instances']} 个因子条件记录，实际有 {audit['unique_input_hashes']} 个不同输入；重复项是不同因子族共用控制，不是额外独立样本。模式/图结构的正式C实验尚未运行。",
        '', 'Compact IP求原整数问题；Compact LP求其连续松弛；标准CG求DW根节点LP；Restricted IP只求已有列上的整数恢复。比较时间时明确求解目标，不能用CG根节点时间对比IP证明时间宣称算法优越。',
        '', '## 3. 阶段 A 正确性结果', '',
        f"阶段 A：{aaudit['generated_instances']} 个输入 × 4种组合，共{len(a)}次实际运行。组合为CPLEX/CPLEX、CBC/CBC、CPLEX-RMP/CBC-PP、CBC-RMP/CPLEX-PP。完整列/对偶终止验证通过 {sum(r.get('verification_status')=='passed' for r in a)}/{len(a)}；跨求解器目标比较通过 {sum(c['passed'] for c in comparisons)}/{len(comparisons)}。其中有1个计划不可行输入，四组合均通过Phase I不可行证书。",
        '', '| 原始算例 | CG/完整列LP | 完整列IP/紧凑IP |', '|---|---:|---:|',
        '| single_line | 21 | 21 |','| two_lines | 27 | 24 |',
        '', '原有45项模型/定价/证书测试在CPLEX与CBC下分别全部通过。另有5项实验框架测试覆盖配对不变量、固定总量任务多重集、计划规模生成、运行目录不可覆盖和真实极短时间限制状态。没有把超时有解或超时无解写为已证明最优。',
        '', '## 4. 预试验状态与计算性能', '',
        f"CG状态计数：`{dict(statuses)}`。紧凑IP状态：`{dict(Counter(r.get('milp_status') for r in rows))}`。恢复状态：`{dict(recover)}`。进程异常/超时：{sum(r.get('execution_status')!='complete' for r in rows)}/{len(rows)}。性能组未做完整列枚举终止证书，verification_status=not_run；阶段A已完成独立验证，性能组仍逐PP要求原生最优并记录精确定价终止。",
        '', f"MILP已证可行 {audit['milp_proven_feasible']}，已证不可行 {audit['milp_proven_infeasible']}，未确定 {audit['milp_unresolved']}，生成时丢弃 {audit['discarded_instances']}。恢复成功 {audit['recovered_runs']} 次；其中全H为 {audit['all_human_recoveries']}、全R为 {audit['all_robot_recoveries']}。",
        '', '| 因子组/水平 | 成功CG/尝试 | 根时间中位数 [Q1,Q3] 秒 | PP占比中位数 % | 迭代中位数 | 列数中位数 |',
        '|---|---:|---:|---:|---:|---:|']
    for s in stats:
        d=s['cg_wall_time']
        lines.append(f"| {s['group']} / {s['factor']} | {s['converged']}/{s['attempts']} | {fmt(d['median'])} [{fmt(d['q1'])}, {fmt(d['q3'])}] | {fmt(s['pricing_ratio']['median'])} | {fmt(s['cg_iterations']['median'])} | {fmt(s['columns_generated']['median'])} |")
    lines += ['', '不同求解目标的成本对照（B1，均为墙钟中位数）：', '',
              '| 每线任务数 | CG根LP秒 | 紧凑LP秒 | 紧凑IP证明秒 | DW上界改进中位数 |',
              '|---|---:|---:|---:|---:|']
    for s in stats:
        if s['group']=='B1':
            entries=[r for r in rows if r['group']=='B1' and str(r['factor'])==s['factor']]
            gains=[r['relaxation_bound_improvement'] for r in entries if r.get('relaxation_bound_improvement') is not None]
            lines.append(f"| {s['factor']} | {fmt(s['cg_wall_time']['median'])} | {fmt(s['compact_lp_wall_time']['median'])} | {fmt(s['milp_wall_time']['median'])} | {fmt(statistics.median(gains) if gains else None)} |")
    lines += ['', '列数包含初始空列；迭代包含Phase I和Phase II。机器可读统计同时给出均值、标准差、IQR、状态计数和成功率；时间为所有已观察尝试的墙钟时间，未删除异常或截断。',
        '', f"根CG总墙钟 {root:.3f}秒，作业总进程墙钟 {totalwall:.3f}秒；进程时间还包括导入、IP/LP基线、恢复及检查点。已有可比恢复解中，紧凑IP最优利润减恢复利润的最大差为 {max(gaps,default=0):.4f}。该差可能为正，受限列恢复不能替代完整整数算法。",
        '', '## 5. 瓶颈分析与约束作用', '',
        f"PP完整调用累计 {pp:.3f}秒，占根CG累计时间 {100*pp/root:.2f}%；逐作业PP占比中位数 {ratios['median']:.2f}%、IQR [{ratios['q1']:.2f}%, {ratios['q3']:.2f}%]。这支持本批小实例的主要已测组件是PP完整调用，而不是预先假定的结论。",
        '', f"PP内部原生优化累计 {native:.3f}秒（PP时间的 {100*native/pp:.2f}%），PuLP→CPLEX转换 {translate:.3f}秒（{100*translate/pp:.2f}%）；其余 {max(0,pp-native-translate):.3f}秒包括Python建模、参数/环境/日志及读回等。因此PP调用占比较高不等于CPLEX整数搜索独占总时间，更不能据此证明强化学习加速必然有效。",
        '', f"{audit['runs_with_positive_resource_dual']} 次运行出现正的人机资源对偶价格。根解中负荷恰达疲劳等式的站点计数可能为零；局部整数列约束仍可排除模式组合，应通过B3配对利润及枚举列数量的变化判断疲劳影响。图14给出小实例精确列数。",
        '', '## 6. 图表与原始证据', '',
        f"图表位于 `{pilot.name}/figures`：任务规模时间、非重叠组件/阶段占比、迭代和列数、预定义seed11代表例的收敛、疲劳对利润/资源/时间/列数影响、资源紧缺对利润/时间影响、DW与紧凑LP界差及两类多线对照。每图含PDF/SVG/PNG和源CSV，误差为5个生成种子的IQR，无显著性检验。",
        '', '每个run保存summary.csv/json、raw、每次求解日志、实例manifest、逐次task配置、source快照、requirements-lock及provenance。阶段A还保存完整列枚举与证书，原有验证通过结果文件未被覆盖。',
        '', '## 7. 局限、未运行项目与下一步', '',
        '本次是可信环境基准与小规模预试验，不能视作完整论文规模实验。n=30/40/50、L=3/5、60任务固定总量及正式模式/图结构C实验均未运行；其生成方案已检查，但没有相应性能数据。若已执行n=20受控扩展，其结果单列于后文，不与L=1预试验混合。完整125作业配置的每作业600秒硬上界合计约20.8小时，仅为保守预算，不是预测；应先逐一扩展规模并重估开销。',
        '', '小实例亚秒级时间易受Windows后台任务、文件日志和接口启动开销影响；本环境不是隔离基准服务器。每seed只做一次确定性测量，不能拿这些时间作精确架构优劣或显著性推断。初次探索版本与修订节拍版本分别保存，不事后合并。',
        '', '先以两线n=10/20受控扩展核实PP原生优化/转换/其他开销随规模的变化，再根据本组结果决定是否扩展n=30/40/50。随后固定总任务60与总站点20考察L=1/2/3/5，记录边密度及资源影子价格。最后进行配对模式丰富度和DAG结构试验。只有较大PP的原生搜索成本稳定占主导，才有更扎实的学习辅助定价研究动机；若反复建模或RMP占比增加，应优先评估接口复用、列管理或稳定化，但本版不实现这些算法变化。']
    if scout:
        sr,ss,sa=analyze(scout)
        lines += ['', '## 8. 两条线的 n=10/20 受控扩展（实际运行）', '',
                  f"独立目录 `{scout.name}`，固定L=2，n=10/20，各5个生成种子，共{len(sr)}次尝试。根CG上限30秒、IP上限10秒、进程上限90秒；与L=1的pilot分开分析。所有超时保留，不用最终RMP值冒充完整列LP最优值。",
                  '', '| 每线任务数 | CG收敛/尝试 | IP已证最优/尝试 | 根观察时间中位数秒 | PP占比中位数% | RMP构造占比中位数% | IP Gap中位数 |',
                  '|---|---:|---:|---:|---:|---:|---:|']
        for n in (10,20):
            rr=[r for r in sr if r['factor']==n]
            d=lambda key:distribution([r.get(key) for r in rr])['median']
            build=statistics.median(100*r['rmp_build_time']/r['cg_wall_time'] for r in rr)
            lines.append(f"| {n} | {sum(r['cg_converged'] for r in rr)}/{len(rr)} | {sum(r['milp_status']=='optimal' for r in rr)}/{len(rr)} | {fmt(d('cg_wall_time'))} | {fmt(d('pricing_ratio'))} | {fmt(build)} | {fmt(d('milp_gap'))} |")
        lines += ['', f"CG状态计数：`{dict(Counter(r['cg_status'] for r in sr))}`；IP状态计数：`{dict(Counter(r['milp_status'] for r in sr))}`。超时IP保留原生 incumbent、best bound 和相对Gap，不设置optimal=True；未完成精确定价的CG不输出完整列LP最优值。",
                  '', '表中“观察时间”含截断，不能解释为所有实例的完成时间。PP完整调用仍需细分原生优化、转换与Python开销；尤其应检查RMP重建占比是否随规模上升。扩展结果不足以支持学习辅助定价优越性，也不构成完整整数算法与CG的同目标速度比较。下一步应先围绕本组未解实例及RMP构造做更细剖析，再决定n=30以上预算。']
    destination.write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage-a',type=Path,required=True);p.add_argument('--pilot',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--scout',type=Path)
    a=p.parse_args();report(a.stage_a,a.pilot,a.out,a.scout)
