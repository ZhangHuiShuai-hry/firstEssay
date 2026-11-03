# Task03 中文总结

**结论：V0–V3 均有可运行入口，最终小规模正确性验证通过，原整数全局最优/不可行证明能力保持。Task03 整体状态为 PARTIAL：细粒度剖析、严格总墙钟公平性及最终代码的中等规模性能复跑尚未完成；T03-4 明确未实现。没有将这些未完成项标成 PASS。**

## 1. 实际完成模块

|阶段|状态|实质交付|
|---|---|---|
|T03-0 基线冻结|PASS|fetch 正式任务书、新分支、代码 SHA、环境与数值策略、原始源码/历史数据不变|
|T03-0 耗时剖析|PARTIAL|节点 PP/RMP/剩余总计、native 原始求解字段；未逐项拆尽 V0 转换、证书与列管理|
|T03-1 持久化节点 PP|PASS（小规模证明域）|每节点每块独立 native MIP；固定域、全部目标更新、两阶段、状态/数值检查、资源释放与 Oracle 回归|
|T03-2 增量节点 RMP|PASS（小规模证明域）|原生 LP 追加列、全部弹性人工、Phase I→II 固定人工为零、primal/dual/dj 校验；验证镜像仍重建|
|T03-3 可验证整数 LB|PASS（已实现路径）|compact_warm_start；完整原约束 witness 验证、计入预算；restricted_ip 路径未实现|
|T03-4 截断 PP bound|NOT IMPLEMENTED|不签发新 UB、不伪报完整定价；对应三类专项 NOT RUN|
|小规模独立验证/回归|PASS|最终 79×两默认后端单测、138 小规模检查、116 树重放、10 类伪造拒绝、12 native 停止证书|
|受控规模运行|PASS（实际执行）/PARTIAL（性能验收）|20/30/40 每线任务×5 seeds×5 方法=75 臂，全部保留；软预算超限，全部 time_limit|

## 2. 新增文件与版本

原有已跟踪核心文件没有修改；新增：

- `code/dwcg/branch_price_v0.py`、`node_master_v0.py`：冻结 V0。
- `node_persistent_pricing.py`、`node_incremental_master.py`、`node_master_optimized.py`：可切换的 native 节点路径。
- `branch_price_engine.py`、`task03.py`：兼容树引擎、版本 API/CLI、V3 acquisition、计时与哈希。
- `test_task03.py`、`test_task03_faults.py`：13 项 adapter 专项。
- `experiments/task03_validation.py`、`task03_replay.py`、`task03_interruptions.py`、`task03_benchmark.py`、`task03_report.py`、`task03_medium_audit.py`。
- 本目录的实现、协议、证书补充、验证、结果、限制与证据索引，以及独立 `task03_verify.py`。

V0 重建 PP/RMP；V1 持久化 PP；V2 再增量 RMP；V3 再增加短 Compact acquisition。CBC 维持 legacy 路径，native 加速仅 CPLEX。独立 V0 CLI 和原 Task02/根 CG CLI 保留。可运行示例见 EXPERIMENT_PROTOCOL.md。

## 3. 正确性与证明结论

最终封存检查：CBC 默认 79 tests、CPLEX 默认 79 tests 均 OK（部分测试内部显式切换后端）；历史实验组件另 32 tests PASS。29 输入×V0/V1/V2/V3=116 次完整搜索中，96 次整数最优、20 次整数不可行；再加 V1/V2 的 22 个节点专项，138/138 PASS。116 树离线重放通过，10 类伪造全部拒绝。V1/V2 各 6 种停止/精度情形共 12 份证书通过，均保留活动节点、未伪报最优。

Task02 原双后端 58 次完整搜索（48 最优、10 不可行）、22 节点及 6 中断/精度检查也重新运行。所有初期装载错误、runner 路径错误与一次 fixture 误标均保留并解释，见 VALIDATION.md；不计入最终 PASS。

**能够在记录浮点容差下，对已完成的小规模实例真正证明原 MILP 整数全局最优或不可行。** 依据依然是原 x 完备分支、合法节点域、广义 Phase I、完整精确定价、修复对偶上界、原始整数 witness 和完整安全树闭合；不是根 LP 或受限列 IP 的 optimal 标签。

|实例|Root Full-LP|Compact-IP/Full-IP/B&P 整数结论|V0/V1/V2/V3 最终界|
|---|---|---|---|
|single_line|21|最优 21|LB=UB=21，Gap=0|
|two_lines|27|最优 24|LB=UB=24，Gap=0|
|generator_n6_L1_s13|59.38|最优 56.63|LB=UB=56.63，Gap=0|
|lp_yes_ip_no|可行|整数不可行|完整搜索树 infeasible_proven|
|mandatory_negative|-8|最优 -8|LB=UB=-8，Gap=0|

最终证书和输入在 `evidence/sealed_validation/<实例>_<版本>/`；独立结论在同目录 verification.json 和 `evidence/sealed_replay/summary.json`。完整原模型/IP/LP 数值对照在 `evidence/task02_full/`，节点专项也独立求完整 LP/IP。

## 4. 性能实验实际结果

完整 75 行利润、UB、Gap、时间、首解、节点/PP 次数与 15 个分组统计见 RESULTS.md/RESULTS.json。每臂名义 5 秒、线程 1、seed 11、相同输入、交替顺序、独立进程。全部 time_limit：V0/V1/V2 都没有整数 incumbent；V3 和 Compact 各 15/15 有已验证整数方案；没有中等规模已证最优。没有省略超时样本。另行复查 75 条输入/性能快照/完整定价标志，并对全部 30 个整数 witness 重新实施原约束验证（medium_audit.json）；这不等于完整域 LP/PP 枚举认证。

示例：两线每线 20 任务、seed11（性能源码快照；软截止，不作严格胜负排名）：

|版本|整数 LB|有效 UB|绝对 Gap|相对 Gap|实际秒|
|---|---|---|---|---|---|
|V0|无|502.7008|null|null|6.677|
|V1|无|339.7589|null|null|7.281|
|V2|无|351.2036|null|null|8.046|
|V3|301.63|364.2435|62.6135|20.7584%|7.370|
|Compact|305.43|320.5089|15.0789|4.9369%|5.034|

V3 这例首个已验证整数解为约 1.064 秒；Compact 首解时间未解析而为 null。PP incumbent、PP best bound、RMP LP 值和整数 LB 明确分开。

## 5. 相比 Task02 是否实际加速，来自哪里

小规模完整求解有单次耗时改善，不能声称统计稳定或所有输入改善。最终封存轮 two_lines：V0 1.837 秒、V1 1.294 秒、V2 1.190 秒、V3 1.389 秒；n6：0.696/0.587/0.495/0.513 秒。single_line 的 V2 因退化 LP 得到不同合法树（7 节点，相比 V0 的 1 节点），并未复现 V1 的改善。

组件数据支持 PP 重复建模减少、V2 原生 LP 求解/读回耗时下降，但 RMP 镜像构造/同步仍存在；不同树和不同 PP 次数使总时间不能全部归因于某个组件。V3 的首解改善直接来自计费的 Compact acquisition。

中等规模并无已证整数完成，不能计算完成时间加速比。更快 CG 轮次产生更大的逐轮 pool/证书：n20 seed11 结果 JSON 为 V0 约 9.39 MiB、V1 12.74 MiB、V2 16.91 MiB，写盘和序列化抵消收益。软截止后最长总超预算约 3.95 秒；因此严格相同总墙钟公平性是 PARTIAL。

## 6. 失败、超时和剩余问题

75 个中等规模臂全部超时，未发生 watchdog kill；5 seeds 的所有状态均在 RESULTS 保留。最终小规模功能/Oracle 无 FAIL；初始命令/runner 错误有原始日志并已修正。

主要待完成项：P0 细粒度计时；证书存储/写盘预算控制；最终代码中等规模矩阵重跑与较长预算重复实验；T03-4 完整截断 bound 契约；可选 restricted-IP acquisition。中等规模不做指数枚举，未宣称全部域独立离线认证。性能快照后增加 PP 显式数值检查、截断 incumbent 元数据和日志防覆盖，最终小规模全矩阵已重跑，但最终代码的 75 臂性能复跑 NOT RUN。

## 7. 下一阶段建议

先继续性能工程，**暂不引入 RL 辅助定价**。优先级：

1. P0：不减少审计信息的追加/去重证书存储，完整细分计时，外层严格墙钟/持久化 checkpoint；解决当前数 GiB 证据和 deadline 后写盘问题。
2. P0：同列池比较再优化 RMP 镜像，利用已验证 witness 的站点列初始化，降低 Phase I 和无 incumbent 风险；全部保持原证书回归。
3. P1：最终固定代码在更长且严格相同总预算下配对复跑，重复统计树大小与组件开销；然后决定是否值得实现截断 PP bound 或 RL。

当前足以保留正确性通过的 native 版本作为可选路径，不足以宣布 Task03 性能目标全面完成或中大规模优于 Compact-IP。原模型、旧证据未改，当前分支只包含新增工作；没有 commit、push、创建 PR 或合并 main。
