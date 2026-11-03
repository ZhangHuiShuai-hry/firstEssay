# Task03 证书补充说明

## 与 Task02 的关系

所有 node.restrictions、initial_pool、逐轮 pool/solution/duals/artificials、逐块 pricing、repaired_upper_bound、branch/pruning、open_nodes、global LB/UB/Gap 原字段保留。V0/V1/V2 使用 certificate_version=1；V3 使用 2，增加 `initial_incumbent`，这是已独立验证的原整数方案，不需要 Compact optimal 状态才能作为 LB。

新入口 `task03_verify.py` 从初始 witness 恢复初始 best，再按原 DFS 顺序验证分支、incumbent 更新、剪枝与活动节点。整数 witness 的校验仍来自原始数据级独立 Oracle；完整列枚举仅用于验证，不被生产算法导入。版本 1 的证书仍由原 Task02 verifier 重放；版本 2 需使用补充入口。

## Native PP 状态与数值契约

- native 101 + 有限 primal/row slack/整数性通过 + 列局部/分支合法 + 目标/RC/最优 bound 一致，才返回 optimal=true。
- native 103 只表示该块局部域已证为空。在节点初始化中可证明节点不可行；完成局部非空确认后的普通定价若发生 103 则 fail-closed。
- native 时限状态记录 time_limit。存在真实 native incumbent 时保存 has_incumbent/objective/incumbent/best_bound，但不返回可冒充最优定价的 column，optimal=false。
- 不明确状态、异常或读回数值检查失败不会签发 exact 证明；记录 solver_error，树保留 unresolved 节点。

同一节点内固定域不随轮次改变；目标每次完整重设。每个节点/兄弟各自新建 native 对象。finally 释放 PP/LP。只读取当前调用新增的记录，避免把前次 native_status 当成本次求解结果。

## Incremental RMP 的数学等价

令本轮旧重建模型矩阵为 A、右端 b、目标 c。适配器逐行保留 row sense/RHS，新增变量以整列 A[:,p] 追加，按名字关联 mirror 变量并读回 primal/dj/dual。对 Phase I 所有非凸性行保留原人工列；Phase II 将其原生上界固定为零，因此投影至真实列空间与无人工重建模型相同。原生状态 LP=1 后仍执行原始 primal、对偶符号、强对偶、dj 与 RC 检查。

对任意真实节点完整列与当前可行对偶，修复每个凸性对偶增加 `max(0,rho_ls)` 可覆盖遗漏列对偶不等式，所以 `max(z_primal,z_dual)+Σmax(0,rho_ls)` 是节点 LP 上界。等式凸性与完整块覆盖是必要条件；浮点误差按原 NumericPolicy 处理。所有树界与继承界取 min；整数 LB 只来自可行 witness。

没有使用“未证最优 PP 的 incumbent”修复对偶。T03-4 未接入时，即使日志保存 best_bound，也不会因此签发新轮次 UB。已有有效节点界、继承界在停止时继续保留；没有有效有限界则为 null。

## 新增观察字段

- task03_version、adapter_sha256：明确实际节点适配器与树引擎，而不只记录旧源码 SHA。
- acquisition：模式、用时、Compact 求解结果；初始 witness 独立校验。
- component_timings：节点 PP/RMP/剩余与总耗时，不是 proof 计算依据。
- first_integer_seconds：验证完成时间，null 表示没有观测到整数方案。
- 节点 elapsed_at_completion：首解观察用途；不参与界证明。

这些是浮点数值证明。对小规模完整枚举域可独立重算全部节点 LP/PP/树结论；对中等规模尚不能离线指数枚举全部域，不能声称严格机器可检验有理证书。
