"""独立随机微型实例搜索，完整枚举后发现整数间隙；不改原生成器。"""
import json,random,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate import enumerate_all,solve_full,audit
from line_cg import run
from compact_solver import run as compact_run

def instance(seed):
    rng=random.Random(seed);lines=[]
    for l in range(2):
        tasks=[]
        for i in range(3):
            modes={m:dict(time=rng.randint(1,4),cost=rng.randint(0,6),beta=0 if m=='R' else rng.choice([0,.08,.2])) for m in ('H','R','J') if rng.random()<.8}
            if not modes:modes={'H':dict(time=2,cost=2,beta=.1)}
            tasks.append(dict(id=str(i),value=rng.randint(3,16),weight=1,modes=modes))
        lines.append(dict(id=str(l),tasks=tasks,stations=[dict(fixed_cost=1,human_cost=1,robot_cost=1)]*2,cycle_time=5,fatigue_limit=.5,
                          required_tasks=['0'],min_recovery=rng.choice([1,2]),precedence=[[str(i),str(j)] for i in range(3) for j in range(i+1,3) if rng.random()<.25]))
    return dict(lines=lines,human_limit=rng.randint(1,3),robot_limit=rng.randint(1,3))

def main():
    out=Path(__file__).resolve().parent/'evidence/counterexamples';out.mkdir(parents=True,exist_ok=False)
    found=[];records=[];tick=time.perf_counter()
    for seed in range(120):
        data=instance(seed);pool=enumerate_all(data)
        if not all(pool.values()):continue
        lp=solve_full(data,pool);ip=solve_full(data,pool,True)
        records.append(dict(seed=seed,LP=lp,IP=ip))
        gap=lp['optimal'] and ip['optimal'] and lp['objective']>ip['objective']+1e-5
        lpnoip=lp['optimal'] and ip['status']=='infeasible'
        if gap or lpnoip:
            folder=out/f'seed{seed}';folder.mkdir()
            support={l:[] for l in pool}
            for e in lp['positive']:support[e['line']].append(pool[e['line']][e['index']])
            support_ip=solve_full(data,support,True)
            result=run(data,time_limit=10);verified=audit(data,result);direct=compact_run(data,time_limit=10)
            if ip['optimal']:assert abs(direct['global_lower_bound']-ip['objective'])<1e-5
            info=dict(seed=seed,LP=lp,IP=ip,support_IP=support_ip,oracle_patterns={l:len(p) for l,p in pool.items()},verification=verified,
                      CG_status=result['status'],CG_LB=result['lower_bound'],CG_UB=result['upper_bound'])
            for name,obj in [('instance',data),('oracle',info),('cg',result),('compact',direct),('lp_support_pool',support)]:
                (folder/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
            found.append(info);print(json.dumps(info),flush=True)
        (out/'search.json').write_text(json.dumps(dict(trials=records,found=found,seconds=time.perf_counter()-tick),indent=2),encoding='utf-8')
        if len(found)>=4:break

if __name__=='__main__':main()
