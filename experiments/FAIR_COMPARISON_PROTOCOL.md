# 较大规模同预算配对实验

本轮不更改MILP、FMP、RMP和定价子问题；只新增实验调度、截断时保留列池、证据记录与汇总。入口为 `fair_compare.py`，配置为 `configs/fair_large.json`。

## 预先固定的设计

- 两条拆卸线；每线20/30/40任务，即总任务40/60/80；每档5个种子11/21/31/41/51。
- 使用现有v2.1生成器、节拍15、F=.6、约20%必拆与35%最低回收。每个生成实例原样交给两种方法，不筛选CG有利案例，不把构造见证作为任一方法的初始解。
- 同机、同Python环境、CPLEX 22.1.1 Python API，单线程、确定性并行、求解器种子11、relative/absolute MIP gap=0、原始/对偶容差1e-8、整数容差1e-7。
- 每种方法30秒名义总墙钟预算，包含Python模型构造、转换、原生求解、解码与内部日志。共同导入/预热及实验报告序列化不计入方法时间。
- 方法A：直接CPLEX求紧凑MILP，动态将扣除构造后的剩余时间作为求解器时限。
- 方法B：现有标准CG的根阶段最多使用总预算73%（21.9秒）；其后一次受限列整数恢复可使用剩余总预算。根阶段提前结束时恢复可用时间增加。受限IP已证明不可行或已解毕时，不为消耗预算而人为继续运行。
- 该固定分配是在正式批量前选定的一个CG流程，不代表所有分配比例中最好的CG政策。不得将较短的无解流程耗时解释为比CPLEX求原问题更快。
- 两种方法的执行先后顺序逐实例交替，避免所有CPLEX或所有CG都固定在第一位。串行执行，不并行占用求解资源。

## 证据与公平比较

比较整数可行利润和可行解获取比例；同时记录原问题上下界与相对Gap。CPLEX直接MILP的最优性是原问题最优性；受限整数主问题的最优性只针对已生成列，`cg_optimal`保持false，根LP的收敛单独记录。

根阶段截断不丢弃已生成的合法列，可以在剩余预算中恢复整数解。这不引入启发式定价：未证明最优的PP结果不会被接纳或用于终止。只有所有站点PP均证明最优的一整轮Phase II才计算修复上界；保存其RMP对偶、列配置、检验数及原生求解日志，跨轮取最小有效上界。未完成的轮次不用于上界，Phase I人工目标不充当利润界。

恢复解必须代回原MILP验证全部约束。若没有恢复解，用null，而非0或原问题不可行。CG界差只有有效原问题上界和整数可行利润同时存在时才计算。受限IP本身的native Gap另存，不混用。双方有解时做逐实例利润差比较；缺解实例单独计数，不能只统计CG成功子集。

紧凑LP另作独立诊断，不计入两种算法的预算，不作为两种方法的热启动，也不混入CG产生的界。可能出现早期CG修复上界比紧凑LP或CPLEX分支定界上界松，这应如实保留。

时间限制非操作系统硬实时限制：Python模型构造不能抢占，求解器清理也有延迟。记录实际时间与overrun；父进程另设90秒保护。每个run使用新目录，保存输入、配置、源码快照、哈希、环境、任务、原始日志、结果CSV/JSON。原先已验证的结果不覆盖。

## 先探测、后批量

先用每线30任务、seed11、每种方法15秒的单实例探测验证接口和保存逻辑，结果单列于 `runs/fair_large_probe_01`，不混入正式30秒批量。随后按固定配置运行15组配对，结果在 `runs/fair_large_01`。名义算法预算总上界15分钟，父进程预算上界22.5分钟；这不是预计平均完成时间。没有在观察结果后修改实例或选择性删除失败。

## 命令

```powershell
experiments/.venv/Scripts/python.exe -m unittest discover -s experiments -p test_fair_compare.py -v
experiments/.venv/Scripts/python.exe experiments/fair_compare.py --config experiments/configs/fair_large.json --out experiments/runs/my_fair_run
experiments/.venv/Scripts/python.exe experiments/report_fair_compare.py experiments/runs/my_fair_run
```

报告位于run下 `FAIR_COMPARISON_CN.md`，逐例数据为 `summary.csv/json`。所有未解、不可行恢复、数值异常和超时均保留；对仅有部分有效数值的统计标明样本量。不进行显著性检验，也不把这一个合成生成族上的结果推广到所有拆卸平衡实例。
