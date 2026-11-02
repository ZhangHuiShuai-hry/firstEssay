# 实现审计与最小修复

数学逐项对应表见 MATHEMATICAL_AUDIT；对偶对应表见 CG_DERIVATION。本次未修改紧凑 build_model、完整主问题 build_master、任何局部/全局数学约束、目标经济口径或实例生成规则。

## 调用链与版本

```text
model.py CLI → validate_data → build_model → make_solver → solution_report
solve.py CLI → run_cg → empty_pool
  Phase I / II → build_master → solve_master → master.duals
  → blocks(all line-stations) → pricing.price → make_column → reduced_cost
  → 去重追加列 / 完整定价终止
  → recover_integer → integer build_master → decode_integer → compact.valid
  --verify → verify.cross_validate → 完整枚举/四模型/最终证书
compare_incremental.execute → 注入 IncrementalMaster.sync/solve，PP不变
compare_pricing.execute → 注入 IncrementalMaster + PricingOracle(V1重建/V2持久)
hybrid.run → compact incumbent → columns_from_solution → hybrid_cg.execute
fair_compare.arm → 预算控制 + 精确CG + 剩余预算受限IP
```

V0/V1/V2 是按实验相对定义的：增量实验 V0=重建RMP、V1=增量RMP；定价实验 V1=增量RMP+重建PP、V2=增量RMP+持久PP。默认 `solve.py` 本身仍重建 RMP/PP，README 的“CG-V2”不能作为 CLI 已启用原生适配器的证据。`hybrid_cg.py` 当前是带绝对 deadline 的根CG适配器，真正串行 MIP+CG 在 `hybrid.py`；没有 Branch-and-Price。

`code/experiments/.../support/audit_dlbp.py` 的早期 SciPy 包、复制的 reference_double 与正式 two_lines 并非相同输入。旧包可以辅助验证，但不能混入当前多线实验目标比较。

## 审计结果

| 项目 | 结果 | 证据/限制 |
|---|---|---|
| RMP行系数与对偶 | PASS | 独立全列向量与两阶段检验数逐项比对 |
| 优先对偶后缀累计 | PASS | 所有 k≥s；随机自由等式价格；AND多层图 |
| Phase I/II目标切换 | PASS | 原生矩阵/目标回归及完整独立实例 |
| 持久 PP | PASS | 原生二进制界、每行矩阵、阶段反复切换、独立枚举最优值 |
| 增量 RMP | PASS | 与重建矩阵、RHS、目标、dj一致；人工上界0 |
| 列池 | PASS（当前生产路径） | 排序任务模式元组、每任务至多一次、正RC重复报错，不以重复列判停 |
| 顺序无关性 | PASS | 任务/列利润为加法；chain与chain_permuted比较，允许多重最优列不同 |
| 全站定价 | PASS | blocks遍历所有候选站；独立证书覆盖检查 |
| 超时及异常 | PASS（已覆盖路径） | 原生真实超时、预过期deadline、故障注入；不产生假最优 |
| 受限IP状态 | PASS | 不可行仅对列池；optimal=False；新增作用域字段 |
| 全局整数最优求解器 | NOT IMPLEMENTED | 无分支树、节点定价和全局树界 |
| 截断PP bound用于CG | NOT IMPLEMENTED | 有字段但控制流拒绝未证最优；只复用此前完整轮有效界 |
| 大规模/极端数值可靠性 | NOT RUN | 本任务不运行性能扩展或病态数据压力实验 |

## 确认并修复的问题

原始位置及修复前失败证据在 CONFIRMED_FINDINGS_BEFORE_FIX.md。

1. **高风险 B01**：`code/solver_backend.py` CplexSolver.actualSolve 漏加目标常数，可能记录低于真最优的“上界”。现在补常数、检查有限数，最优时使用完整目标，重新计算带常数 gap；原生 gap 单独保留。
2. **中风险 B02**：同文件 CBC 解析三位小数直接作为精确 bound。新增 cbc_max_bound 按打印精度外扩半单位，补常数；没有日志界保持null。独立单元测试覆盖正负数。该解析专用于当前最大化模型，非通用最小化接口。
3. **中风险 B03**：objective_value 遇 PuLP 固定零 dummy 未赋值返回null。仅对相同有限上下界变量取确定界值；真正缺失的非固定值仍拒绝。完整列0利润四模型现可审计。
4. **中风险 C01**：`code/dwcg/solve.py` 逐轮缺状态/时间/原生界/primal，异常丢弃局部证据。添加这些字段及异常快照，不吞异常、不接受截断候选。恢复异常保留既有LP结论。
5. **中风险 C02**：`code/dwcg/verify_checked.py` 存在弱的重复验证语义。兼容入口委派至严格 verify；verify 对 v2 证书额外检查 complete_pricing、RMP optimal、PP optimal。
6. **低风险 C03**：恢复结果补充 restricted_master_optimal、restricted_master_infeasible_proven、original_integer_optimal_proven；不自动把恢复最优提升为原IP最优。

`common.PricingResult` 维持二元组解包接口；`require_optimal` 异常附 solver_result。`pricing.py` 与 `persistent_pricing.py` 仅增加元数据传递，不变数学目标。全部修复有 `experiments/test_research_audit.py` 回归；原有核心和实验回归亦重新运行。

| 问题 | 交付版本具体位置 | 回归位置 |
|---|---|---|
| B01：CPLEX常数/界/GAP | `code/solver_backend.py:181` 原生界读回；`:189` 最优界；`:192` gap | `experiments/test_research_audit.py:18` |
| B02：CBC打印界 | `code/solver_backend.py:87` cbc_max_bound；`:235` 使用点 | `experiments/test_research_audit.py:29` |
| B03：固定零目标 | `code/solver_backend.py:70` objective_value | `independent_validation.py` zero_profit；84次验收覆盖 |
| C01：状态及部分证书 | `code/dwcg/solve.py:39` _failure；`:98` 逐轮快照；`:120` PP异常；`:195` 恢复异常；`:236` CLI写盘 | `experiments/test_research_audit.py:35` 起；另有原有证书回归 |
| C01：原生元数据 | `code/dwcg/common.py:44`；`pricing.py:56`；`persistent_pricing.py:94`、`:109` | 实验PP矩阵/随机对偶与新增异常测试 |
| C02：旧验证器弱语义 | `code/dwcg/verify_checked.py:5`；`verify.py:150`、`:180` | 新增legacy_verifier及篡改回归 |
| C03：恢复证明作用域 | `code/dwcg/solve.py:16` recover_integer | 新增complete_round_certificate_and_integer_scope |

## 未修复的限制与下一阶段风险

**P1：节点模型尚不存在。** 增量 RMP sync 以 (line,station,pool_index) 识别列，假定列池只追加且旧元素不变；不会检测任意外部重排/替换。同一输入的当前调用链满足该契约。Branch-and-Price 不可直接跨节点复用未隔离状态，必须设计节点约束、列合法性和缓存键。

**P1：证书仍有适配器信任边界。** 旧包装器会把 PricingResult 再封装为普通二元组；代码将其标记 exact_adapter_contract。已审计包装器只在精确成功时返回，小实例独立枚举也复核；未来启发式接口必须显式区分，不能沿用此契约。

**P1：数值政策分散。** 多种容差的职责有文档，但尚无缩放诊断/区间界/有理认证；较松局部接受容差可能与ε相交。没有为让测试通过放宽约束。进入树搜索前需统一本问题的数值接受标准。

**P2：历史报告语言过时。** 部分协议仍写“无Git”，当时的快照确实记录无Git，当前已有Git；没有追写历史报告或改旧源码快照。基线文档解释时间边界。部分报告和计时脚本路径绑定本机；不影响本次模型验证。

**P2：强制进程退出无法保证完整JSON。** Python异常路径已有快照；进程级终止仍需外层checkpoint，未来长实验应使用原子写盘和独立证书schema。未把外层工程重构混入本任务。
