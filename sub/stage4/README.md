# 整线精确Branch-and-Price

入口branch_price.py，节点CG为line_bp_node.py，节点定价为line_bp_pricing.py；bp_verify.py为独立节点/整树验证器。设计见DESIGN.md，结果见REPORT.md。旧stage1–3入口保持不变。

```powershell
# 输出目录必须不存在；默认单线程CPLEX、seed11、零gap。
& experiments/.venv/Scripts/python.exe sub/stage4/branch_price.py code/data/tasks005_lines02_each03-02.json --time-limit 30 --node-limit 1000 --output sub/stage4/evidence/new_run
& experiments/.venv/Scripts/python.exe sub/stage4/bp_verify.py sub/stage4/evidence/new_run
& experiments/.venv/Scripts/python.exe sub/stage4/test_bp.py
```

大于独立枚举保护规模时，可显式增加`--no-enumeration`，仅做算术、树及原生求解状态重放。不能把该模式称为完整枚举认证。

结果含完整节点限制、列池、每轮RMP原始/对偶/人工变量、精确PP、修复上界、分支与剪枝、活动节点、全局见证、LB/UB/Gap及停止原因。unknown UB以null表示，不能用于剪枝。仅当证书证明全局最优/不可行时CLI退出0；未完成退出2；solver_error退出3。CLI运行上限为run内软预算，压缩落盘另计，summary分开记录algorithm_plus_persistence_seconds，不宣传严格E2E硬预算。

第一版使用重建式节点PP/RMP；stage3原生缓存不支持节点域，因此本版未接入。未实现崩溃恢复、全量增量证据存储、RL或大规模性能优化。原始主线工作站B&P和本整线B&P是两个独立入口。

复现实验时选择全新目录：

```powershell
& experiments/.venv/Scripts/python.exe sub/stage4/validate_suite.py sub/stage4/evidence/new_validation
```

小规模Oracle不被生产算法导入；它独立枚举每任务未选/站点/模式，过滤节点固定域，再构造完整LP/IP。正式搜索不通过枚举初始化节点。
