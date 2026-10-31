import csv,json,collections,shutil
from pathlib import Path
root=Path('experiments/runs/restricted_ip_diagnostic_01');rows=[]
for n in (120,150):
 for mode in ('cg_only','augmented'):
  x=json.loads((root/f'n{n}_{mode}'/'result.json').read_text());counts=collections.Counter(z['source'] for z in x['selected_columns'])
  rows.append(dict(tasks=n,method=mode,status=x['status'],feasible=x['has_feasible'],objective=x['objective'],restricted_bound=x['restricted_best_bound'],restricted_gap=x['restricted_gap'],solver_seconds=x['solver_time'],wall_seconds=x['wall_time'],columns=x['total_columns'],original_cg_selected=counts['original_CG'] if x['has_feasible'] else None,direct_added_selected=counts['direct_added'] if x['has_feasible'] else None,changed_stations=len(x['changed_stations']) if x['has_feasible'] else None,compact_validated=x['independent_compact_validation'],mip_start_accepted=x['mip_start_accepted'],direct_baseline=x['direct_objective'],global_cg_upper=x['original_global_upper_bound']))
 ip=json.loads((Path('experiments/runs/large_120_150_600_01/raw')/f'total{n}_L2_s11_ip.json').read_text())
 rows.append(dict(tasks=n,method='direct_600',status=ip['status'],feasible=True,objective=ip['incumbent'],restricted_bound=None,restricted_gap=None,solver_seconds=ip['native']['solver_time'],wall_seconds=ip['wall_time'],columns=None,original_cg_selected=None,direct_added_selected=None,changed_stations=0,compact_validated=True,mip_start_accepted=None,direct_baseline=ip['incumbent'],global_cg_upper=x['original_global_upper_bound']))
with (root/'summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(root/'summary.json').write_text(json.dumps(rows,indent=2))
source=root/'source';source.mkdir(exist_ok=True)
for p in ('experiments/restricted_ip_diagnostic.py','experiments/report_restricted_ip.py','experiments/inspect_saved_column_pools.py'):shutil.copy2(p,source/Path(p).name)
