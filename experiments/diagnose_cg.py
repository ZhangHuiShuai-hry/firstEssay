"""Compare identical saved RMP matrices before/after sparse implementation fixes."""
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code/dwcg'))
import common,master


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


def matrix(m):
    return ({row:(r.sense,r.constant,tuple(sorted((v.name,c) for v,c in r.items() if c))) for row,r in m.rows.items()},
            tuple(sorted((v.name,c) for v,c in m.objective.items() if c)))


if __name__=='__main__':
    snapshot=ROOT/'experiments/snapshots/20261030_112527/code/dwcg'
    old_common=load('cg_before_common',snapshot/'common.py')
    old_master=load('cg_before_master',snapshot/'master.py');old_master.coefficients=old_common.coefficients
    records=[]
    for n in (20,30,40):
        run=ROOT/'experiments/runs/fair_large_01'
        raw=json.loads((run/'raw'/f'B1_{n}_s11.json').read_text());data=json.loads((run/'instances'/f'B1_{n}_s11.json').read_text())
        lines={l['id']:l for l in data['lines']}
        pool={(b['line'],b['station']):[common.make_column(lines[b['line']],b['station'],a) for a in b['patterns']]
              for b in raw['cg_pipeline']['generated_pool']}
        timings={};models={}
        for label,module in [('before',old_master),('sparse',master)]:
            times=[]
            for repeat in range(3):
                start=time.perf_counter();m=module.build_master(data,pool);times.append(time.perf_counter()-start)
            timings[label]=times;models[label]=m
        equal=matrix(models['before'])==matrix(models['sparse']);assert equal
        records.append(dict(n=n,columns=sum(map(len,pool.values())),matrix_equal=equal,times=timings,
                            speedup=statistics.median(timings['before'])/statistics.median(timings['sparse'])))
    out=ROOT/'experiments/runs/cg_diagnosis';out.mkdir(exist_ok=True)
    (out/'rmp_microbenchmark.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(json.dumps(records,indent=2))
