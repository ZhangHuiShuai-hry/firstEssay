# 第一版B&P实现报告

## 1. 实际改动与兼容性

新增五个生产模块、三个测试模块及本目录的设计/验证/报告程序。**没有修改任何Task01原有tracked文件**，包括紧凑模型、根CG、公共列定义、原生适配器、求解器后端和历史实验。以BASELINE.json的5574个tracked文件SHA-256逐一检查，全部原样。未切分支、commit或push。

| 新增文件 | 核心位置 | 职责 |
|---|---|---|
| `code/dwcg/node_state.py` | NumericPolicy、NodeRestrictions、NodeCertificate、NodeResult、PricingCertificate、most_fractional | 数值职责、不可变固定、显式证书和确定性分支 |
| `code/dwcg/node_pricing.py` | validate_column、validate_pricing_evidence、price_node | 节点局部可行性、重建精确定价、固定域及状态验证 |
| `code/dwcg/node_master.py` | build_node_master、solve_node_master、solve_node | 所有耦合行弹性Phase I、真实Phase II、完整定价和节点界 |
| `code/dwcg/bp_solution.py` | verify_integer_assignments、integer_from_x | 原始x恢复、独立数据级检查、原Compact约束和利润一致性 |
| `code/dwcg/branch_price.py` | minimum_bound、global_bounds、run_branch_price、main | DFS、分支、树界、剪枝、异常/时限和CLI |
| `code/dwcg/test_node_state.py` | 3项 | 限制/冲突/序列化/数值政策 |
| `code/dwcg/test_node_cg.py` | 9项 | 局部空域、广义人工、缺列恢复、域隔离、PP枚举与错误契约 |
| `code/dwcg/test_branch_price.py` | 9项 | 完整树、整数不可行、安全中断、非法证书、CLI和极小RC |

无全局monkeypatch管理节点约束，无跨节点原生模型复用，无完整列枚举或Compact-IP求解进入生产搜索。测试中的mock仅用于注入错误/缺失证据，实际约束一直显式传递。生产调用链为 `run_branch_price → solve_node → build_node_master/price_node`；整数验证调用 `compact.build_model(...).valid(...)`，不调用原MILP优化器。

RMP重用已审计build_master(phase=2)的数学行，然后只在独立节点对象上添加人工变量、覆盖Phase I目标；根build_master本身不改。PP新建同一套局部约束并加入z固定；列仍使用Task01不可变Column，利润和系数不变。兄弟池是独立列表视图，可共享只读Column，不能通过修改某个池列表影响其他池。

## 2. 广义Phase I实现

每个非凸性LE行增加一个系数-1、成本-1的非负人工量；每个非凸性等式增加系数+1和-1、成本均-1的人工量；凸性不加人工。保存每个人工量的row/sign/value/name，全部真实列目标0。节点初始池即便任务重复、资源过量或优先违约，弹性RMP仍可行。

人工量归零时，真正重新构造无人工Phase II RMP并通过原始检查。Phase II若未证最优/不可行，保留numerical_uncertain，不把“人工近0”提升为可行证明。人工总量为正的受限池也不直接剪枝；必须完成所有块精确定价且完整Phase I修复上界严格为负。

本地空域验证允许真正的子节点PP infeasible；仅标签不足，必须有底层可靠infeasible状态。在无强制1的块（包含根）空列理论可行，infeasible报告是异常；在普通定价中已有合法列又报告空域也为异常。无法证明的节点始终保留。

## 3. 整数点与树界

most-fractional使用原始x，按line/station/task/mode打破并列，先DFS 0再1。每条路径不重复固定已有坐标。完整列LP若原x全整数，可合并相同局部assignments；数值实现使用舍入后的任务模式集合，重新检查任务唯一/必拆/AND/节拍/疲劳/资源/回收/费用及原Compact全部行。整数利润不一致时不接受。

只有验证过的整数witness可更新LB，包括合法负利润。界按继承与完整精确定价更新；未知保持null。剪枝必须有局部/Phase I不可行证明、有效界支配已验证LB，或整数witness与节点UB闭合。未解决节点与未访问兄弟全部保留。容差关闭叶的实际界不丢弃，不通过树空后强制赋UB=LB制造零Gap。

如果整数方案有效，但CG误差比用户全局闭合要求大，仍可保留整数LB，但节点未解决；专项测试实际触发了这一情况。该行为避免把单块RC容差与全局Gap混同。

## 4. 运行及文件保护

```powershell
experiments/.venv/Scripts/python.exe code/dwcg/branch_price.py code/milp/examples/two_lines.json --solver cplex_py --time-limit 300 --node-limit 10000 --max-cg-iterations 1000 --output <不存在的新结果路径>
```

推荐使用原项目venv（Python3.10.11、PuLP3.3.2、CPLEX22.1.1.0、CBC2.10.3）。默认系统Python3.12可跑CBC，但不假设它能加载本机CPLEX API。`--numeric-policy`读取NumericPolicy字段JSON；`--verbose`控制详细求解器输出；原始日志始终在正式output_dir保存。0=最优/不可行已证明，2=未证明完成，1=输入/求解器/程序错误。新输出或关联目录存在时拒绝覆盖。

CLI先以独占方式创建属于本次调用的running结果，随后写最终证书；它会更新自己创建的文件，不会覆盖调用前已有结果。每个已处理节点另有独占创建的JSON检查点；最终node_history是权威汇总。尚未实现从检查点恢复搜索，操作系统强制杀进程时也不能保证最后一个检查点完整。

## 5. 独立验证与实际修正

`independent_bp_verify.py` 复用Task01独立枚举/列算术/主问题Oracle，不用生产节点PP生成期望列。它独立按节点固定过滤、求完整节点LP/IP，并逐轮重算primal、弹性对偶范围、定价最优值、修复界、最分数分支、DFS覆盖和历史LB剪枝。

开发中确认并修正了新实现的一处防御性记录缺口：外部节点API直接抛异常时，补全lower_bound_after，使未解决节点仍可严格重放。还收紧了定价证书契约：核对固定域、阶段、块和底层状态，拒绝无证明的optimal/infeasible标签。对应单元测试及最终全量验证均通过。

曾有一项新增测试先请求CPLEX不支持的simplex optimality=1e-10，触发1014参数错误，算法安全保留未知节点；API查询确认最小值1e-9后，测试改用该值（仍严于默认1e-8）。这是测试配置错误，不是通过放宽模型/默认容差修复算法；失败结果、输入和单测日志均保留。

## 6. 已知限制与优化方向

- 只实现重建式单线程DFS，无跨节点原生复用、启发式定价、复杂分支或强化学习。
- 无自动从checkpoint恢复；库加载及Python工作使预算是软墙钟检查，非硬实时。
- 当前证明针对浮点容差；极端缩放、溢出、比求解器支持精度更小的定价收益可能导致numerical_uncertain，不签发虚假最优。
- 独立枚举认证只适用于小规模；大实例保留证明轨迹，但不能声称已经用完整枚举独立认证。
- 完整保留池和逐轮证书，内存/磁盘随树增长；未实现列清理或证书压缩。
- 精度不匹配时保留节点而非自动收紧ε；需要配置更严格的RC精度或适当缩放目标后重新运行。

小规模计时显示，定价调用（含重建、转换/进程开销及MILP求解）约占节点总时间的66%—70%。下一阶段首先在保持节点域/证书契约的前提下评估每节点持久PP与增量RMP，再考虑列缓存和分支策略；不能跳过节点级等价性回归。该比例仅来自本次小实例，不外推大规模性能。
