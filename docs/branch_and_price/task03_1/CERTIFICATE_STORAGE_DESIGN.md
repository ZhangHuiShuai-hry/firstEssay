# 证书存储设计

存储 schema=3；数学载荷仍是 Task03 certificate_version=1/2，不改字段或证明结论。`code/dwcg/evidence_store.py` 提供 JSON / SQLite 统一读取。新重放入口：`experiments/task03_1_replay.py --instance <json> --result <sqlite或json> --output <新json>`，默认独立枚举，`--offline` 不重新优化完整 LP/IP。

SQLite objects 表以 canonical UTF-8 JSON 的 SHA-256 为主键，payload 为 zlib level1；roots 表按序追加 kind/hash/version。普通索引容器使用带类型标记的引用；含 rounds/restrictions 的完整节点证书作为 JSON 压缩块，避免大量微小 SQL 对象。相同节点证书在节点根与全局结果根间复用。列、对偶、人工、PP 状态、原始 x、固定域、分支、剪枝和活动节点全部保留。

写入一个根及全部新对象在同一事务，synchronous=FULL、SQLite journal 原子提交。崩溃未提交根不可见；进程 os._exit 的真实崩溃测试确认保留旧根。SQLite 的持久性依赖本机 NTFS/设备正确执行 flush，不是硬件断电数学保证。读取逐对象解压、校验 SHA、再解码；缺对象、损坏、非有限 JSON 均拒绝。缓存已经校验的编码对象，解码仍创建独立可变容器，防止共享列表污染。

等价性是规范化 JSON 字节完全相等；原文件缩进/键序不承诺原字节重建。116 份历史完整结果通过 canonical-byte equality 和独立 Full-LP/IP/PP/树重放，22 个节点同样通过；12 个新运行树验证接入 hook 后的正确性。10 类数学伪造即使重新生成合法内容哈希仍被拒绝；内容哈希不是数学证明。

开发记录均保留：第一版逐容器 DAG 为 15,831,040 bytes，重建累计约 33.90 秒；最终混合分块 6,918,144 bytes，对比原 JSON 27,855,020 bytes，约节省 75.16%。最终验证轮累计写入 6.21 秒、重建 8.82 秒、独立重放 27.38 秒。这是开发期测量，不能当作隔离硬件下的新旧运行加速比。原文件未重新写盘计时，因此原 JSON 写盘基线 NOT RUN。

限制：仍在内存中保留完整 rounds/pool/node_history，尚未实现按轮增量持久化和释放内存。CAS 写入会暂存规范化 JSON；小输入受固定数据库页开销影响，可能比原 JSON 大。当前避免磁盘重复，不能宣称解决全部内存重复。节点写入与最终全局写入仍会重新遍历相同证书，内容复用不会消除全部编码成本。
