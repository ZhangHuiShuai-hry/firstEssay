# 历史证明复用：首个非学习改进

本目录独立保存，原RL探针、sub、原MILP与历史字节不变。根节点完整整线域，Phase II，人工/机器人价格非负。尚未训练RL。

令历史精确定价值 q_k=max_p(c_p−π_k·a_p)，a=(h,r)。任意合法列满足 c_p≤q_k+π_k·a_p。故资源数量(h,r)下利润上界为 B(h,r)=min_k(q_k+π_k·(h,r)+δ)，当前价格π的定价上界为 Q=max_{h,r=0..K}(B(h,r)−π·(h,r))。资源不可行格仍保留，是安全放松；没有将全局资源限制加进线内列定义。δ=1e−8为向上数值余量，不改变旧数值容差政策；仍属于求解器浮点证明而非有理算术证明。

σ为当前线凸性对偶，若Q−σ≤旧RC阈值1e−7，则可不调用原生PP。该证书只是最大RC上界，并不声称计算出了精确最大RC或返回了最优列。完整轮修复界仍为RMP对偶目标+Σmax(0,RC上界)，逐块有上界即可由对偶修复证明有效；Phase I仍使用旧精确定价。

历史来源仅接受同一线输入SHA、完整根域、PhaseII、无caps/分支、CPLEX native101及经独立数据检查的整数列，核对目标、RC、Best Bound与σ。未证PP不进入缓存，没有扩展一般截断Best Bound契约。

离线轨迹按轮处理，先查询所有块，再加入本轮答案；RMP已知列只取当时pool_sizes前缀。当前轮、未来轮答案均不能为当前查询提供证明。历史源blob和输入记录SHA。

在线入口online.py显式price_override接入独立engine.py。engine.py以sub/stage9/cg_balanced.py为冻结参考复制，改动仅导入路径、证书版本和已认证定价块处理；新字段complete_certified_pricing与bound_certified明确区分原生精确结果和历史上界证书。没有伪造native101或把旧验证器默认视为兼容。audit_online.py以sub/validate.py的独立构造为基础扩展，检查历史证据、逐格上界、全部块覆盖、主问题原/对偶、人工变量、原整数witness及最终界；小例另做完整列LP/IP及逐PP最大值核验。

原始求解域不变。第一版仅筛掉已证明无正RC的块，不主动改变价格或CPLEX模型。被筛掉的调用不再更新该线CPLEX内部重优化状态，因此后续搜索成本可能改变，历史可免调用耗时不能直接当作在线节省。

实验为开发阶段，单线程seed11、gap0，旧NumericPolicy。在线两组使用相同独立引擎，唯一配置差异reuse开关；短经济初始化0.5秒，其余为旧默认。不运行资源档位后处理，以隔离筛选影响；不声称它与已发表实验生产链完全相同。软算法预算含建模/核验/缓存检查，最终写盘单独accounting；不是严格外部watchdog公平预算，不与历史Compact做新的公平速度结论。

运行：python RL/reuse_v1/test_cache.py；python RL/reuse_v1/replay.py --output <新目录>；python RL/reuse_v1/verify.py <轨迹目录> --output <新文件>；python RL/reuse_v1/online.py <实例> --output <新目录> --seconds 60 [--no-reuse]；python RL/reuse_v1/audit_online.py <输入> <压缩结果> --output <新文件> [--no-enumeration]。
