"""打印列池的整数分配及违反的原主问题约束；可在IDE直接运行。

先精确检查原受限IP，再保持每站选一条真实列，最小化其他约束的违约量之和。
弹性分配是解释性反例，只有原约束全部满足才是可行方案。所违反的行不是
唯一不可行核心；不同最优诊断可能违反不同的行。各行使用原单位等权加总。
默认复现40任务、Phase II第25轮（历史整数恢复曾证明不可行）的列池。
"""
from __future__ import annotations
import argparse,hashlib,json,math,sys,time,traceback
from pathlib import Path
import pulp
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(HERE.parent)]
from common import blocks,compact,coefficients
from master import build_master
from root_diagnostics import pool_from_records,config
from node_state import NumericPolicy
from evidence_store import load_result
from solver_backend import use_backend,make_solver

# IDE默认：读取已保存列池，不重新运行CG。支持命令行覆盖。
CERTIFICATE=ROOT/'docs/root_diagnostics/no_compact_tasks040/certificate.sqlite'
ITERATION=25
TIME_LIMIT=30.0  # 整次建模/求解软时限；超时有方案也不假称诊断最优


def coverage(data,pool):
    result=[]
    for line in data['lines']:
        required=set(line.get('required_tasks',[]))
        for t in line['tasks']:
            locations=[dict(station=s,column=p,mode=m) for (l,s),cols in pool.items() if l==line['id']
                       for p,c in enumerate(cols) for i,m in c.assignments if i==t['id']]
            result.append(dict(line=line['id'],task=t['id'],required=t['id'] in required,
                               occurrences=len(locations),locations=locations))
    return result


def row_description(data,key):
    if key[0]=='task':
        line=next(l for l in data['lines'] if l['id']==key[1])
        return f'{key[1]}任务{key[2]}：'+('必做且恰好一次' if key[2] in line.get('required_tasks',[]) else '最多执行一次')
    if key[0]=='precedence':
        line=next(l for l in data['lines'] if l['id']==key[1]);i,j=line['precedence'][key[2]]
        return f'{key[1]}优先关系 {i}→{j}，截至站{key[3]}：后继执行次数≤前驱执行次数'
    return {'human':'全局人工配置上限','robot':'全局机器人配置上限',
            'recovery':f'{key[1]}最低回收要求' if len(key)>1 else '最低回收要求',
            'station':'工作站恰选一列'}.get(key[0],str(key))


def diagnose(data,pool,*,solver='cplex_py',time_limit=TIME_LIMIT,hard_families=()):
    compact.validate_data(data);compact.number(time_limit,'time_limit',0,strict=True)
    if set(hard_families)-{'task','precedence','human','robot','recovery'}:raise ValueError('Unknown hard family')
    # Validate local attributes independently of row relaxation; no invalid columns accepted.
    from node_pricing import validate_column
    from node_state import NodeRestrictions
    policy=NumericPolicy();started=time.perf_counter();deadline=started+time_limit
    for line,s in blocks(data):
        if not pool.get((line['id'],s)):raise ValueError('局部块没有列，无法保持硬凸性')
        for col in pool[line['id'],s]:validate_column(line,s,col,NodeRestrictions(),policy)
    m=build_master(data,pool,integer=True)
    with use_backend(config(solver,min(deadline,time.perf_counter()+time_limit*.35),policy)):
        try:m.problem.solve(make_solver(role='pool_feasibility'));original=dict(m.problem.backend_result)
        except TimeoutError:original=dict(status='time_limit',optimal=False,has_incumbent=False)
    # A fresh model prevents native state or elastic rows leaking into the real-IP check.
    elastic=build_master(data,pool,integer=True)
    specifications={key:(row.sense,-row.constant) for key,row in elastic.rows.items()}
    artificial=[]
    for index,(key,row) in enumerate(elastic.rows.items()):
        if key[0]=='station' or key[0] in hard_families:continue
        for sign in ((1,-1) if row.sense==pulp.LpConstraintEQ else (-1,)):
            v=pulp.LpVariable(f'diagnostic_{index}_{sign}',lowBound=0)
            row.addInPlace(sign*v);artificial.append(v)
    elastic.problem.setObjective(-pulp.lpSum(artificial))
    with use_backend(config(solver,deadline,policy)):
        try:elastic.problem.solve(make_solver(role='pool_diagnosis'));info=dict(elastic.problem.backend_result)
        except TimeoutError:info=dict(status='time_limit',optimal=False,has_incumbent=False)
    result=dict(scope='restricted_pool_explanation_only',coverage=coverage(data,pool),
        original_ip=original,elastic_solver=info,hard_families=list(hard_families),
        assignments=[],violations=[],minimum_violation_proven=info['optimal'],
        explanation='一种最小总违约分配，不是唯一不可行核心；行单位不同，使用未归一化等权和。')
    if not info['has_incumbent']:return result
    if not elastic.problem.valid(policy.primal_validation_tolerance):raise RuntimeError('诊断模型自身不满足约束')
    if any(v.value() is None or not math.isfinite(v.value()) or abs(v.value()-round(v.value()))>policy.pricing_integrality_tolerance for v in elastic.variables.values()):
        raise RuntimeError('诊断分配不是整数')
    lhs={key:0. for key in specifications}
    for line,s in blocks(data):
        chosen=[(p,c) for p,c in enumerate(pool[line['id'],s]) if elastic.variables[line['id'],s,p].value()>.5]
        if len(chosen)!=1:raise RuntimeError('每站必须选择且仅选择一条列')
        p,c=chosen[0]
        result['assignments'].append(dict(line=line['id'],station=s,column=p,assignments=list(c.assignments),
            duration=c.duration,fatigue=c.fatigue,human=c.human,robot=c.robot,
            cycle_limit=line['cycle_time'],fatigue_limit=-math.log1p(-line['fatigue_limit'])*c.human))
        for key,value in coefficients(line,s,c).items():lhs[key]+=value
    for key,(sense,rhs) in specifications.items():
        amount=abs(lhs[key]-rhs) if sense==pulp.LpConstraintEQ else max(0.,lhs[key]-rhs)
        if amount>policy.primal_validation_tolerance:
            result['violations'].append(dict(row=list(key),description=row_description(data,key),
                lhs=lhs[key],sense='=' if sense==pulp.LpConstraintEQ else '<=',rhs=rhs,violation=amount))
    result['total_violation']=sum(x['violation'] for x in result['violations'])
    if abs(result['total_violation']+info['objective'])>policy.bound_consistency_tolerance:raise RuntimeError('独立违约量与弹性目标不一致')
    result['original_constraints_satisfied']=not result['violations']
    result['required_task_execution']=[]
    for line in data['lines']:
        for task in line.get('required_tasks',[]):
            positions=[dict(station=e['station'],mode=m) for e in result['assignments'] if e['line']==line['id']
                       for i,m in e['assignments'] if i==task]
            result['required_task_execution'].append(dict(line=line['id'],task=task,count=len(positions),positions=positions))
    result['seconds']=time.perf_counter()-started
    return result


def render(result):
    lines=['原受限IP状态：'+result['original_ip']['status'],
           '诊断状态：'+result['elastic_solver']['status'],
           '最低总违约已证明：'+str(result['minimum_violation_proven'])]
    missing=[f"{e['line']}/{e['task']}" for e in result['coverage'] if e['required'] and not e['occurrences']]
    lines.append('列池完全缺少的必做任务：'+('、'.join(missing) if missing else '无（每个必做任务至少存在于一条列中）'))
    lines.append('\n逐站整数分配（每站选一条真实列）：')
    for e in result['assignments']:
        tasks=', '.join(f'{i}({m})' for i,m in e['assignments']) or '空站'
        lines.append(f"  {e['line']} 站{e['station']} 列{e['column']}：{tasks}；时间{e['duration']:.4f}/{e['cycle_limit']}；疲劳{e['fatigue']:.6f}/{e['fatigue_limit']:.6f}；H={e['human']} R={e['robot']}")
    lines.append('\n必做任务实际执行次数：')
    for e in result.get('required_task_execution',[]):
        lines.append(f"  {e['line']} 任务{e['task']}：{e['count']}次；位置={e['positions']}")
    lines.append('\n违反的原主问题约束：')
    for e in result['violations']:
        lines.append(f"  {e['description']}：LHS={e['lhs']:.6f} {e['sense']} RHS={e['rhs']:.6f}；违约={e['violation']:.6f}")
    if result['assignments']:
        lines.append(f"总违约量：{result['total_violation']:.6f}；满足原约束：{result['original_constraints_satisfied']}")
    lines.append(result['explanation'])
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--certificate',type=Path,default=CERTIFICATE)
    parser.add_argument('--iteration',type=int,default=ITERATION,help='Phase II轮数；0选最后一份已保存列池')
    parser.add_argument('--time-limit',type=float,default=TIME_LIMIT)
    parser.add_argument('--solver',choices=('cplex_py','cbc'),default='cplex_py')
    parser.add_argument('--hard-family',action='append',default=[],choices=('task','precedence','human','robot','recovery'))
    parser.add_argument('--output',type=Path,help='新目录：保存JSON与中文分配文本；省略只打印')
    a=parser.parse_args()
    if a.output and a.output.exists():raise FileExistsError('输出目录已存在，拒绝覆盖')
    path=a.certificate.resolve();instance=next((p/'instance.json' for p in [path.parent,path.parent.parent] if (p/'instance.json').exists()),None)
    if instance is None:raise FileNotFoundError('证书旁边或父目录缺少instance.json')
    data=json.loads(instance.read_text(encoding='utf-8-sig'));saved=load_result(path)
    if saved['node'].get('restrictions'):raise ValueError('此简单脚本只诊断根节点；拒绝忽略分支限制')
    rounds=saved['node']['certificate']['rounds']
    matches=[r for r in rounds if r['phase']==2 and (a.iteration==0 or r['iteration']==a.iteration)]
    if not matches:raise ValueError('找不到指定Phase II轮列池')
    row=matches[-1];pool=pool_from_records(data,row['pool'])
    try:
        r=diagnose(data,pool,solver=a.solver,time_limit=a.time_limit,hard_families=a.hard_family)
    except Exception as error:
        if a.output:
            a.output.mkdir(parents=True,exist_ok=False)
            (a.output/'error.json').write_text(json.dumps(dict(status='solver_error',error=repr(error),
                traceback=traceback.format_exc(),solver=a.solver,iteration=row['iteration']),ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    r.update(certificate=str(path),phase=2,iteration=row['iteration'],columns=sum(map(len,pool.values())),
             input_sha256=hashlib.sha256(instance.read_bytes()).hexdigest(),
             certificate_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    report=f"Phase II第{row['iteration']}轮，{r['columns']}条列\n"+render(r)
    print(report)
    if a.output:
        a.output.mkdir(parents=True,exist_ok=False)
        (a.output/'diagnosis.json').write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        (a.output/'allocation.txt').write_text(report,encoding='utf-8')
if __name__=='__main__':
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    main()
