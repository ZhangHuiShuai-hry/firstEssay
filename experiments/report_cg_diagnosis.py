"""Evidence-based diagnosis, separating engineering fixes from integer limitations."""
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'experiments/runs/cg_diagnosis'
micro=json.loads((out/'rmp_microbenchmark.json').read_text())
run=ROOT/'experiments/runs/fair_long_diagnosis_01'
rows=json.loads((run/'summary.json').read_text())
lines=['# CG问题排查、工程修正与延时实验','',
 '## 1. 发现的问题与性质','',
 '1. **明确的工程低效：大量零系数与临时表达式。** 原coefficients函数对每条优先边的每个站点前缀都生成字典项，即使前驱与后继的列内包含状态相同、系数必为零。master又为这些零项创建PuLP乘法表达式。每轮还重复计算旧列系数。已改为只保留非零项、按完整图结构及列属性缓存不可变系数，以及用addterm直接插入线性项。没有关闭原检验数核查，也没有改变目标、约束、允许列或定价最优性要求。',
 '2. **仍存在的工程开销：每轮完整重建RMP及CPLEX对象。** 目前不是增量加入CPLEX列、保留原生LP和基的实现。稀疏修正只解决其中一部分；不能宣称已消除这一开销。',
 '3. **实验时限截断了尚未完成的LP。** 原30秒CG流程只给根节点21.9秒，每线40任务的seed11在该时点刚进入Phase II，不能用此结果断言完整列LP已经求完或分解无效。已延长到两种方法各120秒总预算，CG根阶段108秒，剩余时间恢复。时间分配与旧实验不同，单独保存，不能混合统计。',
 '4. **整数恢复的结构性限制。** Phase I找LP可行列、Phase II找LP改善列，都不保证受限列池支持整数可行解。即使完整列LP已最优，已有列的整数主问题仍可能不可行。这不是增加恢复求解时间就能解决的原问题不可行，也不是MILP与完整列IP等价性失效。',
 '5. **分解不保证全局整数求解速度优势。** 此实现反复解局部MILP并协调全局优先约束，直接CPLEX则使用预处理、切平面和分支定界。当前没有Branch-and-Price，不能把根LP与整数最优速度视为同一任务。未发现可以据现有证据判定的MILP/对偶符号错误；小规模正确性与终止证书回归仍通过。',
 '', '## 2. 相同列池的受控构造微基准','',
 '| 每线任务数 | 已保存列数 | 原构造中位数秒 | 修正后中位数秒 | 比率 | 矩阵与目标逐项一致 |',
 '|---|---:|---:|---:|---:|---|']
for item in micro:
    lines.append(f"| {item['n']} | {item['columns']} | {statistics.median(item['times']['before']):.4f} | {statistics.median(item['times']['sparse']):.4f} | {item['speedup']:.2f}× | {item['matrix_equal']} |")
lines+=['', '每组重复3次，包含一次首次构造；后两次可利用系数缓存。中位数对应反复使用旧列的情形，不能将8–13倍误称为整个CG或原问题整数求解加速比。原代码保存在修改前快照；45项原测试在CPLEX和CBC下分别通过。',
 '', '## 3. 120秒总预算的实际诊断运行','',
 '两条线，seed11，每线20/30/40任务。每种方法120秒总预算；CG最多108秒根阶段，剩余用于受限整数恢复。只有每规模1个实例，是机制诊断，不是正式统计结论。',
 '', '| 每线任务数 | 直接IP利润 | IP上界 | IP Gap | CG根状态 | CG根秒 | CG有效上界 | 整数恢复 |',
 '|---|---:|---:|---:|---|---:|---:|---|']
for r in rows:
    upper='—' if r['cg_best_bound'] is None else f"{r['cg_best_bound']:.5f}"
    lines.append(f"| {r['tasks_per_line']} | {r['ip_incumbent']:.5f} | {r['ip_best_bound']:.5f} | {100*r['ip_relative_gap']:.2f}% | {r['cg_root_status']} | {r['cg_root_wall_time']:.2f} | {upper} | {r['cg_recovery_status']} |")
lines+=['', '完整列LP收敛后整数恢复仍被原生CPLEX证明不可行的实例，已经直接证实“缺整数可行列”的问题；不存在用null利润掩盖0利润的处理。直接MILP的可行解证明原问题本身可行。上界来自全部精确定价均完成的轮次，未完成轮次不提供新的有效上界。',
 '', '## 4. 实际耗时组成','',
 '| 每线任务数 | 完整定价轮次 | PP调用数 | RMP构造秒 | RMP接口秒 | PP完整调用秒 |',
 '|---|---:|---:|---:|---:|---:|']
for r in rows:
    raw=json.loads((run/'raw'/(r['instance_id']+'.json')).read_text());c=raw['cg_pipeline']
    lines.append(f"| {r['tasks_per_line']} | {len(c['completed_pricing_rounds'])} | {c['pricing_calls']} | {c['rmp_build_time']:.2f} | {c['rmp_solve_time']:.2f} | {c['pricing_wall_time']:.2f} |")
reference=out/'reference_n20/result.json'
if reference.exists():
    before=json.loads(reference.read_text());after=next(r for r in rows if r['tasks_per_line']==20)
    lines+=['', '## 5. 修改前实现的同实例复跑','',
        f"冻结的修改前源码与修正后源码均在120秒总预算下运行seed11、每线20任务。修改前根状态={before['root_status']}，根时间={before['root_wall_time']:.2f}秒；修正后根状态={after['cg_root_status']}，根时间={after['cg_root_wall_time']:.2f}秒。此为单实例描述性比较，不能替代多种子统计；退化时不同实现可能有不同列路径。"]
lines+=['', '## 后续优先级','',
 '第一，做增量RMP/原生LP基复用的工程对照，仍保留全部原约束与精确定价。第二，单独设计整数可行初列实验：通过可行性求解构造可行站点列，同时给直接CPLEX相同初始可行解，避免只给CG使用生成器见证的不公平优势。第三，若需要比较原问题全局整数最优求解，必须进一步设计分支定价等整数框架；本次不实现。第四，再做更丰富DAG/模式与多种子的时间分配消融，不能为了证明CG有优势而挑选有利实例。']
(out/'CG_DIAGNOSIS_CN.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(out/'CG_DIAGNOSIS_CN.md')
