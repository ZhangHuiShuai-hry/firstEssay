# B&P 证书规范（certificate_version=1）

## 1. 作用域与输入

`algorithm=deterministic_DFS_exact_Branch_and_Price`。`proof_scope=MILP_global_integer_optimality_with_recorded_floating_point_tolerances`。这是一套记录容差下的数值最优性证书，不是有理数或区间算术的严格机器形式证明。

输入另存instance.json；主结果的input_sha256是 `json.dumps(data,sort_keys=True,separators=(',',':'))` 的UTF-8 SHA-256。code_version包含实际git_head和九个生产源文件的逐字节SHA-256，能区分“基线提交+新增未提交代码”。不把基线提交号误称为包含新增代码的提交。

每次CLI输出必须是新路径。根结果JSON关联 `<output_stem>_files/` 的输入、配置、各节点JSON和原生求解器日志；库API的output_dir也必须不存在。直接库调用不指定output_dir时仍返回完整内存证书，但临时求解器日志按旧后端策略回收；正式实验均指定独立输出目录。

## 2. 全局字段

| 字段 | 语义 |
|---|---|
| status | optimal_within_tolerance / infeasible_proven / time_limit / node_limit / numerical_uncertain / solver_error |
| solver_backend | cbc或cplex_py；单线程；不跨节点复用原生模型 |
| numeric_policy / search_config | 下述数值政策及总时间、节点、CG迭代预算；DFS顺序0先于1 |
| has_integer_incumbent | 是否有经数据级与原Compact约束检查的整数方案 |
| integer_incumbent_objective / solution / node | 最佳整数利润、witness和取得该方案的节点 |
| global_lower_bound | 等于已验证incumbent；无incumbent为null，不初始化为0 |
| global_upper_bound | 活动叶与保留的按容差关闭叶的有效界；未知为null；全部不可行时null表示不适用 |
| absolute_gap / relative_gap | UB-LB；max(0,UB-LB)/max(1,abs(LB))。缺任一界为null |
| global_integer_optimal_proven | 仅在完整树安全闭合且有incumbent时为true |
| global_infeasibility_proven | 仅在完整树每叶均证不可行且无incumbent时为true |
| root_lp_status / objective / upper_bound | 根节点求解状态、实际RMP利润及完整定价修复界；不冒用整数值 |
| total_nodes_created / processed / pruned | 包含未访问的已创建节点；processed包括基于继承界直接剪枝 |
| total_pricing_calls / total_columns_generated | 定价及缺池局部可行性调用；新增真实列，不计已知根空列 |
| wall_time / termination_reason | 实际墙钟及终止原因 |
| node_history / processing_order / open_nodes | 全部创建节点、确定性处理顺序，以及所有未访问/未解决节点 |

时间/节点限制和异常默认不签发全局最优标志。即便某个中断状态已经有较好整数解，也保留活动节点及其有效继承界。算法不利用截断PP Best Bound为当前不完整轮签发新界。

## 3. 节点记录

节点保存node_id、parent_id、depth、从父节点产生的branching_variable/value、完整restrictions（原始坐标顺序为line/task/station/mode）、inherited_upper_bound、node_lp_upper_bound、safe_upper_bound、upper_bound_source、phase1/2_status、columns_generated、pricing_calls、solve_seconds、node_status、termination_reason。

branched节点保存branch_decision的LP分数值和两个children；孩子只新增同一个坐标的0/1固定。pruned节点保存pruning.kind和证明依据，区分局部空域、Phase I不可行、界支配、整数闭合。lower_bound_before/after记录当时的全局incumbent，支持重放剪枝时间顺序。整数点记录integer_witness；改进时另有incumbent_update。

node_status：open、branched、pruned_local_infeasible、pruned_phase1_infeasible、pruned_bound、pruned_integer，以及unresolved_前缀的未完成原因。所有open/unresolved均参与全局上界；null继承界不伪造有限数。

certificate内容：

- restrictions：该节点的全部固定。
- initialization：逐块继承数、合法数；缺列时的局部可行性MILP证书。
- initial_pool：全部初始合法列的assignments。Column的经济和资源属性可从输入独立重算。
- rounds：每个Phase I/II轮的完整池、λ原始值、人工变量、RMP状态和底层结果、raw/effective对偶、对偶目标、全部PP、完整定价标记、最大检验数、实际修复界、增加的列。
- solver_events：当前节点的全部原生调用状态、incumbent/bound、时间、配置和日志路径。
- error：异常类型/原因/求解状态；一般异常包括traceback。失败不自动转成节点不可行。

NodeResult另记录status、lp_objective、跨完整轮取最小的lp_upper_bound、最后实际RMP的lp_solution和全体恢复x。已完成节点状态为node_lp_optimal_proven、local_infeasible_proven或phase1_infeasible_proven；其他状态不能视为节点已安全关闭。

## 4. 定价证书契约

生产节点只接受NodePricingResult(PricingCertificate,column)，普通二元组不具证明地位。PP字段含line/station/phase/purpose、fixed_variables、status、optimal、has_incumbent、incumbent、objective、best_bound、reduced_cost、assignments、solve_seconds及solver_result。

fixed_variables仅包含该块的task/mode/value，必须与调用节点一致；purpose区分local_feasibility与pricing。可行性目标0不作为reduced cost。optimal标签还必须有底层optimal=true/status=optimal；infeasible标签必须有底层status=infeasible、optimal=false。所有真实列重算本地可行性、配置逻辑、成本和分支固定；实际RC使用完整行向量重算。

PP未证最优时保留其incumbent/best_bound以便审计，但不会把它的incumbent当作最大化上界，也不会用其best_bound完成本轮CG。本版没有该扩展。局部初始化可可靠证明空域；在已知有合法列的正常定价中出现infeasible则视为矛盾异常。

## 5. 数值政策与安全界

| NumericPolicy字段 | 默认值 | 职责 |
|---|---:|---|
| lp_primal_tolerance | 1e-8 | 传给求解器的LP原始容差 |
| lp_dual_tolerance | 1e-8 | LP最优性、对偶符号及人工对偶边界的允许微残差 |
| pricing_integrality_tolerance | 1e-7 | PP二进制值及后端整数容差 |
| branch_integrality_tolerance | 1e-7 | 恢复x是否需要分支；不是整数witness的唯一验收依据 |
| column_local_tolerance | 1e-8 | 舍入后的列节拍、疲劳及属性重算 |
| reduced_cost_epsilon | 1e-7 | 每块精确定价的加列/终止阈值 |
| artificial_tolerance | 1e-7 | Phase I人工总量和严格负不可行界阈值 |
| primal_validation_tolerance | 1e-6 | RMP原始解与原Compact约束独立检查 |
| bound_consistency_tolerance | 1e-5 | 目标、对偶、界与利润的数值一致性 |
| global_absolute_tolerance | 1e-5 | 全局绝对利润闭合阈值 |
| global_relative_tolerance | 1e-8 | 相对闭合阈值，允许显式设0 |

全局allowance(LB)=max(abs_tol,rel_tol*max(1,abs(LB)))，即绝对或相对阈值满足一个即可。所有阈值在输出中保存，不统一成单一值，也不为了测试放宽原约束。某些自定义求解器容差可能超出本机后端合法范围；本机CPLEX API实际返回simplex optimality最小值1e-9。非法参数安全输出solver_error，不静默调整。

微小对偶越界只在lp_dual_tol内投影：LE价格至非负，Phase I LE至[0,1]、耦合等式至[-1,1]，凸性自由。定价用effective价格，独立重算D；若|D-Z_RMP|>bound_tol则停止。实际UB=max(D,Z_RMP)+Σmax(0,rho)，另存rmp_formula_upper_bound=Z_RMP+Σmax(0,rho)。前者始终不低于修复完整对偶目标D+Σmax(0,rho)。子节点safeUB取父继承界与本节点历轮完整界的最小值。

每块rho≤epsilon不代表全局绝对误差≤epsilon。all-x整数但实际UB未按全局容差闭合时，保存真实可行整数LB及未解决节点，返回numerical_uncertain。极小RC专项证据中LB=0、UB=1.2e-7、目标绝对阈值1e-12，因此没有假签发最优，也未将Gap改为0。

保留容差剪枝叶的真实UB，最终Gap可以是很小的非零值。仅当UB比整数LB低的残差在bound_tol内时做外向max(UB,LB)，超过该容差则报告上下界矛盾，不掩盖。原生求解器预算为剩余时间；Python建模/序列化/库加载不可中断，故墙钟时限是受检查的软预算，不是硬实时保证。若已完整证明后略超预算，证明仍有效。

## 6. 独立验证入口

完整节点LP/IP重解、枚举定价与树覆盖：

```powershell
experiments/.venv/Scripts/python.exe docs/branch_and_price/independent_bp_verify.py --instance docs/branch_and_price/evidence/validation_final/two_lines_cplex_py/instance.json --result docs/branch_and_price/evidence/validation_final/two_lines_cplex_py/result.json --solver cplex_py --output <新的验证JSON路径>
```

加`--offline`则不调用任何求解器：枚举每块合法列、核对各轮primal/dual与完整最大RC、局部空域、修复界、分支/DFS、历史LB、剪枝与全局结论。小规模离线枚举仍可能指数增长，受Task01独立枚举组合数上限保护；大规模不能因此宣称已独立认证。

`replay_certificates.py` 对最终64份树、22份独立节点完成离线重检，拒绝10类伪造证书，并校验实际被测生产源码哈希及所有Task01 tracked文件未改。该程序的固定输出目录必须不存在；证据已存在时应选新目录或参考单文件入口，不删除旧证据。
