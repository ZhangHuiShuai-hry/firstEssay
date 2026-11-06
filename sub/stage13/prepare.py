import hashlib,json,math
from copy import deepcopy
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def save(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2)
def main():
    out=HERE/'evidence/inputs';out.mkdir(parents=True,exist_ok=False);rows=[];cases=[]
    old=HERE.parent/'stage12/evidence';meta=json.loads((old/'inputs/manifest.json').read_bytes())['instances']
    for seed in (32,33,34):
        name=f'tasks120_lines06_ample_seed{seed}.json';raw=(old/'base_inputs'/name).read_bytes();d=json.loads(raw)
        calibration=next(r for r in meta if 'tasks120' in r['file'] and f'seed{seed}' in r['file'])
        d.update(human_limit=math.ceil(.8*calibration['calibration_human']),robot_limit=math.ceil(.8*calibration['calibration_robot']))
        path=out/f'tasks120_lines06_ratio80_seed{seed}.json';save(path,d)
        rows.append(dict(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_sha256=hashlib.sha256(raw).hexdigest(),capacity=[d['human_limit'],d['robot_limit']],calibration=calibration,assignments_provided=False))
        methods=['compact_plain','balanced_bound'];
        if seed%2:methods.reverse()
        cases.append(dict(input=str(path.relative_to(ROOT)),methods=methods))
    src=HERE.parent/'stage11/evidence/inputs/tasks080_lines02_conflict_candidate_seed31.json';path=out/src.name;path.write_bytes(src.read_bytes())
    rows.append(dict(file=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source=str(src.relative_to(ROOT)),rule='unchanged difficult block control'))
    cases.append(dict(input=str(path.relative_to(ROOT)),methods=['balanced_bound','compact_plain']))
    save(out/'manifest.json',dict(instances=rows,resource_rule='ceil(0.8*calibration_resource_count)'))
    plan=json.loads((HERE.parent/'stage12/formal_plan.json').read_bytes());plan.update(phase='stage13_closure',algorithm_baseline='20ff0dc6',prerequisite='stage13/PROTOCOL.md',cases=cases,expected_runs=8,budget_seconds_per_run=180,nominal_budget_sum_seconds=1440)
    save(HERE/'plan.json',plan)
    print('Frozen four cases, eight paired runs')
if __name__=='__main__':main()
