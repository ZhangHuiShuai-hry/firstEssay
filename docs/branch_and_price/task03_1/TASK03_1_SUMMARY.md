# Task03.1 中文总结

**本轮整体 PARTIAL，不能标记全部完成。** 已真正实现并运行混合内容寻址证书、事务 checkpoint、进程级预算控制、冻结输入 pilot 及独立验证；保留原数学模型和 V0–V3 入口。剩余阻塞是内存/轮级证书表示、完整细粒度计时和严格端到端收尾语义。

|结论项|状态|实测依据与限制|
|---|---|---|
|数学正确性|PASS（已验证作用域）|双后端各83测试、原实验32测试；116历史完整树无损重放、22节点Oracle、10类伪造拒绝、12真实新搜索与历史最优/不可行一致|
|证书存储|PARTIAL|无损、SHA、事务/进程崩溃测试通过；116份结果27.86MB→6.92MB，约节省75.16%；仍保留完整内存历史，未完成轮级增量与释放|
|总墙钟公平性|PARTIAL|共同E2E起点、导入/建模/求解/验证/必要持久化计费，外层停止和迟到证明拒绝实现；Windows非硬实时、accounting收尾、异常映射与首解E2E偏移仍有限制|
|小规模性能|PARTIAL|10秒固定scout共10臂，7 timely、3 hard stop；数学与checkpoint安全检查通过；没有完整新旧端到端配对计时基线|
|中等规模性能|PARTIAL|n20×5seed×5方法共25臂30秒pilot全部执行、全部time_limit；没有整数最优证明，不宣称B&P整体优于Compact|

## 代码与证据

新增 `code/dwcg/evidence_store.py`、`test_evidence_store.py`；`branch_price_engine.py` 仅增加可选 evidence_sink、初始保守checkpoint和完成节点追加。原 NumericPolicy、PP、RMP、分支、全局界与剪枝公式不改。新入口在 `experiments/task03_1_*.py`：worker、budget、pilot、replay、validate、nodecheck、live、report。根 .gitattributes 增加本轮源文件字节保护。

新格式为存储schema3，数学载荷仍为旧certificate_version1/2，完整重建后由原独立 verifier 检查。旧JSON继续可读。SQLite FULL事务一次发布根及对象，SHA检查后解码；真实os._exit测试确认未提交根不会冒充完成。规范化JSON字节一致，不承诺恢复原缩进字节。保留全部开发失败与原Task01/02/03数据。

源码冻结在 source_snapshot/SHA256.json；验证在 evidence/storage_chunked、nodes、live_chunked、final_cbc/final_cplex_py、experiments_tests。116是历史完整结果迁移重放，不伪称116份全新运行；本轮新完整搜索12份。新旧同列池数学对照测试通过，但全面计时微基准 NOT RUN。

## 预算与实际结果

输入由主进程每例生成一次并冻结原JSON字节SHA，全部worker读取同一文件，禁止重生成和生成器见证。所有方法CPLEX单线程seed11，相同数值策略，独立进程串行、交替顺序；cold import计入预算，全部启用相同cProfile。30秒pilot 25臂中11份及时完整结果被采纳，14臂外层停止并读取保守checkpoint；最大实测超限约0.662秒。所有10个可用整数witness已重新通过原约束验证。

未及时形成完整证书时不采纳晚到的最优标志；checkpoint可以有经验证的V3初始LB而没有UB。未实现从checkpoint继续完整DFS搜索。未完成的profile和进程峰值内存保留null，不能填零。首解字段目前是原API相对时间，未补齐进程启动偏移，不能作精确E2E首解比较。未捕获worker异常仍须根据returncode/日志区分，顶层操作状态分类尚需完善。

完整逐臂LB/UB/Gap、真实时间、硬停止、采纳状态和证据大小见 FAIR_BENCHMARK.md/JSON。代表性seed51：V3 LB=358.28、UB≈367.613，绝对Gap≈9.333；Compact LB=359.68、UB≈374.308，绝对Gap≈14.628。V3有更强UB但更弱LB，不是整体支配或速度优势。两者均未证明整数最优。

## 瓶颈与下一步

压缩改善磁盘体积，但没有消除完整pool历史与asdict递归复制。seed41 V2的算法净时间约25.643秒，节点/最终持久化合计约0.880秒；原生MIPopt exclusive约11.601秒，asdict累计约6.425秒（含子调用，不可重复相加）。根LP已收敛但只处理1个节点。不能把困难全归因于写盘，也没有证据称已形成庞大搜索树。

P0-C仍PARTIAL：保存了每函数exclusive原始数据及互斥粗分组，但未严格拆齐PP创建/原生创建/目标更新/read、RMP创建/追加/read、列管理和核验证书各类别。原JSON独立写盘计时、全面同池微基准、116份全新搜索、n30/40及120秒扩展均NOT RUN。开发scout曾有39–43秒回收过载，已保留并修复为小摘要读取；该轮不纳入公平结论。

建议继续原生B&P与证书工程，暂不建立RL比较基准：先把每列/每轮表示规范化为一次写入的ID/增量，移除节点终点整树asdict复制，形成可独立验证的逐轮安全UB checkpoint；再补全独占剖析和预算收尾/异常/首解语义；之后改善整数LB获取与根初始化，重复更长预算对照。T03-4未引入，未用截断PP incumbent当上界。没有合并main。
