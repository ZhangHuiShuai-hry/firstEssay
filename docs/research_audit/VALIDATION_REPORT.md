# Task01 小规模正确性验证报告

## 验收结果

**PASS：28个不同实例，重建式CG双求解器56次，增量RMP+持久PP的CPLEX28次，总84次验收运行全部通过。** 实例每线最多6任务、总任务最多10；一任务例用于LP可行/IP不可行边界，没有运行120/150任务拆卸实验。

每次保存 instance.json、config.json（目录级配置和当次源码哈希）、result.json、求解器事件和原生日志。环境/锁文件位于同一evidence根目录，由PROJECT_BASELINE统一关联。没有把不存在的Best Bound、incumbent或gap补为0。

独立oracle不调用生产 make_column、coefficients、build_master 或定价模型来生成答案；枚举任务“不选或一种允许模式”，独立重算配置逻辑、时间、疲劳、回收和利润；独立组装完整主问题。生产函数作为被测对象逐项比较。优化仍使用相同PuLP接口与求解器，但数学构造、列算术及可行性/检验数检查独立；双求解器降低共同状态错误风险，不能声称完全独立求解器实现。

独立检查：完整列集合和每列属性；所有稀疏行向量；Compact-IP→列解；Full-IP和Full-LP→紧凑模型；四模型目标及可行性包含关系；CG与Full-LP目标；逐轮 primal/dual/覆盖/RC/修复界；两阶段任意自由/非负对偶的PP最优值；人为放松的合法定价上界修复完整对偶的定理。

已独立复核374轮保存对偶/定价证书，另做360次两阶段任意对偶定价对比（不含CG本身的PP调用）。多重最优仅比较目标、可行性与检验数，不要求相同列。

## 四模型与CG结果

表中列出CPLEX目标，CBC全部对应状态一致、目标差≤1e-5；原生CG亦与独立Full-LP一致。列数按每个线站列出，包含空列。不可行栏表示已证模型不可行；CG为空时通过Phase I不可行证书，不是求解异常。

| 实例 | Compact-IP | Compact-LP | Full-IP | Full-LP | CG-LP | 各块完整列数 | 结论 |
|---|---:|---:|---:|---:|---:|---|---|
| and_diamond | 不可行 | 16.33333333 | 不可行 | 不可行 | 不可行 | 13/13/13 | PASS |
| chain | 16 | 17 | 16 | 16 | 16 | 67/67/67 | PASS |
| chain_permuted | 16 | 17 | 16 | 16 | 16 | 67/67/67 | PASS |
| dual_degenerate | 8 | 8 | 8 | 8 | 8 | 16/16 | PASS |
| generator_n2_L1_s11 | 14.15 | 14.15 | 14.15 | 14.15 | 14.15 | 6 | PASS |
| generator_n3_L2_s14 | 24.59 | 28.86439903 | 24.59 | 24.59 | 24.59 | 36/24 | PASS |
| generator_n4_L1_s12 | 17.83 | 20.23 | 17.83 | 17.83 | 17.83 | 72/72 | PASS |
| generator_n5_L2_s15 | 45.72 | 53.72 | 45.72 | 45.72 | 45.72 | 324/324/416/416 | PASS |
| generator_n6_L1_s13 | 56.63 | 64.93 | 56.63 | 59.38 | 59.38 | 137/137 | PASS |
| heterogeneous_gap | 3 | 3 | 3 | 3 | 3 | 4/4 | PASS |
| human_only | 6 | 7.66666667 | 6 | 6 | 6 | 3/3 | PASS |
| human_scarce | 6 | 7.66666667 | 6 | 6 | 6 | 7/7 | PASS |
| impossible_recovery | 不可行 | 不可行 | 不可行 | 不可行 | 不可行 | 7 | PASS |
| joint_only | 4 | 6.66666667 | 4 | 4 | 4 | 3/3 | PASS |
| lp_yes_ip_no | 不可行 | 4 | 不可行 | 4 | 4 | 3/2 | PASS |
| multi_optimum | 10 | 10 | 10 | 10 | 10 | 7/7 | PASS |
| negative_profit | 0 | 0 | 0 | 0 | 0 | 7/7 | PASS |
| overlong_required | 不可行 | 不可行 | 不可行 | 不可行 | 不可行 | 4 | PASS |
| phase1_impossible | 不可行 | 不可行 | 不可行 | 不可行 | 不可行 | 7/7 | PASS |
| robot_only | 6 | 7.66666667 | 6 | 6 | 6 | 3/3 | PASS |
| robot_scarce | 6 | 7.66666667 | 6 | 6 | 6 | 7/7 | PASS |
| single_line | 21 | 22.23991205 | 21 | 21 | 21 | 23/23 | PASS |
| tight_fatigue | 6 | 7.66666667 | 6 | 6 | 6 | 3/3 | PASS |
| tight_recovery | 6 | 7.66666667 | 6 | 6 | 6 | 7/7 | PASS |
| two_lines | 24 | 36.70163534 | 24 | 27 | 27 | 23/23/8/8 | PASS |
| zero_fatigue | 6 | 7.66666667 | 6 | 6 | 6 | 3/3 | PASS |
| zero_human_load | 6 | 7.66666667 | 6 | 6 | 6 | 3/3 | PASS |
| zero_profit | 0 | 0 | 0 | 0 | 0 | 7/7 | PASS |

单线实际值：IP=21，Full-LP=21，Compact-LP=22.23991205。双线IP=24，Full-LP=27，Compact-LP=36.70163534。明确否定 Full-LP 一般等于 Compact-LP。双线根LP仍有整数间隙3，不能证明当前恢复的24仅凭根CG就是原IP最优；本次是由完整列IP和直接紧凑MILP另外证到24。

LP可行/IP不可行例：A线一项必拆任务可H或R；B线J任务权重2、最低回收1，资源上限各1。LP令A在H/R各0.5，B的J列0.5和空列0.5，资源均1；整数B必须选J耗尽两类资源，A无法执行。Full-LP=4，两个IP均不可行。

dual_degenerate中两任务都必拆，终端优先行等于两个任务覆盖等式的线性组合；可沿μ与两任务自由π的补偿方向改变对偶而保持所有列价格及对偶目标不变，显式构成非唯一对偶。zero_human_load中人工模式β=0、Fmax=0，仍需人工配置，正确区分“零负荷”和“无人工”。

## 场景覆盖

| 要求 | 对应实例/测试 | 结果 |
|---|---|---|
| 单线、双线、不同站数 | 参考例、generator、chain | PASS |
| 简单AND、多层AND | single_line、and_diamond、chain | PASS |
| 必拆/可选 | tight_recovery、chain、negative_profit | PASS |
| H-only / R-only / J-only | human_only、robot_only、joint_only | PASS |
| 零疲劳任务/紧疲劳 | zero_human_load、zero_fatigue、tight_fatigue | PASS |
| 人工/机器人资源紧张 | human_scarce、robot_scarce、two_lines | PASS |
| 最低回收紧张/不可能 | tight_recovery、impossible_recovery | PASS |
| 零利润、负利润、空站、异质站空缺 | zero_profit、negative_profit、heterogeneous_gap | PASS |
| Phase I不可行 | phase1_impossible、overlong_required | PASS |
| LP可行IP不可行 | lp_yes_ip_no | PASS |
| 多重最优、退化/非唯一对偶 | multi_optimum、dual_degenerate | PASS |
| 任务输入顺序 | chain / chain_permuted | PASS |
| 时间截断、未知状态、证书篡改 | 原有证书测试、实验真实超时、新增故障注入 | PASS |
| 极端数值缩放/近机器精度病态实例 | 未纳入本次有限小规模验证 | NOT RUN |

## 回归和失败记录

| 运行 | 实际结果 | 证据 |
|---|---|---|
| 修改前核心CBC | 45/45 PASS | baseline_cbc.txt |
| 修改前核心CPLEX | 45/45 PASS | baseline_cplex.txt |
| 修改前独立验证 | 50/52 PASS；2次零目标事件缺值FAIL | independent_baseline/summary.json |
| 修改前新增缺陷回归 | FAIL，重现常数上界及缺少证书接口 | defects_before.txt |
| 首次native_final | 4/26 PASS，22次测试适配器接口错误 | native_final/summary.json；不计入验收通过 |
| 修正测试适配器native_final_v2 | 26/26 PASS | native_final_v2/summary.json |
| 最终核心CBC | 45/45 PASS | acceptance_cbc.txt |
| 最终核心CPLEX | 45/45 PASS | acceptance_cplex.txt |
| 最终全部实验回归 | 32/32 PASS，包含新增8项 | acceptance_experiments.txt |
| 最终独立模型验收 | 56/56 PASS | acceptance_rebuilt、acceptance_extra |
| 最终原生适配器验收 | 28/28 PASS | acceptance_native、acceptance_extra_native |
| 离线证书重放 | PASS，无求解器调用 | offline_certificate_replay.json |
| 全部离线证书及篡改拒绝 | 84份PASS，6类篡改均拒绝 | offline_all_certificates.json |

首次native_final的lambda适配器只接受LP签名，却把整数恢复integer=True送入同一接口；这是新增测试脚本错误，非生产模型错误。改为原生根CG recover=False，退出注入后单独调用原生产整数恢复。旧失败文件保留。修改前零目标失败属于真实后端日志缺陷B03，已修复并覆盖回归。没有抹除失败或用修复后结果覆盖旧记录。

真实极短超时测试是通用150二进制变量求解器状态夹具，不是150任务拆卸实验；CPLEX许可证1201变量测试也是纯LP接口探测。均未运行用户禁止的大规模优化作业。

## 复现

```powershell
experiments/.venv/Scripts/python.exe experiments/run_regressions.py --solver cbc
experiments/.venv/Scripts/python.exe experiments/run_regressions.py --solver cplex_py
experiments/.venv/Scripts/python.exe -m unittest discover -s experiments -p test_*.py -v
experiments/.venv/Scripts/python.exe docs/research_audit/independent_validation.py --out docs/research_audit/evidence/my_new_rebuilt
experiments/.venv/Scripts/python.exe docs/research_audit/independent_validation.py --out docs/research_audit/evidence/my_new_native --native
```

运行目录必须不存在；脚本拒绝覆盖。全量当前脚本一次覆盖全部28实例，验收原始证据因两个边界后加入而分为26+2实例。最终代码及每轮运行源码哈希均可核查；历史失败仍使用当时版本哈希，不能混成同一实现的成功率。

## 验收状态

Phase 0：基线、工作区、版本、求解器、SHA清单、功能/缺失、历史保护全部PASS；历史大规模结论重跑NOT RUN。

Phase 1数学：紧凑/完整列模型、双向证明、LP关系、RMP对偶、全部RC项、两阶段、完整定价终止及上界公式/条件全部PASS。

Phase 1程序：枚举、四模型、PP独立验证、双向映射、独立dj、双求解器、回归、失败解释全部PASS。证书是浮点容差下数值证明；精确有理/区间认证NOT IMPLEMENTED。截断PP的Best Bound驱动CG扩展NOT IMPLEMENTED，但不影响当前“只接受精确定价”算法验收。
