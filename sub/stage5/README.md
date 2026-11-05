# 整线B&P节点原生定价

原模型和stage4基线保持不变。新入口branch_price5.py，`--pricing rebuild|reuse|warm`；默认rebuild，原生模式仅CPLEX。reuse仅节点内复用，warm额外从当前节点合法继承列及上次方案中选择显式MIP start。节点结束释放原生对象，父子/兄弟节点不共享原生状态。

```powershell
& experiments/.venv/Scripts/python.exe sub/stage5/branch_price5.py code/data/tasks005_lines02_each03-02.json --pricing warm --time-limit 30 --output sub/stage5/evidence/new_run
& experiments/.venv/Scripts/python.exe sub/stage5/verify5.py sub/stage5/evidence/new_run
& experiments/.venv/Scripts/python.exe sub/stage5/test_native.py
```

输出目录须不存在。CLI的time-limit是run内软预算，最终压缩落盘另计；统一E2E配对使用paired5.py：

```powershell
& experiments/.venv/Scripts/python.exe sub/stage5/paired5.py --budget 15 --output sub/stage5/evidence/new_paired15
```

该程序只读取evidence/inputs已经冻结的四个JSON，不重新生成数据、不使用构造见证。单线程seed11，统一2秒收尾；Windows软截止，不是硬实时保证。每worker保存输入/源码/结果SHA及完整原生日志。不要在性能运行时并行启动其他求解回归。

默认verify5做完整枚举；过大时可显式加`--no-enumeration`做算术与原生状态重放，并明确缩小认证范围。本轮合成族每线只有5任务，所有保存节点可进行完整枚举。

详细数学边界见DESIGN.md，最终结果见REPORT.md。节点RMP仍重建；没有RL、跨节点原生复用、完整崩溃恢复或截断定价上界扩展。
