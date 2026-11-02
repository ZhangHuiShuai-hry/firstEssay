# 小规模实验逐例结果

以下全部来自 evidence/validation_final，未混入早期smoke或v1试运行。实例为Task01原有28个加1个必拆负利润实例，两求解器共58次完整搜索；所有结果均与直接Compact-IP和独立完整列IP一致。根CG-LP列指本版广义Phase I后的根节点CG值，已与独立Full-LP核对。

“—”在IP列表示已证不可行；相应无incumbent、无有限利润界/Gap，不填0。表中节点数为processed（含继承界直接剪枝）。时间仅为本次小规模复现运行，部分回归在独立进程同时执行，且含不同API暖启动开销；不用于算法性能优越性结论。

| 实例 | 后端 | Compact-IP | Full-IP | 根CG-LP | B&P整数LB | 全局UB | 绝对Gap | 节点数 | PP/局部可行调用 | B&P秒 | 证明状态 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| single_line | cbc | 21 | 21 | 21 | 21 | 21 | 0 | 7 | 30 | 2.7461 | optimal_within_tolerance |
| single_line | cplex_py | 21 | 21 | 21 | 21 | 21 | 0 | 1 | 14 | 0.5933 | optimal_within_tolerance |
| two_lines | cbc | 24 | 24 | 27 | 24 | 24 | 0 | 21 | 152 | 11.7955 | optimal_within_tolerance |
| two_lines | cplex_py | 24 | 24 | 27 | 24 | 24 | 0 | 19 | 120 | 2.1968 | optimal_within_tolerance |
| human_only | cbc | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 6 | 0.6808 | optimal_within_tolerance |
| human_only | cplex_py | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 6 | 0.1829 | optimal_within_tolerance |
| robot_only | cbc | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 6 | 0.6034 | optimal_within_tolerance |
| robot_only | cplex_py | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 6 | 0.1791 | optimal_within_tolerance |
| joint_only | cbc | 4 | 4 | 4 | 4 | 4 | 0 | 1 | 6 | 0.5954 | optimal_within_tolerance |
| joint_only | cplex_py | 4 | 4 | 4 | 4 | 4 | 0 | 1 | 6 | 0.2321 | optimal_within_tolerance |
| zero_fatigue | cbc | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 6 | 0.6258 | optimal_within_tolerance |
| zero_fatigue | cplex_py | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 6 | 0.1940 | optimal_within_tolerance |
| tight_fatigue | cbc | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 6 | 0.7396 | optimal_within_tolerance |
| tight_fatigue | cplex_py | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 6 | 0.2006 | optimal_within_tolerance |
| human_scarce | cbc | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 10 | 0.9667 | optimal_within_tolerance |
| human_scarce | cplex_py | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 6 | 0.1546 | optimal_within_tolerance |
| robot_scarce | cbc | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 8 | 0.8269 | optimal_within_tolerance |
| robot_scarce | cplex_py | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 10 | 0.2197 | optimal_within_tolerance |
| tight_recovery | cbc | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 8 | 0.7453 | optimal_within_tolerance |
| tight_recovery | cplex_py | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 10 | 0.2911 | optimal_within_tolerance |
| zero_profit | cbc | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 0.2981 | optimal_within_tolerance |
| zero_profit | cplex_py | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 0.1317 | optimal_within_tolerance |
| negative_profit | cbc | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 0.2922 | optimal_within_tolerance |
| negative_profit | cplex_py | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 0.0946 | optimal_within_tolerance |
| phase1_impossible | cbc | — | — | — | — | — | — | 1 | 6 | 0.6010 | infeasible_proven |
| phase1_impossible | cplex_py | — | — | — | — | — | — | 1 | 4 | 0.1543 | infeasible_proven |
| multi_optimum | cbc | 10 | 10 | 10 | 10 | 10 | 0 | 1 | 8 | 0.8178 | optimal_within_tolerance |
| multi_optimum | cplex_py | 10 | 10 | 10 | 10 | 10 | 0 | 1 | 6 | 0.1654 | optimal_within_tolerance |
| heterogeneous_gap | cbc | 3 | 3 | 3 | 3 | 3 | 0 | 1 | 4 | 0.4715 | optimal_within_tolerance |
| heterogeneous_gap | cplex_py | 3 | 3 | 3 | 3 | 3 | 0 | 1 | 6 | 0.1491 | optimal_within_tolerance |
| and_diamond | cbc | — | — | — | — | — | — | 1 | 15 | 1.2606 | infeasible_proven |
| and_diamond | cplex_py | — | — | — | — | — | — | 1 | 15 | 0.3101 | infeasible_proven |
| chain | cbc | 16 | 16 | 16 | 16 | 16 | 0 | 21 | 114 | 8.4875 | optimal_within_tolerance |
| chain | cplex_py | 16 | 16 | 16 | 16 | 16 | 0 | 27 | 174 | 2.6747 | optimal_within_tolerance |
| chain_permuted | cbc | 16 | 16 | 16 | 16 | 16 | 0 | 3 | 42 | 2.8802 | optimal_within_tolerance |
| chain_permuted | cplex_py | 16 | 16 | 16 | 16 | 16 | 0 | 7 | 48 | 0.7473 | optimal_within_tolerance |
| lp_yes_ip_no | cbc | — | — | 4 | — | — | — | 3 | 10 | 0.8416 | infeasible_proven |
| lp_yes_ip_no | cplex_py | — | — | 4 | — | — | — | 3 | 10 | 0.1754 | infeasible_proven |
| overlong_required | cbc | — | — | — | — | — | — | 1 | 1 | 0.1826 | infeasible_proven |
| overlong_required | cplex_py | — | — | — | — | — | — | 1 | 1 | 0.1145 | infeasible_proven |
| impossible_recovery | cbc | — | — | — | — | — | — | 1 | 2 | 0.2712 | infeasible_proven |
| impossible_recovery | cplex_py | — | — | — | — | — | — | 1 | 2 | 0.1157 | infeasible_proven |
| generator_n2_L1_s11 | cbc | 14.15 | 14.15 | 14.15 | 14.15 | 14.15 | 1.776356839e-15 | 1 | 4 | 0.5143 | optimal_within_tolerance |
| generator_n2_L1_s11 | cplex_py | 14.15 | 14.15 | 14.15 | 14.15 | 14.15 | 0 | 1 | 3 | 0.1241 | optimal_within_tolerance |
| generator_n4_L1_s12 | cbc | 17.83 | 17.83 | 17.83 | 17.83 | 17.83 | 0 | 1 | 22 | 1.8597 | optimal_within_tolerance |
| generator_n4_L1_s12 | cplex_py | 17.83 | 17.83 | 17.83 | 17.83 | 17.83 | 0 | 1 | 14 | 0.2598 | optimal_within_tolerance |
| generator_n6_L1_s13 | cbc | 56.63 | 56.63 | 59.38 | 56.63 | 56.63 | 7.105427358e-15 | 5 | 30 | 2.7055 | optimal_within_tolerance |
| generator_n6_L1_s13 | cplex_py | 56.63 | 56.63 | 59.38 | 56.63 | 56.63 | 0 | 5 | 42 | 0.6777 | optimal_within_tolerance |
| generator_n3_L2_s14 | cbc | 24.59 | 24.59 | 24.59 | 24.59 | 24.59 | 0 | 1 | 16 | 1.4404 | optimal_within_tolerance |
| generator_n3_L2_s14 | cplex_py | 24.59 | 24.59 | 24.59 | 24.59 | 24.59 | 0 | 1 | 16 | 0.2952 | optimal_within_tolerance |
| generator_n5_L2_s15 | cbc | 45.72 | 45.72 | 45.72 | 45.72 | 45.72 | 0 | 1 | 40 | 2.6438 | optimal_within_tolerance |
| generator_n5_L2_s15 | cplex_py | 45.72 | 45.72 | 45.72 | 45.72 | 45.72 | 0 | 1 | 32 | 0.4800 | optimal_within_tolerance |
| zero_human_load | cbc | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 6 | 0.5647 | optimal_within_tolerance |
| zero_human_load | cplex_py | 6 | 6 | 6 | 6 | 6 | 0 | 1 | 6 | 0.1407 | optimal_within_tolerance |
| dual_degenerate | cbc | 8 | 8 | 8 | 8 | 8 | 0 | 1 | 8 | 0.6713 | optimal_within_tolerance |
| dual_degenerate | cplex_py | 8 | 8 | 8 | 8 | 8 | 0 | 1 | 8 | 0.1675 | optimal_within_tolerance |
| mandatory_negative | cbc | -8 | -8 | -8 | -8 | -8 | 0 | 1 | 6 | 0.5670 | optimal_within_tolerance |
| mandatory_negative | cplex_py | -8 | -8 | -8 | -8 | -8 | 0 | 1 | 8 | 0.2366 | optimal_within_tolerance |

证明状态：optimal_within_tolerance=记录数值政策下的原整数全局最优；infeasible_proven=完整树证明原整数不可行。CBC generator_n6_L1_s13的Gap保留约7.1e-15的浮点差，没有强制改0。

每行证据目录：`evidence/validation_final/<实例>_<后端>/`；mandatory_negative在`additional/mandatory_negative_<后端>/`。instance.json输入，config.json配置及源码版本，result.json完整树证书，tree/节点及原生日志，verification.json逐节点Full-LP/IP与检验数验证，compact.json独立紧凑求解状态/目标/bound/gap，oracle_events.json原生验证调用。

## 安全停止与精度专项

| 场景 | 实际状态 | 整数LB | 有效UB | 未解决节点 | 证明标志 |
|---|---|---:|---:|---:|---|
| 根处理后node_limit=1 | node_limit | null | 27 | 2 | false |
| 根求解前极短实际墙钟预算 | time_limit | null | null | 1 | false |
| 根已完成、子节点过期deadline（故障注入） | time_limit | null | 27 | 2 | false |
| 节点API直接异常（故障注入） | solver_error | null | null | 1 | false |
| Phase I只允许1轮CG | numerical_uncertain | null | null | 1 | false |
| 极小RC、全局绝对阈值比RC精度更严 | numerical_uncertain | 0 | 1.2e-7 | 1 | false |

最后一例真实整数候选为空站方案，利润0；LP定价最大值约6e-8≤默认epsilon=1e-7，但修复总界1.2e-7大于指定绝对目标1e-12，故保留节点。它是按预期安全未完成的精度测试，不计入58次已完成搜索。

前五例证据在interruptions/，第六例在additional/tiny_rc_unclosed_cplex_py/。均保存输入、结果与独立验证。Fault injection明确标注，不把测试注入当成自然发生的原生超时。
