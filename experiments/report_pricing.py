"""Chinese evidence report for completed V1/V2 experiments and fixed-dual replay."""
import argparse
import csv
import json
from pathlib import Path
import re
import statistics

from analyze_pricing import analyze


def f(value,digits=3):return '—' if value is None else f'{value:.{digits}f}'


def report(runs,replay,out):
    rows,stats,pairs,pp=analyze(runs,replay,out)
    budgets=sorted({r['budget'] for r in rows})
    text=['# CG-V2原生CPLEX持久化定价：实测分析','',
      '## 研究范围、冻结与公平性','',
      'V1为原生增量RMP+原PuLP精确定价；V2保留同一RMP和CG主循环，仅将PP改为每工作站一个持久化原生CPLEX模型。任务—模式、节拍、疲劳、资源配置及允许列均不变，不含RL、启发式定价、分支定价或整数恢复。V1源码和两轮完整数据已备份，详见CG_V1_FROZEN.json及快照SHA256清单。',
      '', '两线，每线20/30/40任务，种子11/21/31/41/51，原生成器及原JSON逐字保持一致。各版本独立进程，工作进程PYTHONHASHSEED=11；单线程CPLEX22.1.1，solver seed11、parallel=1，默认预处理和算法。原始/对偶容差1e-8、整数容差1e-7，PP相对/绝对Gap均0，只接受原生状态101。CG epsilon/可行性容差1e-7，每阶段迭代上限1000。根预算包含首次模型创建、更新、求解、读回和在线检查；共同CPLEX模块导入与最终序列化不计时。时限返回开销按真实wall time保存。各对版本交替先后次序，性能作业串行运行。',
      '', '实例沿用witness-paired-v2.1生成器的分层AND型DAG和混合可行模式。每线候选站为7/10/14，节拍15，实验疲劳阈值0.6，必拆比例目标20%，最低回收指标为总权重的35%，共享资源预算来自合法配置见证。站点费用保持生成器原值；完整图、任务时间/成本/疲劳和资源参数保存在各instances目录及manifest中。',
      '', '原稀疏系数函数遍历Python集合；为减少浮点累加和项顺序的非受控变化，正式端到端固定子进程哈希种子，不改变任何RMP源码。未控制哈希的persistent_pp_120_01保留为中断预试验，不参与正式性能统计。该控制不保证两种PP产生相同最优列，也不将预试验轨迹差异全部归因于哈希。',
      '', '## 模型与两阶段目标一致性','',
      'Phase I定价只计对偶项，Phase II再计任务回收利润、直接执行成本、站点及人机配置成本。两阶段都包含任务唯一性、最低回收、前缀优先、共享人机资源对偶项和工作站凸组合对偶常数。每次更新全部目标系数，防止阶段切换残留利润。每个返回列由原make_column检查局部可行性，并使用原独立列系数重算检验数。',
      '', 'V2对齐PuLP实际交给CPLEX的原生表示：0/1有界整数变量（数学上为二进制），同一变量名/顺序、行顺序；凸组合常数在求解器外加回目标与界。首轮表示预检查pricing_replay_01中途停止并保留，正式比较使用pricing_replay_02，不混用预检查性能。',
      '', '## 相同对偶下的全部PP调用','',
      '取已保存V1的三个完整历史：20/30任务seed11的120秒结果、40任务seed11的300秒收敛结果。遍历其中每一轮、每个工作站的PP，交替调用V1/V2，单次每臂上限60秒。允许最优列不同，检验数必须一致。该设计隔离CG轨迹变化；PP调用依赖于同一历史，因此均值/中位数为描述性统计，未将调用当作独立随机样本做显著性检验。',
      '', '| 每线任务 | 配对调用数 | V1均值ms | V2均值ms | 均值降幅 | V1中位ms | V2中位ms | 中位降幅 |',
      '|---|---:|---:|---:|---:|---:|---:|---:|']
    for p in pp:
        if p['phase']!='all':continue
        text.append(f"| {p['n']} | {p['calls']} | {1000*p['V1_mean']:.3f} | {1000*p['V2_mean']:.3f} | {p['mean_reduction_pct']:.1f}% | {1000*p['V1_median']:.3f} | {1000*p['V2_median']:.3f} | {p['median_reduction_pct']:.1f}% |")
    validation=json.loads((replay/'validation.json').read_text())
    text+=['',f"全部{validation['paired_calls']}对调用通过，V1、V2及原日志的检验数比较容差1e-5；最大V1/V2差为{validation['max_delta']:.3g}。保存了calls.csv、完整duals快照、输入/原历史哈希和求解器日志。",'',
      '### 单次调用时间分解（算术均值，毫秒）','',
      '| 任务 | 版本 | Python构造 | 原生创建 | 完整转换 | 目标更新 | 原生MIP优化 | 其余读回/检查 |',
      '|---|---|---:|---:|---:|---:|---:|---:|']
    for p in pp:
        if p['phase']!='all':continue
        for v in ('V1','V2'):
            keys=([v+'_build_mean',None,v+'_translation_mean',None,v+'_native_mean',v+'_other_mean'] if v=='V1' else
                  [v+'_build_mean',v+'_native_creation_mean',None,v+'_update_mean',v+'_native_mean',v+'_other_mean'])
            values=[0 if k is None else 1000*p[k] for k in keys]
            text.append(f"| {p['n']} | {v} | "+' | '.join(f'{x:.3f}' for x in values)+' |')
    text+=['', 'V1的目标装配包含于每次Python构造，原生模型创建包含在完整转换区间，原生创建栏不另行重复计时。V2没有完整PuLP转换，但构造/原生创建在首次调用发生并实测，已摊入全部调用，目标更新每次计时。其余包括API配置、读回、验证和清理，不能全解释成Python建模。原生MIP时间可能受持久对象的内部解/状态影响；没有主动加入MIP start或改变CPLEX参数，不能预先认为复用一定减少整数优化时间。',
      '', '## 端到端根CG配对结果','',
      '| 预算秒 | 每线任务 | V1收敛/尝试 | V2收敛/尝试 | V1观察时间中位秒 | V2观察时间中位秒 | 双方完成数 | 完成时间比中位V1/V2 |',
      '|---|---|---:|---:|---:|---:|---:|---:|']
    for budget in budgets:
        for n in sorted({r['n'] for r in rows if r['budget']==budget}):
            groups={v:next(s for s in stats if (s['budget'],s['n'],s['version'])==(budget,n,v)) for v in ('V1','V2')}
            ratios=[p['speedup'] for p in pairs if p['budget']==budget and p['n']==n and p['speedup'] is not None]
            a,b=groups['V1'],groups['V2']
            text.append(f"| {budget} | {n} | {a['converged']}/{a['attempts']} | {b['converged']}/{b['attempts']} | {f(a['wall_time']['median'])} | {f(b['wall_time']['median'])} | {len(ratios)} | {f(statistics.median(ratios) if ratios else None)} |")
    text+=['','观察时间包含时限截断，不是全部实例的完成时间。不同预算独立统计；一方完成另一方截断只保存速度比下/上界，双方截断没有完成时间比。全部异常/超时保留，status明示，缺失目标写null。统计JSON包含均值、中位数、标准差、Q1/Q3及状态计数。',
      '', '### RMP、PP和原生MIP在根时间中的占比（逐例比例中位数）','',
      '| 预算 | 任务 | 版本 | Phase I秒 | Phase II秒 | RMP完整秒 | PP完整秒 | PP占比 | 原生PP占比 |',
      '|---|---|---|---:|---:|---:|---:|---:|---:|']
    for s in stats:
        group=[r for r in rows if (r['budget'],r['n'],r['version'])==(s['budget'],s['n'],s['version'])]
        rmp=statistics.median(r['rmp_build_time']+r['rmp_interface_time'] for r in group)
        text.append(f"| {s['budget']} | {s['n']} | {s['version']} | {f(s['phase1_time']['median'])} | {f(s['phase2_time']['median'])} | {rmp:.3f} | {f(s['pp_time']['median'])} | {100*s['pp_fraction']['median']:.1f}% | {100*s['native_pp_fraction']['median']:.1f}% |")
    text+=['','根时间分解不重复相加RMP接口及其原生求解子时间，也不把Phase I/II再叠加到组件上。逐实例的组件合计等于根wall time；图中可加组件使用算术均值。',
      '', '## 正确性、界与截断状态','']
    audit=json.loads((out/'validation.json').read_text())
    text+=[f"跨版本、跨预算所有已收敛实例目标均核对，最大目标差{audit['converged_objective_max_delta']:.3g}。截断时保留最大已证明最优Phase II RMP目标作为完整列LP下界，最小完整精确定价轮次修复值作为上界；未完整定价的轮次不产生上界。所有有已知收敛目标的截断界均未排斥该最优值。以上界只针对DW-LP，不是整数解界/整数最优证明。",'',
      '| 预算 | 任务 | 种子 | V1状态 | V2状态 | V1 LP上界 | V2 LP上界 | 速度比下界/上界 |',
      '|---|---|---|---|---|---:|---:|---|']
    for p in pairs:
        if p['speedup'] is not None:continue
        bound=('>'+f(p['speedup_lower_bound'])) if p['speedup_lower_bound'] is not None else ('<'+f(p['speedup_upper_bound'])) if p['speedup_upper_bound'] is not None else '—'
        text.append(f"| {p['budget']} | {p['n']} | {p['seed']} | {p['V1_status']} | {p['V2_status']} | {f(p['V1_upper'],6)} | {f(p['V2_upper'],6)} | {bound} |")
    text+=['','小例仍独立枚举全列并验证最终定价/人工变量证书；大例不做不可承受的完整枚举，不能宣称已对所有大例求解FMP。回归测试日志记录真实CPLEX及CBC运行；旧数学源代码和V1实验数据的哈希核查另存审计文件。',
      '', '## 六个研究问题与下一步','']
    with (out/'bound_checks.csv').open(encoding='utf-8',newline='') as stream:unknown=[r for r in csv.DictReader(stream) if r['converged_target_available']=='False']
    if unknown:
        position=text.index('## 六个研究问题与下一步')
        text[position:position]=['仍未证明LP最优的实例，其跨版本/预算最好有效区间为：'+ '；'.join(f"{r['instance_id']} [{float(r['best_lower']):.9f}, {float(r['best_upper']):.9f}]" for r in unknown)+'。这些区间不代表已获得最优目标。','']
    text+=['1. **单次PP调用变化**：'+ '；'.join(f"{p['n']}任务均值降低{p['mean_reduction_pct']:.1f}%、中位数降低{p['median_reduction_pct']:.1f}%" for p in pp if p['phase']=='all')+'。采用同对偶全历史调用，没有剔除不利调用。']
    text+=['2. **端到端加速比**：']
    for budget in budgets:
        ratios=[p['speedup'] for p in pairs if p['budget']==budget and p['speedup'] is not None]
        if ratios:text.append(f"   {budget}秒档双方完成{len(ratios)}对，时间比中位数{statistics.median(ratios):.3f}，范围{min(ratios):.3f}–{max(ratios):.3f}；其中{sum(v<1 for v in ratios)}对V2更慢。该结果只适用于双方完成配对，不能代表全部截断实例的完成时间。")
    text+=['3. **加速来源**：同对偶原生MIP均值变化（V2相对V1，正数为增加）：'+ '；'.join(f"{p['n']}任务{100*(p['V2_native_mean']/p['V1_native_mean']-1):+.1f}%" for p in pp if p['phase']=='all')+'。与构造/转换/更新分解一起判断：结构复用省下接口工作，但不能据此假定整数优化本身一定更快；完整CG的列轨迹差异还会改变调用数量。',
      '4. **40任务收敛率**：']
    for budget in budgets:
        group=[s for s in stats if s['budget']==budget and s['n']==40]
        if group:text.append(f"   {budget}秒："+'，'.join(f"{s['version']} {s['converged']}/{s['attempts']}" for s in group)+'。')
    text+=['5. **新的主要瓶颈**：']
    for budget in budgets:
        group=[r for r in rows if r['budget']==budget and r['version']=='V2']
        native=statistics.median(r['pp_native_time']/r['wall_time'] for r in group)
        rmp=statistics.median((r['rmp_build_time']+r['rmp_interface_time'])/r['wall_time'] for r in group)
        components={'原生PP优化':lambda r:r['pp_native_time'],
                    'RMP完整调用':lambda r:r['rmp_build_time']+r['rmp_interface_time'],
                    'PP创建/转换/更新':lambda r:sum(r[k] for k in ('pp_build_time','pp_native_creation_time','pp_translation_time','pp_objective_update_time')),
                    'PP读回及其他':lambda r:r['pp_other_time'],'根其他开销':lambda r:r['other_time']}
        shares={label:statistics.mean(fn(r)/r['wall_time'] for r in group) for label,fn in components.items()}
        largest=max(shares,key=shares.get)
        text.append(f"   {budget}秒档V2逐例原生PP占根时间比例中位数{100*native:.1f}%，RMP完整占比中位数{100*rmp:.1f}%。组件占比取均值时，最大项为{largest}（{100*shares[largest]:.1f}%）。")
    cost_budget=max((b for b in budgets if b<=300),default=max(budgets))
    hard=[r for r in rows if r['version']=='V2' and r['n']==40 and r['budget']==cost_budget]
    text+=['6. **学习辅助定价是否值得**：'+(f"{cost_budget}秒档{len(hard)}个40任务V2实例的原生PP累计优化观察时间中位数为{statistics.median(r['pp_native_time'] for r in hard):.3f}秒，" if hard else '')+
      '这为下一轮受控研究提供了可测成本目标，而非学习方法已有效的证据。应区分找到正检验数列与证明不存在正检验数列，后者仍需精确证书；还应检查长尾调用和根节点即可证明的PP占比，不能把所有原生MIP时间都视为可由学习消除。原生节点数/成功调用p95及失败调用时间另存root_pp_calls_summary.csv，正/非正检验数时间另存fixed_dual_rc_classes.csv。本轮未实现学习或提前终止。']
    with (out/'duplicate_objectives.csv').open(encoding='utf-8',newline='') as stream:dup=list(csv.DictReader(stream))
    text+=['','### 完全相同变量目标的重复性诊断（未实施去重）','',
      '仅比较同一条线、同一完整Phase II定价轮次中逐项完全相同的浮点变量目标系数；工作站凸组合常数单独排除，局部约束保持相同。每组还核对已保存精确最优值加回凸组合对偶后的一致性。不使用近似相似度，不新增求解优化。',
      '', '| 预算 | 任务 | V2完整定价调用数 | 重复目标调用占比 | 重复调用原生时间占比 |', '|---|---|---:|---:|---:|']
    for budget in budgets:
        for n in sorted({r['n'] for r in rows if r['budget']==budget}):
            group=[d for d in dup if d['version']=='V2' and int(d['budget'])==budget and int(d['n'])==n]
            total=sum(int(d['priced_calls']) for d in group);repeated=sum(int(d['duplicate_calls']) for d in group)
            native=sum(float(d['priced_native_time']) for d in group);repeated_native=sum(float(d['duplicate_native_time']) for d in group)
            text.append(f"| {budget} | {n} | {total} | {100*repeated/total:.1f}% | {100*repeated_native/native:.1f}% |" if total and native else f'| {budget} | {n} | {total} | — | — |')
    text+=['','比例只针对完整Phase II轮次，未包含末轮未完成PP；重复调用的耗时比例不是已实现或保证可获得的加速比。若重复性较高，下一步应将完全相同目标的精确结果复用作为独立消融，再评估剩余独特难PP是否值得学习加速。本轮仍逐站独立精确定价，未把这种可能收益计入V2。']
    shares=[]
    for n in sorted({r['n'] for r in rows if r['budget']==cost_budget}):
        g=[d for d in dup if d['version']=='V2' and int(d['budget'])==cost_budget and int(d['n'])==n]
        total=sum(float(d['priced_native_time']) for d in g)
        if total:shares.append(sum(float(d['duplicate_native_time']) for d in g)/total)
    if shares:
        text+=['',f"在{cost_budget}秒主要实验中，按规模分组的同轮完全重复目标对应原生时间占比为{100*min(shares):.1f}%–{100*max(shares):.1f}%。"+('本诊断未发现它足以解释主要计算成本；仍值得针对独特困难PP及长尾优化开展受控研究。' if max(shares)<.5 else '重复性值得先做精确结果复用消融，再评估学习价值。')+'跨轮重复没有在这里归并，不将当前范围的结果外推为全部重复性。']
    partial=[d for d in dup if int(d['partial_failed_goals_already_proven'])>0]
    if partial:
        text+=['','末轮诊断还发现：'+ '；'.join(f"{d['instance_id']}、{d['budget']}秒、{d['version']}有{d['partial_failed_goals_already_proven']}个失败调用，其变量目标已被同轮前面的工作站证明最优，该失败调用消耗原生时间{float(d['partial_failed_redundant_native_time']):.3f}秒" for d in partial)+
               '。这只说明存在可进一步研究的精确目标复用机会，没有在本轮实施，也不把截断CG重新标为收敛。']
    with (out/'root_pp_calls_summary.csv').open(encoding='utf-8',newline='') as stream:call_summary=list(csv.DictReader(stream))
    for r in call_summary:
        if r['version']=='V2' and int(r['budget'])==600:
            text+=['',f"600秒代表例中，V2已证明最优的{r['completed_calls']}个PP有{r['positive_calls']}个最优检验数为正；成功调用耗时中位数{1000*float(r['median']):.3f}ms、原生优化p95为{1000*float(r['native_p95']):.3f}ms。未记录首次正价可行解出现时间，因此不能仅由最优检验数正负判定耗时是寻找列还是证明该列最优。下一轮应增加incumbent/best-bound事件轨迹，测量学习候选或启动解对净时间与精确证书的影响。"]
    logs=[('新增V2（原生PP/枚举/证书/边界）','regression_v2.log'),('V1增量RMP回归','regression_v1.log'),
          ('原数学/验证测试：CPLEX','regression_cplex.log'),('原数学/验证测试：CBC','regression_cbc.log')]
    tests=[]
    for label,name in logs:
        path=out/name
        if path.exists():
            b=path.read_bytes();s=b.decode('utf-16' if b.startswith(b'\xff\xfe') else 'utf-8-sig')
            matched=re.search(r'Ran (\d+) tests',s)
            if not matched or not s.rstrip().endswith('OK'):raise RuntimeError('Regression log did not pass: '+name)
            tests.append((label,int(matched.group(1)),name))
    if tests:
        text+=['','## 真实求解器代码回归','', '| 测试组 | 通过数 | 日志 |', '|---|---:|---|']
        text += [f'| {label} | {count} | {name} |' for label,count,name in tests]
        text+=['',f"合计{sum(count for _,count,_ in tests)}项通过。新增V2测试含随机对偶与独立全列枚举、矩阵/变量界/目标比较、两阶段反复切换、原始单/双线终止证书、迭代上限、Phase I不可行/不确定、LP可行但整数不可行、零目标、零疲劳、过长任务及过期deadline。"]
    env_path=out/'environment.json'
    if env_path.exists():
        env=json.loads(env_path.read_text());memory=env.get('hardware',{}).get('physical_memory_bytes')
        text+=['','## 实际运行环境','',f"Python {env['python']}；CPLEX {env.get('cplex_version')}；PuLP {env['packages'].get('pulp')}；CBC {env.get('cbc_version')}；SciPy {env['packages'].get('scipy')}。CPU：{env.get('cpu_brand',env['cpu'])}，{env['logical_cpus']}个逻辑处理器"+(f"，物理内存{memory/2**30:.2f} GiB。" if memory else '。')+'environment.json保存原生LP对偶/检验数和MIP烟雾测试及版本诊断；所有主性能求解使用同一机器的单线程CPLEX。']
    text+=['','## 文件与复现','',
      'per_instance.csv为逐例结果，iterations.csv为逐轮日志，paired_speedups.csv/speedup_summary.csv为配对及分组速度比，fixed_dual_pp_statistics.csv为单次PP统计；原运行raw/保留完整对偶、定价列、状态与阶段记录，logs/保留CPLEX原生日志。配置、源码哈希及输入均在各运行目录。实验方法和复现命令见experiments/PERSISTENT_PP_PROTOCOL.md。',
      '', '本实验只研究根LP工程基线，不据此声称V2完成原MILP整数最优证明，也不预先声称其优于直接求解原整数MILP。']
    text+=['','## 局限','',
      '主实验仅两线、每线最多40任务、五个实例种子及现有生成器的一类参数分布；每个预算每个版本一次运行，没有把重复确定性求解冒充独立实例。固定对偶只覆盖三个完整历史，PP调用相互依赖。所有截断保留，但无法由截断时间得到真实完成速度比。',
      '', '未测量峰值内存；每站保留原生模型可能增加内存占用，后续扩展更多工作站时需单独测试。哈希、CPLEX种子及单线程控制提高复现性，但墙钟时限、数值退化和持久解状态仍可能改变列轨迹。学习辅助的推理开销、稳定性及精确终止证明收益均未测试。']
    (out/'REPORT_CN.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    print('Chinese report written:',out/'REPORT_CN.md')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runs',nargs='+',type=Path,required=True);p.add_argument('--replay',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();report(a.runs,a.replay,a.out)
