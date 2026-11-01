"""Environment-only feasibility pilot using SciPy/HiGHS on the user's compact MILP.

This is NOT a run of the user's PuLP/CBC CG. It runs their original model.py
builder through the previously independently audited minimal algebraic adapter.
"""
import csv, json, sys, time
from pathlib import Path

if __name__ == '__main__':
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/'support'))
    from audit_dlbp import solve_source
    manifest=list(csv.DictReader((root/'instances/pilot/manifest.csv').open(encoding='utf-8-sig')))
    selected=['reference_single','reference_double', 'size_n6_seed11','size_n6_seed12',
              'lines_L2_seed21','fatigue_0.40_seed31','fatigue_0.85_seed31',
              'resource_0.40_seed41','resource_0.80_seed41']
    rows=[]
    for entry in manifest:
        if entry['case_id'] not in selected: continue
        case_path=root/'instances/pilot'/f"{entry['case_id']}.json"
        data=json.loads(case_path.read_text())
        t0=time.perf_counter()
        report, _=solve_source(data)
        row={'case_id':entry['case_id'],'tasks':entry['tasks'],'lines':entry['lines'],
             'status':report['status'],'objective':report['objective'],
             'humans':(report.get('resources_used') or {}).get('humans'),
             'robots':(report.get('resources_used') or {}).get('robots'),
             'wall_s':round(time.perf_counter()-t0,4),
             'solver':'SciPy/HiGHS MILP (not original CBC; compact P0 only)'}
        print(row,flush=True);rows.append(row)
    out=root/'results/scipy_compact_pilot.csv'
    with out.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print('Wrote',out)
