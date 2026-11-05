"""原模型下AND链+可选J任务资源紧张族；生成一次冻结，worker不再生成。"""
import json,random,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
def instance(lines,seed):
    rng=random.Random(seed);result=[]
    for l in range(lines):
        tasks=[]
        for mode in ('H','R'):
            for n in (1,2):tasks.append(dict(id=mode+str(n),value=0 if n==1 else rng.randint(7,12),weight=int(n==2),modes={mode:dict(time=1,cost=1,beta=0)}))
        tasks.append(dict(id='J',value=rng.randint(13,22),weight=0,modes={'J':dict(time=1,cost=1,beta=0)}))
        result.append(dict(id=f'L{l}',tasks=tasks,cycle_time=1,fatigue_limit=.5,
            stations=[dict(fixed_cost=.1,human_cost=.2,robot_cost=.2) for _ in range(3)],
            required_tasks=[],min_recovery=1,precedence=[['H1','H2'],['R1','R2']]))
    return dict(lines=result,human_limit=2*lines-1,robot_limit=2)
def main():
    out=HERE/'evidence/inputs';out.mkdir(parents=True,exist_ok=False);manifest=[]
    for lines,seed in [(2,11),(4,11),(4,12),(6,11)]:
        d=instance(lines,seed);p=out/f'tasks{lines*5:03d}_lines{lines:02d}_tight_seed{seed}.json'
        raw=json.dumps(d,indent=2).encode();p.write_bytes(raw)
        manifest.append(dict(path=p.name,sha256=hashlib.sha256(raw).hexdigest(),lines=lines,seed=seed,tasks=lines*5))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
if __name__=='__main__':main()
