# 多线结构实验

结果：SUMMARY.md。初始协议：PROTOCOL.md。追加开发确认：CONFIRM_PROTOCOL.md。输入冻结和正式矩阵：evidence/inputs/manifest.json、pilot_plan.json、confirm_plan.json。

```powershell
# 用不存在的新目录运行正式清单；固定算法，最多18×120秒
experiments/.venv/Scripts/python.exe sub/stage11/run_plan_v2.py --plan sub/stage11/pilot_plan.json --output <新目录>

# 只读独立重放，不改原证据
experiments/.venv/Scripts/python.exe sub/stage11/verify_v2.py sub/stage11/evidence/pilot120
experiments/.venv/Scripts/python.exe sub/stage11/verify_v2.py sub/stage11/evidence/confirm600

# 重新生成表格到新目录
experiments/.venv/Scripts/python.exe sub/stage11/analyze.py --output <新目录>
```

正式入口是v2。worker.py/run_plan.py是已冻结的容量校准快照，缺少迁移后D所需的显式stage9导入路径，不作为完整三方法入口；不要修改它们破坏校准哈希。prepare_v2.py生成正式入口，微例及正式记录均通过验证。所有生成脚本拒绝覆盖已有输出。

evidence/analysis包含完整120/600秒Markdown和LaTeX表、原始行、资源/迭代/耗时诊断，以及由已证最优结果得到的后验质量参照。后验参照从未提供给worker。独立基线无合法全局方案时LB/Gap为空，不用0代替，不判原模型不可行。

源码、输入、配置和每worker结果哈希在批次内；本目录总清单见SHA256.json。计划中的NOT RUN原值保留，实际完成以批次COMPLETED/accounting/replay为准。
