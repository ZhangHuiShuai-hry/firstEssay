# 入口验证记录

实际使用现有 Python 3.10 / PuLP / CPLEX 环境运行：

```powershell
$env:PYTHONPATH='code'
experiments/.venv/Scripts/python.exe -m unittest test_solver_entries -v
```

3 tests PASS，约11.7秒（本次运行观测值）：

- 五个输入均通过原模型数据校验、任务计数和来源 SHA-256 检查。
- 从 `code/` 工作目录无参数运行两个入口，均证明默认5任务实例整数最优24。
- `--strategy cg` 得到LP最优27、原整数全局最优标志false；完整证书通过独立完整列枚举交叉验证。
- 6任务实例两个入口均得到56.63。
- 极短时限的DW入口退出码2，原整数最优标志false、整数LB=null。

20/40任务只验证输入合法性与哈希，**本轮没有启动其求解实验**，不声明其最优值。默认运行的日志与结果在 `code/results/`（忽略提交）；测试使用临时输出目录，避免污染历史数据。
