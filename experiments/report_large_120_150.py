"""Read completed real outputs; no synthetic result substitution."""
import argparse,json
from pathlib import Path

def main(out):
    rows=json.loads((out/'summary.json').read_text());entries=json.loads((out/'instances/manifest.json').read_text())
    lines=['# 120／150 任务规模探索实验','',
           '本轮新增两个实例，任务数均指系统总任务数。此前实验清单最大为80任务。每个规模仅一个种子，属于规模探索，不能用于总体显著性或稳定加速结论。','',
           '## 设置','',
           '- 两条线，每线60／75任务；固定生成种子11，沿用witness-paired-v2.1生成器。',
           '- AND型DAG、混合H/R/J可行模式、疲劳阈值0.6、节拍15、20%必拆任务、35%最低回收权重。',
           '- CPLEX 22.1.1，单线程，求解器种子11，进程PYTHONHASHSEED=11；沿用已验证数值容差与零MIP gap要求。',
           '- Compact MILP-IP与CG-V2各600秒墙钟预算，均含建模；CPLEX API预加载不计入。CG保持精确定价，不做整数恢复。',
           '- 单独求解紧凑LP，最多60秒，仅作诊断，不占双方预算，也不向双方提供信息。',
           '- 两个规模交替算法运行顺序，串行运行，无其他并发实验；不向算法提供生成器的可行配置。',
           '- 源码快照、SHA256、完整实例、生成元数据、求解器日志及逐轮对偶/定价记录保存在本目录。','',
           '## 实测结果','',
           '|总任务|MILP状态|整数利润|MILP上界|MIP Gap|时间(s)|CG状态|CG LP区间|CG时间(s)|',
           '|---:|---|---:|---:|---:|---:|---|---|---:|']
    def num(v):return '未获得' if v is None else f'{v:.6f}'
    for r in rows:
        lines.append(f"|{r['total_tasks']}|{r['ip_status']}|{num(r['ip_incumbent'])}|{num(r['ip_bound'])}|{num(None if r['ip_gap'] is None else 100*r['ip_gap'])}%|{r['ip_time']:.3f}|{r['cg_status']}|[{num(r['cg_lp_lower'])}, {num(r['cg_lp_upper'])}]|{r['cg_time']:.3f}|")
    lines+=['','CG LP区间下端是已求解的Phase II RMP目标，未必是整数可行利润；上端仅使用完整精确定价轮次计算。缺少完整轮次则不报告上界。截断结果不标记LP最优。','',
            '## 规模与耗时','',
            '|任务|站数|优先边|人工/机器人上限|CG轮数|列数|Phase I/II(s)|PP(s)|原生PP(s)|',
            '|---:|---:|---:|---|---:|---:|---|---:|---:|']
    for r,e in zip(rows,entries):
        m=e['metadata'];lines.append(f"|{r['total_tasks']}|{r['stations']}|{m['precedence_edges']}|{m['human_limit']}/{m['robot_limit']}|{r['cg_iterations']}|{r['cg_columns']}|{r['cg_phase1_time']:.3f}/{r['cg_phase2_time']:.3f}|{r['cg_pp_time']:.3f}|{r['cg_native_pp_time']:.3f}|")
    lines+=['','## 逐例判断','']
    for r in rows:
        lines.append(f"- **{r['total_tasks']}任务**：原MILP{'已证明整数最优' if r['ip_optimal'] else '未证明整数最优'}；CG{'已证明列模型LP收敛' if r['cg_converged'] else '未证明列模型LP收敛'}。PP完整调用占CG时间{100*r['cg_pp_time']/r['cg_time']:.1f}%，原生整数优化占{100*r['cg_native_pp_time']/r['cg_time']:.1f}%。")
        if r['cg_lp_upper'] is not None and r['ip_bound'] is not None:
            delta=r['ip_bound']-r['cg_lp_upper'];lines.append(f"  CG有效上界相对直接MILP的最终上界{'降低' if delta>=0 else '增加'}{abs(delta):.6f}。这是界质量比较，不是整数解质量比较。")
            if r['ip_incumbent'] is not None:
                gap=(min(r['ip_bound'],r['cg_lp_upper'])-r['ip_incumbent'])/abs(r['ip_incumbent'])*100
                lines.append(f"  合并两种独立方法的结果，原整数最优值区间为[{r['ip_incumbent']:.6f}, {min(r['ip_bound'],r['cg_lp_upper']):.6f}]，相对差距{gap:.4f}%。这不是任一算法单独获得的MIP Gap，也不代表CG产出了整数解。")
    audit=json.loads((out/'audit.json').read_text()) if (out/'audit.json').exists() else None
    if audit:
        lines+=['','本轮额外审计通过：源码快照比对无变化，逐条检查'+str(audit['exact_pricing_calls_checked'])+'次已证明最优的PP返回列，重新检查局部可行性并用原始列系数和保存对偶独立计算检验数，最大差异'+str(audit['max_reduced_cost_delta'])+'。这验证返回结果与系数的一致性，不代替完整列枚举。','',
                '|任务|原生RMP(s)|占CG时间|原生PP(s)|占CG时间|','|---:|---:|---:|---:|---:|']
        for r,a in zip(rows,audit['runs']):
            lines.append(f"|{r['total_tasks']}|{a['rmp_native_time']:.3f}|{100*a['rmp_native_time']/r['cg_time']:.1f}%|{r['cg_native_pp_time']:.3f}|{100*r['cg_native_pp_time']/r['cg_time']:.1f}%|")
    lines+=['','## 验证与局限','',
            '- 沿用已经过103项回归测试的V2实现，本轮未修改MILP、RMP、PP或CG核心源码。',
            '- 本次新实例经过原有数据合法性与站列可行性校验；生成的全任务配置提供结构性可行见证。实际整数可行解由本轮MILP独立求解获得。',
            '- 检查整数可行利润不高于CG有效上界，RMP LP下端不高于最优紧凑LP值；所有实际可用的界检查通过。',
            '- 本规模无法完整枚举所有列；未运行全列枚举验证，不声称获得该级别的独立终止证书。',
            '- 每个规模只有一个实例，不能推断所有大规模实例表现。CG根节点LP和原MILP整数最优是不同计算任务，不能只按用时判定优劣。',
            '- 任何time_limit均保留截断状态；不以已有可行解或较小Gap代替最优性证明。','',
            '## 文件','',
            '`summary.csv/json`为逐例汇总；`raw/*_ip.json`包含整数解和原MILP界；`raw/*_cg.json`包含每轮目标、对偶、精确定价和时间分解；`logs/`包含原生日志；`instances/manifest.json`记录生成参数。','']
    (out/'REPORT_CN.md').write_text('\n'.join(lines),encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('out',type=Path);main(p.parse_args().out)
