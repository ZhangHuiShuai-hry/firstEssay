# 候选找列与精确认证

原整线列域不变。主问题最大化利润，RMP资源对偶π≥0、凸性对偶σ_l，原价检验数为 c_p−π·a_p−σ_l。PhaseI维持旧广义弹性主问题、原价精确定价和不可行性判定。

PhaseII候选目标可使用另一组非负价格π̃。候选MILP即使时间截断，也可能返回合法整数列；每条列仍按原线约束核验，加入前按当前π和σ重算检验数并去重。候选目标值和候选求解器incumbent均不构成原价最大检验数的上界。任何候选轮都不直接更新全局UB，也不能据未找到新列判LP最优或节点不可行。

候选补列只扩大RMP列池：所有加入列都属于原域，下一次RMP及受限整数主问题仍给出原约束下的真实解。通过原MILP约束检查的整数witness才可更新LB。一个候选成功轮之后强制尝试原价认证；无新列当轮立即认证。有效已有UB与新LB若已闭合，可以安全提前结束，无须为流程形式再作一次定价。预算结束或异常也允许保留未证明状态。

认证轮使用当前原价π：每线原生最优RC，或reuse_v1历史证明推出的最大RC上界ρ̂_l。完整覆盖后，由提高凸性对偶至σ_l+max(0,ρ̂_l)，得到有效完整列LP上界 Zdual_RMP+Σ_l max(0,ρ̂_l)。因此全部ρ̂_l≤ε时，可按旧浮点政策证明LP最优达到块数累计精度。整数最优则额外要求已验证LB和有效UB在全局容差内闭合。正整数间隙仍可能存在，本阶段没有增加分支搜索。

已证最优的候选PP虽然不构成当前原价终止证明，但其完整原域、目标已核对的原生最优值可成为历史证明缓存来源；后续使用时必须按新价格重新推导界。这与把候选incumbent当成原价上界不同。缓存检查继承上一阶段同域SHA、无caps/分支、CPLEX101及局部列校验。

实现：engine.py以reuse_v1/engine.py为冻结参考复制，显式增加candidate_override，候选证书与认证证书使用不同列表；online.py管理四策略、时间份额和会话；check_candidates.py独立核对价格、历史参考、raw RC、补列及回退；audit.py以旧独立枚举/主对偶重放扩展，不调用生产定价生成Oracle。

证书版本candidate-certified-1。history中candidate_pricing保存原生候选状态与目标，candidate_added保存原RMP检验数和列索引，candidate_action保存价格、参考轮、α与预算，candidate_only说明本轮没有认证；pricing/complete_certified_pricing/repaired_upper_bound仅用于认证。pricing_audit_calls记录所有调用，索引严格递增。候选被拒绝或无进展的调用也保留。PP真实策略与原生时间在当前版本直接正确写入pricing_strategy/timing，修正了上一版注入接口下的统计口径。

数值政策与原生产一致，proof_scope为solver_floating_point_tolerances。软墙钟不是硬实时，候选上限也受native非抢占调用影响可能有小幅超出；记录实际耗时而不宣称硬上限。模型构建、验证、缓存和候选耗时纳入算法时间，会话释放纳入online_wall_seconds；最终写盘另行accounting。终止异常不丢弃已有证据，但不把未完成定价升级为证明。

命令：python RL/adaptive_v1/online.py <输入> --policy exact|short_raw|fixed|adaptive --seconds 60 --output <新目录>；python RL/adaptive_v1/audit.py <输入> <result.json.zlib> --output <新文件> [--no-enumeration]。所有输出均拒绝已有路径。
