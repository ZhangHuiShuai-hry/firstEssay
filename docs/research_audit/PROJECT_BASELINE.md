# 项目可信基线

日期：2026-11-02（Asia/Shanghai）。基线提交 `2a1f76cc62bbef2a4c6592589972878986ba38cf`，分支 `main`，origin=`https://github.com/ZzzHry/firstEssay.git`。以本地完整工作区为对象；未拉取远程、切分支、提交或推送。

## 工作区与身份

任何写入前，bundled Git 的 porcelain 输出为空，工作区干净。baseline.json 是创建审计计划后采集，故 initial_status 仅多出本次 `docs/research_audit/AUDIT_PLAN.md`；不是用户原有修改。Git日志仅两个提交：`2a1f76c Track project from workspace root`、`799f959 Initial research code and formulation`。

系统 PATH 优先的 `C:/mynewpc/Git/cmd/git.exe` 发生所有权检查失败；使用 Codex bundled Git 并对每次命令传 `-c safe.directory=<workspace>` 成功。未更改全局/本地 Git 配置。没有 AGENTS.md 指令文件。忽略目录实际存在：experiments/.venv、runs、snapshots；默认 rg --files 会跳过，已单独核查。

baseline.json 保存全部150个 tracked 文件的原始 SHA-256；最终 HASHES_FINAL.tsv 保存交付时 tracked 文件与新增审计源码/报告的哈希，EVIDENCE_HASHES.tsv 保存本次证据文件的哈希（不自包含自身）。哈希可区分初始提交和未提交修复；各次独立运行 config.json 另外保存当次被测源码哈希。对 core 源码的接受测试哈希必须与交付一致。

## 环境（实际测试）

| 项 | 版本/结果 |
|---|---|
| 默认 Python | 3.12.9，CBC/PuLP可用；不是本次双求解器验收解释器 |
| 项目解释器 | `D:\Hrychang\Code\PostGraduate\test\P1Test\experiments\.venv\Scripts\python.exe`，Python 3.10.11 |
| PuLP | 3.3.2 |
| CPLEX API/引擎 | 22.1.1.0；安装路径 `D:\CodeProgram\IBM\cplexOp\cplex` |
| CBC | 2.10.3，PuLP内置 win/i64 版本 |
| NumPy / SciPy | 2.2.6 / 1.15.3 |
| matplotlib / PyMuPDF | 3.10.9 / 1.28.2 |
| LP/MIP smoke | CBC与CPLEX均实际求解成功；含对偶和非零dj |
| CPLEX许可证实际探测 | 1201变量纯LP实际求解成功；只证明当时可运行，不推断许可期限 |

完整环境在 evidence/environment.json；依赖锁在 evidence/requirements-lock.txt。系统Python3.10没有单独安装PuLP，原有项目venv有；未安装/升级系统包。默认3.12的泛化包扫描遇site-packages权限错误，改用项目venv的逐项版本及pip freeze完成记录，未把该扫描失败当测试通过。

## 功能与稳定入口

| 组件 | 实现状态 | 验证状态 |
|---|---|---|
| 紧凑MILP | code/milp/model.py | 小规模双求解器完整验证 |
| 根两阶段CG | code/dwcg/solve.py | 重建RMP+重建PP；完整列LP证书验证 |
| 完整列IP/LP与解码 | master.py、verify.py | 理论等价及独立四模型验证 |
| 增量原生RMP | incremental_master.py | 固定/追加矩阵、阶段切换、根CG验证 |
| 持久原生PP | persistent_pricing.py | 矩阵/目标更新及独立定价验证 |
| 受限整数恢复 | solve.recover_integer | 原问题整数可行解；列池作用域最优 |
| Hybrid | experiments/hybrid.py | 现有3项回归已运行；本次不重跑大规模质量实验 |
| 截断PP Best Bound | 字段已有，本次修复通用后端常数 | 尚未实现以截断界替代精确定价的CG控制流 |
| Branch-and-Price | 未实现 | NOT RUN |

版本标签必须带实验名称：增量实验 V0=重建RMP、V1=增量RMP；PP实验 V1=增量RMP+重建PP、V2=增量RMP+持久PP。基线精确入口是 `code/milp/model.py` 和 `code/dwcg/solve.py --verify`；原生V2由 `experiments/compare_pricing.py` 注入。默认CG CLI不自动启用V2。

现有核心测试45项，两后端修复前后均真实运行；最终实验测试32项（含新增8项回归）。原有测试/历史报告与本次实际执行结果分开记录，详见 VALIDATION_REPORT。

## 历史输入、配置和日志盘点

下表为目录盘点，不代表重新执行历史优化。source_manifest 存在且非空的运行，已检查所有列出的冻结源码文件，无missing或mismatch。各目录完整字段/哈希见 evidence/historical_inventory_v2.json。

| 运行目录 | summary记录 | 输入文件 | tasks | raw | logs | 材料判断 |
|---|---:|---:|---:|---:|---:|---|
| cg_diagnosis | — | 0 | 0 | 0 | 0 | 派生/诊断/部分材料，逐目录判断 |
| environment_confirmed | — | 0 | 0 | 0 | 0 | 派生/诊断/部分材料，逐目录判断 |
| environment_final | — | 0 | 0 | 0 | 0 | 派生/诊断/部分材料，逐目录判断 |
| environment_initial | — | 0 | 0 | 0 | 0 | 派生/诊断/部分材料，逐目录判断 |
| equivalent_pricing_audit_01 | 3 | 0 | 0 | 0 | 0 | 派生/诊断/部分材料，逐目录判断 |
| fair_large_01 | 15 | 16 | 15 | 15 | 13349 | 可追溯材料齐备 |
| fair_large_probe_01 | 1 | 2 | 1 | 1 | 615 | 可追溯材料齐备 |
| fair_long_diagnosis_01 | 3 | 4 | 3 | 3 | 6613 | 可追溯材料齐备 |
| hybrid_baseline_audit_01 | — | 0 | 0 | 0 | 0 | 派生/诊断/部分材料，逐目录判断 |
| hybrid_large_01 | — | 0 | 0 | 0 | 0 | 派生/诊断/部分材料，逐目录判断 |
| hybrid_smoke_01 | — | 0 | 0 | 0 | 0 | 派生/诊断/部分材料，逐目录判断 |
| incremental_rmp_01 | 30 | 16 | 30 | 30 | 66677 | 可追溯材料齐备 |
| incremental_rmp_hard300_01 | 2 | 2 | 2 | 2 | 9598 | 可追溯材料齐备 |
| large_120_150_600_01 | 2 | 3 | 6 | 6 | 108 | 派生/诊断/部分材料，逐目录判断 |
| persistent_pp_120_01 | 29 | 16 | 30 | 29 | 34251 | 派生/诊断/部分材料，逐目录判断 |
| persistent_pp_120_02 | 30 | 16 | 30 | 30 | 34927 | 可追溯材料齐备 |
| persistent_pp_300_02 | 30 | 16 | 30 | 30 | 37807 | 可追溯材料齐备 |
| persistent_pp_600_02 | 2 | 2 | 2 | 2 | 4211 | 可追溯材料齐备 |
| persistent_pp_analysis_02 | — | 0 | 0 | 0 | 0 | 派生/诊断/部分材料，逐目录判断 |
| pilot_01 | 60 | 61 | 60 | 60 | 4197 | 可追溯材料齐备 |
| pilot_02 | 60 | 61 | 60 | 60 | 4543 | 可追溯材料齐备 |
| pricing_replay_01 | — | 0 | 0 | 0 | 5586 | 派生/诊断/部分材料，逐目录判断 |
| pricing_replay_02 | — | 0 | 0 | 0 | 8746 | 派生/诊断/部分材料，逐目录判断 |
| restricted_ip_diagnostic_01 | 6 | 0 | 0 | 0 | 0 | 派生/诊断/部分材料，逐目录判断 |
| restricted_ip_pool_audit_01 | — | 0 | 0 | 0 | 0 | 派生/诊断/部分材料，逐目录判断 |
| scaling_scout_01 | 10 | 11 | 10 | 10 | 6383 | 可追溯材料齐备 |
| stage_a_01 | 36 | 10 | 36 | 36 | 860 | 可追溯材料齐备 |
| stage_a_02 | 36 | 10 | 36 | 36 | 860 | 可追溯材料齐备 |

四个快照均保留。V1冻结清单的40个源码、76502个数据文件逐一SHA-256匹配；V0的33个源码亦核查；最早快照11个源码匹配。`20261030_112527/snapshot.json` 只有用途说明，没有源哈希清单，故其密码学完整性为PARTIAL，不能追补成历史证据。历史报告“当时无Git”与现在有Git属于不同时间点，未改写旧报告。

信任分级：快照字节完整性PASS；有配置/输入/原始日志/冻结源码的历史结果可追溯；8684对历史定价回放及120/150任务性能结论本次未重新求解，标NOT RUN，不据其宣称当前性能。派生图表/诊断目录没有统一run材料不能与正式独立作业计数混合；persistent_pp_120_01仅29条且无环境文件，属于部分/中断材料。早期复制双线数据与正式two_lines不是同一输入。

所有原有实验结果、快照、输入和配置均未写入或删除。本次产物仅在 docs/research_audit（以及明确的源码最小修复/新增测试），未执行git reset/clean或切分支。
