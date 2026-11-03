# 实际验证

- 新增量表示：12个集成搜索通过 canonical JSON 字节等价和独立 Full-LP/IP/PP/树重放；前缀改变、回滚后重复写入等专项通过。
- 最终矩阵：`evidence/final_validation` 为116个**全新**搜索（29实例×4版本），最优值/不可行性与历史一致；22个节点完整Oracle、10类数学伪造拒绝均通过。不是只迁移旧结果。
- CBC 默认91 tests、CPLEX默认92 tests通过；两者计数不同是新增accounting测试在CBC之后加入，额外 `final_accounting_tests.txt` 的4个预算语义测试全部通过。显式Cplex专项不等于每项都使用默认后端。
- 原实验组件32 tests通过；固定池/固定对偶微基准通过数值等价，原始时间见microbench/result.json。
- 进程在已提交轮次后被强制终止：forced_stop/result.json 确认有 pricing_round、摘要可读、全局最优/不可行标志为false；这是**安全停止**测试，不是恢复搜索测试。
- schema3对象损坏/缺失、事务崩溃回滚、过期对偶、缺少工作站定价证明拒绝测试通过。
- `resume_search` 显式拒绝完整恢复；完整中断/恢复与不中断结论等价验证 **NOT RUN**，功能 **NOT IMPLEMENTED**。
- n20五seed×五方法25臂全部运行；全部time_limit，全部及时采纳、无硬停止。25回执绑定accounting SHA、输入字节与上一轮相同、10整数witness复查通过。完整列枚举不用于普通规模生产求解，中等规模不声称完整离线枚举认证。

结果来自冻结源码，性能记录不含并行验证负载。原Task01/02/03/03.1报告与数据未覆盖。完整组件计时仅在微基准中分解；全搜索的完整统一独占分类仍PARTIAL。没有调整数值容差隐藏失败。
