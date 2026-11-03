# Task03 证据索引

## 正式读取入口

- TASK03_SUMMARY.md：中文结论及验收状态。
- IMPLEMENTATION.md、CERTIFICATE_NOTES.md：模块、数学不变量和证书增补。
- VALIDATION.md：测试计数、失败说明及作用域。
- EXPERIMENT_PROTOCOL.md、RESULTS.md/JSON、LIMITATIONS.md：配置、逐尝试与限制。
- V0_SHA256.json：开始时 Task02 生产代码 SHA；source_snapshot/manifest.json：中等规模运行源码。
- CODE_AND_BASELINE.json：最终源码、Git 状态、冻结政策和原始代码不变性。
- ARTIFACT_SHA256.json、SEAL_RECEIPT.json：本次新增源码/报告/原始记录的清单与封存摘要；排除缓存与自身递归哈希。

## 最终正确性（优先于开发轮）

- evidence/sealed_regression_cbc.txt、sealed_regression_cplex_py.txt：各 79 tests OK。
- evidence/adapter_final_tests.txt：13 adapter 专项（已包含于上面 79）。
- evidence/sealed_validation/summary.json：116 完整树 + 22 节点，共 138 PASS。各实例子目录保存 instance.json、result.json/node.json、verification.json 和 native 日志。
- evidence/sealed_replay/summary.json：116 个真证书离线重放和 10 类伪造拒绝；同目录保存伪造输入。
- evidence/sealed_interruptions/summary.json：V1/V2 各 6 场景的 12 份停止证书，活动节点及继承上界保留。
- evidence/task02_full/：原双后端 58 完整搜索、22 节点、6 停止/精度；含 Compact/Full-IP/Full-LP 对照和日志。
- evidence/regression_experiments.txt：原实验组件 32 tests。
- evidence/cli_result.json、cli_verification.json、cli_refuse_existing.txt：V3 CLI 的 24=LB=UB 证明、重放、防覆盖。
- evidence/environment.json：真实 CBC/CPLEX smoke、版本、硬件。

## 性能原始记录

- evidence/scout/：n10/n20、3 秒、10 臂探索；不混入正式 75 臂统计。
- evidence/medium/config.json、input_n*_s*.json、summary.json：15 输入、75 次尝试的统一配置、输入和逐次指标。
- evidence/medium/arm_n*_s*_<version>/：独立进程配置、输入、单臂 summary、worker stdout、原始 result、逐节点树及求解日志；Compact 也保存完整整数方案。
- evidence/medium_audit.json：对中等规模输入/性能源码哈希、整数 witness 和完整定价标志做非指数域检查，不冒充完整 LP/PP Oracle。
- evidence/medium_console.txt：执行顺序与全部停止状态。

## 开发/失败记录（全部保留）

native_tests、small_validation、v3_validation、final_validation、release_validation、对应 replay/regression 及 console 是开发轮；不能与 sealed_* 累加为新的独立输入数量。final_native_tests.txt、final_replay_console.txt、final_regression_cplex.txt 中有装载/路径错误；原因及修正见 VALIDATION.md。早期 V3 negative fixture 的误标不计正式覆盖。没有删除失败记录或覆写 Task01/02 原始数据。

## 作用域

完整枚举独立数学认证只用于小规模。中等规模保存算法证据并验证 witness，但没有离线完整枚举；所有结果为 time_limit。ARTIFACT 哈希保证字节一致性，不将 solver 自述状态提升为严格有理证明。封存不表示 commit/push/PR 已执行；本次没有这些操作。
