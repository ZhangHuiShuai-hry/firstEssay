# Task02 正确性验证报告

## 总体结果

**PASS：29个完整求解实例×CBC/CPLEX两后端=58次搜索，48次最优、10次整数不可行，均与Compact-IP和独立Full-IP一致。** 另有22次独立节点专项及6次中断/精度测试，合计86次按预期通过。安全停止不是已证最优。

28个Task01主实例的56次搜索共有166个节点，每个节点独立求解Full-LP和Full-IP（局部允许集空时直接枚举证明空域），并重算428轮完整定价证书、1151次PP/局部可行调用的记录。主树节点分布：branched 55，Phase I不可行叶21，界支配叶37，整数闭合叶53；没有把开发测试的局部强制空域冒充正常分数分支树中发生的叶。

全部64份全局结果（58个完成+6个安全未完成）和22份独立节点已无求解器离线重放；10类伪造证书均拒绝。生产源码哈希与最终验收一致；5574个Task01 tracked文件未改变。原始结果、失败记录和所有日志保留。

## 独立性

完整列由Task01独立enumerate_patterns生成，不调用生产节点PP/列构造；节点限制独立过滤；完整节点LP/IP使用独立行向量组装。节点证明还逐轮检查初始/演进列池、全部lambda、弹性人工行、raw/effective价格、完整块覆盖、枚举最大RC及修复界。全局重放独立检查原x最分数选择、两个子域、DFS处理前缀、各时刻整数LB、剪枝与活动叶，没有用B&P自己给出的最优标志作为答案。

优化器依然通过同一PuLP后端接入，不能声称求解器实现独立；CBC/CPLEX交叉验证及不调用求解器的枚举/对偶重放共同提供证据。离线范围限本次小规模实例，不外推指数枚举至大实例。

## 逐实例对照

下表利润采用CPLEX数值，CBC对应状态一致、目标差≤1e-5；完整数值、UB/LB/Gap、时间和PP次数见BP_EXPERIMENT_SUMMARY。

| 实例 | Compact-IP | Full-IP | 根Full-LP/CG-LP | B&P整数 | CBC/CPLEX节点 | 全局结论 | 核对 |
|---|---:|---:|---:|---:|---:|---|---|
| and_diamond | — | — | — | — | 1/1 | 不可行已证 | PASS |
| chain | 16 | 16 | 16 | 16 | 21/27 | 最优已证 | PASS |
| chain_permuted | 16 | 16 | 16 | 16 | 3/7 | 最优已证 | PASS |
| dual_degenerate | 8 | 8 | 8 | 8 | 1/1 | 最优已证 | PASS |
| generator_n2_L1_s11 | 14.15 | 14.15 | 14.15 | 14.15 | 1/1 | 最优已证 | PASS |
| generator_n3_L2_s14 | 24.59 | 24.59 | 24.59 | 24.59 | 1/1 | 最优已证 | PASS |
| generator_n4_L1_s12 | 17.83 | 17.83 | 17.83 | 17.83 | 1/1 | 最优已证 | PASS |
| generator_n5_L2_s15 | 45.72 | 45.72 | 45.72 | 45.72 | 1/1 | 最优已证 | PASS |
| generator_n6_L1_s13 | 56.63 | 56.63 | 59.38 | 56.63 | 5/5 | 最优已证 | PASS |
| heterogeneous_gap | 3 | 3 | 3 | 3 | 1/1 | 最优已证 | PASS |
| human_only | 6 | 6 | 6 | 6 | 1/1 | 最优已证 | PASS |
| human_scarce | 6 | 6 | 6 | 6 | 1/1 | 最优已证 | PASS |
| impossible_recovery | — | — | — | — | 1/1 | 不可行已证 | PASS |
| joint_only | 4 | 4 | 4 | 4 | 1/1 | 最优已证 | PASS |
| lp_yes_ip_no | — | — | 4 | — | 3/3 | 不可行已证 | PASS |
| mandatory_negative | -8 | -8 | -8 | -8 | 1/1 | 最优已证 | PASS |
| multi_optimum | 10 | 10 | 10 | 10 | 1/1 | 最优已证 | PASS |
| negative_profit | 0 | 0 | 0 | 0 | 1/1 | 最优已证 | PASS |
| overlong_required | — | — | — | — | 1/1 | 不可行已证 | PASS |
| phase1_impossible | — | — | — | — | 1/1 | 不可行已证 | PASS |
| robot_only | 6 | 6 | 6 | 6 | 1/1 | 最优已证 | PASS |
| robot_scarce | 6 | 6 | 6 | 6 | 1/1 | 最优已证 | PASS |
| single_line | 21 | 21 | 21 | 21 | 7/1 | 最优已证 | PASS |
| tight_fatigue | 6 | 6 | 6 | 6 | 1/1 | 最优已证 | PASS |
| tight_recovery | 6 | 6 | 6 | 6 | 1/1 | 最优已证 | PASS |
| two_lines | 24 | 24 | 27 | 24 | 21/19 | 最优已证 | PASS |
| zero_fatigue | 6 | 6 | 6 | 6 | 1/1 | 最优已证 | PASS |
| zero_human_load | 6 | 6 | 6 | 6 | 1/1 | 最优已证 | PASS |
| zero_profit | 0 | 0 | 0 | 0 | 1/1 | 最优已证 | PASS |

重点：two_lines根27→整数24（CBC21节点、CPLEX19节点）；generator_n6_L1_s13根59.38→整数56.63（均5节点）。lp_yes_ip_no根LP=4，但整数不可行；两后端均3节点，根对A线H坐标分0/1，两叶Phase I修复上界均-0.5，正确输出infeasible_proven。

single_line的LP最优值与IP均21，但CBC所得根最优LP的原x可分数，仍用了7节点；CPLEX根解整数，仅1节点。相同最优值不意味着所有最优LP解均整数，也不要求不同求解器的树或最优列相同。

## 24类边界逐项验收

| 编号 | 场景 | 实际证据 | 状态 |
|---:|---|---|---|
| 1 | 根LP整数 | single_line_cplex_py，1节点 | PASS |
| 2 | 根正整数Gap | two_lines、generator_n6_L1_s13 | PASS |
| 3 | Branch 0 | 两个正Gap树及test_node_cg | PASS |
| 4 | Branch 1 | 同上及one_no_empty | PASS |
| 5 | Branch 1禁止空列 | node_scenarios/one_no_empty，两后端 | PASS |
| 6 | Branch 1局部空域 | one_local_time_empty、one_local_fatigue_empty | PASS |
| 7 | 局部可行、全局LP不可行 | human_global_infeasible、robot_global_infeasible | PASS |
| 8 | 初始池冲突、完整节点可行 | human/robot_missing_column_recovery、AND_missing_column_recovery | PASS |
| 9 | 分支冲突/未知/重复固定 | test_node_state | PASS |
| 10 | 父子列池隔离 | test_branch_zero_and_sibling_pool_isolation | PASS |
| 11 | 兄弟状态隔离 | 同上及不可变限制测试 | PASS |
| 12 | 可选任务重复造成Phase I违约 | duplicate_optional_recovery | PASS |
| 13 | AND导致节点不一致 | AND_global_infeasible | PASS |
| 14 | 人工资源紧缺 | human_global_infeasible及human_scarce主例 | PASS |
| 15 | 机器人紧缺 | robot_global_infeasible及robot_scarce主例 | PASS |
| 16 | 疲劳阈值紧张 | tight_fatigue及one_local_fatigue_empty | PASS |
| 17 | LP可行IP不可行 | lp_yes_ip_no，完整3节点证明 | PASS |
| 18 | 零/负利润 | zero_profit、mandatory_negative=-8 | PASS |
| 19 | 多重最优 | multi_optimum | PASS |
| 20 | 退化/非唯一对偶 | dual_degenerate | PASS |
| 21 | 超时仍有继承有效界 | interruptions/child_time_limit，UB27且2活动节点 | PASS（明确故障注入） |
| 22 | 节点限制保留活动节点 | interruptions/node_limit，2个孩子 | PASS |
| 23 | 非法剪枝证书 | 10类篡改与test_branch_price拒绝 | PASS |
| 24 | 全树剪枝证明整数不可行 | lp_yes_ip_no、and_diamond等 | PASS |

专项局部空域使用外部固定的合法节点限制；正常most-fractional分支完整继承父池时两个取值各有父LP正权重支持，不会凭空失去所有局部列。说明见数学设计第8节。所有专项数据/父池/固定/节点JSON/Full-LP-IP验证及日志在node_scenarios/，没有跳过某类场景后虚报通过。

## 回归与开发失败

| 测试 | 实际结果 | 证据 |
|---|---|---|
| 核心数据结构首次测试 | 3项PASS | step2_state_tests.txt |
| 节点CG首次测试 | 7项PASS | step3_node_tests.txt |
| 初次树测试 | 8项PASS | step4_tree_tests.txt |
| 增强节点测试 | 最终9项纳入回归PASS | regressions_cbc/cplex.txt |
| 极小RC首次增强树测试 | 1项FAIL：测试参数低于CPLEX允许最小值 | tree_tests_extended.txt、tiny_rc_before_fix.json |
| 查询API允许最小值后 | 9项PASS | tree_tests_final.txt |
| 最终综合CBC配置回归 | 66项PASS | regressions_cbc.txt |
| 最终综合CPLEX配置回归 | 66项PASS | regressions_cplex.txt |
| 原实验组件回归 | 32项PASS | regressions_experiments.txt |
| 最终完整模型矩阵 | 56次PASS | validation_final/summary.json |
| 最终独立节点 | 22次PASS | node_scenarios/summary.json |
| 补充负利润/极小RC | 3次符合预期PASS | additional/summary.json |
| 时间/节点/异常/CG迭代停止 | 5次符合预期PASS | interruptions/summary.json |
| 全局离线证书+独立节点 | 64+22份PASS，10类伪造均拒绝 | certificate_replay/summary.json |

66项=原有Task01核心45项+新增21项；新增树测试内部显式选择后端/故障注入，不把它们误称为每个方法均各跑一次两种后端。29个完整实例的真正双后端对照由58次矩阵运行提供。

唯一实际失败的新增断言来自测试请求dual=1e-10；本机CPLEX参数最小值为1e-9，求解器在建模时拒绝，B&P保留solver_error/open节点、最优标志false。改用API允许的1e-9（仍严于默认1e-8）后得到预期numerical_uncertain和非零Gap。未放宽约束或默认整数精度。失败输入按input_sha256匹配另存tiny_rc_before_fix_instance.json；unsupported_tolerance_context.json解释参数及安全状态。因参数设置阶段失败，没有发生原生优化，不能伪造原生求解日志。

v1及smoke早期通过结果保留，不并入最终矩阵统计。最终生产契约收紧后重新运行了全部验证；交付生产源码与该最终运行一致。全部原始tracked文件不变，不覆盖或删除历史数据。

## 复现

```powershell
experiments/.venv/Scripts/python.exe docs/branch_and_price/run_validation.py --out docs/branch_and_price/evidence/my_new_validation --boundaries
experiments/.venv/Scripts/python.exe experiments/run_regressions.py --solver cbc
experiments/.venv/Scripts/python.exe experiments/run_regressions.py --solver cplex_py
experiments/.venv/Scripts/python.exe -m unittest discover -s experiments -p test_*.py -v
```

新目录必须不存在；默认每个主搜索60秒、1000节点，独立Oracle每次30秒；本次全部主搜索正常完成，未为得到结果延长预算。未运行120/150任务实验。framework中的150二进制变量极短时限状态夹具和环境1201变量纯LP许可证探测不是拆卸规模实验。

## 范围外

大规模性能：NOT RUN；精确有理/区间认证：NOT IMPLEMENTED；截断PP Best Bound驱动新轮CG：NOT IMPLEMENTED；跨节点原生模型复用/并行分支搜索/强化学习：NOT IMPLEMENTED。上述均为明确范围边界，不混入本次通过计数。
