# Task 03：保持精确性证明的 Branch-and-Price 性能工程与受控规模验证

> **任务状态**：待实施的工作说明；不是已完成的实验报告。  
> **上游基线**：`ZzzHry/firstEssay` 的 `main@4c3b67c0de70e090a4d0e96b558c2c91805ad60a`（Task 02）。  
> **实施原则**：先保证原模型与证明等价，再优化速度。禁止用不完整定价、根 LP 或受限 IP 的状态冒充原问题整数最优证明。

## 一、背景与目标

Task 02 已完成原始变量 `x_(l,i,s,m)` 的精确 Branch-and-Price（B&P），保留广义弹性 Phase I、合法列池继承、节点精确定价、双子域覆盖、有效树界、整数 witness、独立枚举/离线证书重放。已归档的小规模证据为 29 个输入 × CBC/CPLEX = 58 次完整搜索（48 次最优、10 次整数不可行），22 次独立节点专项、6 次中断/精度测试，另有 10 类伪造证书拒绝。该证据不能外推为中大规模效率。

**Task 03 目标**：

1. 降低节点内 PP 重复建模、PuLP→CPLEX 转换和 RMP 重建的开销，得到可审计的加速或明确的负结果。
2. 维持与 Task 02 完全相同的允许列集合、原 MILP 整数可行域、节点 LP 目标、分支树语义和上下界证明契约。
3. 在公平总预算内，提高获取**已验证整数可行解（全局 LB）**和有效上界（UB）的能力；重点解决较大算例下没有 incumbent 的问题。
4. 执行逐级、同输入、同预算的中等规模配对实验，判断哪些工程优化值得保留；不提前宣称 120/150 任务已验证或 RL 已带来收益。

Task 03 **不训练、不接入 RL**；RL 作为后续独立任务，不能污染此处的精确基线。

## 二、强制不变量（任何一项失败即停止对应升级）

- 原 `problem/main.tex`、`problem/dwcg/main.tex` 的数学语义不变：可选/必拆、AND 前序闭包、工作站顺序、H/R/J、节拍、线性化累计疲劳、最低回收、全局人机预算、站点配置利润均保持一致。
- 每个节点的 `x=0/1` 固定必须落实到**每个工作站定价的局部二元 `z` 域**及继承列池过滤；Branch 1 不得错误允许空列或放松所固定模式。
- Phase I 的站点凸性等式保持硬约束；**全部其他耦合 `<=` 行设单向弹性人工，`=` 行设双向弹性人工**。不能直接套用仅覆盖必拆/回收的 Task 01 `IncrementalMaster`。
- 只有全局原整数约束验证通过的 witness 能更新整数 LB。根 RMP 目标及受限列 IP 的 optimal 标志本身都不是原整数最优证书。
- 完整节点 Phase II 的有效上界仍由站点最优（或被严格核验的保守上界）检验数构造：
  `UB_node = max(z_RMP, z_dual) + sum_(l,s) max(0, rho_upper_(l,s))`。
  其中 `rho_upper` 必须是匹配当前节点、阶段和对偶向量的**站点最大 reduced cost 的上界**。PP incumbent 仅为下界，绝不可替换它。跨节点安全上界与父节点上界取 `min`。
- 保留 `optimal_within_tolerance`、`infeasible_proven` 与 `time_limit`、`node_limit`、`solver_error`、`numerical_uncertain` 的严格区别。数值/时间中断不能丢失活动节点或伪造 Gap=0。
- 保留 Task 02 独立验证器和已提交的全部原始证据/哈希；禁止删除旧失败、回写历史报告为「通过」、为了加速关闭 witness/检验数/证书核查。

## 三、实施顺序

### T03-0：冻结基线、剖析耗时（P0）

1. 基于固定提交新建独立开发分支；先确认 `docs/branch_and_price/`、`code/dwcg/`、`experiments/` 当前文件，不依赖用户再次上传附件。冻结基线源码 SHA-256、Python/PuLP/CPLEX/CBC 版本、CPU、线程、随机种子、容差。
2. 对 Task 02 原 B&P 新增**不改算法行为**的节点级计时：RMP 创建/转换/原生优化/读回、PP 创建/转换/原生优化/读回、完整检验证书核查、列数与定价次数、节点总时间；非重叠总计应与 wall-clock 近似对齐。先复跑 `single_line`、`two_lines`、`generator_n6_L1_s13`、`lp_yes_ip_no` 和代表性中断。
3. 记录基线实测值。若测量显示 PP 并非主瓶颈，报告原因，但仍需验证下述优化，不得虚构加速。

### T03-1：节点内持久化原生 CPLEX 定价（P0）

1. 复用 `code/dwcg/persistent_pricing.py` 的已验证原生建模思想，在 `node_pricing.py` 增设**可切换**的节点级 persistent PP 后端。每个 `(line,station)` 的同一个节点内建立一次局部 MILP；CG 轮次只更新目标系数及必要求解时限。
2. 原生变量、约束、任务—模式选择、`u/h/r` 双向关联、节拍、疲劳、Phase I/II 真实利润及所有对偶系数必须与当前 `price_node` 完全一致。站点凸性对偶常数必须进入返回 RC 和 best bound。
3. 每节点每工作站的固定 `z=0/1` 必须在求解前设置并受同一模型约束；可用显式变量上下界或原生约束。兄弟节点不得共享残留固定域。优先节点内复用，**不要求跨节点共享原生实例**。
4. 保持现有 `PricingCertificate` 及 `validate_pricing_evidence` 契约，注明后端、原生状态、局部固定域、精度、objective/best_bound、耗时。只接受原生已证明最优状态为 exact PP 最优；未证最优不允许生成“完整精确定价”标志。
5. CBC 继续使用当前可靠路径。任何 CPLEX-native 异常必须 fail-closed（保留未解节点），而非静默换成虚假最优。

### T03-2：节点内增量 RMP 与 Phase I/II 切换（P0）

1. 参考 `code/dwcg/incremental_master.py`，**新建**节点适配器，不破坏 Task 01 原模块。一个节点内保留原生 CPLEX LP RMP 和可能的可用基；合法列追加时仅插入新增稀疏列。
2. 对照 `code/dwcg/node_master.py::build_node_master` 逐行匹配凸性、任务、前序、共享资源、回收及所有弹性人工；检查 row sense、RHS、系数符号、目标、列顺序、duals 和 dj。
3. Phase I→II 将全部人工变量固定为 0，目标切换为真实利润；不能误把此前的人工作为可使用列。Phase II 首次原生 RMP 必须重新验证“没有人工变量”的真实可行性。
4. 必须支持 `legacy_node_rmp` 与 `incremental_node_rmp` 切换。保留当前数值签名和证明字段，扩展 schema 时提供版本号与旧证书兼容重放。
5. 任意节点 RMP/PP 失败时，正确释放 native 资源并保留安全上界和活动节点。

### T03-3：可验证的早期整数 LB（P1，独立开关与消融）

1. 当前 B&P 可能长时间无整数 incumbent。加入可选根级/搜索期间的 **incumbent acquisition**：例如给 Compact CPLEX 极短且计入总墙钟预算的时间片，或对现有 CG 列池求受限整数主问题；至少实现并验证一种方式。
2. 新解必须完整转化为每站任务—模式配置，经 `bp_solution.verify_integer_assignments` 与原紧凑约束、资源、回收、疲劳、优先、利润核验后，才能更新全局 LB。超时解必须确实存在且可读，不能仅凭 native `has_incumbent` 声明。
3. 任一受限 IP 返回 `infeasible` **不代表原问题整数不可行**；其 `optimal` 仅限受限列集合。补充列/缩短时间均不得放松本条。
4. 开关 `off / compact_warm_start / restricted_ip` 分别计时、计入各自公平总预算；不用来自输入生成器的构造见证作为只有一个方法享有的秘密 warm start。

### T03-4：中断定价的可核验上界（P1，条件实施）

在 T03-1 完成后，评估 CPLEX 对**未证最优 PP** 返回的 native MIP best bound 是否为可靠、方向正确、含站点凸性常数的最大化 RC **上界**。只有在全部工作站于同一最优 RMP 对偶下都有有效 `rho_upper` 时，才允许产生一个新的保守节点 UB，并逐站记录原生状态、最优性/界性质和数值校验。

若无法严格保证某个站点的 best bound 有效，则对应轮次不签发新 UB，继承此前有效界。即使拥有保守 UB，也不得把未经精确定价证明的 PP incumbent 当作“无正检验数”，不得直接宣布节点 LP 最优。独立构造至少三种故障输入：best bound 方向反转、漏加凸性常数、一个站点缺失 bound；验证器必须全部拒绝。

此部分可以单独列为未实现，并在报告中说明，不得为完成进度降低认证门槛。

## 四、验收测试（必须先正确，再谈加速）

1. **同节点同列池等价**：新旧 PP 在相同节点固定域、Phase I/II、同一对偶下比较最优 RC（允许不同等价最优列）；新旧 RMP 比较目标、dual-repaired UB、人工变量、最终 `x`、所有行/列与 dj。在退化情形不要求对偶数值逐项相同，但每个各自证书都必须独立成立。
2. **边界回归**：原 Task 02 的 29 个完整实例 × 两后端基线、22 个节点专项、6 个中断/精度测试以及 10 类伪造证书拒绝，保留原始版本继续通过；新的 native 组合额外跑相同小规模矩阵，不把 CBC 模式谎称成 native CPLEX。
3. **完整整数对照**：Task 03 B&P 最终目标/整数不可行状态与 Compact-IP 和独立 Full-IP 一致；节点 LP/PP 的完整列枚举 Oracle 验证；至少 `two_lines`、`generator_n6_L1_s13`、`lp_yes_ip_no` 必须有完整端到端证据。对浮点差异使用书面冻结容差，不事后调阈值隐藏差异。
4. **故障注入**：包括 Branch 1 遗失、兄弟残留固定域、Phase I 人工遗漏、缓存后对偶过期、PP/RMP timeout、无 incumbent、native solver exception、坏 best bound、失去活动节点；都必须显式拒绝虚假证明。
5. **独立重放**：Task 02 `certificate_version=1` 证书保持可验证；新证书独立离线重放通过。算法正式求解不能调用小规模枚举或独立验证 Oracle 生成列。

## 五、公平性能实验（先小后大）

按版本逐级配对，至少包含：

- **V0**：Task 02 基线 B&P（重建 RMP + 重建精确 PP）。
- **V1**：V0 + 节点内 persistent PP。
- **V2**：V1 + 节点内 incremental RMP。
- **V3**：V2 + 早期整数 LB（如已实现），单列消融。

先使用小例、测试边界及一组 n=10/20 的受控试运行检查是否能结束、内存和日志体积；再根据实际时耗执行合成实例两线、每线 n=20/30/40、种子 11/21/31/41/51 的分层试验。每臂固定相同的**总墙钟预算**（例如 120 秒；困难例另设 300 秒，不与前者合并），相同输入、线程=1、求解器 seed=11、同机器同求解器版本和数值策略；同一实例版本运行顺序交替，防止恒定先后顺序偏差。

同时保留 **Compact CPLEX-IP** 基线；它与 B&P 均以原问题整数可行解质量、有效全局 UB/Gap、最优已证率、首个 integer incumbent 时间和总时间比较。RMP/CG 根 LP 时间仅作单独的诊断指标，不能拿来证明整数算法更快。

每次尝试均记录：状态、整数 incumbent、有效 UB、绝对/相对 Gap、首解时间、节点数、PP 次数、总列数、每组件非重叠耗时、内存指标、是否超预算、日志/配置/哈希；不丢弃失败和无解样本。统计每个规模的成功率、中位数、Q1/Q3和所有样本状态。不同版本若产生不同合法搜索树，报告树大小与时间变化，不强行要求节点轨迹一致。

**120/150 总任务仅作为后续可选独立 scout**：在中等规模正确性和内存均通过、且有可负担预算后才运行；至少保存完整状态、实例、配置、日志。没跑就明确写 `NOT RUN`，不能从 Task 01 的旧根 CG 实验推断 Task 03 B&P 效率。

## 六、代码组织与交付物

建议新增而非破坏旧模块：

- `code/dwcg/node_persistent_pricing.py`、`code/dwcg/node_incremental_master.py`（命名可调整，但职责明确）。
- `code/dwcg/` 下新单测，保留原 `node_pricing.py`、`node_master.py` 可切换的稳定基线。
- `experiments/` 下独立 Task03 配置、runner、审计与统计脚本。
- `docs/branch_and_price/task03/` 下 `IMPLEMENTATION.md`、`VALIDATION.md`、`EXPERIMENT_PROTOCOL.md`、`RESULTS.md`、`LIMITATIONS.md` 和新证据索引。
- 新运行目录**必须不存在**，不得覆盖 Task01/Task02 历史输出；冻结源码和环境依赖、commit SHA、输入 SHA-256、原始 native 日志、逐节点证书、失败案例以及可复算报告。

历史 Task 02 文档中的 `HEAD=70d5bca`、`task02_pushed=false` 是执行完毕、尚未提交时的封存快照；2026-11-02 的 GitHub `main` 已为 `4c3b67c`。另写只增补的 `TASK02_POST_PUSH_AUDIT.md` 解释，不改 `SEAL_RECEIPT.json`、旧哈希或证据目录。

## 七、最终验收门槛与输出格式

**正确性是硬门槛，性能是实证结论**：原 Task02 全部测试仍通过；新旧节点域/LP/PP/整数值在冻结精度下等价；新的证书和故障注入有效；最终 B&P 仅在活动节点清空、整数 LB 与有效 UB 收敛时宣布全局整数最优或通过整棵树证明不可行。任何失败必须报告，不得因「运行更快」忽略证明缺口。

最终给出逐版本、逐实例的原始对照表及汇总，区分**实测收益、实测退化、截断无法比较**；解释加速究竟来自建模/转换、native 优化、重优化状态、缩小搜索树，还是 warm start，不能仅根据总时间推测。代码连同可复现测试提交独立 PR，经审阅再合并。

**明确禁止**：直接修改原模型使结果改变；对大例调用指数枚举作生产算法；以 RMP 的 LP 值更新整数 LB；以 PP incumbent 充当 PP 最优上界；将 partial pricing 标成完整精确定价；篡改或覆盖已封存 Task02 结果；预先声称尚未进行的实验或 RL 提升。

**交付时回答**：哪些版本完成、每项测试是否真的运行、29×双后端/22节点/中断与伪造证书实际通过数、每规模完整状态、相同预算下 V0/V1/V2/V3 和 Compact-IP 的整数利润/UB/Gap/时间、失败原因、下一阶段是否值得引入 RL，以及剩余证明/性能风险。
