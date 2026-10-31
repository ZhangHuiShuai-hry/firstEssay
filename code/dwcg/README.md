# 工作站列生成：CG-ML-HRC-DLBP-CF

数学文档在 `problem/dwcg/main.tex`，公式编号 CG-1 至 CG-58 对应所给推导，并补充了实现所用的 Phase I 定价公式。

## 运行

在项目根目录，使用 Python 3.10+：

```powershell
python -m pip install -r code/dwcg/requirements.txt
python code/dwcg/solve.py code/milp/examples/single_line.json --verify --output code/dwcg/results/single_line.json
python code/dwcg/solve.py code/milp/examples/two_lines.json --verify --output code/dwcg/results/two_lines.json
python -m unittest discover -s code/dwcg -p "test_*.py" -v
python -m unittest discover -s code/milp -p test_model.py -v
```

输入完全复用原 MILP JSON 格式和数据校验，详见 `code/milp/README.md`。无需另建 CG 数据。`code/dwcg` 依赖同项目的 `code/milp/model.py`，请保留相对目录结构。普通 CG 不使用枚举；`--verify` 仅用于小实例，会额外枚举所有局部模式并求解完整列 LP、完整列 IP、紧凑 MILP 及其 LP 松弛。默认每站枚举组合数上限 100000，可用 `--enumeration-limit` 调整。

可选：`--no-integer` 跳过受限整数恢复，`--epsilon 1e-7` 设置正检验数容差，`--max-iterations 1000` 设置每阶段最大 RMP 求解次数，`--verbose` 输出 CBC 日志。定价器不设置时间截断，且要求 CBC 证明最优、MIP gap 为零；未证明最优就报错，不能冒充已完成精确定价。CBC 使用一线程，原始/对偶可行容差设置为 1e-8。所有结论仍受浮点求解容差约束。

## 代码结构

| 文件 | 职责 |
|---|---|
| `common.py` | 兼容原数据与模型；不可变工作站列；完整列枚举；显式列系数和检验数 |
| `master.py` | RMP/FMP 的 LP/IP；Phase I 人工变量；整数解码及原约束核验 |
| `pricing.py` | 独立站点 MILP 精确定价；累积优先对偶后缀、模式调整收益 |
| `solve.py` | 空列初始化、两阶段 CG、日志与上下界、受限整数恢复、命令行入口 |
| `verify.py` | CG / 完整列 LP / 完整列 IP / 原始 MILP 自动交叉验证 |
| `test_dwcg.py` | 单元测试及固定种子小实例回归 |

主问题每站选择一列，包含空列。任务可选行 ≤1，必拆行 =1；优先关系使用所有工作站前缀；最低回收行采用负号 ≤ 形式。LP 的 lambda 不显式设置上界，因为每站凸组合已保证 ≤1，避免额外上界价格影响对偶核对。正式循环每站每轮至多加一条最优正检验数列，按任务模式组合去重；退化导致目标暂时不变并不影响继续加列。

## Phase I 与 Phase II

Phase I 加入必拆缺额和回收缺额人工变量，以 **最大化负人工变量总和** 实现材料中的最小化模型。真实列目标系数为零，因此定价不能包含原利润、固定费用或配置费用。定价仍保留人工/机器人共享资源价格，任务唯一性价格、回收价格、优先价格以及凸组合价格。

人工总和为零后移除人工变量，Phase II 恢复净利润最大化，重新求解 RMP 并提取相应对偶。每轮所有 PP 都精确求解后，才判断是否不存在大于 epsilon 的检验数。Phase I 无正列且其修复上界严格小于负可行容差时，报告完整列 LP 不可行；精度不足时报告 `phase_I_numerically_inconclusive`。

PP 仅保证任务模式唯一、节拍、站点及人机配置精确逻辑、疲劳。PP 不要求前驱闭包，不加入必拆、最低回收或全局资源上限。前驱和后继的对偶调整分别加、减，且只累加 k≥s 的前缀对偶。疲劳是局部约束，不额外添加主问题疲劳对偶。

## 输出与结论范围

### 最终精确定价终止证书

每轮完成定价后的日志增加 `duals`（该轮 RMP 的完整行对偶快照）；Phase I 同时记录 `artificials`（人工变量名称及值）。Phase I 不可行返回时还输出 `final_duals` 和 `phase_I_lp_upper_bound`。这些只是记录求解结果，没有修改 MILP、FMP、RMP 或 PP 的目标及约束。

当声称收敛时，验证器要求最后一条历史记录为 Phase II，且最大检验数 ≤ epsilon + 验证数值容差。其目标和上界必须与最终返回值一致。验证器使用该轮保存的对偶值，逐一枚举全部局部可行列，独立计算 `目标系数 - 对偶加权列系数`，比较每站的最大检验数、报告中的最大值和修复上界。同时检查每个站点恰有一条定价结果、每行恰有一个有限对偶价格、对偶符号、原始/对偶目标一致和最终对偶快照一致。缺少站点或必需数值不能通过证书；重复站点、错误数值或相互矛盾的记录会报错。

Phase I 声称不可行时，除枚举完整列 LP 确认不可行，还检查最后一轮 Phase I 的人工变量覆盖、非负性、分量总和、负人工目标、最终人工总和及上界的一致性；人工总和必须大于可行容差，独立重算的上界必须严格小于负可行容差。保存的 Phase I 对偶还必须满足人工变量对应的对偶约束；使用同一完整列池求解完整 Phase I，交叉核对其目标及上界。

结果区分以下字段：

| 字段 | 含义 |
|---|---|
| `model_consistency_passed` | 独立模型比较通过 |
| `optimal_objective_cross_validated` | 声称的 LP 最优目标与完整列 LP 一致 |
| `cg_infeasibility_checked` | 声称的不可行结论与完整列 LP 一致 |
| `pricing_termination_certificate_verified` | 保存对偶下的逐站完整枚举检验数和终止证书均通过 |
| `phase_I_infeasibility_certificate_verified` | Phase I 人工变量及负上界证书通过 |
| `termination_certificate_verified` | 对应阶段的完整终止证书通过 |
| `cg_verified` | 交叉验证结论与终止证书均通过 |
| `passed` | 模型一致性与 CG 验证均通过 |

旧结果即使目标正确，若缺少最后一轮证书，仍保留 `optimal_objective_cross_validated: true`（或不可行交叉检查标志），但 `certificate_status: "missing"`、`verification_status: "inconclusive"`，且 `cg_verified`、`passed` 都为 false。重新运行算法才能补充真实证书。证书验证成功时 `termination_certificate` 保存每站报告值与枚举值、对偶目标和重算上界。迭代上限、Phase I 数值不确定不会因目标偶合而升级为 CG 验证通过。

`--verify` 模式下若证书缺失使 `passed: false`，命令也不会以退出码 0 表示验证成功。合法的不可行结果仍按原约定返回退出码 2。

`--verify` 分别报告 `model_consistency_passed`（独立模型比较）和 `cg_verified`（CG 最优或不可行结论经完整列模型核验），只有两者都通过才有 `passed: true`。迭代上限和 Phase I 数值不确定返回 `verification_status: "inconclusive"`、`passed: false`；矛盾结论、非有限数值或错误上下界会抛出异常。验证器检查最终及迭代历史中所有已有的 Phase II LP 上下界，截断运行也检查；Phase I 的目标不同，不与利润最优值混用。即使整数不可行，只要两种 LP 可行，仍检查 DW LP ≤ 紧凑 LP。零目标函数仅忽略系数为零的 PuLP 辅助项，不掩盖真实目标项缺失。

`status`、`lp_converged`、`lp_objective`、`lp_upper_bound` 明确记录根节点 LP 状态。`history` 含阶段、轮次、目标、最大检验数、各站最优定价配置、每轮新增列数、人工总和（Phase I）和 LP 上界。最终保存非零 lambda、列数及行对偶。行键中的优先边编号从 0 开始，对应输入边列表；站号从 1 开始。

对最大化，当前 RMP 值是完整列 LP 的下界；修复上界为 RMP值 + Σ max(0, 各站最大检验数)。这个下界不能称作整数问题的可行利润下界。停止时仍保存实际修复上界。超过迭代上限报告 `iteration_limit`，不报告 LP 最优；输出中记录停止阶段。退出码：LP 收敛为 0；不可行、截断或数值结论不足为 2；数据/求解器错误为 1。LP 收敛但受限整数模型不可行时，退出码仍为 0，整数状态需单独读取。

`integer_recovery` 在已生成列上求解二进制主问题，并将恢复的 x/y/u/h/r 代回原 MILP 全部约束。结果总是标记 `optimal: false`，表示未作一般性的原整数全局最优宣称。若受限列整数不可行，只报告 `infeasible_on_generated_columns`；原问题可能仍可行。LP 可行也不保证整数可行。`integer_upper_bound_gap` 是 LP 上界与已恢复整数利润之差，不是受限整数求解器的 MIP gap。

完整列 IP 与原 MILP 等价，但完整列 LP 不必等于紧凑 LP。正确比较为 CG LP = 完整列 LP；最大化的界关系为 IP ≤ 完整列 LP ≤ 紧凑 LP。未来若需一般性的全局整数最优性证明，需要 Branch-and-Price，本版未实现。

## 已运行的合成示例

| 算例 | CG LP / 完整列 LP | 受限整数恢复 | 完整列 IP / 原 MILP | 紧凑 LP |
|---|---:|---:|---:|---:|
| single_line | 21 | 21 | 21 | 22.239912 |
| two_lines | 27 | 24 | 24 | 36.701635 |

保存在 `results/*.json`。单线每站完整局部列数 23，双线四个站分别为 23、23、8、8。测试覆盖 PP vs 完整枚举、显式列检验数 vs 求解器 reduced cost、两阶段根节点 CG vs 完整列 LP、整数等价和解码、零目标、零疲劳、紧共享资源、异质站点空缺、LP 可行但整数不可行及截断。所有示例为合成数据，疲劳只代表单周期模型。
