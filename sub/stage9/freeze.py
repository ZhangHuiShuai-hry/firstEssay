"""生成一次冻结两线60/80任务留出实例；构造见证只作离线输入检查。"""
import hashlib,importlib.util,json,math,sys
from copy import deepcopy
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE.parent),str(ROOT/'code/dwcg')]
spec=importlib.util.spec_from_file_location('research_generator',ROOT/'experiments/generate_instances.py')
gen=importlib.util.module_from_spec(spec);spec.loader.exec_module(gen)
from bp_solution import verify_integer_assignments

def main():
    out=HERE/'evidence/inputs';out.mkdir(parents=True,exist_ok=False);rows=[]
    for n in (60,80):
        for seed in (21,22,23):
            data,meta=gen.generate(lines=2,seed=seed,total_tasks=n,total_stations=2*math.ceil((n//2)/3),graph='layered',mode_profile='mixed',fatigue=.6)
            for level in (90,70,50):
                d=deepcopy(data);k=sum(len(l['stations']) for l in d['lines'])
                d['human_limit']=d['robot_limit']=math.ceil(k*level/100)
                gen.compact.validate_data(d)
                records=[dict(line=l['id'],station=s,assignments=group) for l,groups in zip(d['lines'],meta['witness']) for s,group in enumerate(groups,1)]
                witness_ok=meta['witness_humans']<=d['human_limit'] and meta['witness_robots']<=d['robot_limit']
                if witness_ok:verify_integer_assignments(d,records)
                name=f'tasks{n:03d}_lines02_r{level}_seed{seed}.json';raw=json.dumps(d,indent=2).encode()
                (out/name).write_bytes(raw)
                rows.append(dict(file=name,sha256=hashlib.sha256(raw).hexdigest(),tasks=n,tasks_per_line=n//2,stations_per_line=len(d['lines'][0]['stations']),seed=seed,resource_percent=level,
                    constructor_witness_verified=witness_ok,constructor_witness_provided_to_solver=False,metadata=gen.metadata(d)))
    (out/'manifest.json').write_text(json.dumps(dict(generator_sha256=hashlib.sha256((ROOT/'experiments/generate_instances.py').read_bytes()).hexdigest(),instances=rows),indent=2),encoding='utf-8')
    print('Frozen',len(rows),'inputs; no constructor assignment passed to solvers')

if __name__=='__main__':main()
