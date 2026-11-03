# 性能瓶颈与归因

基线为 `198799c42f9fee61842edd33332f7aaec456ff50`，开始时工作区干净，新分支 task03_1/storage-budget。原始 MILP、数值政策和分支规则不变，仅给 branch_price_engine 增加可选 evidence_sink；旧调用不变。Task03 的 source_snapshot 是旧性能版本，sealed_validation 是后期正确性版本，本轮不混淆二者。

重复位置：node_master_optimized 每轮 pool_snapshot 保存完整增长池；solution 又含 assignments；branch_price_engine 用 asdict 复制整个 NodeCertificate 后保存节点文件，再把同一节点嵌入全局 node_history；Task03 worker 最终 indent=2 dump 再写一份。V3 的整数方案还可同时存在 initial_incumbent、incumbent_update 和最终 incumbent。不能因重复而删除证明字段，故以存储层去重和压缩处理。

两次实测设计演化：完整容器 DAG 的大量对象/SQL 解码比预期慢；缓存编码对象后仍有页与哈希成本；最终采用节点证书整体压缩块，在保留内容哈希的同时减少微对象。这说明只增加 CAS 不必然加速。

worker 保存 cProfile 每函数 exclusive/cumulative/calls（SQLite metrics 根），以及原节点 component_timings、PP 原生记录、RMP 原生信息。exclusive 可相加；cumulative 不可相加。algorithm_seconds 中已含节点写盘，另给排除该部分的净值；额外 final persistence 与剩余时间分开。

**P0-C 为 PARTIAL。** 虽有完整每函数 exclusive 原始数据，尚未可靠将共享 CPLEX 内部函数时间分别归属 PP 创建、目标更新、PP read、RMP 创建/追加/read、列管理和证书核查全部互斥类别；不能用累计时间或按调用次数分摊冒充严格分解。同列池 PP/RMP 的数学对照由现有专项测试复跑，但完整新旧同列池计时微基准 NOT RUN。

因此只可确认减少重复 JSON 写盘的机制；暂不能把总时间差严格归因于 basis 重用、PP 接口或搜索树。cProfile 对 Python 调用密集方法本身有额外开销，所有 pilot 方法同样启用，但不代表未剖析版本的纯求解性能。

旧15个软预算配对中 Compact 的 LB/UB 同时不劣于 V3，不能只解释为写盘：V3 给 Compact 的 acquisition 仅占总预算20%且最多2秒，剩余时间需 Phase I、根 LP 和分支；早期 witness 没有注入根列池。PP/RMP 接口改进不会自动解决这些算法结构成本。新记录应结合 root状态、阶段轮次、PP次数、节点和界，不从无 incumbent 或大 Gap 单独断言“树太大”。

## 30秒 pilot 中的可复查瓶颈

seed41 V2：Phase I 为6轮、Phase II 为60轮，根LP已证最优，但只处理了1个节点。互斥粗分组约为算法净时间25.643秒、节点持久化0.491秒、最终持久化0.389秒、其他0.840秒，合计约27.362秒。**实际写入并非唯一或主要成本**。

该臂 metrics 的 cProfile 中，原生 CPXXmipopt exclusive 约11.601秒；dataclasses._asdict_inner exclusive约2.283秒、cumulative约6.425秒；copy.deepcopy exclusive约1.358秒；master.build_master cumulative约1.842秒。这些 cumulative 包含子调用，不能相互或与exclusive重复相加。它们直接揭示节点结束后 asdict 递归复制/证书生成成本，以及真实定价求解和镜像建模成本，不能统称写盘。

及时返回的其他B&P臂也仅处理1–2个节点；本轮没有支持“大搜索树导致超时”的完整观测证据。硬停止臂未发布完整profile，根LP状态与耗时细分未知，不能推断其Phase I已结束。seed51 V2/V3根LP已证最优，上界约367.613，低于Compact的374.308，但V3的整数LB358.28仍弱于Compact359.68，说明更强DW界与更好的整数可行解是两个不同问题。
