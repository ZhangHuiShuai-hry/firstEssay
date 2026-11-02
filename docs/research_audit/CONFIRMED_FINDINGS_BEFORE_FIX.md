# 修复前确认的问题

2026-11-02；原始提交 `2a1f76cc62bbef2a4c6592589972878986ba38cf`。

| ID | 等级 | 位置（原始版本） | 事实与数学影响 | 最小修复 |
|---|---|---|---|---|
| B01 | 高 | `code/solver_backend.py` CplexSolver.actualSolve，原生 get_best_objective 读回 | 回归 `max 3x±7` 已证最优但 best_bound=3，遗漏目标常数，正常数时上界低于真实最优。PP exact rc 显式重算，根 CG 的现有 exact UB 不受影响；不可直接用该字段支持截断定价界。 | 原生 bound 加回 PuLP 常数，有限数检查；最优时使用完整目标。 |
| B02 | 中 | 同文件 CBC 的 `Upper bound` 正则读取 | CBC 日志通常只保留三位小数；直接转换可能向下舍入最大化上界，且没有补回目标常数。现有核心 CG 不用截断 PP bound。 | 按打印精度向外扩张半个末位单位，加目标常数；缺失界保持 null。 |
| B03 | 中 | 同文件 objective_value | 独立四模型零利润例，两后端的 full IP/LP 均 optimal，但事件 objective/best_bound 为 null。PuLP fixObjective 在 actualSolve 期间插入系数为1的固定零 dummy，dummy 值可能缺失。 | 仅对有限且上下界相同的变量使用确定的界值；真正缺失的自由变量继续拒绝。 |
| C01 | 中 | `code/dwcg/solve.py` run_cg | 定价异常会抛出并丢失该函数的部分 history；逐轮缺少定价状态、时间、原生界、完整覆盖标记和 RMP primal witness。新增回归实际失败。 | 保持异常契约，异常附带部分证书，CLI 在输出路径写入失败 JSON；补充成功轮字段。 |
| C02 | 中 | `code/dwcg/verify_checked.py` cross_validate | 旧验证器可在目标一致时 passed=True，无对偶/定价证书；当前 CLI 使用较严格 verify.py，旧入口仍可误用。 | 兼容入口委派到当前验证器；增加缺证书回归。 |
| C03 | 低 | `code/dwcg/solve.py` recover_integer | 原输出已正确 optimal=False/scope=restricted，但未显式分别记录 restricted-master optimal 与 original optimal。 | 增加三类证明字段，不改变求解模型。 |

修复前新增测试：`evidence/defects_before.txt`，2 个断言失败、4 个子测试/方法错误；现有回归仍各45项通过。独立验证26实例×2求解器=52次，其中50次PASS，2次因B03无法读取零目标而FAIL；未把失败算成通过。原始结果保存在 `evidence/independent_baseline`。
