# Task03.1b 总结

**本轮整体 PARTIAL。** 增量列池/原始解表示、取消整节点asdict复制、逐轮事务证明、预算异常/admission语义已实际实现并验证；完整可恢复DFS搜索没有实现，不能称收尾全部完成。

|项目|状态|依据|
|---|---|---|
|P0-1 列池与节点重复复制|PASS（目标范围）|列链ID、不可变前缀、原始解坐标/权重视图；无整节点asdict；旧格式按需还原。仍保留轮次权重/对偶等必要历史，内存不是常数|
|P0-2 完整恢复搜索|NOT RUN / NOT IMPLEMENTED|只有安全LB摘要与逐轮证明，没有原子DFS状态闭包；恢复入口明确拒绝，不冒称恢复通过|
|P0-3 时间/异常语义|PARTIAL|启动与首解E2E偏移、solver_error/hard_stop/missing_evidence区分、accounting原子写入和独立admission；回执观察发布本身非硬实时，Compact内部首解未知|
|P0-4 完整组件剖析|PARTIAL|固定同列池微基准、RMP读回与持久化互斥分项已记录；全搜索统一互斥归因仍未覆盖所有组件|
|P1 小规模数学与有限配对复验|PASS（已运行范围）|116新搜索、22节点Oracle、10伪造拒绝；91/92回归、32实验组件、25臂pilot。完整恢复等价测试不在PASS内|

## 实际实现

新增 `incremental_evidence.py` 的 ColumnLedger/PoolView/PrimalView；修改 node_master_optimized 的快照构造及逐轮发布，branch_price_engine 的证书字段映射，task03 的可配置增量路径，evidence_store 的schema4列链/向量解码。旧默认API及原模型保持可用，schema3与旧JSON继续可读。

所有任务模式、对偶、人工、定价、原始变量权重、限制与剪枝证据保留。116新搜索逐项 canonical JSON 等价并通过独立Oracle。schema4只改变物理表示，最优性语义仍为原记录浮点容差下的证书，不是严格有理证明。

## 内存、存储和时间

固定同池137个前缀快照的tracemalloc峰值约955KB→49KB，时间约0.0148→0.0046秒。这是快照专项，不能外推整个进程降幅。可配对、原先有内存记录的B&P臂：seed11 V0约123.7→51.5MiB；seed41 V2约149.9→68.9MiB；seed51 V3约133.2→68.3MiB，搜索轨迹不同不能全部归于单一接口。

116新搜索SQLite总量约8.91MB，旧JSON约27.86MB，但上一轮混合压缩迁移结果约6.92MB；新列链/向量索引与逐轮记录存在额外开销，不宣称磁盘单调变小。中等规模总证据约26.42MB，旧轮约20.64MB，旧轮14臂没有完整结果，证据完整程度不同。

## 30秒配对结果

使用与Task03.1字节相同的n20五个冻结输入、同预算、CPLEX单线程seed11、同数值政策、独立进程串行、交替顺序。全部方法启用相同cProfile，导入和必要证据/accounting计费。完整表见 FAIR_BENCHMARK.md/JSON。

25臂全部及时发布最终结果、0硬停止，运行约25.24–25.76秒；上轮11/25及时、14硬停止。**25臂仍全部time_limit，没有中等规模整数最优证明。** 10个可用整数witness复查通过；V0/V1/V2均无整数LB，V3的5个LB来自已验证Compact短时间片，Compact五臂均有可行整数解。

证据发布能力改善不等于优化质量改善。例seed51：新V3 LB358.28、UB≈379.983；Compact LB359.68、UB≈375.369，Compact同时更好。例seed31：V2 UB≈318.002略强于Compact≈318.081，但V2没有整数LB。所有及时B&P结果只处理1个节点，根LP仍未证明收敛；没有观察到大搜索树，不能将超时归因于树大。

seed41 V2约6轮Phase I、42轮Phase II；算法净时间约21.156秒，节点持久化1.953秒、最终持久化0.322秒、其余2.177秒。profile中原生MIPopt exclusive约10.966秒，build_master cumulative约2.142秒。上轮该臂曾到60轮Phase II并证根LP最优；本轮没有复现更强根界，不能说全面加速。每轮FULL事务提交、接口成本与定价轨迹均会影响结果，cumulative不能重复相加。

## Checkpoint 与下一步

强制中止后摘要/已提交轮次可读取，不会宣布最优。缺少完整DFS队列、活动节点/继承界、父列池和阶段记录的原子闭包，`recoverable_search=false`，完整恢复测试NOT RUN。详见 CHECKPOINT_RECOVERY.md。

下一步应先实现并证明安全的节点边界恢复协议、完成全搜索互斥计时与持久化批处理的独立审计，再改善整数LB/根初始化与较长预算复验。暂不进入RL。未引入T03-4、未改变模型/分支/精度，未合并main。所有历史数据保留。
