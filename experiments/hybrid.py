"""Sequential compact MIP and exact CG-V2 under one wall-clock deadline."""
import argparse,json,time,sys
from pathlib import Path
from fair_compare import arm
from hybrid_cg import execute as execute_cg
import solve
from common import compact,empty_pool,make_column
from solver_backend import load_cplex

def columns_from_solution(data,solution):
    lines={l['id']:l for l in data['lines']};pool=empty_pool(data);objective=0.;humans=robots=0
    for ls in solution['lines']:
        line=lines[ls['id']];seen={};recovery=0
        for st in ls['stations']:
            assignments=[(x['task'],x['mode']) for x in st['assignments_in_order']]
            col=make_column(line,st['station'],assignments)
            assert (st['active'],st['human'],st['robot'])==(int(bool(assignments)),col.human,col.robot)
            for i,_ in assignments:
                if i in seen:raise ValueError('Duplicate task')
                seen[i]=st['station']
            if assignments:pool[line['id'],st['station']].append(col)
            objective+=col.profit;recovery+=col.recovery;humans+=col.human;robots+=col.robot
        if not set(line['required_tasks'])<=seen.keys() or recovery<line['min_recovery']-1e-7:raise ValueError('Line requirements violated')
        for i,j in line['precedence']:
            if j in seen and (i not in seen or seen[i]>seen[j]):raise ValueError('Precedence violated')
    if humans>data['human_limit'] or robots>data['robot_limit'] or abs(objective-solution['objective'])>1e-5:raise ValueError('Invalid original MIP solution')
    return pool

def run(instance,out,budget,mip_budget):
    out.mkdir(parents=True,exist_ok=False); data=json.loads(instance.read_text());compact.validate_data(data)
    load_cplex();start=time.perf_counter();deadline=start+budget
    mip=arm(data,dict(equal_budget_seconds=min(mip_budget,budget),solver_seed=11),'compact_ip',out/'mip_logs')
    after_mip=time.perf_counter();pool=None
    if mip.get('solution'):pool=columns_from_solution(data,mip['solution'])
    after_conversion=time.perf_counter(); remaining=deadline-after_conversion
    result=dict(budget=budget,mip_budget=mip_budget,mip=mip,mip_elapsed=after_mip-start,conversion_elapsed=after_conversion-after_mip,initial_columns=sum(map(len,pool.values())) if pool else 0,cg_status='not_run',cg=None)
    if remaining>0:
        original=solve.empty_pool
        if pool is not None:solve.empty_pool=lambda _:pool
        try:
            task=dict(input=str(instance.resolve()),output=str((out/'cg.json').resolve()),logs=str((out/'cg_logs').resolve()),version='V2',budget=remaining,deadline=deadline,entry=dict(instance_id=data['name'],factor=len(data['lines'][0]['tasks']),seed=11),max_iterations=10000)
            result['cg']=execute_cg(task);result['cg_status']=result['cg']['status']
        finally:solve.empty_pool=original
    cg=result['cg'];bounds=[x for x in (mip.get('best_bound'),cg.get('upper_bound') if cg else None) if x is not None]
    lb=mip.get('incumbent');ub=min(bounds) if bounds else None
    if lb is not None and ub is not None and lb>ub+1e-5:raise RuntimeError('Invalid combined bounds')
    result.update(integer_lower_bound=lb,upper_bound=ub,gap=(max(0,ub-lb)/abs(lb) if lb not in (None,0) and ub is not None else None),wall_time=time.perf_counter()-start)
    (out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('instance',type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--budget',type=float,default=600);p.add_argument('--mip-budget',type=float,default=60);a=p.parse_args()
    r=run(a.instance,a.out,a.budget,a.mip_budget);print(json.dumps({k:v for k,v in r.items() if k not in ('mip','cg')},indent=2))
