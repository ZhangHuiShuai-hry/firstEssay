# 固定每线20任务的规模验证

实验协议：PROTOCOL.md。新脚本仅冻结数据和只读汇总，求解器继续使用阶段11正式v2入口及阶段9算法。

```powershell
# 生成原始容量校准输入（目标目录不得已存在）
experiments/.venv/Scripts/python.exe sub/stage12/freeze.py
experiments/.venv/Scripts/python.exe sub/stage11/run_plan_v2.py --plan sub/stage12/calibration_plan.json --output <新的校准目录>

# 本次freeze.py --final读取固定的evidence/calibration已完成结果；复现应保留该目录结构或在新工作副本运行
experiments/.venv/Scripts/python.exe sub/stage12/freeze.py --final

# 已有冻结输入可直接重跑计划到新的输出目录，不重新生成输入
experiments/.venv/Scripts/python.exe sub/stage11/run_plan_v2.py --plan sub/stage12/pilot_plan.json --output <新的pilot目录>
experiments/.venv/Scripts/python.exe sub/stage11/run_plan_v2.py --plan sub/stage12/formal_plan.json --output <新的600秒目录>

# 只读重放，输出审计文件必须使用新文件名
experiments/.venv/Scripts/python.exe sub/stage11/verify_v2.py sub/stage12/evidence/formal600 --output <新的审计JSON>

# 本次结果表的只读再生成
experiments/.venv/Scripts/python.exe sub/stage12/analyze.py --output <新的分析目录>

# 后验跨模型界与完整定价检查（不调用求解器）
experiments/.venv/Scripts/python.exe sub/stage12/cross_check.py --output <新的交叉检查JSON>
```

正式完成状态以批次COMPLETED.json、accounting.json和replay.json为准，plan内的NOT RUN是事前计划值。每worker保留原始输入、源码哈希、原生日志、压缩完整证据、E2E accounting及独立重放。所有新输出拒绝覆盖已有目录；历史阶段资料保持原字节。

最终中文结论见SUMMARY.md；数学/程序核验范围见VALIDATION.md；原始证据位置见EVIDENCE_INDEX.md。cross_check.py是在实验完成后新增的只读分析入口，不参与任何worker数学求解或预算。
