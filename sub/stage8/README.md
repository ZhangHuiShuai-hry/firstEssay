# 阶段8：120秒配对诊断

运行环境：仓库 experiments/.venv 的Python3.10.11，PuLP3.3.2，CPLEX22.1.1.0。输入与完整协议见PROTOCOL.md。

```powershell
experiments/.venv/Scripts/python.exe -m unittest discover -s sub/stage8 -p test_observation.py -v
experiments/.venv/Scripts/python.exe sub/stage8/experiment.py --output <新的目录> --budget 120
experiments/.venv/Scripts/python.exe sub/stage8/replay.py <结果目录>
experiments/.venv/Scripts/python.exe sub/stage8/analyze.py <结果目录>
```

已生成的cg_traced.py/compact_traced.py/demand_traced.py保留独立调用接口；build_instrumented.py记录来源变换，正式实验后不要重新生成或改动已哈希的代码。对后续改进使用新文件。

正式120秒复验使用experiment_v2.py（四种方法，包含root_first），对应replay_v2.py/analyze_v2.py。confirm600.py只对第一个40任务输入比较无观察回调Compact与root_first，默认600秒；使用新的输出目录。该确认没有Compact中间LB回调，因此其首次原生发现整数解时间保持未知。

progress.jsonl记录当时已核算的界，没有记录时沿用此前有效界。Compact新incumbent在回调中通过原始约束核验，约1秒节流，所以首次核验时间不是精确的原生首次发现时间。回调不提交方案、不改变原模型，但存在观察开销。完整验证器重放最终证书；逐事件轨迹仅做顺序/界一致性检查，不能将它当作每个时刻的完整离线证明。

开发失败保留：第一次smoke_compact输入路径不存在，未进入求解；第二次smoke_compact_v2由于复制文件后ROOT路径层级变化导致common导入失败（error.json已保存）。修正独立副本的ROOT后smoke_compact_v3成功。最终正式运行使用修复后的源码。失败目录没有删除，早期smoke源码哈希与最终代码不同，不纳入正式冻结源码重放。
