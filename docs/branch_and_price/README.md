# Task02：精确 Branch-and-Price

先读 [TASK02_SUMMARY.md](TASK02_SUMMARY.md)。当前生产代码位于 `code/dwcg/branch_price.py`；不改Task01的紧凑模型与根CG。

- [数学设计及完备性证明](BP_MATHEMATICAL_DESIGN.md)
- [实现和接口](BP_IMPLEMENTATION_REPORT.md)
- [验证及失败解释](BP_VALIDATION_REPORT.md)
- [证书与数值政策](BP_CERTIFICATE_SPEC.md)
- [逐例实验表](BP_EXPERIMENT_SUMMARY.md)
- [验收清单](ACCEPTANCE_CHECKLIST.md)

从仓库根目录运行（输出路径必须不存在）：

```powershell
experiments/.venv/Scripts/python.exe code/dwcg/branch_price.py code/milp/examples/two_lines.json --solver cplex_py --time-limit 300 --node-limit 10000 --output docs/branch_and_price/evidence/my_result.json
```

结果会有完整的全局及节点证书和关联 `_files` 日志目录。最优/不可行已证退出0，未完成退出2，输入/求解器异常退出1。

独立验证（`--offline`不调用求解器，但完整枚举只适用小规模）：

```powershell
experiments/.venv/Scripts/python.exe docs/branch_and_price/independent_bp_verify.py --instance docs/branch_and_price/evidence/validation_final/two_lines_cplex_py/instance.json --result docs/branch_and_price/evidence/validation_final/two_lines_cplex_py/result.json --offline
```

重新执行全部小规模验证：

```powershell
experiments/.venv/Scripts/python.exe docs/branch_and_price/run_validation.py --out docs/branch_and_price/evidence/my_new_validation --boundaries
```

不删除或重用已有实验目录。`validation_v1`、初期smoke、失败测试均保留；正式结论使用 `validation_final` 和最终回归。源码、环境、输入及原始结果均可定位，见各报告和SHA清单。当前没有提交或推送Task02代码。
