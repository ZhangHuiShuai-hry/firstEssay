# Checkpoint 恢复验证与边界

**完整可恢复搜索：NOT IMPLEMENTED。中断后完整恢复与不中断求解结论对照：NOT RUN。**

本轮新增逐轮已提交证明、列链和原始变量向量，但这些不等于完整 DFS 状态。原实现仍只在初始时发布 safe_initial_frontier，可能包含已验证整数 LB，没有已完成的 DFS 队列/活动节点/父列池/阶段进度原子对应关系。不能用已存 pricing_round 拼装未经验证的剪枝。

新摘要明确 `recoverable_search=false`；预算记录 `search_resume_supported=false`、`recovery_kind=safe_summary_only`。`search_checkpoint.resume_search` 显式抛 NotImplementedError，避免错误地恢复。这个拒绝测试 PASS **不代表恢复功能通过**。当前生产程序不恢复 CPLEX 内部状态，也没有 pickle native 模型。

安全的完整恢复至少还需：在 pop 当前节点之前或完成两个子节点及入栈之后，原子绑定输入/源码/策略 SHA、完整历史节点和证明索引、processed 次序、DFS stack、父节点必要列池、当前 incumbent、界来源和未解节点。恢复应先验证 frontier 完备性与全部剪枝依据，再重建原生 RMP/PP；未完成的定价只能重做，不能当成无改进列。此闭包目前没有实现，因此本轮不宣称 P0-2 完成。

已实际运行的安全测试：事务 rollback、os._exit 未提交根回滚、对象损坏/缺失拒绝、硬停止不采纳最终证明、worker 异常和缺失证据分类、过期对偶与缺站定价拒绝。数学故障在重建旧格式后由独立 verifier 检查，内容 SHA 不替代数学证明。
