# 可复现的 ML-HRC-DLBP-CF 计算实验

先阅读 [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md)。源码保持 `code/milp`、`code/dwcg` 的数学模型；统一适配层为 `code/solver_backend.py`。旧实验包保留在 `code/experiments/dwcgTest/dlbp_experiment_kit`，旧结果不会被覆盖。

## 环境

本机 CPLEX API 支持 Python 3.10，已使用该解释器建立 `.venv`。不需要改系统 PATH。项目依赖在虚拟环境中；每次运行的 `requirements-lock.txt` 给出精确版本。

```powershell
# 项目根目录执行，使用已建立的环境
experiments/.venv/Scripts/python.exe experiments/environment_check.py --out experiments/runs/new_environment/environment.json
experiments/.venv/Scripts/python.exe experiments/run_regressions.py --solver cplex_py
experiments/.venv/Scripts/python.exe experiments/run_regressions.py --solver cbc
experiments/.venv/Scripts/python.exe -m unittest discover -s experiments -p test_framework.py -v
```

移至其他机器时，用匹配 CPLEX 安装版本的 Python 创建项目 venv，按已运行目录中的 lock 文件安装依赖，并调整 `solver_backend.CPLEX_ROOT`。API只在进程内加入搜索路径；默认 CBC 不依赖 CPLEX。

## 分阶段执行

```powershell
experiments/.venv/Scripts/python.exe experiments/run_experiments.py --config experiments/configs/stage_a.json --out experiments/runs/my_stage_a
# 确认阶段A与跨求解器比较通过后再运行pilot
experiments/.venv/Scripts/python.exe experiments/run_experiments.py --config experiments/configs/pilot.json --out experiments/runs/my_pilot
experiments/.venv/Scripts/python.exe experiments/analyze_results.py experiments/runs/my_stage_a
experiments/.venv/Scripts/python.exe experiments/plot_results.py experiments/runs/my_pilot
# pilot完成后，受控扩展到L=2、n=10/20（仍保留每作业预算）
experiments/.venv/Scripts/python.exe experiments/run_experiments.py --config experiments/configs/scaling_scout.json --out experiments/runs/my_scaling
```

目录必须是新目录；重复使用已存在的 run 会报错。`--limit 2` 可先跑两个实例。`planned_BC.json` 是后续大规模计划，未自动执行；先缩小配置并估算开销。仅生成算例可调用 `generate_instances.py --config ... --out ...`，同样要求新目录。

原始命令行兼容，并新增求解器选择：

```powershell
experiments/.venv/Scripts/python.exe code/dwcg/solve.py code/milp/examples/two_lines.json --solver cplex_py --verify
python code/dwcg/solve.py code/milp/examples/two_lines.json --solver cbc --verify
experiments/.venv/Scripts/python.exe code/milp/model.py code/milp/examples/two_lines.json --solver cplex_py
```

## 文件与结果

- `environment_check.py`：目录/API/CLI/实际许可范围测试与小LP/MILP。
- `generate_instances.py`：带见证、配对设计、独立元数据的合成算例。
- `worker.py`：单个实例的4类基线、非重叠计时、checkpoint和原始日志。
- `run_experiments.py`：串行批量运行、子进程超时、冻结配置/代码/环境。
- `analyze_results.py`：保留失败的统计、跨求解器比较、实例多样性审计。
- `plot_results.py`：论文用矢量图和PNG预览，源数据可追溯。
- `test_framework.py`：配对控制、固定总量、计划规模可生成性与真实超时状态测试。

每个 run 的 `summary.csv/json` 为原始逐算例记录；`raw` 包含迭代、定价、对偶、恢复与求解器事件；`logs` 包含每次原生求解日志及进程标准输出/错误；`tasks` 保存每次调用配置；`instances/manifest.json` 保存seed、参数、见证、规模/图密度/模式数/资源等信息。

`analysis/enriched_summary.csv/json` 增加资源价格、LP资源使用、PP原生/转换开销及小规模可行列数。`group_statistics.json` 报告均值、中位数、样本标准差、IQR和成功率；`dataset_audit.json` 记录有效/不可行/未解/丢弃与重复控制输入；`cross_solver_comparison.json` 比较不同组合的数学目标。

`figures` 保存 PDF/SVG/PNG、CSV源数据、图形契约和审计。探索目录 `_01` 保留，修订生成器后最终结果见中文报告指定的 `_02` 目录；不要跨不同生成版本汇总。没有Git时以 `provenance.json` 的源码 SHA-256及 `source` 快照复现。

本次实际结果：`runs/stage_a_02` 为36次独立跨求解器作业，`runs/pilot_02` 为60次预试验作业，`runs/scaling_scout_01` 为10次两线规模扩展。完整中文分析见 [REPORT_CN.md](REPORT_CN.md)。后处理示例：

```powershell
experiments/.venv/Scripts/python.exe experiments/audit_figures.py experiments/runs/my_pilot/figures
experiments/.venv/Scripts/python.exe experiments/write_report.py --stage-a experiments/runs/my_stage_a --pilot experiments/runs/my_pilot --scout experiments/runs/my_scaling --out experiments/MY_REPORT.md
```

图形审计使用本机科研绘图技能的脚本；换机后可调整 `audit_figures.py` 和 `plot_results.py` 的 `SKILL` 路径。优化与实验不依赖该审计路径。主论文图应重新检查目标期刊规范；当前图是基于实际数据的预试验分析图，并无期刊接收或人体安全阈值声明。

## 较大规模的同预算整数质量比较

新增 [FAIR_COMPARISON_PROTOCOL.md](FAIR_COMPARISON_PROTOCOL.md)。`fair_compare.py` 比较同一输入上的30秒直接CPLEX-IP，与同样30秒总预算的标准CG＋一次受限列整数恢复，包含建模时间。较大实例为两条线、每线20/30/40任务、各5个种子；不是之前IP10秒与CG根30秒的探索设置。

```powershell
experiments/.venv/Scripts/python.exe -m unittest discover -s experiments -p test_fair_compare.py -v
experiments/.venv/Scripts/python.exe experiments/fair_compare.py --config experiments/configs/fair_large.json --out experiments/runs/my_fair_run
experiments/.venv/Scripts/python.exe experiments/audit_fair_results.py experiments/runs/my_fair_run
experiments/.venv/Scripts/python.exe experiments/report_fair_compare.py experiments/runs/my_fair_run
```

实际批量目录为 `runs/fair_large_01`，报告为其 `FAIR_COMPARISON_CN.md`，逐例数据为 `summary.csv/json`。单例15秒探测另存 `fair_large_probe_01`，不混入正式统计。根节点截断后保留合法列池，剩余预算尝试恢复；只有已完整完成精确定价的轮次才产生CG上界。没有整数解写null，不把受限IP不可行当作原问题不可行，也不将根阶段超时误报LP最优。两种算法可提前结束，但不能把无解提前停止称为速度优势。

## CG工程排查与延时诊断

`common.py` 的列系数改为稀疏且有界缓存，`master.py` 直接插入非零线性项，避免每轮创建大量零乘法表达式。没有修改数学定义、允许列、检验数符号或精确定价要求。修改前完整源码保存在 `snapshots/20261030_112527`，微基准逐项比较同一列池的矩阵和目标。

诊断报告在 `runs/cg_diagnosis/CG_DIAGNOSIS_CN.md`。`runs/fair_long_diagnosis_01` 为每种方法120秒总预算、根CG最多108秒、每规模seed11一个实例的实际延时运行；它是机制诊断，不与此前5种子的30秒实验混算。`reference_n20` 使用冻结的修改前源码复跑同一实例，用于比较完整根LP时间而不是把构造微基准加速比当成算法总加速比。

```powershell
experiments/.venv/Scripts/python.exe experiments/diagnose_cg.py
experiments/.venv/Scripts/python.exe experiments/fair_compare.py --config experiments/configs/fair_long_diagnosis.json --out experiments/runs/my_long_diagnosis
experiments/.venv/Scripts/python.exe experiments/report_cg_diagnosis.py
```

仍待解决：RMP/CPLEX原生LP的增量更新与基复用，以及LP最优列池未必支持整数恢复的结构性限制。当前不通过给CG独占输入生成见证或关闭验证来制造优势。

## 增量RMP实验（CG-V0 / CG-V1）

新增实验规程 [INCREMENTAL_RMP_PROTOCOL.md](INCREMENTAL_RMP_PROTOCOL.md)。V0冻结在 `snapshots/CG_V0_20261030_134805`，V1适配器为 `code/dwcg/incremental_master.py`，通过原生CPLEX稀疏追加列并保留LP求解对象。定价文件及原CG主循环不变；运行器只替换RMP接口，不覆盖旧源码快照或实验数据。

120秒根LP配对运行保存于 `runs/incremental_rmp_01`；逐例为 `summary.csv/json`，详细CG及基状态为 `raw/`，CPLEX日志为 `logs/`。统计及中文报告使用 `report_incremental.py`，图表使用 `plot_incremental.py`。300秒难例须独立运行并明确预算。这里的120秒全部用于根LP，不与先前108秒根LP加整数恢复的流水线混算。此实验不解决受限列池整数恢复的结构性局限。

## 持久化原生PP（CG-V2）

新增方法与复现说明 [PERSISTENT_PP_PROTOCOL.md](PERSISTENT_PP_PROTOCOL.md)。V1源码及全部两轮数据完整备份，位置和SHA256清单由 `CG_V1_FROZEN.json` 索引。`code/dwcg/persistent_pricing.py` 每工作站保留一个原生CPLEX定价MILP，只更新对偶目标；原 `pricing.py`、`incremental_master.py` 和数学模型不变。`pricing_profile.py` 统一记录两版PP的结构创建、转换、目标更新、原生MIP优化及读回开销。

正式同对偶验证为 `runs/pricing_replay_02`，遍历三个已保存完整历史的8684对调用；`pricing_replay_01` 是中断的原生表示预检查，不混入性能统计。端到端两档配对分别保存为 `runs/persistent_pp_120_02`、`runs/persistent_pp_300_02`，完整对偶、逐轮PP日志及原生求解器日志均保留。`run_pricing_plan.py` 仅在完整同对偶验证通过后依次运行两档各30次配对。额外600秒难例另设目录，不替代原截断结果。

后处理命令：

```powershell
experiments/.venv/Scripts/python.exe experiments/report_pricing.py --runs experiments/runs/persistent_pp_120_02 experiments/runs/persistent_pp_300_02 --replay experiments/runs/pricing_replay_02 --out experiments/runs/persistent_pp_analysis_02
experiments/.venv/Scripts/python.exe experiments/plot_pricing.py experiments/runs/persistent_pp_analysis_02 --replay experiments/runs/pricing_replay_02
experiments/.venv/Scripts/python.exe experiments/audit_figures.py experiments/runs/persistent_pp_analysis_02/figures --source experiments/plot_pricing.py
experiments/.venv/Scripts/python.exe experiments/audit_pricing.py --runs experiments/runs/persistent_pp_120_02 experiments/runs/persistent_pp_300_02 --check-frozen-data --out experiments/runs/persistent_pp_analysis_02/source_result_audit.json
```

两版仍采用精确MILP定价，不进行整数恢复。根LP上下界和收敛状态与原问题整数最优证明严格分开。计时区间及截断速度比规则见实验规程。

正式V1/V2端到端对子进程固定PYTHONHASHSEED=11，不修改RMP源码。未控制哈希的persistent_pp_120_01保留为中断预试验，正式分析不混入该数据。
