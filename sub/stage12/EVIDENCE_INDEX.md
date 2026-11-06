# 证据索引

- PROTOCOL.md：观察正式结果前冻结的矩阵、容量规则、120秒检查与600秒预算。
- calibration_plan.json、pilot_plan.json、formal_plan.json：事前清单，NOT RUN为冻结计划原值。
- evidence/preflight/：3份历史哈希清单校验及3组共6项实际回归的命令/日志/退出码。
- evidence/ENVIRONMENT_VERIFIED.json：实际Python/PuLP/CPLEX版本及数值政策文件哈希。
- evidence/base_inputs/manifest.json：6份宽松校准输入、原生成器哈希、任务参数库哈希。
- evidence/inputs/manifest.json：6份正式输入字节哈希、H/R校准计数、局部最优状态及“不提供构造见证”记录。
- evidence/calibration/：6次I校准。120/33有一条局部经济MILP未证，状态完整保留，不当作最优。
- evidence/pilot120/：120任务seed32的D/C入口检查，2份结果。
- evidence/formal600/：6输入×2方法的12次正式结果。
- 各批次manifest/input_hashes/sources/CONFIG/ENVIRONMENT/preparation：输入、源码和配置冻结。
- 各批次accounting/COMPLETED/replay：真实E2E、及时/硬停止、退出码和逐次核验。
- 各worker目录instance.json、result.json.zlib、summary.json、progress.jsonl（D）、logs/、replay-check.json：输入、完整可重建证明数据、整数witness、原生求解和独立检查。C无progress回调，不伪造首次发现最优值的时间。
- evidence/replay-final-{calibration,pilot120,formal600}.{json,txt}：原输出不修改的第二次只读批次重放，共20份。
- evidence/analysis/：完整Markdown/LaTeX表、原始行、耗时/对偶/人工量诊断、已知最优参照及配对数据。参照只在实验结束后计算，未输入worker。
- evidence/CROSS_MODEL_CHECKS.json、CROSS_MODEL_RECHECK.json：六组同字节跨方法界相容、PhaseI归零、完整精确定价及最终界闭合。
- SHA256.json：本阶段全部文件（不含自身/字节码）的最终字节清单，seal12.py --check可校验。

本阶段求解源码为已存在的sub/stage9/balanced_bound.py及其依赖、sub/compact_solver.py；运行/重放入口为sub/stage11/run_plan_v2.py、verify_v2.py。本阶段新增cross_check.py仅为后验只读核验，不属于已计时worker算法。
