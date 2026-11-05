# 阶段9：中大规模受控实验

原模型、求解精度不变。协议与界推导分别见PROTOCOL.md和ECONOMIC_BOUND_DESIGN.md。输入文件名标明总任务数、线数、资源水平和seed；两线60/80任务分别每线30/40任务。

```powershell
experiments/.venv/Scripts/python.exe sub/stage9/benchmark.py --suite pilot --budget 120 --output <新目录>
experiments/.venv/Scripts/python.exe sub/stage9/replay.py <pilot目录>
experiments/.venv/Scripts/python.exe -m unittest discover -s sub/stage9 -p test_economic.py -v
experiments/.venv/Scripts/python.exe sub/stage9/benchmark_bound.py --suite confirm --budget 600 --output <新目录>
experiments/.venv/Scripts/python.exe sub/stage9/replay_bound.py <confirm目录>
experiments/.venv/Scripts/python.exe sub/stage9/analyze_bound.py <confirm目录>
experiments/.venv/Scripts/python.exe -m unittest discover -s sub/stage9 -p test_balanced.py -v
experiments/.venv/Scripts/python.exe sub/stage9/benchmark_balanced.py --suite confirm --budget 600 --output <新目录>
```

freeze.py只能向不存在的新输入目录生成，已冻结输入不重新生成。测试中的真实截断用例依赖本轮冻结pilot证书；兼容性测试见阶段8，运行日志保存在本目录evidence。stage8及此前全部历史数据不变。

旧root_first完整证书由旧独立验证器重放。新economic_bound证书保存base_result和额外经济界，verify_economic.py先重放旧结果，再独立核算新界；不把后处理改进UB写回旧120秒结果。原生Best Bound的正确性仍依赖CPLEX适配器及日志，不是有理算术形式证明。

数据构造见证未提供给任何worker。未执行的seed/资源组必须列为NOT RUN。无回调Compact的首次原生发现解时间未知，first_verified_integer_seconds仅表示返回后完成核验时刻；分解外层首次接收方案时间也不能冒充内层首次找到方案时间。中间轨迹用于诊断，正式证明以完整持久化并重放通过的结果为准。
