# Task03 实现说明

本目录是 Task03 的新增工作，不改写 Task01/02 的证据。基线是 Task02 `4c3b67c0de70e090a4d0e96b558c2c91805ad60a`；实现分支从任务书提交 `5a95dd793f2f84d82a7431f9dbcc3142abcc482a` 建立。两者差异仅为任务书及 post-push 审计文档。最终状态、实际数字及未完成项以本目录 SUMMARY、VALIDATION、RESULTS 为准。

## 版本与调用

- V0：`branch_price_v0.py` + `node_master_v0.py` 冻结原算法；统一实验 API 的 V0 使用同一节点算法与兼容树引擎。
- V1：V0 的数学结构 + `node_persistent_pricing.py`。每节点每块各建一次 native CPLEX MIP，固定域在构造时设置；每轮完整更新目标（包括 Phase I 清除利润、凸性对偶常数）。不跨节点共享 native 对象。
- V2：V1 + `node_incremental_master.py`。每节点一个 native CPLEX LP，追加新列，保留基状态；广义 Phase I 人工按原行结构建立，进入 Phase II 后全部人工上界设零、清除旧目标并设置真实利润。
- V3：V2 + Compact 短时间片获得整数 witness。时间片 `min(2 秒, 总预算的 20%)` 计入总预算。只有 `verify_integer_assignments` 通过才提供初始整数 LB；失败保持无 incumbent。未实现 restricted-IP 获取方式。

`task03.run(data, version=..., solver=..., time_limit=..., output_dir=...)` 显式选择版本。CBC 保持原重建式路径，不声称支持 CPLEX-native 加速。原根 CG、Task02 B&P、Compact 数学模型及历史实验入口原样保留。

## 数学与证书不变量

允许列仍为 Task02 局部整数集合与节点固定域的交。所有凸性行硬约束；其他全局行保留弹性人工；Phase I 真实列利润为零。分支仍为原始 x 的 most-fractional 二元分割。完整最优定价后仍使用

`max(RMP primal, repaired dual objective) + sum(max(0, rho_upper))`

形成上界，与继承界取 min。持久化模型只接受 native 已证最优 PP（101）与 LP（1）。未证最优、超时、异常均不签发完整定价证明；保留活动节点。

`branch_price_engine.py` 是隔离的兼容树引擎副本，只新增已验证初始 witness 和首解观察时间，不改原 `branch_price.py`。V3 的证书版本为 2，增加 initial_incumbent；其独立重放入口为 `task03_verify.py`，除验证初始 witness 外沿用 Task02 枚举/原始数据级检查。V0/V1/V2 证书版本 1 继续由原验证器接受。没有严格有理算术证书；证明作用域仍为冻结浮点容差下的 MILP 整数结论。

## 实现取舍及局限

增量 RMP **仍每轮重建 PuLP 验证镜像**，用旧验证逻辑检查 primal/dual/人工及列，原生优化模型本身不会每轮重建。这保证保守迁移，但未消除全部 Python 行构造成本。未验证实际基因子复用比例，不能把任何时间变化全部归因于 basis。

计时当前区分 PP 总墙钟、RMP 镜像构造/同步、RMP 求解/读回（含 primal/dual 检查）、节点剩余与节点总时间。持久化 PP 的原对象保留结构/原生创建计时，证书记录包含目标更新、native 求解和读回；创建分项尚未全部序列化。失败调用的未完成计时归入节点剩余。尚未完成 V0 所有构造/转换/证书检查的逐项非重叠剖析，T03-0 的细粒度剖析为 PARTIAL。

节点适配器在历史 PP 读回检查后，进一步应用 NumericPolicy 的整数及 primal 容差，检查最优状态 best_bound 与重算 RC 一致。单次异常只读取本次新产生的原生记录，避免误用旧状态。V3 日志目录按输出名称隔离，存在时拒绝覆盖。

T03-4 截断 PP Best Bound 新 UB 契约未接入。中断后仅使用先前已证上界或父界，不将 incumbent 当 PP 上界，也不宣布节点 LP 最优。相应三类截断 bound 契约专项测试是 NOT RUN。
