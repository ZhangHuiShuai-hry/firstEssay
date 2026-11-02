# 最优性证书审计

## 已有与修复后的证明范围

原实现的核心数学控制流是保守的：RMP 与 PP 均必须通过 require_optimal；两阶段分离；只在全部块定价完成后计算界；受限整数恢复的 optimal=False。原有主要缺口是日志证据和通用后端字段，并未发现“超时当无改善列”的正常控制流。

本次采用 `certificate_version=2`，保留原 status 接口，增加 certificate_status 与 termination_reason。精确 PP 的最佳检验数用于根 LP 界，求解器原生 Best Bound 作为可核查字段保存，不把 incumbent 当成截断定价上界。

| certificate_status | 含义与处理 |
|---|---|
| `lp_optimal_proven` | 全部块精确定价，最大检验数≤ε；是记录容差下的完整列 LP 证明，proof_scope 明确为浮点 LP |
| `lp_feasible_unproven` | 已有利润 LP 可行或求解未证完；是否已建立原 LP 可行性需同时看 `full_lp_feasible_established`，Phase I 人工可行不算原 LP 可行 |
| `pricing_time_limit` | 定价时间不足；本轮完整标记false，不新造本轮上界，保留此前有效界 |
| `pricing_infeasible` | 定价报告不可行；空列理论可行，因此视为异常证据，不能当作rho≤0 |
| `phase1_infeasible_proven` | 完整 Phase I 定价及严格负的修复对偶上界证明 Full-LP 不可行 |
| `solver_error` | 求解器/API异常，无最优结论 |
| `numerical_uncertain` | 数值或证据不足，包括 Phase I 界不够严格为负；不宣称不可行或最优 |

`status=iteration_limit` 明确未收敛；Phase I 仅有人工解时 `full_lp_feasible_established=false`。RMP 超时的具体角色在 failed_role/failed_solver_result；上述证书状态并非每一种底层状态的一一枚举。

## 每轮证书结构

Phase II 的 history 记录：phase、iteration、rmp_status、objective、rmp_solution（λ权重、站点与任务模式）、完整 duals（行键与数值）、columns_before/added；pricing 列表覆盖每个 line/station，保存 status/optimal、incumbent、best_bound、reduced_cost、assignments、solve_seconds、solver_result、evidence_source；complete_pricing、lp_lower_bound、lp_upper_bound、lp_gap、maximum_reduced_cost、upper_bound_source。

RMP 正常时 rmp_status=optimal 来自已证最优检查。定价 solver_result 保存原生码、原生说明、求解器配置和日志索引。重建 PP 和直接持久 PP 返回兼容二元组的 PricingResult，并附带元数据。少数历史实验适配器重新封装普通二元组时，evidence_source=exact_adapter_contract，意味着已审计适配器只在精确定价成功后返回；不能向未来启发式适配器推广该契约。元数据明确 optimal=false 时立即拒绝。

Phase I 定价轮还保存人工变量值和人工行键，可逐行验证原始可行性。人工已归零的阶段切换记录是 event，不是完整定价轮。异常附带 error.cg_result/error.cg_pool，继续抛出以兼容旧运行器；CLI 指定 --output 时会保存失败证书 JSON 并返回非零。整数恢复异常单独记录，已经建立的 LP 证明仍保留。

本次未把实验运行器的所有异常路径重新设计为统一持久存储；旧运行器仍有各自 checkpoint 与外层日志。内存不足、进程被操作系统强制终止等情况下不能保证 Python finally/CLI 写盘。历史普通二元组也不具备原生状态的自包含证明；可通过独立枚举重新认证小实例。

## 界的解释

利润 Phase II：$LB_{LP}=Z_{RMP}\le Z_{Full-LP}$；$UB_{LP}=Z_{RMP}+\sum_{ls}\max(0,\rho_{ls})$。历史有效 UB 可取最小值；可行 RMP 值可取最大值。LP 下界不是整数可行利润下界。

整数下界只来自通过紧凑约束检查的整数恢复/直接 MILP incumbent。完整列 LP 的 UB 也上界原 IP。若一个整数可行值和有效全局 UB 在所选容差内闭合，可以**另行**证明原 IP 最优；当前恢复例程没有自动签发这一证明，只报告差距。

Best Bound 若针对截断的最大化 PP，须是其最优值的上界且包含凸性常数。通用 CPLEX 后端原先遗漏常数，本次已修复；CBC 打印界按最后一位精度加半单位外向扩张并补常数。不可行状态的 bound 置null，不把其求解器残留值作为有效利润信息。CPLEX native_relative_gap 与补常数后重新计算的 relative_gap 分开保存。

目前 CG 不消费截断 PP bound，遇未证最优会中止；所以“基于截断 Best Bound 的全覆盖上界流水线”仍为 NOT IMPLEMENTED。CG_DERIVATION 证明该扩展的条件成立，独立验证以人为放松的合法PP上界检查修复后所有完整列的不等式。

## 数值边界

默认求解器 primal/dual=1e-8、MIP integrality=1e-7；CG ε=1e-7、Phase I 可行容差=1e-7；生产列局部判定1e-8；生产解可行性1e-6；dj/目标一致性及独立交叉验证1e-5。独立枚举局部判断1e-10。

容差有不同职责，并非统一单一数值；本次未为通过测试而放宽任何一个原约束。验收实例没有刻意卡在这些容差差异的狭缝内。终止误差按块数累加，不能把所有 epsilon 语义混用。当前是浮点容差下的数值最优证据，未实现有理重构或严格区间算术的机器可检验证明。极端缩放、溢出、近阈值输入仍需下一阶段数值政策。

## 独立复核入口

```powershell
experiments/.venv/Scripts/python.exe docs/research_audit/independent_validation.py --certificate docs/research_audit/evidence/acceptance_rebuilt/two_lines_cplex_py/result.json --instance docs/research_audit/evidence/acceptance_rebuilt/two_lines_cplex_py/instance.json
```

该入口不运行优化器：从保存输入独立重建局部全集及行向量，检查各轮 primal witness、对偶目标、符号、完整站点覆盖、全部列检验数、修复后的完整对偶可行性及最终LP可行解。不调用生产 make_column/coefficients/build_master/pricing 生成 oracle。

失败回归包括缺 dual、缺覆盖、重复/未知站、非有限数、正检验数、伪造终止、错误上界、人工残留、截断、定价optimal标志伪造和恢复异常。新回归不把时间截断标记为最优。

最终离线验收：`recheck_evidence.py` 无优化器调用地重放全部84份验收证书，均PASS；另外对上界、最终对偶、站点覆盖、PP最优标志、LP原始解和非有限对偶做6类篡改，全部被拒绝。并逐一确认验收运行的生产源码哈希与最终交付一致。原始结果在 `evidence/offline_all_certificates.json`。
