"""Post-run arithmetic and column/dual audits, including interrupted CG roots."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code/dwcg'))
from common import make_column,reduced_cost


def audit(run):
    checks=[]
    rows=json.loads((run/'summary.json').read_text())
    for row in rows:
        raw=json.loads((run/'raw'/(row['instance_id']+'.json')).read_text())
        data=json.loads(Path(raw['task']['instance_path']).read_text());lines={l['id']:l for l in data['lines']}
        expected={(l['id'],s) for l in data['lines'] for s in range(1,len(l['stations'])+1)}
        cg=raw['cg_pipeline'];upper_bounds=[];count=0
        for record in cg['completed_pricing_rounds']:
            pricing=record['pricing'];keys=[(p['line'],p['station']) for p in pricing]
            assert len(keys)==len(expected) and set(keys)==expected
            duals={tuple(d['row']):d['value'] for d in record['duals']}
            for p in pricing:
                column=make_column(lines[p['line']],p['station'],p['assignments'])
                rc=reduced_cost(lines[p['line']],p['station'],column,duals,record['phase'])
                assert abs(rc-p['reduced_cost'])<1e-4
                count+=1
            objective=sum(duals['station',l,s] for l,s in expected)
            objective+=sum(duals['task',l['id'],t['id']] for l in data['lines'] for t in l['tasks'])
            objective+=duals['human',]*data['human_limit']+duals['robot',]*data['robot_limit']
            objective-=sum(duals['recovery',l['id']]*l.get('min_recovery',0) for l in data['lines'])
            assert abs(objective-record['objective'])<1e-4
            repaired=record['objective']+sum(max(0,p['reduced_cost']) for p in pricing)
            assert abs(repaired-record['upper_bound'])<1e-4
            if record['phase']==2:upper_bounds.append(repaired)
        expected_upper=min(upper_bounds) if upper_bounds else None
        assert cg['best_bound']==expected_upper
        for item in cg['generated_pool']:
            for assignments in item['patterns']:make_column(lines[item['line']],item['station'],assignments)
        if not cg['root_converged']:assert cg['root_lp_objective'] is None
        if cg['incumbent'] is not None:
            assert cg['solution']['has_feasible_solution']
            assert abs(cg['incumbent']-cg['solution']['objective'])<1e-5
            if expected_upper is not None:assert cg['incumbent']<=expected_upper+1e-4
        if raw['compact_ip']['incumbent'] is not None and expected_upper is not None:
            assert raw['compact_ip']['incumbent']<=expected_upper+1e-4
        checks.append(dict(instance_id=row['instance_id'],passed=True,complete_station_pricings_checked=count,
                           note='Validates saved coefficients/arithmetic/local columns. Exact PP optimality relies on native CPLEX proof; no full enumeration at these sizes.'))
    (run/'audit_results.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    print(f'Post-run audits passed: {len(checks)} pairs, {sum(c["complete_station_pricings_checked"] for c in checks)} saved station pricings')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();audit(a.run)
