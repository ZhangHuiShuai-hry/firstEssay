import json,sys
from pathlib import Path
from datetime import datetime,timezone
from hybrid import columns_from_solution
from common import blocks,make_column,reduced_cost

root=Path('experiments/runs/hybrid_large_01');base=Path('experiments/runs/large_120_150_600_01/instances');reports=[]
for n in (120,150):
  data=json.loads((base/f'total{n}_L2_s11.json').read_text());lines={l['id']:l for l in data['lines']};expected={(l['id'],s) for l,s in blocks(data)}
  for m in (60,120,180):
    path=root/f'n{n}_hybrid{m}'/'result.json'
    if not path.exists():reports.append(dict(tasks=n,mip_budget=m,status='not_completed'));continue
    result=json.loads(path.read_text());cg=result['cg'];columns_from_solution(data,result['mip']['solution']) if result['mip'].get('solution') else None
    best=None;calls=0;error=0.;best_round=None
    for rnd in cg['rounds']:
      if rnd['phase']!=2 or not rnd['complete_pricing']:continue
      ps=rnd['pricing'];assert len(ps)==len(expected) and {(p['line'],p['station']) for p in ps}==expected
      dual={tuple(d['row']):d['value'] for d in rnd['duals']}
      for p in ps:
        assert p['status']=='optimal' and p['native_status']==101
        c=make_column(lines[p['line']],p['station'],p['assignments'],tolerance=1e-6)
        diff=abs(reduced_cost(lines[p['line']],p['station'],c,dual,2)-p['rc']);assert diff<1e-5;error=max(error,diff);calls+=1
      upper=rnd['objective']+sum(max(0,p['rc']) for p in ps);assert abs(upper-rnd['upper_bound'])<1e-5
      if best is None or upper<best:best=upper;best_round=rnd['round']
    if best is not None:assert abs(best-cg['upper_bound'])<1e-5
    if result['integer_lower_bound'] is not None and result['upper_bound'] is not None:assert result['integer_lower_bound']<=result['upper_bound']+1e-5
    reports.append(dict(tasks=n,mip_budget=m,status='passed',cg_upper=best,certificate_round=best_round,checked_pricing_calls=calls,max_rc_delta=error))
(root/'audit.json').write_text(json.dumps(dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),results=reports),indent=2))
print(json.dumps(reports,indent=2))
