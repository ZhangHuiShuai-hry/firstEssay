# 整线分解与模型变体探索

结论：整线方案列已体现更好的整数兼容性和更强的 LP 界；部分保留全部约束的40总任务输入，在相同15秒名义预算内，比直接 CPLEX 更早完成整数最优证明。还没有建立普遍的性能优势，较紧资源的三例反而都是 Compact 更快。详细结论见 [EXPERIMENT_REPORT.md](EXPERIMENT_REPORT.md)，全部原始表见 [ALL_RESULTS.md](evidence/analysis_final/ALL_RESULTS.md)。

本目录为独立实验，`code/`、`problem/`、Task01–03历史文件均未修改。原模型不变的主试验将一列定义为一条线的全部整数方案；另有明确改变物理含义的删优先关系、去疲劳和容量消融，不将它们的解回填为原问题解。

## 运行

使用项目的 `experiments/.venv/Scripts/python.exe`，CPLEX 22.1.1.0，单线程 seed11、gap0。

```powershell
# 以原5任务输入运行整线CG；每次必须用新的输出目录
experiments/.venv/Scripts/python.exe sub/line_cg.py --output sub/evidence/my_line_run

# 更换输入，例如40任务、两条线、seed12（全约束保留）
experiments/.venv/Scripts/python.exe sub/line_cg.py sub/evidence/inputs_v1/tasks040_lines02_seed12.json --time-limit 30 --output sub/evidence/my_seed12

# 相同实例直接CPLEX对照；预算也包含模块导入与结果写盘
experiments/.venv/Scripts/python.exe sub/compact_solver.py --instance sub/evidence/inputs_v1/tasks040_lines02_seed12.json --budget 30 --output sub/evidence/my_compact

# 串行配对，读取已经冻结的同一输入字节
experiments/.venv/Scripts/python.exe sub/benchmark.py --suite sub/evidence/inputs_v1 --names existing20_original existing40_original --methods compact station line --budget 15 --output sub/evidence/my_pair

# 小规模数学回归和完整枚举
experiments/.venv/Scripts/python.exe -m unittest discover -s sub -p test_line_cg.py -v
experiments/.venv/Scripts/python.exe sub/validate.py sub/_smoke_line_solver/instance.json sub/_smoke_line_solver/result.json

# 重放全部保存实验；中等规模的定价最优性仍依赖原生CPLEX状态/界
experiments/.venv/Scripts/python.exe sub/replay_experiments.py sub/evidence/pilot_v1 sub/evidence/ablation_v2 sub/evidence/line_counts_v2 sub/evidence/resource_stress_v2 --output sub/evidence/my_replay.json
```

`line_cg.py` 是根CG+受限整数恢复，没有整线 B&P。只有经过原模型验证的 LB 与有效 UB 闭合才声明整数最优；LP 收敛但 Gap 未闭合时保留未证明状态。传入 `use_initial_bounds=False` 可关闭V2的单线原生初始化界，便于对照；精确定价逻辑不变。

## 文件

|文件|用途|
|---|---|
|`MODEL_DESIGN.md`|模型、完整列IP等价、LP强化、Phase I、定价和界的证明|
|`line_cg.py`|整线定价、两阶段主问题、整数恢复与证书|
|`compact_solver.py`|相同新输入的原Compact直接求解|
|`instances.py`|第一轮输入冻结及四种变体；生成器见证不传给算法|
|`resource_stress.py`|第二轮真正资源紧张的三例，明确为自适应诊断组|
|`benchmark.py`|串行独立worker、软截止时间、真实E2E与超预算标记|
|`validate.py`|直接枚举任务—站—模式的独立完整列Oracle与证书核算|
|`test_line_cg.py`|14项数学、数值及伪造证书拒绝测试|
|`replay_experiments.py`|三种方法保存证据的重放入口|
|`analyze.py`|从原始数据重新生成完整配对结果与非重叠耗时汇总|
|`evidence/`|冻结输入、63次运行、日志、SQLite/压缩JSON、独立重放、测试记录|

源码及输入哈希在 `SOURCE_SHA256.json`，整个交付目录证据清单在 `EVIDENCE_SHA256.json`。生成器结构组2线/4线共享任务参数库，但线内优先图、必做集合和回收行随分线改变，不能称作同一数学实例。所有胜负只能在同一冻结输入的两种算法之间比较。
