# CG界引导按需资源档

新入口demand_profiles.py，原模型和旧stage1–6保持不变。先执行有预算的整线根CG，再使用完整Phase II定价仿射界或经济初始化MILP有效界填充完整资源档表，只查询乐观整数DP最优路径上的未知档。它是混合精确算法，非纯CG。

```powershell
& experiments/.venv/Scripts/python.exe sub/stage7/demand_profiles.py code/data/tasks005_lines02_each03-02.json --time-limit 30 --output sub/stage7/evidence/new_run
& experiments/.venv/Scripts/python.exe sub/stage7/test_demand.py
& experiments/.venv/Scripts/python.exe sub/stage7/paired7.py --budget 20 --output sub/stage7/evidence/new_paired20
```

输出目录必须不存在。CLI预算从run开始，最终落盘另计；paired7统一计入启动/导入/求解/验证/持久化，预留2秒，Windows软限制。单线程CPLEX seed11/gap0。API支持CBC用于小规模交叉验证。

verify7.audit(data,result,enumerate_profiles=True)逐步重放CG来源、查询路径和档表，用独立整数主问题核对DP；大实例显式关闭枚举时依赖原生最优/Best Bound契约。结果完整保存CG证书、每次精确档查询及所有未查询档上界，不能将它们当不可行。

当前根域算法不支持分支固定/跨节点原生缓存；不提供崩溃恢复。先CG后查询的预算比例固定，性能效果需看REPORT.md，尚未实现自适应预算分配。
