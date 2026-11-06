# 学习辅助整线列生成：独立实验区

当前阶段是RL动作空间验证，尚未训练网络；生产分解基线保留在sub/，原模型保留在code/milp/。后续实验、数据划分和学习代码统一在本目录版本化追加。

## 实验01

- pricing_actions.py：离散价格混合与仅完整精确定价可用的拉格朗日LP上界。
- test_pricing_actions.py：完整列小例Oracle、四动作上界、错误价格/目标/缺块和超时处理。
- action_probe.py：5个开发状态×4动作×2重复，每线初始化.5秒/目标2秒。
- action_probe_exact.py：事先固定的单状态四动作补充，每线目标10秒，不覆盖原结果。
- verify_actions.py、verify_actions_exact.py：来源哈希、列可行性、RC、完整定价上界的独立算术重放，不调用定价模型求解。
- analyze_actions.py：首批40次只读汇总。
- PROTOCOL.md、EXACT_FOLLOWUP.md：观察各批结果前固定的预算、范围和结论边界。

```powershell
experiments/.venv/Scripts/python.exe -m unittest discover -s RL -p test_pricing_actions.py -v
experiments/.venv/Scripts/python.exe RL/action_probe.py --output <新目录>
experiments/.venv/Scripts/python.exe RL/verify_actions.py RL/evidence/actions_v1 --output <新审计JSON>
experiments/.venv/Scripts/python.exe RL/action_probe_exact.py --output <新目录>
experiments/.venv/Scripts/python.exe RL/verify_actions_exact.py RL/evidence/actions_exact_v1 --output <新审计JSON>
experiments/.venv/Scripts/python.exe RL/analyze_actions.py RL/evidence/actions_v1 --output <新分析目录>
```

所有路径使用不存在的新输出，不覆盖历史资料。sources.json冻结实际源码字节；states.json保存原输入、当时列池前缀、RMP对偶/参考价格及证据来源。当前已有种子均属开发数据，未用作未来RL最终未见测试。

## 正确性约定

π必须非负，定价使用原整线域。新价格下的目标常数σ=0，不能沿用原RMP目标作为新价格的对偶目标。完整已证的局部最大值q_l给出U=π·资源容量+Σq_l；未证任一线时U为空。不存在完整精确定价证书时，PP incumbent只作为候选列，不能转成最大值上界。

列的有用性按原RMP对偶重算，并与当时池去重；没有使用后续列或后验最优方案初始化。即使某个新U有效，本实验也不恢复全局整数witness或宣称原IP最优。

计时是微基准setup+target读回/验证，含模型建立和初始化，不含末尾释放与JSON落盘，不是在线CG端到端时间。各动作模型从相同机制独立启动，原生time_limit不等同于外部硬墙钟限制。完整native状态、Best Bound和未证记录均保留，但本轮没有启用一般截断界驱动的CG契约。

## 训练准入

先看动作是否在状态间存在可利用差异，并以有效界/有用列和时间共同评价；“较快但无进展”不能直接标成最优动作。如果固定规则已足够，不为加入RL而训练网络。固定状态探针不能证明后续轨迹改善；正式训练前还要做有限在线规则对照，冻结实例级训练/验证/最终测试划分，保留非学习基线和原有证书回退。
