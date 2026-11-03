# 证据入口

- TASK03_1B_SUMMARY.md：逐项目结论与未完成项。
- INCREMENTAL_STORAGE.md：schema4列链/向量与内存边界。
- CHECKPOINT_RECOVERY.md：安全摘要与完整恢复严格区分，后者NOT IMPLEMENTED。
- TIME_AND_PROFILE.md：时间、异常、admission与组件计时口径。
- FAIR_BENCHMARK.md/JSON：25臂完整配对指标；evidence/pilot_audit.json保存逐臂witness检查。
- evidence/final_validation：116新完整搜索、22节点Oracle、10类伪造拒绝；每例输入和SQLite完整证明。
- evidence/final_cbc.txt、final_cplex_py.txt、final_accounting_tests.txt：91/92回归及4个最新预算测试；experiments_tests.txt为32原实验测试。
- evidence/forced_stop：已提交轮次后强制终止，摘要可读；不是完整恢复验证。
- evidence/schema3_compatibility.json：真实旧schema3文件通过当前独立重放。
- evidence/memory.json：137个固定前缀的tracemalloc专项；microbench/result.json为固定池/对偶的接口计时与数值对照。
- evidence/pilot30：冻结JSON及SHA、每臂SQLite、worker输出、accounting与admission回执。各metrics根保留cProfile exclusive原始数据及持久化分项。
- source_snapshot/SHA256.json：性能运行前固定的全部算法/worker源代码。SHA256.json为最终新增证据清单；BASELINE_CHECK.json核对输入与源码。

读取新旧证书均可使用现有 `experiments/task03_1_replay.py --instance <json> --result <sqlite或json> --output <新json>`；默认使用独立完整Oracle，`--offline`不重新求解完整LP/IP。生产求解不调用枚举Oracle。

incremental_tests、incremental_vectors、contracts、safety_gate和validation为开发轮保留；最终结论以final_validation和最终预算/回执测试为准，不把重复运行累加为独立实例。完整恢复对照、n30/40及120秒扩展NOT RUN。历史Task01/02/03/03.1数据未覆盖。
