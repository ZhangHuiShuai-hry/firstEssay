"""寻找合法但缺列的受限池：LP可行/IP不可行，而完整IP可行。"""
import json,random
from pathlib import Path
from find_cases import instance,enumerate_all,solve_full

def main():
    dest=Path(__file__).resolve().parent/'evidence/pool_counterexample';dest.mkdir(parents=True,exist_ok=False)
    rng=random.Random(1104);trials=[];found=None
    for seed in range(30):
        d=instance(seed);full=enumerate_all(d)
        if not all(full.values()):continue
        ip=solve_full(d,full,True)
        if not ip['optimal']:continue
        # 相同资源档保留最好列，仅用于缩小独立搜索；不用于生产CG。
        profiles={}
        for l,cs in full.items():
            best={}
            for c in cs:
                key=c['human'],c['robot']
                if key not in best or c['profit']>best[key]['profit']:best[key]=c
            profiles[l]=list(best.values())
        for attempt in range(25):
            pool={l:rng.sample(cs,min(2,len(cs))) for l,cs in profiles.items()}
            lp=solve_full(d,pool)
            if not lp['optimal']:continue
            rip=solve_full(d,pool,True);trials.append(dict(seed=seed,attempt=attempt,LP=lp,IP=rip))
            if rip['status']=='infeasible':
                found=dict(seed=seed,attempt=attempt,full_IP=ip,restricted_LP=lp,restricted_IP=rip)
                for name,obj in [('instance',d),('restricted_pool',pool),('oracle',found),('full_pool',full)]:
                    (dest/(name+'.json')).write_text(json.dumps(obj,indent=2),encoding='utf-8')
                break
        if found:break
    (dest/'search.json').write_text(json.dumps(dict(trials=trials,found=found),indent=2),encoding='utf-8')
    print(json.dumps(found))

if __name__=='__main__':main()
