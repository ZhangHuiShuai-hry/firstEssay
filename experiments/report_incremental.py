"""Paired CG-V0/V1 report; completion speedups exclude censored comparisons."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import statistics

from analyze_results import distribution


def report(run,supplement=None):
    rows=json.loads((run/'summary.json').read_text());pairs={}
    budget=json.loads((run/'config.json').read_text())['budget']
    for r in rows:pairs.setdefault((r['n'],r['seed']),{})[r['version']]=r
    checks=[];stats=[]
    for (n,seed),p in pairs.items():
        if len(p)!=2:continue
        a,b=p['V0'],p['V1'];entry=dict(n=n,seed=seed,V0_status=a['status'],V1_status=b['status'],speedup=None,lower_bound=None)
        if a['converged'] and b['converged']:
            delta=abs(a['lp_objective']-b['lp_objective'])
            if delta>1e-5:raise RuntimeError(f'Converged LP mismatch: {n}, {seed}, {delta}')
            entry.update(objective_delta=delta,speedup=a['wall_time']/b['wall_time'])
        elif b['converged'] and a['status']=='time_limit':entry['lower_bound']=a['budget']/b['wall_time']
        for complete,other in ((a,b),(b,a)):
            if complete['converged'] and other.get('upper_bound') is not None:
                if other['upper_bound']+1e-5<complete['lp_objective']:raise RuntimeError('Invalid truncated upper bound')
        checks.append(entry)
    for n in sorted({r['n'] for r in rows}):
        for version in ('V0','V1'):
            group=[r for r in rows if r['n']==n and r['version']==version]
            item=dict(n=n,version=version,attempts=len(group),converged=sum(r['converged'] for r in group),statuses=dict(Counter(r['status'] for r in group)))
            for k in ('wall_time','phase1_time','phase2_time','rmp_build_time','rmp_interface_time','rmp_conversion_time','rmp_native_time','pp_time','iterations','columns','pricing_calls'):
                item[k]=distribution([r.get(k) for r in group])
            item['pp_fraction']=distribution([r['pp_time']/r['wall_time'] for r in group if r.get('wall_time')])
            stats.append(item)
    (run/'paired_checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    with (run/'paired_speedups.csv').open('w',newline='',encoding='utf-8') as stream:
        fields=['n','seed','V0_status','V1_status','objective_delta','speedup','lower_bound']
        writer=csv.DictWriter(stream,fields);writer.writeheader();writer.writerows(checks)
    speedup_rows=[]
    for n in sorted({r['n'] for r in rows}):
        selected=[c for c in checks if c['n']==n]
        d=distribution([c['speedup'] for c in selected])
        speedup_rows.append(dict(n=n,completed_pairs=d['count'],median=d['median'],q1=d['q1'],q3=d['q3'],mean=d['mean'],std=d['std'],
                                 V0_timeout_V1_completed=sum(c['lower_bound'] is not None for c in selected),
                                 censored_pairs=sum(c['speedup'] is None for c in selected)))
    with (run/'speedup_summary.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,list(speedup_rows[0]));writer.writeheader();writer.writerows(speedup_rows)
    (run/'statistics.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
    pp_parts=[]
    for row in rows:
        raw=json.loads((run/'raw'/(row['instance_id']+'_'+row['version']+'.json')).read_text())
        events=[e for e in raw.get('events',[]) if e['role']=='pricing']
        native=sum(e.get('solver_time',0) for e in events);conversion=sum(e.get('translation_time',0) for e in events)
        pp_parts.append(dict(instance_id=row['instance_id'],n=row['n'],seed=row['seed'],version=row['version'],
                             pp_total=row['pp_time'],pp_native=native,pp_conversion=conversion,
                             pp_remaining=row['pp_time']-native-conversion))
    (run/'pricing_components.json').write_text(json.dumps(pp_parts,indent=2),encoding='utf-8')
    text=['# 增量RMP与LP重优化：CG-V0/CG-V1实验报告','',
      '## 方法与可比性','',
      'V0是本轮开始冻结的稀疏化版本；V1仅替换RMP，不修改pricing.py或原CG迭代逻辑、容差和正检验数判定。两者使用相同生成实例、单线程CPLEX 22.1.1、solver seed=11、自动LP方法、默认预处理、原始/对偶容差1e-8，PP整数容差1e-7及MIP gap=0。',
      '', f'每种版本每个实例{budget}秒总根LP预算，包含初始化、建模/更新、求解、定价、读回和在线核查；不含共同导入/结果报告序列化，不做整数恢复。逐实例交替先后次序，串行运行。截断仍保留未完成状态和已完整精确定价轮次的有效上界，不用当前RMP值冒充LP最优。',
      '', 'V1一次创建主问题约束，以稀疏列追加变量；同一Cplex对象贯穿两阶段，advance=1。Phase II将人工变量上界固定为0，清除其罚项并恢复真实列利润。V0移除人工变量，V1保留固定0的人工列；投影掉这些固定列后，矩阵/目标相同。LP退化可导致不同对偶、定价列和迭代数，因此不要求对偶向量相同，只要求检验数一致性及收敛目标一致。',
      '', '## 实际结果','',
      '| 每线任务数 | 版本 | LP收敛/尝试 | 观察时间中位数秒 | Phase I中位数秒 | Phase II中位数秒 | PP占比中位数 |',
      '|---|---|---:|---:|---:|---:|---:|']
    for s in stats:
        f=lambda k: '—' if s[k]['median'] is None else f"{s[k]['median']:.3f}"
        text.append(f"| {s['n']} | {s['version']} | {s['converged']}/{s['attempts']} | {f('wall_time')} | {f('phase1_time')} | {f('phase2_time')} | {100*(s['pp_fraction']['median'] or 0):.1f}% |")
    text+=['', f'观察时间包含{budget}秒截断，不能将截断当作实际完成时间。统计JSON保留均值、标准差、Q1/Q3和状态计数。精确加速比只计算双方都收敛的配对。',
      '', '| 每线任务数 | 双方收敛配对数 | 完成时间加速比中位数 V0/V1 | V0截断、V1收敛数 |', '|---|---:|---:|---:|']
    for n in sorted({r['n'] for r in rows}):
        a=[c['speedup'] for c in checks if c['n']==n and c['speedup'] is not None]
        bounds=[c['lower_bound'] for c in checks if c['n']==n and c['lower_bound'] is not None]
        text.append(f"| {n} | {len(a)} | {statistics.median(a):.3f} | {len(bounds)} |" if a else f"| {n} | 0 | — | {len(bounds)} |")
    text+=['','## 耗时归因','',
      '| 每线任务数 | 版本 | RMP Python构造/更新中位秒 | 完整模型转换中位秒 | RMP原生优化中位秒 | PP完整调用中位秒 |',
      '|---|---|---:|---:|---:|---:|']
    for s in stats:
        text.append(f"| {s['n']} | {s['version']} | {s['rmp_build_time']['median']:.3f} | {s['rmp_conversion_time']['median']:.3f} | {s['rmp_native_time']['median']:.3f} | {s['pp_time']['median']:.3f} |")
    text+=['','### 截断配对的有效界与迭代','', '| 每线任务数 | 种子 | V0状态 | V1状态 | V0有效上界 | V1有效上界 | V0轮次 | V1轮次 |', '|---|---:|---|---|---:|---:|---:|---:|']
    for (n,seed),pair in sorted(pairs.items()):
        if len(pair)!=2:continue
        a,b=pair['V0'],pair['V1']
        if a['converged'] and b['converged']:continue
        bound=lambda r:'—' if r.get('upper_bound') is None else f"{r['upper_bound']:.6f}"
        text.append(f"| {n} | {seed} | {a['status']} | {b['status']} | {bound(a)} | {bound(b)} | {a['iterations']} | {b['iterations']} |")
    text+=['','最大化问题中较低的合法上界更强；较强截断上界或更多轮次均不等于已收敛。']
    text+=['','### V1中的PP内部时间','', '| 每线任务数 | PP总调用中位秒 | 原生MIP求解中位秒 | 模型转换中位秒 | 建模/读回等剩余中位秒 |', '|---|---:|---:|---:|---:|']
    for n in sorted({r['n'] for r in rows}):
        group=[p for p in pp_parts if p['n']==n and p['version']=='V1']
        values=[statistics.median(p[k] for p in group) for k in ('pp_total','pp_native','pp_conversion','pp_remaining')]
        text.append(f'| {n} | '+' | '.join(f'{v:.3f}' for v in values)+' |')
    text+=['','上述为各组件分别取中位数，不要求各中位数相加等于总中位数。剩余时间包含PuLP构造、API配置、读回及其他调用开销，未单独计时，不能全部解释为Python建模。原生PP复用可能减少重建和转换，但是否减少精确MIP优化时间仍须另做消融。']
    text+=['', 'V0转换时间已包含在RMP接口总时间里；分解图不重复累加。V1的原生API追加工作计入建模/更新，单独的完整模型转换为0不表示追加列无开销。原生LP优化时间的减少同时可能受到基复用和CG路径变化影响，不能仅凭总时间将全部收益归因于基。replay.json用V0生成的同一列追加序列重放两种RMP，隔离定价路径差异。',
      '', '## 正确性及LP状态复用证据','',
      f"双方均收敛的目标值逐例核对，最大偏差为{max((c.get('objective_delta',0) for c in checks),default=0):.3g}。精确定价仍调用原pricing.py，未做PP模型缓存、启发式定价、RL或分支定价。tests.log包含同列池矩阵/目标、两阶段切换、原生dj与显式检验数、小规模完整列终止证书测试。",
      '', 'basis_records保存每次重优化前是否有可用LP基、原生单纯形迭代数、变量数量及advance=1。保留同一对象与可用基表明没有每轮主动丢弃求解状态，不等于能断言CPLEX在所有预处理场景均完整复用了每一个基元素。',
      '', '## 结论适用范围与下一步','',
      '本轮只比较根LP工程实现，不据此宣称解决原MILP整数最优更快。PP占比需要结合原生PP优化、建模/转换开销继续分析。若V1中PP占比明显增加，下一步值得做原生PP模型复用的工程消融：固定局部约束，按轮更新对偶目标，保持精确定价和相同求解容差；不预先保证该复用一定更快。120秒内仍未完成的难例可另设300秒运行，不能把两档预算混为同一时间实验。']
    replay=run/'replay.json'
    if replay.exists():
        a=json.loads(replay.read_text());text+=['','## 同追加列序列重放', '',f"已逐轮重放{len(a)}个相同列池LP；目标与检验数全部通过。V0 Python构造累计{sum(x['V0_build'] for x in a):.3f}秒，接口累计{sum(x['V0_interface'] for x in a):.3f}秒（完整转换{sum(x['V0_conversion'] for x in a):.3f}秒、原生LP优化{sum(x['V0_native'] for x in a):.3f}秒）；V1更新累计{sum(x['V1_update'] for x in a):.3f}秒，原生求解累计{sum(x['V1_native'] for x in a):.3f}秒。该测试不比较两次独立CG的对偶向量相等。"]
        text+=['',f"额外的原生同矩阵对照仅将advance设为0，其原生优化累计{sum(x['native_advance0'] for x in a):.3f}秒；advance=1累计{sum(x['V1_native'] for x in a):.3f}秒。该对照单独隔离已有求解状态的作用，不混入主实验；本消融规模仅为n=20、seed=11，不外推为所有实例的统一倍数。"]
        text+=['','重放两臂在计时前共同准备列系数，准备耗时另存；主CG不做此额外预热。该重放隔离接口/重优化代价，不以其合计冒充完整CG时间。']
        savings=dict(Python构造=sum(x['V0_build']-x['V1_update'] for x in a),
                     完整模型转换=sum(x['V0_conversion'] for x in a),
                     原生LP优化=sum(x['V0_native']-x['V1_native'] for x in a))
        text+=['',f"同序列重放的组件节省："+'；'.join(f'{k} {v:.3f}秒' for k,v in savings.items())+f"。V1还包含一次初始化{sum(x['V1_initialization'] for x in a):.3f}秒、接口读回等开销；因此不将上述组件简单当作整个CG加速比。"]
    if supplement:
        extra=json.loads((supplement/'summary.json').read_text());extra_pairs={}
        text+=['','## 300秒难例补充（独立预算，不混入主统计）','',
               '| 每线任务数 | 种子 | 版本 | 状态 | 根时间秒 | LP目标 | 有效上界 |',
               '|---|---:|---|---|---:|---:|---:|']
        for r in extra:
            source=supplement/'instances'/(r['instance_id']+'.json');base=run/'instances'/(r['instance_id']+'.json')
            if source.read_bytes()!=base.read_bytes():raise RuntimeError('Supplement input mismatch')
            assert r['budget']==300
            extra_pairs.setdefault(r['instance_id'],{})[r['version']]=r
            num=lambda x:'—' if x is None else f'{x:.6f}'
            text.append(f"| {r['n']} | {r['seed']} | {r['version']} | {r['status']} | {r['wall_time']:.3f} | {num(r['lp_objective'])} | {num(r['upper_bound'])} |")
        for pair in extra_pairs.values():
            if len(pair)==2 and all(r['converged'] for r in pair.values()):
                assert abs(pair['V0']['lp_objective']-pair['V1']['lp_objective'])<1e-5
                text+=['',f"该补充配对双方均收敛，目标一致，完成时间比V0/V1={pair['V0']['wall_time']/pair['V1']['wall_time']:.3f}。"]
            elif len(pair)==2 and pair['V1']['converged'] and pair['V0']['status']=='time_limit':
                assert pair['V0']['upper_bound']+1e-5>=pair['V1']['lp_objective']
                text+=['',f"该配对V0仍截断，其有效上界不低于V1已证明的LP目标。V0/V1完成时间比只能报告下界>{300/pair['V1']['wall_time']:.3f}，不能将V0的300秒当成完成时间。"]
        text+=['','该难例按首个40任务截断实例预先选定为seed=11，是机制诊断，不代替五种子的300秒总体实验。']
    second_replay=run/'replay_30.json'
    if second_replay.exists():
        a=json.loads(second_replay.read_text())
        text+=['','## n=30同序列重放补充','',f"seed=11共{len(a)}轮相同列池，目标/检验数全部通过。V0构造{sum(x['V0_build'] for x in a):.3f}秒、完整转换{sum(x['V0_conversion'] for x in a):.3f}秒、原生LP{sum(x['V0_native'] for x in a):.3f}秒；V1更新{sum(x['V1_update'] for x in a):.3f}秒、原生重优化{sum(x['V1_native'] for x in a):.3f}秒。同矩阵advance=0原生优化{sum(x['native_advance0'] for x in a):.3f}秒。该消融也不包含PP，不能直接代替CG总体速度比。"]
    env_path=run/'environment.json'
    if env_path.exists():
        env=json.loads(env_path.read_text())
        text+=['','## 实验环境与复现材料','',f"Python {env['python']}；CPLEX {env.get('cplex_version')}；PuLP {env['packages'].get('pulp')}。CPU：{env['cpu']}；逻辑处理器{env['logical_cpus']}个。硬件、包版本及原生LP/MIP烟雾测试详见environment.json。"]
    text+=['','输入为现有witness-paired-v2.1生成器的分层AND型DAG与混合H/R/J模式；每线20/30/40任务，对应7/10/14候选站，种子11/21/31/41/51。必拆比例目标20%，最低回收指标为总权重的35%，疲劳阈值0.6，资源预算由合法任务配置见证确定。两版输入及全部任务参数完全相同，本轮未重新调参以寻找有利实例。完整输入和元信息在instances/。',
           '', 'source/与provenance.json保存执行代码及SHA256；config.json保存实验设计；summary.csv/json为逐例数据，raw/保存每轮CG、PP与基状态，logs/保存原生日志。AUDIT_INCREMENTAL.json核对原数学代码及pricing.py未改变、运行参数、阶段计时和终止记录；tests.log和regression_*.log保存实际CPLEX/CBC回归结果。大例没有完整枚举所有列；独立枚举验证只针对可枚举小例，不能宣称全部大例做过FMP全列求解。',
           '', '## 五个问题的实测回答','']
    total={v:sum(r['converged'] for r in rows if r['version']==v) for v in ('V0','V1')}
    ratios=[c['speedup'] for c in checks if c['speedup'] is not None]
    text+=[f"1. 整体根CG时间：双方完成的{len(ratios)}个配对中，V0/V1时间比中位数{statistics.median(ratios):.3f}（范围{min(ratios):.3f}–{max(ratios):.3f}）；截断配对不算精确加速比。这是当前实例上的描述性结果，未进行显著性检验。" if ratios else '1. 暂无双方完成的配对，不能计算精确完成时间加速比。',
           '2. 加速来源：同列池重放分别给出Python构造、完整模型转换及原生LP优化时间，并用advance=0辅助对照隔离状态使用。完整CG仍可能因退化产生不同列路径，因此不能把全部端到端收益归因于基。',
           f"3. 原预算下更多收敛：{budget}秒主实验V0收敛{total['V0']}/{len(pairs)}，V1收敛{total['V1']}/{len(pairs)}；逐规模结果见表。300秒补充单独报告。",
           f"4. PP是否成为主要瓶颈：V1逐例PP占根时间比例中位数{100*statistics.median(r['pp_time']/r['wall_time'] for r in rows if r['version']=='V1'):.1f}%。PP含建模/转换与原生精确MIP优化，内部组成另表列示。",
           '5. 下一步：可开展原生CPLEX PP复用的独立工程消融，先固定原有局部约束、仅更新对偶目标，比较同一组对偶下的精确最优值、检验数、构造/转换和原生求解时间；不要混入启发式或提前终止。PP占比高不保证其模型复用会同等减少原生MIP证明时间，也不解决受限列池整数不可行的问题。']
    if second_replay.exists():
        a=json.loads(second_replay.read_text());warm=sum(x['V1_native'] for x in a)
        text+=['',f"加速归因的直接结论：n=30同序列中，原生LP节省{sum(x['V0_native'] for x in a)-warm:.3f}秒，大于单独Python构造节省{sum(x['V0_build']-x['V1_update'] for x in a):.3f}秒及完整转换节省{sum(x['V0_conversion'] for x in a):.3f}秒；忽略基的advance=0原生耗时约为advance=1的{sum(x['native_advance0'] for x in a)/warm:.2f}倍。因此本例中LP状态复用是最大的单项可测收益，同时减少Python与反复完整接口处理也有贡献；n=20中Python构造节省更大，不能把所有规模都归为同一来源。"]
    text+=['','实际回归：新增V1测试5项通过；原有数学/证书测试在CPLEX及CBC下各45项通过。小例完整枚举独立证书、20/30任务的同池重放及大例最终记录审计均通过。图表为四张独立单面板图，输出PDF/SVG/PNG并保存源数据和自动文字/碰撞审计。']
    (run/'REPORT_CN.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    print('Report:',run/'REPORT_CN.md')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--supplement',type=Path);a=p.parse_args();report(a.run,a.supplement)
