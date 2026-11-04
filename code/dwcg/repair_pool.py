"""冲突定向修复补列，IDE可直接运行。保持原列域、全部原约束与利润定义。

先最小化整数主问题违约，再在同等违约下最大化真实利润；生成删除、
前驱插入、交换和模式变更列，求真实受限IP。必要时仅释放少量站做原MILP
联合修复。启发式失败不代表不可行；本模块不签发原问题整数最优证明。
"""
from __future__ import annotations
import argparse,hashlib,json,math,sys,time
from pathlib import Path
import pulp
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(HERE.parent)]
from common import blocks,compact,make_column,coefficients
from master import build_master
from node_state import NumericPolicy,NodeRestrictions
from node_pricing import validate_column
from root_diagnostics import config,pool_from_records,restricted_recovery
from bp_solution import verify_integer_assignments
from evidence_store import load_result
from solver_backend import use_backend,make_solver
from diagnose_pool import CERTIFICATE,ITERATION,row_description


def selected(data,pool,m):
    if not m.problem.valid(1e-6):raise ValueError('Invalid elastic primal')
    if any(v.value() is None or abs(v.value()-round(v.value()))>1e-7 for v in m.variables.values()):raise ValueError('Fractional lambda')
    records=[]
    for l,s in blocks(data):
        chosen=[(p,c) for p,c in enumerate(pool[l['id'],s]) if m.variables[l['id'],s,p].value()>.5]
        if len(chosen)!=1:raise ValueError('Not one column per station')
        p,c=chosen[0];records.append(dict(line=l['id'],station=s,column=p,assignments=list(c.assignments)))
    return records


def violations(data,records):
    pool={(l['id'],s):[] for l,s in blocks(data)};lines={l['id']:l for l in data['lines']}
    for e in records:pool[e['line'],e['station']]=[make_column(lines[e['line']],e['station'],e['assignments'])]
    m=build_master(data,pool,integer=True);lhs={k:0. for k in m.rows}
    for (l,s),cols in pool.items():
        for k,v in coefficients(lines[l],s,cols[0]).items():lhs[k]+=v
    out=[]
    for k,row in m.rows.items():
        amount=abs(lhs[k]+row.constant) if row.sense==0 else max(0.,lhs[k]+row.constant)
        if amount>1e-6:out.append(dict(row=list(k),amount=amount,description=row_description(data,k)))
    return out


def profit_aware_seed(data,pool,deadline,solver='cplex_py',seconds=4.):
    """词典序两次求解；第一次未证最优时只称预算内违约种子。"""
    policy=NumericPolicy();m=build_master(data,pool,integer=True);profit=m.objective.copy();art=[]
    for idx,(key,row) in enumerate(m.rows.items()):
        if key[0]=='station':continue
        for sign in ((1,-1) if row.sense==0 else (-1,)):
            v=pulp.LpVariable(f'repair_a_{idx}_{sign}',lowBound=0);row.addInPlace(sign*v);art.append(v)
    total=pulp.lpSum(art);m.problem.setObjective(-total);events=[]
    end=min(deadline,time.perf_counter()+seconds)
    with use_backend(config(solver,min(end,time.perf_counter()+seconds*.5),policy)):
        m.problem.solve(make_solver(role='repair_elastic'))
    info=dict(m.problem.backend_result);events.append(info)
    if not info['has_incumbent']:return dict(assignments=[],events=events)
    records=selected(data,pool,m);vstar=sum(a.value() for a in art)
    if abs(sum(v['amount'] for v in violations(data,records))-vstar)>1e-5:raise ValueError('Elastic objective mismatch')
    m.problem+=total<=vstar+1e-7,'same_violation_level';m.problem.setObjective(profit)
    if time.perf_counter()<end:
        with use_backend(config(solver,end,policy)):m.problem.solve(make_solver(role='repair_profit'))
        second=dict(m.problem.backend_result);events.append(second)
        if second['has_incumbent']:records=selected(data,pool,m)
    bad=violations(data,records)
    if sum(x['amount'] for x in bad)>vstar+1e-5:raise ValueError('Profit step increased violations')
    return dict(assignments=records,violations=bad,violation_total=sum(x['amount'] for x in bad),
                minimum_violation_proven=info['optimal'],events=events)


def generate_columns(data,pool,seed,*,limit=200,deadline=math.inf):
    """只追加新列；不直接修改旧列。移除闭包前检查必做/必做前驱保护集合。"""
    lines={l['id']:l for l in data['lines']};seen={k:{c.assignments for c in cs} for k,cs in pool.items()};added=[]
    def add(l,s,a,operation):
        if len(added)>=limit or time.perf_counter()>=deadline:return
        try:c=make_column(lines[l],s,a)
        except ValueError:return
        if c.assignments in seen[l,s]:return
        validate_column(lines[l],s,c,NodeRestrictions(),NumericPolicy())
        seen[l,s].add(c.assignments);pool[l,s].append(c)
        added.append(dict(line=l,station=s,assignments=list(c.assignments),profit=c.profit,operation=operation))
    for line in data['lines']:
        l=line['id'];tasks={t['id']:t for t in line['tasks']};edges=line.get('precedence',[])
        chosen=[e for e in seed['assignments'] if e['line']==l]
        positions={i:[e['station'] for e in chosen if any(q==i for q,m in e['assignments'])] for i in tasks}
        protected=set(line.get('required_tasks',[]))
        changed=True
        while changed:
            before=len(protected);protected.update(i for i,j in edges if j in protected);changed=len(protected)!=before
        # Duplicate deletion preserves another occurrence; global IP decides which variant to use.
        for e in chosen:
            a=[tuple(x) for x in e['assignments']];s=e['station']
            for i,m in a:
                if len(positions[i])>1:add(l,s,[(q,n) for q,n in a if q!=i],'delete_duplicate')
        for i,j in edges:
            for target in positions[j]:
                if any(s<=target for s in positions[i]):continue
                for e in chosen:
                    s=e['station'];a=[tuple(x) for x in e['assignments']]
                    if s>target or any(q==i for q,m in a):continue
                    for mode in tasks[i]['modes']:
                        add(l,s,a+[(i,mode)],'insert_predecessor')
                        for q,n in a:
                            if q not in protected:add(l,s,[(t,m) for t,m in a if t!=q]+[(i,mode)],'swap_for_predecessor')
                closure={j};changed=True
                while changed:
                    before=len(closure);closure.update(v for u,v in edges if u in closure);changed=len(closure)!=before
                if not closure&protected:
                    for e in chosen:add(l,e['station'],[(q,n) for q,n in e['assignments'] if q not in closure],'delete_successor_closure')
        # Bounded diversity around chosen patterns; deleting a mandatory occurrence is only a candidate,
        # never accepted globally without coverage/precedence validation by the true integer master.
        for e in chosen:
            a=[tuple(x) for x in e['assignments']];s=e['station']
            for i,m in a:
                add(l,s,[(q,n) for q,n in a if q!=i],'single_deletion')
                for mode in tasks[i]['modes']:
                    if mode!=m:add(l,s,[(q,mode if q==i else n) for q,n in a],'mode_change')
    return added


def joint_repair(data,seed,deadline,solver='cplex_py',max_stations=4,free_stations=None):
    """原Compact模型中仅释放冲突附近的站，其他站的所有x固定；全局行全部保留。"""
    hot=[]
    for bad in seed['violations']:
        k=bad['row']
        if k[0]=='task':affected={k[2]};l=k[1]
        elif k[0]=='precedence':
            l=k[1];line=next(x for x in data['lines'] if x['id']==l);affected=set(line['precedence'][k[2]])
        else:continue
        for e in seed['assignments']:
            key=e['line'],e['station']
            if key[0]==l and any(i in affected for i,m in e['assignments']) and key not in hot:hot.append(key)
    # Empty early stations provide capacity for missing predecessors.
    for e in seed['assignments']:
        key=e['line'],e['station']
        if not e['assignments'] and any(l==key[0] for l,s in hot) and key not in hot:hot.append(key)
    free=hot[:max_stations]
    if not free:free=[(e['line'],e['station']) for e in seed['assignments'][:max_stations]]
    if free_stations is not None:
        allowed={(l['id'],s) for l,s in blocks(data)}
        if not free_stations or len(set(free_stations))!=len(free_stations) or not set(free_stations)<=allowed:raise ValueError('Invalid free station set')
        if len(free_stations)>max_stations:raise ValueError('Too many free stations')
        free=list(free_stations)
    chosen={(e['line'],i,e['station'],m) for e in seed['assignments'] for i,m in e['assignments']}
    model=compact.build_model(data)
    for q,v in model.x.items():
        if (q[0],q[2]) not in free:model.problem+=v==int(q in chosen)
    with use_backend(config(solver,deadline,NumericPolicy())):model.problem.solve(make_solver(role='joint_repair'))
    info=dict(model.problem.backend_result);w=None
    if info['has_incumbent']:
        if not model.problem.valid(1e-6) or any(v.value() is None or not math.isfinite(v.value()) or abs(v.value()-round(v.value()))>1e-7 for v in model.x.values()):
            raise ValueError('Joint repair returned invalid/nonintegral original variables')
        records=[dict(line=l['id'],station=s,assignments=[(i,m) for (li,i,ss,m),v in model.x.items() if li==l['id'] and ss==s and v.value()>.5]) for l,s in blocks(data)]
        w=verify_integer_assignments(data,records,expected=info['objective'])
    return dict(free_stations=free,solver_result=info,witness=w)


def repair(data,original_pool,*,time_limit=30.,rounds=3,column_limit=200,joint=True,solver='cplex_py'):
    compact.number(time_limit,'time_limit',0,strict=True);compact.integer(rounds,'rounds',1);compact.integer(column_limit,'column_limit',1)
    started=time.perf_counter();deadline=started+time_limit;pool={k:list(v) for k,v in original_pool.items()};history=[];best=None;first=None
    for line,s in blocks(data):
        if not pool.get((line['id'],s)):raise ValueError('Empty block')
        for c in pool[line['id'],s]:validate_column(line,s,c,NodeRestrictions(),NumericPolicy())
    def accept(w):
        nonlocal best,first
        if w:
            w=verify_integer_assignments(data,w['stations'],expected=w['objective'])
            if best is None or w['objective']>best['objective']:
                best=w
                if first is None:first=time.perf_counter()-started
    try:
        base=restricted_recovery(data,pool,solver,min(deadline,time.perf_counter()+2))
        history.append(dict(stage='original_pool_integer',result=base));accept(base['witness'])
        for iteration in range(rounds):
            if time.perf_counter()>=deadline:break
            seed=profit_aware_seed(data,pool,deadline,solver);entry=dict(stage='repair',iteration=iteration+1,seed=seed,columns=[]);history.append(entry)
            if not seed['assignments']:break
            new=generate_columns(data,pool,seed,limit=column_limit,deadline=deadline);entry['columns']=new
            if time.perf_counter()>=deadline:break
            attempt=restricted_recovery(data,pool,solver,min(deadline,time.perf_counter()+2))
            entry['integer_recovery']=attempt;accept(attempt['witness']);entry['elapsed']=time.perf_counter()-started
            if not new:break
        if joint and best is None and time.perf_counter()<deadline and history[-1].get('seed',{}).get('assignments'):
            seed=history[-1]['seed'];tick=time.perf_counter();attempt=joint_repair(data,seed,deadline,solver)
            history.append(dict(stage='joint_repair',result=attempt,seconds=time.perf_counter()-tick));accept(attempt['witness'])
            if attempt['witness']:
                new=[];lines={l['id']:l for l in data['lines']}
                for e in best['stations']:
                    key=e['line'],e['station'];c=make_column(lines[key[0]],key[1],e['assignments'])
                    if c.assignments not in {old.assignments for old in pool[key]}:
                        pool[key].append(c);new.append(dict(line=key[0],station=key[1],assignments=list(c.assignments),profit=c.profit,operation='joint_repair'))
                history[-1]['columns']=new
        # Once feasible, optimize profit in small station neighborhoods; preserve best even on failure.
        if joint and best is not None:
            for line in data['lines']:
                if time.perf_counter()>=deadline:break
                records=best['stations'];active=[(e['line'],e['station']) for e in records if e['line']==line['id'] and e['assignments']]
                empty=[(e['line'],e['station']) for e in records if e['line']==line['id'] and not e['assignments']]
                free=(active[:3]+empty[:1])[:4]
                if not free:continue
                tick=time.perf_counter();attempt=joint_repair(data,dict(assignments=records,violations=[]),
                    min(deadline,time.perf_counter()+4),solver,free_stations=free)
                before=best['objective'];accept(attempt['witness'])
                entry=dict(stage='profit_improvement',result=attempt,incumbent_before=before,incumbent_after=best['objective'],seconds=time.perf_counter()-tick,columns=[])
                history.append(entry)
                if attempt['witness']:
                    lines={l['id']:l for l in data['lines']}
                    for e in best['stations']:
                        key=e['line'],e['station'];c=make_column(lines[key[0]],key[1],e['assignments'])
                        if c.assignments not in {old.assignments for old in pool[key]}:
                            pool[key].append(c);entry['columns'].append(dict(line=key[0],station=key[1],assignments=list(c.assignments),profit=c.profit,operation='profit_improvement'))
    except TimeoutError:history.append(dict(stage='time_limit'))
    exhausted=time.perf_counter()>=deadline
    result=dict(algorithm='conflict_directed_repair_columns',scope='verified_integer_LB_only',budget_exhausted=exhausted,
        global_integer_optimal_proven=False,status='feasible' if best else 'time_limit' if exhausted else 'no_feasible_solution_found',
        initial_columns=sum(map(len,original_pool.values())),final_columns=sum(map(len,pool.values())),
        witness=best,integer_lower_bound=None if best is None else best['objective'],first_integer_seconds=first,
        seconds=time.perf_counter()-started,config=dict(time_limit=time_limit,rounds=rounds,column_limit=column_limit,joint=joint,solver=solver),history=history)
    return result,pool


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--certificate',type=Path,default=CERTIFICATE)
    p.add_argument('--iteration',type=int,default=ITERATION);p.add_argument('--time-limit',type=float,default=30)
    p.add_argument('--rounds',type=int,default=3);p.add_argument('--column-limit',type=int,default=200);p.add_argument('--no-joint',action='store_true')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    path=a.certificate.resolve();instance=next(q/'instance.json' for q in (path.parent,path.parent.parent) if (q/'instance.json').exists())
    raw=instance.read_bytes();data=json.loads(raw);saved=load_result(path)
    if saved['node']['restrictions']:raise ValueError('Root-only repair refuses branch restrictions')
    row=next(r for r in saved['node']['certificate']['rounds'] if r['phase']==2 and r['iteration']==a.iteration)
    pool=pool_from_records(data,row['pool']);(a.output/'instance.json').write_bytes(raw)
    try:result,new_pool=repair(data,pool,time_limit=a.time_limit,rounds=a.rounds,column_limit=a.column_limit,joint=not a.no_joint)
    except Exception as error:
        import traceback
        (a.output/'error.json').write_text(json.dumps(dict(status='solver_error',error=repr(error),traceback=traceback.format_exc()),indent=2),encoding='utf-8')
        raise
    result.update(input_sha256=hashlib.sha256(raw).hexdigest(),certificate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),iteration=a.iteration)
    (a.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    if result['witness']:
        text='\n'.join(f"{e['line']} 站{e['station']}：{e['assignments']}" for e in result['witness']['stations'])
        (a.output/'allocation.txt').write_text(text,encoding='utf-8');print(text)
    print(json.dumps({k:result[k] for k in ('status','integer_lower_bound','initial_columns','final_columns','first_integer_seconds','seconds')},ensure_ascii=False))
if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
