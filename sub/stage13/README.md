# 分解基线收尾包

协议：PROTOCOL.md；最终基线：BASELINE.md；RL设计准入与数据隔离：RL_READINESS.md。结果与实际状态见SUMMARY.md。

本目录只增加冻结输入、实验编排、固定对偶探针及后验报告，不修改生产算法。所有原始失败/限时记录保留，所有输出使用新目录。

```powershell
# 已冻结的四个输入，C/D相同180秒预算
experiments/.venv/Scripts/python.exe sub/stage11/run_plan_v2.py --plan sub/stage13/plan.json --output <新目录>

# 实际批次只读重放，使用新的输出文件名
experiments/.venv/Scripts/python.exe sub/stage11/verify_v2.py sub/stage13/evidence/robust180 --output <新审计JSON>

# 已有开发快照的固定对偶探针：24次，目标native各5秒，persistent setup各3秒
experiments/.venv/Scripts/python.exe sub/stage13/probe.py --output <新探针目录>

# 汇总本次封存路径，生成到新的输出目录
experiments/.venv/Scripts/python.exe sub/stage13/analyze.py --output <新分析目录>

# 探针离线重放，并重新审计4份原始参考证书
experiments/.venv/Scripts/python.exe sub/stage13/verify_probe.py --output <新探针审计JSON>

# 字节完整性
experiments/.venv/Scripts/python.exe sub/stage13/seal13.py --check
```

evidence/inputs/manifest.json记录正式输入字节、原输入/校准来源及容量规则。robust180中每worker保存原始输入、完整压缩证书、对偶/列/人工量/PP状态、原生日志及单份独立重放；批次sources.json冻结求解源码。probe保存完整局部列和证书、setup及target计时、来源哈希与相同对偶，返回状态未证时不要求等于已知最优。

定价微基准total_seconds为开始准备至target读回/验证的时间，含setup但不含最后模型释放和结果JSON写入；不是端到端算法时间。正式算法E2E则包含必要证据落盘。首次正RC列时间无回调，明确NOT MEASURED，不用native返回时刻代替首次发现时刻。

probe.py/prepare.py在正式实验前写入；analyze.py为后验只读工具。所有实际使用的来源可由Git版本与最终SHA256清单复查。

verify_probe.py亦为实验后的只读核验入口，实际复验结果evidence/probe-replay.json为PASS（24次探针及4份参考证书）。正式8次E2E累计1114.09秒，约18.57分钟，不含前置测试、微基准和独立重放。主实验逐份证据、逐份源码哈希和原生日志均保留，未覆盖阶段1–12资料。
