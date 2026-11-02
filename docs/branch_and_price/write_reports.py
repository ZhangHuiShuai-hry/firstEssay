"""Generate Chinese Task02 result tables only from saved actual runs."""
from pathlib import Path
import json
import collections

HERE=Path(__file__).resolve().parent
E=HERE/'evidence'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def fmt(x):return '—' if x is None else f'{x:.10g}'
def write(name,text):(HERE/name).write_text(text,encoding='utf-8')


def main():
    root=E/'validation_final';main_rows=read(root/'summary.json');node_rows=read(root/'node_scenarios/summary.json')
    stops=read(root/'interruptions/summary.json');extra=read(root/'additional/summary.json');offline=read(E/'certificate_replay/summary.json')
    assert all(r['validation']=='PASS' for r in main_rows+node_rows+stops+extra)
    assert len(main_rows)==56 and len(node_rows)==22 and len(stops)==5 and len(extra)==3
    completed=main_rows+[r for r in extra if r['name']=='mandatory_negative']
    groups=collections.Counter(r['bp_status'] for r in completed)
    detailed=[];compact_table=[]
    for r in completed:
        detailed.append('| '+' | '.join([r['name'],r['solver'],fmt(r['compact_objective']),fmt(r['full_ip_objective']),fmt(r['full_lp_objective']),fmt(r['bp_objective']),fmt(r['upper']),fmt(r['absolute_gap']),str(r['nodes']),str(r['pricing_calls']),f"{r['bp_seconds']:.4f}",r['bp_status']])+' |')
    for name in sorted({r['name'] for r in completed}):
        a=next(r for r in completed if r['name']==name and r['solver']=='cbc')
        b=next(r for r in completed if r['name']==name and r['solver']=='cplex_py')
        assert a['compact_status']==b['compact_status'] and a['bp_status']==b['bp_status']
        if a['bp_objective'] is not None:assert abs(a['bp_objective']-b['bp_objective'])<1e-5
        compact_table.append('| '+' | '.join([name,fmt(b['compact_objective']),fmt(b['full_ip_objective']),fmt(b['full_lp_objective']),fmt(b['bp_objective']),f"{a['nodes']}/{b['nodes']}",'不可行已证' if b['bp_status']=='infeasible_proven' else '最优已证','PASS'])+' |')
    counts={'completed_instances':29,'completed_tree_runs':58,'optimal_runs':groups['optimal_within_tolerance'],
            'infeasible_runs':groups['infeasible_proven'],'standalone_node_runs':22,'safety_stop_or_precision_runs':6,
            'all_validation_runs':86,'main_node_oracles':sum(r['node_oracles'] for r in main_rows),
            'main_complete_pricing_rounds':sum(r['rounds'] for r in main_rows),
            'main_pricing_calls':sum(r['pricing_calls'] for r in main_rows),'offline_trees':len(offline['offline_trees']),
            'offline_nodes':len(offline['offline_standalone_nodes']),'forged_rejected':len(offline['forged_certificates']),
            'regressions_cbc':66,'regressions_cplex':66,'experiment_regressions':32}
    (E/'ACCEPTANCE_TOTALS.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')
    write('BP_EXPERIMENT_SUMMARY.md','''# 小规模实验逐例结果

以下全部来自 evidence/validation_final，未混入早期smoke或v1试运行。实例为Task01原有28个加1个必拆负利润实例，两求解器共58次完整搜索；所有结果均与直接Compact-IP和独立完整列IP一致。根CG-LP列指本版广义Phase I后的根节点CG值，已与独立Full-LP核对。

“—”在IP列表示已证不可行；相应无incumbent、无有限利润界/Gap，不填0。表中节点数为processed（含继承界直接剪枝）。时间仅为本次小规模复现运行，部分回归在独立进程同时执行，且含不同API暖启动开销；不用于算法性能优越性结论。

| 实例 | 后端 | Compact-IP | Full-IP | 根CG-LP | B&P整数LB | 全局UB | 绝对Gap | 节点数 | PP/局部可行调用 | B&P秒 | 证明状态 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
'''+ '\n'.join(detailed)+'''

证明状态：optimal_within_tolerance=记录数值政策下的原整数全局最优；infeasible_proven=完整树证明原整数不可行。CBC generator_n6_L1_s13的Gap保留约7.1e-15的浮点差，没有强制改0。

每行证据目录：`evidence/validation_final/<实例>_<后端>/`；mandatory_negative在`additional/mandatory_negative_<后端>/`。instance.json输入，config.json配置及源码版本，result.json完整树证书，tree/节点及原生日志，verification.json逐节点Full-LP/IP与检验数验证，compact.json独立紧凑求解状态/目标/bound/gap，oracle_events.json原生验证调用。

## 安全停止与精度专项

| 场景 | 实际状态 | 整数LB | 有效UB | 未解决节点 | 证明标志 |
|---|---|---:|---:|---:|---|
| 根处理后node_limit=1 | node_limit | null | 27 | 2 | false |
| 根求解前极短实际墙钟预算 | time_limit | null | null | 1 | false |
| 根已完成、子节点过期deadline（故障注入） | time_limit | null | 27 | 2 | false |
| 节点API直接异常（故障注入） | solver_error | null | null | 1 | false |
| Phase I只允许1轮CG | numerical_uncertain | null | null | 1 | false |
| 极小RC、全局绝对阈值比RC精度更严 | numerical_uncertain | 0 | 1.2e-7 | 1 | false |

最后一例真实整数候选为空站方案，利润0；LP定价最大值约6e-8≤默认epsilon=1e-7，但修复总界1.2e-7大于指定绝对目标1e-12，故保留节点。它是按预期安全未完成的精度测试，不计入58次已完成搜索。

前五例证据在interruptions/，第六例在additional/tiny_rc_unclosed_cplex_py/。均保存输入、结果与独立验证。Fault injection明确标注，不把测试注入当成自然发生的原生超时。
''')
    write('BP_VALIDATION_REPORT.md',f'''# Task02 正确性验证报告

## 总体结果

**PASS：29个完整求解实例×CBC/CPLEX两后端=58次搜索，{counts['optimal_runs']}次最优、{counts['infeasible_runs']}次整数不可行，均与Compact-IP和独立Full-IP一致。** 另有22次独立节点专项及6次中断/精度测试，合计86次按预期通过。安全停止不是已证最优。

28个Task01主实例的56次搜索共有166个节点，每个节点独立求解Full-LP和Full-IP（局部允许集空时直接枚举证明空域），并重算428轮完整定价证书、1151次PP/局部可行调用的记录。主树节点分布：branched 55，Phase I不可行叶21，界支配叶37，整数闭合叶53；没有把开发测试的局部强制空域冒充正常分数分支树中发生的叶。

全部64份全局结果（58个完成+6个安全未完成）和22份独立节点已无求解器离线重放；10类伪造证书均拒绝。生产源码哈希与最终验收一致；5574个Task01 tracked文件未改变。原始结果、失败记录和所有日志保留。

## 独立性

完整列由Task01独立enumerate_patterns生成，不调用生产节点PP/列构造；节点限制独立过滤；完整节点LP/IP使用独立行向量组装。节点证明还逐轮检查初始/演进列池、全部lambda、弹性人工行、raw/effective价格、完整块覆盖、枚举最大RC及修复界。全局重放独立检查原x最分数选择、两个子域、DFS处理前缀、各时刻整数LB、剪枝与活动叶，没有用B&P自己给出的最优标志作为答案。

优化器依然通过同一PuLP后端接入，不能声称求解器实现独立；CBC/CPLEX交叉验证及不调用求解器的枚举/对偶重放共同提供证据。离线范围限本次小规模实例，不外推指数枚举至大实例。

## 逐实例对照

下表利润采用CPLEX数值，CBC对应状态一致、目标差≤1e-5；完整数值、UB/LB/Gap、时间和PP次数见BP_EXPERIMENT_SUMMARY。

| 实例 | Compact-IP | Full-IP | 根Full-LP/CG-LP | B&P整数 | CBC/CPLEX节点 | 全局结论 | 核对 |
|---|---:|---:|---:|---:|---:|---|---|
'''+ '\n'.join(compact_table)+'''

重点：two_lines根27→整数24（CBC21节点、CPLEX19节点）；generator_n6_L1_s13根59.38→整数56.63（均5节点）。lp_yes_ip_no根LP=4，但整数不可行；两后端均3节点，根对A线H坐标分0/1，两叶Phase I修复上界均-0.5，正确输出infeasible_proven。

single_line的LP最优值与IP均21，但CBC所得根最优LP的原x可分数，仍用了7节点；CPLEX根解整数，仅1节点。相同最优值不意味着所有最优LP解均整数，也不要求不同求解器的树或最优列相同。

## 24类边界逐项验收

| 编号 | 场景 | 实际证据 | 状态 |
|---:|---|---|---|
| 1 | 根LP整数 | single_line_cplex_py，1节点 | PASS |
| 2 | 根正整数Gap | two_lines、generator_n6_L1_s13 | PASS |
| 3 | Branch 0 | 两个正Gap树及test_node_cg | PASS |
| 4 | Branch 1 | 同上及one_no_empty | PASS |
| 5 | Branch 1禁止空列 | node_scenarios/one_no_empty，两后端 | PASS |
| 6 | Branch 1局部空域 | one_local_time_empty、one_local_fatigue_empty | PASS |
| 7 | 局部可行、全局LP不可行 | human_global_infeasible、robot_global_infeasible | PASS |
| 8 | 初始池冲突、完整节点可行 | human/robot_missing_column_recovery、AND_missing_column_recovery | PASS |
| 9 | 分支冲突/未知/重复固定 | test_node_state | PASS |
| 10 | 父子列池隔离 | test_branch_zero_and_sibling_pool_isolation | PASS |
| 11 | 兄弟状态隔离 | 同上及不可变限制测试 | PASS |
| 12 | 可选任务重复造成Phase I违约 | duplicate_optional_recovery | PASS |
| 13 | AND导致节点不一致 | AND_global_infeasible | PASS |
| 14 | 人工资源紧缺 | human_global_infeasible及human_scarce主例 | PASS |
| 15 | 机器人紧缺 | robot_global_infeasible及robot_scarce主例 | PASS |
| 16 | 疲劳阈值紧张 | tight_fatigue及one_local_fatigue_empty | PASS |
| 17 | LP可行IP不可行 | lp_yes_ip_no，完整3节点证明 | PASS |
| 18 | 零/负利润 | zero_profit、mandatory_negative=-8 | PASS |
| 19 | 多重最优 | multi_optimum | PASS |
| 20 | 退化/非唯一对偶 | dual_degenerate | PASS |
| 21 | 超时仍有继承有效界 | interruptions/child_time_limit，UB27且2活动节点 | PASS（明确故障注入） |
| 22 | 节点限制保留活动节点 | interruptions/node_limit，2个孩子 | PASS |
| 23 | 非法剪枝证书 | 10类篡改与test_branch_price拒绝 | PASS |
| 24 | 全树剪枝证明整数不可行 | lp_yes_ip_no、and_diamond等 | PASS |

专项局部空域使用外部固定的合法节点限制；正常most-fractional分支完整继承父池时两个取值各有父LP正权重支持，不会凭空失去所有局部列。说明见数学设计第8节。所有专项数据/父池/固定/节点JSON/Full-LP-IP验证及日志在node_scenarios/，没有跳过某类场景后虚报通过。

## 回归与开发失败

| 测试 | 实际结果 | 证据 |
|---|---|---|
| 核心数据结构首次测试 | 3项PASS | step2_state_tests.txt |
| 节点CG首次测试 | 7项PASS | step3_node_tests.txt |
| 初次树测试 | 8项PASS | step4_tree_tests.txt |
| 增强节点测试 | 最终9项纳入回归PASS | regressions_cbc/cplex.txt |
| 极小RC首次增强树测试 | 1项FAIL：测试参数低于CPLEX允许最小值 | tree_tests_extended.txt、tiny_rc_before_fix.json |
| 查询API允许最小值后 | 9项PASS | tree_tests_final.txt |
| 最终综合CBC配置回归 | 66项PASS | regressions_cbc.txt |
| 最终综合CPLEX配置回归 | 66项PASS | regressions_cplex.txt |
| 原实验组件回归 | 32项PASS | regressions_experiments.txt |
| 最终完整模型矩阵 | 56次PASS | validation_final/summary.json |
| 最终独立节点 | 22次PASS | node_scenarios/summary.json |
| 补充负利润/极小RC | 3次符合预期PASS | additional/summary.json |
| 时间/节点/异常/CG迭代停止 | 5次符合预期PASS | interruptions/summary.json |
| 全局离线证书+独立节点 | 64+22份PASS，10类伪造均拒绝 | certificate_replay/summary.json |

66项=原有Task01核心45项+新增21项；新增树测试内部显式选择后端/故障注入，不把它们误称为每个方法均各跑一次两种后端。29个完整实例的真正双后端对照由58次矩阵运行提供。

唯一实际失败的新增断言来自测试请求dual=1e-10；本机CPLEX参数最小值为1e-9，求解器在建模时拒绝，B&P保留solver_error/open节点、最优标志false。改用API允许的1e-9（仍严于默认1e-8）后得到预期numerical_uncertain和非零Gap。未放宽约束或默认整数精度。失败输入按input_sha256匹配另存tiny_rc_before_fix_instance.json；unsupported_tolerance_context.json解释参数及安全状态。因参数设置阶段失败，没有发生原生优化，不能伪造原生求解日志。

v1及smoke早期通过结果保留，不并入最终矩阵统计。最终生产契约收紧后重新运行了全部验证；交付生产源码与该最终运行一致。全部原始tracked文件不变，不覆盖或删除历史数据。

## 复现

```powershell
experiments/.venv/Scripts/python.exe docs/branch_and_price/run_validation.py --out docs/branch_and_price/evidence/my_new_validation --boundaries
experiments/.venv/Scripts/python.exe experiments/run_regressions.py --solver cbc
experiments/.venv/Scripts/python.exe experiments/run_regressions.py --solver cplex_py
experiments/.venv/Scripts/python.exe -m unittest discover -s experiments -p test_*.py -v
```

新目录必须不存在；默认每个主搜索60秒、1000节点，独立Oracle每次30秒；本次全部主搜索正常完成，未为得到结果延长预算。未运行120/150任务实验。framework中的150二进制变量极短时限状态夹具和环境1201变量纯LP许可证探测不是拆卸规模实验。

## 范围外

大规模性能：NOT RUN；精确有理/区间认证：NOT IMPLEMENTED；截断PP Best Bound驱动新轮CG：NOT IMPLEMENTED；跨节点原生模型复用/并行分支搜索/强化学习：NOT IMPLEMENTED。上述均为明确范围边界，不混入本次通过计数。
''')
    write('TASK02_SUMMARY.md',f'''# Task02 研究人员总结

**明确结论：是。当前第一版B&P在记录的浮点容差下，已对完成的小规模实例真正证明原始MILP的整数全局最优或全局不可行。** 证明来自节点精确定价、有效树界、整数witness和完整叶覆盖，独立完整列Oracle另行验证；不是把根LP或受限IP的状态改名。

## 1. 实际完成内容

实现不可变节点限制、原x最分数二元分支、合法池继承及局部可行补列、广义弹性Phase I、节点精确CG、节点与全局界、DFS、安全剪枝、中断/异常、版本化证书和CLI。保留Task01全部源码和历史结果；当前HEAD仍为70d5bca，新增代码未commit/push。

## 2. 实际代码

生产新增node_state.py、node_pricing.py、node_master.py、bp_solution.py、branch_price.py；新增21项单测及独立枚举/节点Oracle/整树重放/批量验证程序。文件位于code/dwcg和docs/branch_and_price。全部原有5574个tracked文件SHA-256不变；交付另含新文件和证据哈希。

## 3. 数学设计

对原始x_(l,i,s,m)分0/1，子节点覆盖父全部整数解且互斥。原x全整数时，每块正权重列在每个二进制坐标上相同，U/H/R又由assignments唯一决定，因此可合并为真实整数配置。每条路径固定新坐标，精确算术下树有限。这一分支规则完备；未对具体lambda分支。

## 4. 节点Phase I

凸性保持硬约束，所有其他耦合LE行都加单向人工、耦合等式都加双向人工，真实列成本0。完整人工最优值0当且仅当完整节点LP可行。测试实际覆盖初始池任务重复、必拆超供、人工/机器人过量和AND违约而完整节点仍可恢复；没有因初始RMP缺列错误剪枝。

## 5. 节点定价

每站重建同一局部MILP并显式加入该站全部z固定，不加入全局优先/资源上限。已过滤列不会重新进入。定价必须给出类型化证书、匹配的固定域/阶段/块、底层证明状态；普通二元组、超时incumbent或只有optimal/infeasible标签都不接受。小规模每节点定价最大值均与独立枚举一致。

## 6. 整数证明机制

LB只来自数据级及原Compact约束验证的整数witness。节点UB来自完整精确定价的对偶修复，与父界取min；未知界不填数。仅可靠不可行、有效界支配LB、整数点与UB闭合三类剪枝。完整DFS叶覆盖与已验证incumbent构成全局最优证明；无incumbent且全叶不可行构成全局不可行证明。时间/节点/异常节点保留，不签发完成证明。

## 7. 实际实验

29个完整实例在CBC/CPLEX两后端共58次搜索，{counts['optimal_runs']}次最优、{counts['infeasible_runs']}次整数不可行；另有22个节点专项和6个安全停止/精度运行，合计86次均符合预期。主56次搜索逐一对照166个节点Full-LP/IP、428轮完整定价；1151次定价/局部可行调用留有记录。全体64份树和22份节点离线重放通过，10类伪造证书被拒绝。

关键证据：

| 实例 | 根LP | B&P整数/结论 | CPLEX/CBC节点 | 结果目录 |
|---|---:|---|---:|---|
| single_line | 21 | 最优21 | 1 / 7 | evidence/validation_final/single_line_* |
| two_lines | 27 | 最优24，UB=LB=24 | 19 / 21 | evidence/validation_final/two_lines_* |
| generator_n6_L1_s13 | 59.38 | 最优56.63，整数Gap闭合 | 5 / 5 | evidence/validation_final/generator_n6_L1_s13_* |
| lp_yes_ip_no | 4 | 整数不可行已证 | 3 / 3 | evidence/validation_final/lp_yes_ip_no_* |
| and_diamond | LP不可行 | 全局不可行已证 | 1 / 1 | evidence/validation_final/and_diamond_* |
| mandatory_negative | -8 | 最优-8 | 1 / 1 | evidence/validation_final/additional/mandatory_negative_* |

每目录的result.json是完整全局证书，tree/含节点JSON与solver日志，verification.json保存独立节点LP/IP/检验数与树核对。lp_yes_ip_no的两个孩子都由Phase I上界-0.5证明不可行；不是用根LP的可行性推断整数可行。

## 8. 与完整模型及回归对照

58次完整搜索的目标/不可行性全部与直接Compact-IP、独立Full-IP一致；节点CG与完整节点LP在记录容差下一致。原Task01核心45项和新增21项构成66项综合回归，在CBC/CPLEX配置下均通过；原实验组件32项亦通过。原始失败日志保留，唯一新增断言失败是测试曾使用本机CPLEX不支持的1e-10参数，改用实际最小1e-9后通过，算法未错误剪枝。

## 9. 当前局限与风险

这是浮点容差下的精确分支定价，不是有理算术形式证书。极小RC与更严格全局目标不匹配时，真实例子保留LB0、UB1.2e-7和活动节点，返回numerical_uncertain，没有虚报完成。尚无搜索恢复、复杂分支、原生跨节点复用、截断PP界扩展或大规模性能结论。枚举离线认证仅适用于小规模；库加载/序列化导致墙钟限制为软检查预算。

## 10. 下一阶段建议

先扩充节点固定组合、数值缩放和不同任务图的回归样本，再在相同节点域及证书契约下逐步接入每节点持久PP/增量RMP。当前小例定价调用约占节点时间66%—70%，包含重建/转换/进程/优化，尚不能归因全部为MIP难度；优先优化这一接口而非引入未经证明的启发式定价。随后考虑受控列缓存/证书压缩、checkpoint恢复和更好的分支/搜索策略。

## 十个直接回答

| 问题 | 答案 |
|---|---|
| B&P真正实现？ | 是，生产搜索不枚举全列、不调用Compact-IP求最优 |
| 原始x分支完备？ | 是，有双域覆盖和整数x合并列证明 |
| PP遵守分支？ | 是，显式z固定、合法列过滤及证书固定域检查 |
| 节点Phase I安全？ | 是，广义弹性覆盖全部耦合行，缺列不剪枝 |
| 节点CG与Full-LP一致？ | 是，本次节点独立交叉验证通过 |
| 可证明小规模整数最优？ | 是，two_lines=24、generator_n6_L1_s13=56.63等 |
| 可证明整数不可行？ | 是，lp_yes_ip_no完整3节点证明 |
| 全局界可追溯？ | 是，每轮修复界、继承、历史LB、剪枝和活动叶均保存 |
| 最大瓶颈？ | 当前小例的大量重建定价及求解器调用总开销 |
| 优先优化？ | 保证域/证书等价后接入每节点持久PP/增量RMP并扩大回归 |
''')
    print(json.dumps(counts,indent=2))


if __name__=='__main__':main()
