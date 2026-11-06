import argparse,hashlib,importlib.util,json,sys,zlib
from copy import deepcopy
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('original_generator',ROOT/'experiments/generate_instances.py')
gen=importlib.util.module_from_spec(spec);spec.loader.exec_module(gen)
def save(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2)
def plan(cases,phase):
    p=json.loads((HERE.parent/'stage10/heldout_plan.json').read_bytes())
    p.update(phase=phase,cases=cases,expected_runs=sum(len(c['methods']) for c in cases),budget_seconds_per_run=120,
             nominal_budget_sum_seconds=120*sum(len(c['methods']) for c in cases),algorithm_baseline='37e1a525')
    p['method_definitions']['independent']='Existing independent economic line MILPs; no CG or repair'
    return p
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--final',action='store_true');a=parser.parse_args()
    if not a.final:
        out=HERE/'evidence/base_inputs';out.mkdir(parents=True,exist_ok=False);rows=[];cases=[]
        for count in (2,4,8):
            d,meta=gen.generate(lines=count,seed=31,total_tasks=80,total_stations=32,graph='layered',mode_profile='mixed',fatigue=.6)
            d['human_limit']=d['robot_limit']=32
            name=f'tasks080_lines{count:02d}_ample_seed31.json';save(out/name,d)
            rows.append(dict(file=name,sha256=hashlib.sha256((out/name).read_bytes()).hexdigest(),task_bank_hash=meta['base_task_parameter_hash'],metadata=gen.metadata(d)))
            cases.append(dict(input=str((out/name).relative_to(ROOT)),methods=['independent']))
        assert len({r['task_bank_hash'] for r in rows})==1
        save(out/'manifest.json',dict(instances=rows,generator_sha256=hashlib.sha256((ROOT/'experiments/generate_instances.py').read_bytes()).hexdigest()))
        save(HERE/'calibration_plan.json',plan(cases,'E2_capacity_calibration'))
    else:
        batch=HERE/'evidence/calibration';assert json.loads((batch/'COMPLETED.json').read_bytes())['runs']==3
        assert json.loads((batch/'replay.json').read_bytes())['status']=='PASS'
        out=HERE/'evidence/inputs';out.mkdir(parents=True,exist_ok=False);rows=[];cases=[]
        for count in (2,4,8):
            base=f'tasks080_lines{count:02d}_ample_seed31';raw=(HERE/f'evidence/base_inputs/{base}.json').read_bytes();d=json.loads(raw)
            result=json.loads(zlib.decompress((batch/f'{base}__independent/result.json.zlib').read_bytes()))
            cols=[c['column'] for c in result['initialization']]
            assert len(cols)==count and all(cols),'Calibration missing local plans; do not guess capacity'
            h=sum(c['human'] for c in cols);r=sum(c['robot'] for c in cols)
            for level in ('ample','conflict_candidate'):
                e=deepcopy(d)
                if level!='ample':e.update(human_limit=max(0,h-1),robot_limit=max(0,r-1))
                gen.compact.validate_data(e)
                name=f'tasks080_lines{count:02d}_{level}_seed31.json'
                if level=='ample':(out/name).write_bytes(raw)
                else:save(out/name,e)
                rows.append(dict(file=name,sha256=hashlib.sha256((out/name).read_bytes()).hexdigest(),
                    calibrated_human=h,calibrated_robot=r,calibration_all_local_optimal=all(c['optimal'] for c in result['initialization']),
                    calibration_combination_exceeds_capacity=(h>e['human_limit'] or r>e['robot_limit']),
                    assignments_provided_to_worker=False,metadata=gen.metadata(e)))
                methods=['compact_plain','balanced_bound','independent'];i=len(cases)%3;methods=methods[i:]+methods[:i]
                cases.append(dict(input=str((out/name).relative_to(ROOT)),methods=methods))
        save(out/'manifest.json',dict(instances=rows,capacity_rule='calibration_sum_minus_one_in_each_resource',scope='development_seed31; does not prove all economic optima incompatible'))
        save(HERE/'pilot_plan.json',plan(cases,'E2_structure_pilot'))
    print('Frozen',3 if not a.final else 6,'inputs')
if __name__=='__main__':main()
