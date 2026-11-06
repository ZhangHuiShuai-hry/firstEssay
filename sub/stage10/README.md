# 固定版本留出实验

执行计划见WORKFLOW.md；本次实际完成E0/E1，结论与限制见SUMMARY.md。

```powershell
# 必须使用不存在的新输出目录；完整8次最多80分钟，另加审计
experiments/.venv/Scripts/python.exe sub/stage10/run_plan.py --plan sub/stage10/heldout_plan.json --output <新目录>

# 只读重放已经完成的批次，不覆盖原证据
experiments/.venv/Scripts/python.exe sub/stage10/verify10.py sub/stage10/evidence/heldout600

# 从原始结果生成新分析目录
experiments/.venv/Scripts/python.exe sub/stage10/analyze10.py sub/stage10/evidence/heldout600 --output <新分析目录>
```

`heldout_plan.json` 是运行前计划，保留其NOT RUN原值；执行状态以批次COMPLETED.json、accounting.json和replay.json为准。`e0_plan.json`用于两个微例，不混入性能统计。

当前31项相关回归通过、4份微例和8份正式证书重放通过。一次零测试匹配日志与损坏证据副本均保留。源码快照包括run_plan.py，实验开始后该文件不再修改；analyze10.py/verify10.py是实验结束后的只读分析与审计入口，不作为已测求解算法新组件。

实测Python3.10.11/PuLP3.3.2/CPLEX22.1.1.0。ENVIRONMENT.json记录平台；数值政策保存在完整分解结果及analysis/diagnostics.json。本次只提交阶段10新增文件，不提交用户新增的essay模板及其他未跟踪文件。
