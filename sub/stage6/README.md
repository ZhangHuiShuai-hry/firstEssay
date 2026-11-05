# 资源组合诊断与精确对照

resource_dp.py执行每线每个精确(H,R)档的原MILP，然后用二维整数DP组合。它是资源档MILP+DP算法，不称为普通CG。数学等价和截断界见DESIGN.md，实验见REPORT.md。

```powershell
& experiments/.venv/Scripts/python.exe sub/stage6/resource_dp.py code/data/tasks005_lines02_each03-02.json --time-limit 30 --output sub/stage6/evidence/new_run
& experiments/.venv/Scripts/python.exe sub/stage6/test_profiles.py
& experiments/.venv/Scripts/python.exe sub/stage6/paired6.py --budget 20 --output sub/stage6/evidence/new_paired20
```

输出目录必须不存在。CLI预算是run内软预算，落盘另计；paired6统一计入启动/建模/求解/核验/落盘，并预留2秒。不保证Windows硬实时。

未知资源档保留，不能被当不可行。DP下界只来自真实整数代表；DP上界使用同档原生经济目标Best Bound，未知界为null。证书保留每档状态、完整方案、原生界和选档路径。verify6独立枚举每档并用另一个整数主问题核验DP；大输入可关闭枚举，但其证明依赖原生状态和界契约。

当前模块已支持同一节点的原x固定；未将资源档分支或有效不等式接入整线B&P。不同节点必须重新确定档内最优代表。不要把LP资源平均值取整当作真实档。
