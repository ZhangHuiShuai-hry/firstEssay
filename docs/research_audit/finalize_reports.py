"""Build audit tables from actual saved results; fail on any unpassed acceptance."""
from pathlib import Path
import json
import hashlib
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
E=HERE/'evidence'

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(name,text):(HERE/name).write_text(text,encoding='utf-8')
def fmt(x):return '不可行' if x is None else f'{x:.8f}'.rstrip('0').rstrip('.')

def main():
    base=read(HERE/'baseline.json');env=read(E/'environment.json')
    hist=read(E/'historical_inventory_v2.json')
    rows=[];full=[]
    for run in ('acceptance_rebuilt','acceptance_native','acceptance_extra','acceptance_extra_native'):
        summary=read(E/run/'summary.json')
        assert summary and all(r['status']=='PASS' for r in summary)
        for r in summary:
            raw=read(E/run/f"{r['name']}_{r['backend']}"/'result.json')
            rows.append(r|{'run':run});full.append(raw)
    rebuilt=[r for r in rows if not r['native']]
    native=[r for r in rows if r['native']]
    assert len(rebuilt)==56 and len(native)==28
    names=sorted({r['name'] for r in rebuilt})
    assert len(names)==28
    table=[]
    for name in names:
        a=next(r for r in rebuilt if r['name']==name and r['backend']=='cbc')
        b=next(r for r in rebuilt if r['name']==name and r['backend']=='cplex_py')
        c=next(r for r in native if r['name']==name)
        for k in a['models']:
            assert a['models'][k]['status']==b['models'][k]['status']==c['models'][k]['status']
            if a['models'][k]['objective'] is not None:
                assert abs(a['models'][k]['objective']-b['models'][k]['objective'])<=1e-5
                assert abs(c['models'][k]['objective']-b['models'][k]['objective'])<=1e-5
        raw=read(E/b['run']/f'{name}_cplex_py'/'result.json')
        vals=b['models']
        table.append('| '+ ' | '.join([name,fmt(vals['compact_ip']['objective']),fmt(vals['compact_lp']['objective']),fmt(vals['full_ip']['objective']),fmt(vals['full_lp']['objective']),fmt(raw['cg']['lp_objective']),'/'.join(map(str,b['columns'].values())),'PASS'])+' |')
    rounds=sum(len(r.get('certificate_rounds',[])) for r in full)
    prices=sum(len(r.get('pricing_comparisons',[])) for r in full)
    metadata=dict(distinct_instances=28,rebuilt_runs=56,native_runs=28,passed_runs=84,
                  independently_audited_rounds=rounds,arbitrary_dual_pricing_checks=prices,
                  core_cbc_tests=45,core_cplex_tests=45,experiment_tests=32)
    (E/'acceptance_totals.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    historical_table=[]
    for r in hist['runs']:
        counts=r['counts']
        state='可追溯材料齐备' if all(r[k] for k in ('config.json','environment.json','provenance.json','summary.json')) and counts['raw'] and counts['instances'] and counts['logs'] else '派生/诊断/部分材料，逐目录判断'
        historical_table.append(f"| {r['name']} | {r.get('summary_records','—')} | {counts['instances']} | {counts['tasks']} | {counts['raw']} | {counts['logs']} | {state} |")
    write('PROJECT_BASELINE.md',f'''# 项目可信基线

日期：2026-11-02（Asia/Shanghai）。基线提交 `{base['commit']}`，分支 `{base['branch']}`，origin=`https://github.com/ZzzHry/firstEssay.git`。以本地完整工作区为对象；未拉取远程、切分支、提交或推送。

## 工作区与身份

任何写入前，bundled Git 的 porcelain 输出为空，工作区干净。baseline.json 是创建审计计划后采集，故 initial_status 仅多出本次 `docs/research_audit/AUDIT_PLAN.md`；不是用户原有修改。Git日志仅两个提交：`2a1f76c Track project from workspace root`、`799f959 Initial research code and formulation`。

系统 PATH 优先的 `C:/mynewpc/Git/cmd/git.exe` 发生所有权检查失败；使用 Codex bundled Git 并对每次命令传 `-c safe.directory=<workspace>` 成功。未更改全局/本地 Git 配置。没有 AGENTS.md 指令文件。忽略目录实际存在：experiments/.venv、runs、snapshots；默认 rg --files 会跳过，已单独核查。

baseline.json 保存全部150个 tracked 文件的原始 SHA-256；最终 HASHES_FINAL.tsv 保存交付时 tracked 文件与新增审计源码/报告的哈希，EVIDENCE_HASHES.tsv 保存本次证据文件的哈希（不自包含自身）。哈希可区分初始提交和未提交修复；各次独立运行 config.json 另外保存当次被测源码哈希。对 core 源码的接受测试哈希必须与交付一致。

## 环境（实际测试）

| 项 | 版本/结果 |
|---|---|
| 默认 Python | 3.12.9，CBC/PuLP可用；不是本次双求解器验收解释器 |
| 项目解释器 | `{env['executable']}`，Python 3.10.11 |
| PuLP | {env['packages']['pulp']} |
| CPLEX API/引擎 | {env['cplex_version']}；安装路径 `{env['cplex_root']}` |
| CBC | {env['cbc_version']}，PuLP内置 win/i64 版本 |
| NumPy / SciPy | {env['packages']['numpy']} / {env['packages']['scipy']} |
| matplotlib / PyMuPDF | {env['packages']['matplotlib']} / {env['packages']['pymupdf']} |
| LP/MIP smoke | CBC与CPLEX均实际求解成功；含对偶和非零dj |
| CPLEX许可证实际探测 | 1201变量纯LP实际求解成功；只证明当时可运行，不推断许可期限 |

完整环境在 evidence/environment.json；依赖锁在 evidence/requirements-lock.txt。系统Python3.10没有单独安装PuLP，原有项目venv有；未安装/升级系统包。默认3.12的泛化包扫描遇site-packages权限错误，改用项目venv的逐项版本及pip freeze完成记录，未把该扫描失败当测试通过。

## 功能与稳定入口

| 组件 | 实现状态 | 验证状态 |
|---|---|---|
| 紧凑MILP | code/milp/model.py | 小规模双求解器完整验证 |
| 根两阶段CG | code/dwcg/solve.py | 重建RMP+重建PP；完整列LP证书验证 |
| 完整列IP/LP与解码 | master.py、verify.py | 理论等价及独立四模型验证 |
| 增量原生RMP | incremental_master.py | 固定/追加矩阵、阶段切换、根CG验证 |
| 持久原生PP | persistent_pricing.py | 矩阵/目标更新及独立定价验证 |
| 受限整数恢复 | solve.recover_integer | 原问题整数可行解；列池作用域最优 |
| Hybrid | experiments/hybrid.py | 现有3项回归已运行；本次不重跑大规模质量实验 |
| 截断PP Best Bound | 字段已有，本次修复通用后端常数 | 尚未实现以截断界替代精确定价的CG控制流 |
| Branch-and-Price | 未实现 | NOT RUN |

版本标签必须带实验名称：增量实验 V0=重建RMP、V1=增量RMP；PP实验 V1=增量RMP+重建PP、V2=增量RMP+持久PP。基线精确入口是 `code/milp/model.py` 和 `code/dwcg/solve.py --verify`；原生V2由 `experiments/compare_pricing.py` 注入。默认CG CLI不自动启用V2。

现有核心测试45项，两后端修复前后均真实运行；最终实验测试32项（含新增8项回归）。原有测试/历史报告与本次实际执行结果分开记录，详见 VALIDATION_REPORT。

## 历史输入、配置和日志盘点

下表为目录盘点，不代表重新执行历史优化。source_manifest 存在且非空的运行，已检查所有列出的冻结源码文件，无missing或mismatch。各目录完整字段/哈希见 evidence/historical_inventory_v2.json。

| 运行目录 | summary记录 | 输入文件 | tasks | raw | logs | 材料判断 |
|---|---:|---:|---:|---:|---:|---|
'''+ '\n'.join(historical_table)+'''

四个快照均保留。V1冻结清单的40个源码、76502个数据文件逐一SHA-256匹配；V0的33个源码亦核查；最早快照11个源码匹配。`20261030_112527/snapshot.json` 只有用途说明，没有源哈希清单，故其密码学完整性为PARTIAL，不能追补成历史证据。历史报告“当时无Git”与现在有Git属于不同时间点，未改写旧报告。

信任分级：快照字节完整性PASS；有配置/输入/原始日志/冻结源码的历史结果可追溯；8684对历史定价回放及120/150任务性能结论本次未重新求解，标NOT RUN，不据其宣称当前性能。派生图表/诊断目录没有统一run材料不能与正式独立作业计数混合；persistent_pp_120_01仅29条且无环境文件，属于部分/中断材料。早期复制双线数据与正式two_lines不是同一输入。

所有原有实验结果、快照、输入和配置均未写入或删除。本次产物仅在 docs/research_audit（以及明确的源码最小修复/新增测试），未执行git reset/clean或切分支。
''')
    write('VALIDATION_REPORT.md',f'''# Task01 小规模正确性验证报告

## 验收结果

**PASS：28个不同实例，重建式CG双求解器56次，增量RMP+持久PP的CPLEX28次，总84次验收运行全部通过。** 实例每线最多6任务、总任务最多10；一任务例用于LP可行/IP不可行边界，没有运行120/150任务拆卸实验。

每次保存 instance.json、config.json（目录级配置和当次源码哈希）、result.json、求解器事件和原生日志。环境/锁文件位于同一evidence根目录，由PROJECT_BASELINE统一关联。没有把不存在的Best Bound、incumbent或gap补为0。

独立oracle不调用生产 make_column、coefficients、build_master 或定价模型来生成答案；枚举任务“不选或一种允许模式”，独立重算配置逻辑、时间、疲劳、回收和利润；独立组装完整主问题。生产函数作为被测对象逐项比较。优化仍使用相同PuLP接口与求解器，但数学构造、列算术及可行性/检验数检查独立；双求解器降低共同状态错误风险，不能声称完全独立求解器实现。

独立检查：完整列集合和每列属性；所有稀疏行向量；Compact-IP→列解；Full-IP和Full-LP→紧凑模型；四模型目标及可行性包含关系；CG与Full-LP目标；逐轮 primal/dual/覆盖/RC/修复界；两阶段任意自由/非负对偶的PP最优值；人为放松的合法定价上界修复完整对偶的定理。

已独立复核{rounds}轮保存对偶/定价证书，另做{prices}次两阶段任意对偶定价对比（不含CG本身的PP调用）。多重最优仅比较目标、可行性与检验数，不要求相同列。

## 四模型与CG结果

表中列出CPLEX目标，CBC全部对应状态一致、目标差≤1e-5；原生CG亦与独立Full-LP一致。列数按每个线站列出，包含空列。不可行栏表示已证模型不可行；CG为空时通过Phase I不可行证书，不是求解异常。

| 实例 | Compact-IP | Compact-LP | Full-IP | Full-LP | CG-LP | 各块完整列数 | 结论 |
|---|---:|---:|---:|---:|---:|---|---|
'''+ '\n'.join(table)+f'''

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
''')
    write('TASK01_SUMMARY.md',f'''# Task01 研究审计总结

**建议：具备进入 Phase 2（Branch-and-Price）受控设计与小规模原型开发的条件。当前代码还不是通用整数全局最优算法。** 已确认的错误已修复并回归；没有尚未解释的验收失败。数值、适配器和历史证明范围须按下面的进入条件管理。

## 1. 本次完成的工作

完成Phase 0可信基线及Phase 1数学/程序审计，保留提交 `{base['commit']}` 的原始哈希；读取全部核心实现与实际实验调用链，核查28个历史运行目录和四个快照。生成七份要求报告、独立验证器、证据目录及哈希清单。未提交/推送、切分支或覆盖历史实验。

## 2. 数学模型审计结论

在仓库明示的确定性、单周期、固定配置资源、AND DAG与顺序作业假设下，紧凑模型内部正确，文档与实现一致。完整列IP与Compact-IP已给出包括空站、配置变量和异质站空缺的双向保目标映射，数学等价成立。Full-IP≤Full-LP≤Compact-LP，两个LP一般不相等；已有明确数值反例。模型一致性不等同于疲劳参数的生理实证校准。

## 3. CG算法审计结论

RMP对偶与所有reduced-cost项正确：必拆π自由、回收行正调整、前缀对偶按k≥s累计、凸性常数保留。Phase I只清除人工量来建立LP可行性；Phase II恢复原利润。精确定价覆盖所有候选线站；正常终止能证明完整列LP在记录容差下最优。截断/异常不视为无改善列。

## 4. 代码正确性结论

重建RMP、增量RMP、重建PP、持久PP在小规模的矩阵、阶段切换、列可行性、目标及证书一致。生产列构造/系数函数被独立枚举和独立主问题校验。已补充逐轮primal/dual/状态/时间/界证据与失败快照；旧验证入口已指向严格验证器。

## 5. 实际测试结果

28个不同实例，56次CBC/CPLEX重建式验证，加28次CPLEX原生适配器验证，84次全部PASS；另有核心CBC45项、CPLEX45项、实验32项回归全部PASS。独立重算{rounds}轮证书和{prices}次任意对偶定价。单线IP/Full-LP=21；双线IP=24、Full-LP=27。LP可行IP不可行、零利润、零负荷人工、非唯一对偶、超时和异常均有实际证据。原始失败及解释保留于VALIDATION_REPORT。

## 6. 已修复问题

CPLEX Best Bound漏目标常数；CBC打印上界的向下舍入及常数；PuLP固定零dummy导致目标日志null；异常丢部分CG证书；旧verify_checked的弱通过语义；恢复结果证明作用域字段不足。数学构造和物理假设未改。新增8项回归，修复前后证据均保存。

## 7. 未解决问题与前三优先项

1. **P1：节点精确性尚未实现。** 需要分支规则、节点合法列、节点Phase I/定价、树管理与全局界；现有incremental_master仅支持同输入的追加式根列池，不能直接跨节点共享可变状态。
2. **P1：数值及证书接口边界。** 把不同容差的接受规则统一成节点策略，明确本项目采用浮点最优容差；逐步移除普通二元组适配器的隐含精确定价契约，保证每节点状态/覆盖/界可审计。极端病态输入、精确有理认证未实现。
3. **P2：规模与历史结论需独立重证。** 当前小规模正确性证据充分，但未重跑8684对历史回放及120/150任务实验。截断Best Bound继续CG的扩展也未实现；若Phase2依赖该能力，先补全覆盖、常数与界状态测试，否则沿用精确定价失败即停的保守策略。

不存在必须先改变原模型才能开始Phase2的阻塞性数学差异。上述第1项属于Phase2本身；第2项应在第一轮节点原型验收前完成接口约束，不应据根CG成功直接扩展性能实验。

## 8. 当前数学证明能力

能证明紧凑IP与完整列IP等价、LP包含关系、两阶段精确定价和对偶修复界。$UB=Z_{{RMP}}+\sum\max(0,\widehat\rho)$ 在RMP强对偶、全部块有效定价上界、同一阶段同一对偶、每块凸性RHS=1的条件下成立；一般非最优RMP应改用对偶目标D。当前已证最优PP产生的CG上界可靠至记录数值容差；通用后端遗漏常数已修复。现有代码尚不利用截断PP的Best Bound签发新轮CG上界。

## 9. 当前整数最优性证明能力

小规模可通过完整列枚举IP与直接Compact-MILP都证到相同全局最优；双方不可行亦可交叉验证。仅受限整数恢复时，能得到原问题整数可行解、并在求解完成时证明**受限主问题**最优，不能一般性证明原IP最优，也不能以列池不可行证明原IP不可行。若整数可行值与有效全局上界闭合，可另行签发该实例最优性证明；当前恢复例程保守不自动提升标志。

## 10. 进入Branch-and-Price的具体任务与验收门槛

先选对恢复变量 $x_{{lism}}$ 的完备二元分支，证明其能排除当前分数解；把分支条件同步施加于RMP、所有已有列和每个PP（包含空列、必拆、节点不可行性）。节点Phase I须证明该节点LP不可行，不能仅凭受限列池缺列剪枝。为每节点保存父节点/分支/合法列/完整定价/LP界/整数incumbent，树全局上界取存活节点有效界的最大值；只用原整数可行值剪枝。

验收先用本次28实例及额外具有正整数间隙的小实例，比较完整列IP/Compact-IP；覆盖分支后PP不可行、局部列过滤、节点初始列池不可行但可恢复、超时存活节点和界闭合。未满足这些门槛之前，所有结果只能称根LP/受限IP结果，不能称Branch-and-Price全局最优。

## 十个直接回答

| 问题 | 回答 |
|---|---|
| 当前数学模型正确吗？ | PASS，在仓库明确假设下内部一致 |
| Compact-IP与Full-IP已证明等价？ | PASS，双向保目标映射 |
| Reduced Cost正确？ | PASS，全部项独立推导/数值核对 |
| Phase I/II正确？ | PASS，注意Phase I不证明整数可行 |
| CG能证明完整列LP最优？ | PASS，完整精确定价及记录容差下 |
| 小规模能证明原整数最优？ | PASS，通过完整列IP或直接紧凑MILP；不能只靠CG |
| 当前有效上界可靠？ | PASS，精确定价修复界及明确数值条件；截断扩展未实现 |
| 整数恢复的最优作用域？ | 仅受限列池，原整数可行解；自动全局证明未实现 |
| 最重要三个问题？ | 节点精确性、数值/证书接口、规模与扩展验证 |
| 能进入Phase2吗？ | 可以受控开发，须按节点级精确性门槛验收 |
''')
    print(json.dumps(metadata,indent=2))

if __name__=='__main__':main()
