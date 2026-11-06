"""Read-only batch replay; optional new output file, never rewrites frozen evidence."""
import argparse
import json
from pathlib import Path
from run_plan_v2 import audit, sha

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    batch=a.directory;plan=json.loads((batch/'manifest.json').read_bytes());rows=json.loads((batch/'accounting.json').read_bytes())
    expected=[(Path(c['input']).stem,m) for c in plan['cases'] for m in c['methods']]
    assert [(r['case'],r['method']) for r in rows]==expected
    assert len(rows)==plan['expected_runs']
    inputs=json.loads((batch/'input_hashes.json').read_bytes())
    for rec in inputs:assert sha((batch/'inputs'/rec['frozen']).read_bytes())==rec['sha256']
    checks=[]
    for r in rows:
        folder=batch/(r['case']+'__'+r['method']);s=json.loads((folder/'summary.json').read_bytes())
        assert s['input_sha256']==next(v['sha256'] for v in inputs if Path(v['frozen']).stem==r['case'])
        assert r['exit_code']==0 and not r['hard_stop']
        assert r['timely']==(r['end_to_end_seconds']<=plan['budget_seconds_per_run'])
        for key in ('global_lower_bound','global_upper_bound','global_integer_optimal_proven'):assert r[key]==s[key]
        checks.append(audit(folder,plan.get('enumerate_profiles',False)))
    result=dict(status='PASS',runs=len(checks),timely_runs=sum(r['timely'] for r in rows),results=checks)
    if a.output:
        with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=True))

if __name__=='__main__':main()
