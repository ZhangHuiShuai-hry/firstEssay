# Task03.1 验证

已实际运行：

|检查|结果|证据|
|---|---|---|
|存储往返、去重、别名隔离、损坏/缺失拒绝|PASS|store_chunk_tests.txt|
|进程 os._exit 后回滚未提交根|PASS|store_chunk_tests.txt，共4 tests|
|历史116完整搜索：规范化字节与完整数学重放|PASS|storage_chunked，116/116；含 Full-LP/IP/PP、Phase I、树、witness|
|十类伪造数学证书重新压缩后拒绝|PASS|storage_chunked/faults.json，10/10|
|22独立节点 Oracle 经新存储重放|PASS|nodes/summary.json|
|新搜索接入 CAS 对照历史最优/不可行|PASS|live_chunked：two_lines/n6/lp_yes_ip_no × V0–V3，12/12|
|原算法、PP/RMP、故障、Compact 单测|PASS|final_cbc：83 tests；final_cplex_py：83 tests|
|原实验组件回归|PASS|experiments_tests：32 tests|
|固定10秒 scout|PASS（停止安全检查）|scout_fixed：10臂，7 admitted、3 hard stop；audit验证witness与未证最优标志|
|116份全新搜索而非历史重放|NOT RUN|本轮是116份历史证书迁移/重放，加12份真实新搜索；不伪称116份新运行|
|PP/RMP全部组件同池计时微基准|NOT RUN|旧数学等价专项继续通过，但完整新剖析分类尚未实现|

所有损坏测试和数学伪造是不同层：SHA 检查拒绝字节损坏；合法重算 SHA 的假数学证明仍须独立 Oracle 拒绝。生产求解不导入枚举器。旧 JSON 继续被统一入口读取，新 SQLite 按完整 legacy schema 重建后交给原独立 verifier。

失败记录全部保留：scout 开发轮的整份解码回收造成39–43秒总耗时（名义10秒）；该轮与开发验证并行且源码发生修正，不能作为公平实验。storage_validation、storage_final 为开发中逐容器DAG测量，最终采用 storage_chunked。小文件数据库页开销可能使数据膨胀。没有把这些负结果删除或标记加速。

计数不相加为新的独立实例。最终节点/全局搜索证书仍是浮点容差证明，不是严格有理数证书。pilot30 的执行状态/数据以 FAIR_BENCHMARK.md 和原始 summary.json 为准，不能把超时自动计为数学验证失败或整数不可行。
