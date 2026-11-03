# Task03 正确性验证

## 实际已经执行的检查

|项目|状态|证据与作用域|
|---|---|---|
|Task02 原双后端完整验证|PASS|evidence/task02_full：29 输入×CBC/CPLEX=58 次搜索，48 次整数最优、10 次整数不可行；同时比较 Compact-IP、独立 Full-IP/LP|
|Task02 原节点专项|PASS|task02_full/node_scenarios：22 次；合法/空域、初池缺列、资源/AND 全局冲突等|
|Task02 中断/精度|PASS|task02_full/interruptions 的 5 次 + additional/tiny_rc 的 1 次；保留未解节点与有效继承界|
|历史根 CG、定价、证书及原 Compact 单测|PASS|原首次回归 CBC/CPLEX 各 69 项；含当时新增 3 项；后续封存回归见下文|
|历史实验组件|PASS|regression_experiments.txt：32 tests，包含公平比较、Hybrid/增量/持久化等原组件|
|最终 adapter 专项|PASS|adapter_final_tests.txt：13 tests，包含 PP/RMP 同域等价、分支丢失/目标更新/坏 bound/时限/异常、人工关闭、整数容差读回与截断 incumbent 记录|
|V0/V1/V2/V3 独立完整搜索矩阵|PASS（已复跑）|release_validation：29×4=116，96 次整数最优、20 次整数不可行；22 个 V1/V2 节点专项，合计 138 PASS|
|116 树离线重放与十类伪造证书|PASS（已复跑）|release_replay：116 真证书通过，10 类伪造全部拒绝|
|native 节点中断专项|PASS（已复跑）|native_interruptions：V1/V2 各 6 次，共 12 份保存的停止证书；含有界子节点超时和极小 RC 未闭合|
|CLI、输出防覆盖及 V3 离线重放|PASS|cli_console、cli_refuse_existing、cli_verification|
|封存前双后端与全矩阵再确认|PASS|sealed_regression_cbc/cplex_py：各 79 tests；sealed_validation 138 PASS；sealed_replay 116 真证书与 10 类伪造；sealed_interruptions 12 PASS|
|截断 PP bound 三故障契约|NOT RUN|T03-4 NOT IMPLEMENTED；已有最优 native PP 错 bound 拒绝测试不能替代此项|
|中等规模独立完整列枚举|NOT RUN|指数域不用于普通规模生产求解或冒充完整 Oracle|
|中等规模输入/来源与 witness 复查|PASS（有限作用域）|medium_audit：75 条输入/快照与状态检查、30 个整数 witness 通过原约束数据级复查；不是完整节点 LP/PP 认证|

## 测试覆盖说明

独立 Oracle 枚举局部允许列、按分支过滤、独立构造完整节点 LP/IP，并重算所有定价最优 RC、对偶修复界、人工变量、原始整数 witness 和完整搜索树。比较的是最优值与合法性，不要求退化对偶或最优列相同。29 输入来自 Task01 的 28 个输入，另加真正的 mandatory_negative（整数利润 -8），均保存输入与原始日志。

`two_lines` 必须闭合 27→24，`generator_n6_L1_s13` 必须闭合 59.38→56.63，`lp_yes_ip_no` 必须搜索后证明整数不可行。分支仍为原 x，不对 λ 单列分支。完整 Phase I 为零与真实 Phase II 可行性分别确认，不把初始受限池不可行当成完整节点不可行。

13 个 adapter tests 还检查所有 RMP 行 sense/RHS、零与非零系数、目标系数、Phase II 人工上界及目标为零；原节点检查 dj/强对偶；native 两阶段对偶反复变化与旧 PP RC 一致；两后端旧验证继续保留。CBC 下 native 专项仍显式调用 CPLEX，不把 CBC 模式称为 native 实现。

十类伪造：全局界、分支域、未证最优 PP、非法整数方案、丢孩子、非法对偶、错 PP 固定域、空初始池、人工符号、伪造活动节点清单。native fault tests 另外覆盖 Branch1 遗失、过期目标风险、PP/LP timeout/native exception、人工删除和错误 native bound。旧 NodeRestrictions/列池隔离测试及新 sibling 固定域等价一起验证节点不共享状态。

## 所有失败与修正记录

- final_native_tests.txt：首次以路径 `code/dwcg/...` 交给 unittest，误解析为标准库 code 模块，2 个装载错误。改为 PYTHONPATH 后直接模块名，corrected 与后续 13 tests PASS；没有将该首次命令标为通过。
- final_replay_console.txt：新 replay runner 使用相对路径对绝对 ROOT 做 relative_to，报错。修复为 resolve，失败目录与日志保留，后续 release_replay 全部通过。
- final_regression_cplex.txt：复用默认 TestLoader 连续 discover 两个非 package 目录导致装载失败。改为独立 TestLoader 后 78 tests PASS。不是模型或优化结果失败。
- 早期 v3_validation 中追加的 mandatory_negative 标签误用了 optional negative_profit 输入，不计入正式 29 输入覆盖。release/sealed_validation 使用实际 required_tasks=['a','b']、value=-2 的输入，目标为 -8。
- 所有中等规模 75 次为 time_limit，保留，不算成功闭合最优 Gap。结果写盘超时是性能/预算限制，不能转为数学最优状态。

## 封存确认

最终生产源码已冻结后再运行：CBC 默认环境 79 tests（46.348 秒），CPLEX 默认环境 79 tests（19.586 秒），均 OK。新 native 专项显式指定 CPLEX，不能简单理解为所有 79 项各自都使用默认后端。sealed_validation 共 138 PASS；sealed_replay 为 116 树 + 10 类伪造拒绝；sealed_interruptions 为 12 份停止证书。与前面的开发轮不累加为独立输入数量。最终正确性结论采用 sealed_*；中等规模性能采用独立冻结快照，二者版本作用域分开。

本表不替代原始 JSON/求解器日志。
