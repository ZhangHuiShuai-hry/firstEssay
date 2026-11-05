# 整线定价优化实验入口

数学设计见DESIGN.md；完整结果见REPORT.md、MICROBENCHMARK.md及evidence。旧入口sub/line_cg.py、sub/stage2/solver.py保持原样可运行。

新API：`sub/stage3/solver.py::run(data, pricing="rebuild"|"reuse"|"warm", init_seconds=None, ...)`。rebuild为旧重建PP；reuse每线复用；warm额外提交完整MIP start。API默认初始化仍为None（原残余预算分配），本轮配对明确设为0.5秒。quota默认关闭。

在项目根目录PowerShell中运行（输出目录须不存在）：

```powershell
& experiments/.venv/Scripts/python.exe sub/stage3/test_persistent.py
& experiments/.venv/Scripts/python.exe sub/stage3/paired.py --output sub/stage3/evidence/new_paired30 --budget 30
& experiments/.venv/Scripts/python.exe sub/stage3/validate_runs.py sub/stage3/evidence/new_paired30
& experiments/.venv/Scripts/python.exe sub/stage3/seal.py --check
```

`microbenchmark.py`和`validate_runs.py`无参数模式使用固定且不可覆盖的evidence/micro、evidence/oracle目录；重做需复制脚本并改为独立输出路径，保留已封存结果。单次worker可通过paired.py的`--worker warm --instance <冻结JSON> --output <新目录> --budget 30`执行。

新证书版本4保留原始数据结构、完整对偶/人工量/定价和见证，新增PP组件时间及已验证LB轨迹。独立验证沿用stage2_verify，不从生产PP生成Oracle。大实例重放仍依赖原生CPLEX最优状态和界契约，不能声称有理算术独立证明。

不支持原生节点分支域，不实现整线B&P，不提供被杀死进程的恢复。CBC、新数值策略和大规模任务在本轮NOT RUN。新API只在本报告的CPLEX默认数值设置范围验证。
