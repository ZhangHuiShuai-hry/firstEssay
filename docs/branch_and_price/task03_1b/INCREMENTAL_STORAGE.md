# 增量证书与内存

schema4 与旧 schema3 共存。原数学 certificate_version=1/2 不变，旧 JSON/SQLite 仍可读取。`incremental_evidence=True` 开启新表示；原 API 默认保持 legacy 列池表示。原数学模型与 NumericPolicy 不变。

ColumnLedger 只追加不可变 assignments，验证旧前缀未被替换；PoolView 保存每个 line/station 的列数。存储将每个新增列写成带前驱 SHA 的 column_link；一个历史列池只引用列链尾和长度。列 ID 的作用域包括 line/station，assignment 相同的内容可以共享物理对象。链读取检查 SHA、长度和终止点。

PrimalView 保存原始变量坐标和完整权重向量，assignments 从相应列 ID 推导；保留全部零权重与负零。这样每轮原始解不再重复复制任务模式列表。所有对偶、人工、定价状态、目标、reduced cost、分支、剪枝仍原样保存。

节点证书使用 dataclass 字段的浅映射，移除整份 asdict 递归复制。轮次在完成或已知未完成状态时追加 pricing_round 事务，带完整节点 restrictions；它是证明记录而不是恢复搜索状态。节点与最终结果引用同样的列链与原始解向量。legacy 视图在独立验证或显式 JSON 输出时按需展开，规范化 JSON 字节必须相同。

存储 timing 分成 serialize_hash、compress、sql_execute、commit、other；同一次成功 put 的分项与总耗时相加一致。它们是 persistence 总量的子项，不能再次加到已包含写盘的 algorithm wall 上。失败事务不发布 root，内存 hash cache 仅在成功 commit 后更新。

固定同列池的137个前缀快照专项：旧表示峰值954,528 bytes，新表示49,169 bytes；耗时约0.0148/0.0046秒（tracemalloc 开启）。此测量仅覆盖列池快照，不是整个 B&P 的内存降幅。新旧完整进程峰值及最终证据大小应看受控 pilot，不可由该专项外推。

剩余成本：所有轮次的权重、对偶与定价仍保留在内存，尚未全部替换为按需磁盘读取；node/end/global 编码仍会遍历证明记录，并非零成本。列链视图消除了增长列池与 assignments 的重复保存，但不能宣称整个证书内存已恒定。
