# 总墙钟与 checkpoint 审计

入口 `experiments/task03_1_budget.py <冻结输入> <新目录> <V0/V1/V2/V3/Compact> <秒>`。父进程在启动 worker 前开始 perf_counter，传共享绝对 deadline；Python 启动、导入、输入读取/字节 SHA 校验、建模、全部求解、整数验证、节点持久化、最终完整证书、profile/摘要持久化与父进程摘要检查均消耗预算。预留 max(0.5秒, 启动后剩余预算20%) 给持久化。

父进程 watchdog 只终止自己的 worker。Windows 调度、进程创建/kill/wait、SQLite rollback 不能保证硬实时；真实 overrun 明示，不能称零超限硬保证。搜索使用软截止，外层采用进程级停止。记录 worker_seconds、end_to_end_seconds、hard_stop、worker_returncode、final_admitted、overrun、恢复错误。派生 accounting.json 写入后另观测 accounting_finished_seconds；该收尾计时目前不回写其自身文件，而存在汇总返回值，因此正式严格端到端验收仍为 PARTIAL。

最终完整数学结果由事务 result 根发布，随后 summary 根记录对应 result SHA。父进程仅读取小摘要及核对根绑定；完整解码/独立重放属于离线审计，不纳入在线搜索预算。只有正常退出且摘要检查在截止内完成，才采用最终结果；超时或异常一律不能用迟到的最优标志。后续离线完整 SHA/数学核验仍是证书有效性的必要条件，摘要本身不独立证明全部对象未损坏。

初始 checkpoint 是 root 未解、UB=null、无最优证明。V3 的已验证初始 witness 可保存在 safe_initial_frontier checkpoint 提供 LB；尚未实现从它继续原 DFS 栈搜索。节点完成时追加 node 根，但它们不被拼接成未经验证的全局证明。若中止，只报告此前已完整提交并可读的保守 checkpoint。未提交 SQLite 事务自动 rollback。没有及时 checkpoint 时明确记录不可恢复，而不是伪造可行方案或 Gap=0。

开发 scout 中父进程曾读取整份 result，导致 10秒预算总耗时约39–43秒，记录保留于 evidence/scout/；已修复为读取小摘要。该轮混用了开发代码且有并发测试，不用于公平比较。固定源码与输入的后续 scout/pilot 独立归档。

时间不重叠的粗分组：algorithm_excluding_node_persistence、node_persist_seconds、final_persist_seconds，以及 E2E 减上述总和的残余。algorithm_seconds 包含节点写盘；不能再把 evidence_total_seconds 与它直接相加。metadata/profile 发布、导入、父进程校验等归入残余。精确逐项 PP/RMP 创建/翻译/读回分类尚未完成，见 PERFORMANCE_PROFILE。
