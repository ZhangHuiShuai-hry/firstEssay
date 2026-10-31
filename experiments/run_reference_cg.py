"""Run the frozen pre-fix CG implementation on one unchanged diagnosis instance."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
frozen=ROOT/'experiments/runs/fair_large_01/source'
sys.path[:0]=[str(frozen/'experiments'),str(frozen/'code/dwcg'),str(frozen/'code')]
spec=importlib.util.spec_from_file_location('reference_fair',frozen/'experiments/fair_compare.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
data=json.loads((ROOT/'experiments/runs/fair_long_diagnosis_01/instances/B1_20_s11.json').read_text())
out=ROOT/'experiments/runs/cg_diagnosis/reference_n20';out.mkdir(parents=True,exist_ok=False)
result=module.arm(data,dict(equal_budget_seconds=120,root_fraction=.9,max_iterations=1000,solver_seed=11),
                  'cg_pipeline',out/'logs')
(out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
print({k:result[k] for k in ['root_status','root_wall_time','incumbent','best_bound']})
