# 增量RMP与LP重优化实验

本实验比较两个根LP实现，不比较整数最优证明速度。V0是已验证的稀疏化标准CG，V1只替换主问题的创建、追加和求解接口。原始紧凑MILP、列定义、主问题行、精确MILP定价、双阶段CG迭代与收敛判定保持不变。

## 版本保存

开始修改前的源码及SHA256保存在 `snapshots/CG_V0_20261030_134805`。每个新实验目录另存执行时源码、配置、逐实例输入、启动时间、Python路径和SHA256。旧结果目录保持原样；运行程序要求新输出目录不存在。

`code/dwcg/incremental_master.py` 使用原生CPLEX创建固定的主问题行，通过 `variables.add(columns=...)` 批量追加非零列。同一个Cplex对象跨轮使用，`advance=1`，保留可用LP基。Phase I最大化人工变量之和的负值；进入Phase II，将人工变量上界固定为0、其目标系数改为0、真实列目标改为利润。投影掉固定0的人工变量后与重建版Phase II一致。LP方法自动选择、预处理默认，V1未单独改变算法参数。

## 配对设计

- 两条拆卸线；每线20、30、40任务；实例种子11、21、31、41、51。
- 两版使用逐字相同的实例；单线程CPLEX 22.1.1，求解器种子11。
- 原始/对偶容差1e-8，PP整数容差1e-7，PP相对/绝对MIP Gap为0；CG epsilon及可行性容差均1e-7。
- 每臂120秒根LP wall-clock总预算，包含建模、更新、读回、在线核查、求解和精确定价。不做整数恢复。CPLEX共同模块导入和运行结束后的报告序列化不计时。
- 时限按剩余墙钟预算传递给求解器；求解器返回、模型接口与读回可能造成少量超出。结果保存实测wall time，不将120.2秒等观测裁剪成120秒，也不把时限状态改成最优。
- 单进程串行运行各臂，按实例交替版本先后次序，不同时运行其他求解作业。
- 若120秒的难例需额外核查，另设300秒配对，独立目录统计，不与120秒结果混算。
- 实例由现有确定性生成器生成：AND型DAG、混合模式、约20%必拆、35%最低回收指标；资源预算来自合法配置见证。输入、见证和元信息完整保存。本轮不改变生成器。

## 状态与界

只有最优RMP及全部工作站的精确最优PP已完成，且最大检验数不超过epsilon，才报告LP收敛。时限或数值异常写明确状态；最终LP目标未证明时为空。截断上界只使用已完整完成所有精确定价的Phase II轮次，取其有效上界最小值，不使用部分轮次。

两臂均收敛时，逐例目标差不得超过1e-5。若只有一臂收敛，检查另一臂有效上界不低于其最优值。双方收敛配对才计算精确完成时间比；V0截断、V1完成时只报告速度比下界；双方截断无完成速度比。

## 非重叠计时

根总时间分解为RMP构造/追加、RMP接口、PP完整调用以及其他开销。RMP原生求解、V0完整模型转换是RMP接口的内部子区间，不可再与接口重复相加。分解图采用构造/追加 + 完整模型转换 + RMP原生求解 + PP完整调用 + 残差，每例严格合计为根总时间。V1的追加API调用计入构造/追加；转换为0仅表示没有完整PuLP模型转换。

Phase I/II是对同一根总时间的另一种划分，不与上述组件累加。PP完整调用仍包含PuLP建模、CPLEX转换、精确MIP求解和读回；原生求解/转换子时间可从events读取。聚合组件图用均值保证可加；总时间与阶段时间报告中位数、IQR及成功率，不删除超时。

## 正确性与归因

`test_incremental.py` 在真实CPLEX环境下对同一完整列池比较两阶段矩阵、目标、行对偶所导出的检验数与原生dj；检查真实追加、人工变量固定，以及原单/双线小例完整枚举终止证书。不同最优对偶可能来自退化，不要求两种求解路径的对偶向量逐项相等。

`replay_incremental.py` 重放V0的同一追加列序列，逐轮比较RMP目标与检验数，同时测量重建/转换/原生求解和增量更新/原生重优化。这个消融隔离了两次独立CG可能产生的定价路径差异。basis_records保存求解前是否存在可用基、LP迭代数和advance设置；它证明求解对象与可用状态被保留，不声称CPLEX每次预处理内部行为完全相同。

同列池重放另设原生矩阵advance=0的辅助对照，仅观察原生优化累计时间，以区分基/状态使用和接口重建收益。此额外消融不混入主实验；主实验V1始终advance=1。不因退化对偶不同而要求不同臂得到相同基或相同CG路径。

重放微基准每轮在两臂计时前共同准备列系数，避免先运行的臂为后运行的臂独占预热缓存。该准备时间另行保存，不计入重放的构造/求解对比；主CG实验不做此额外预热，其总预算包含正常列系数计算。重放是接口与重优化的隔离测量，不用其总和代替主CG时间。

## 复现

在项目根目录的PowerShell执行：

```powershell
experiments/.venv/Scripts/python.exe -m unittest discover -s experiments -p test_incremental.py -v
experiments/.venv/Scripts/python.exe experiments/compare_incremental.py --config experiments/configs/incremental_rmp.json --out experiments/runs/my_incremental
experiments/.venv/Scripts/python.exe experiments/replay_incremental.py experiments/runs/my_incremental --out experiments/runs/my_incremental/replay.json
experiments/.venv/Scripts/python.exe experiments/report_incremental.py experiments/runs/my_incremental
experiments/.venv/Scripts/python.exe experiments/plot_incremental.py experiments/runs/my_incremental
experiments/.venv/Scripts/python.exe experiments/audit_figures.py experiments/runs/my_incremental/figures --source experiments/plot_incremental.py
```

CPLEX Python API通过现有solver_backend在进程内加载；不修改系统PATH或全局安装。旧CBC和V0接口不变。V1适配器当前仅支持连续RMP；整数恢复仍使用原接口，不涉及原生增量整数主问题。
