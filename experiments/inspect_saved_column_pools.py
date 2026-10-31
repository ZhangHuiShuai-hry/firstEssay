"""Reconstruct only columns actually admitted by the saved exact-CG histories."""
import json,hashlib,sys
from pathlib import Path
from datetime import datetime,timezone
from hybrid import columns_from_solution
from common import empty_pool,make_column,coefficients

base=Path('experiments/runs/large_120_150_600_01'); hybrid=Path('experiments/runs/hybrid_large_01')
out=Path('experiments/runs/restricted_ip_pool_audit_01');out.mkdir(exist_ok=False)
results=[]
for n in (120,150):
 key=f'total{n}_L2_s11';data=json.loads((base/'instances'/f'{key}.json').read_text());orig=json.loads((base/'raw'/f'{key}_ip.json').read_text())['solution'];lines={l['id']:l for l in data['lines']}
 original_pool=columns_from_solution(data,orig)
 for method in ('cg','hybrid60','hybrid120','hybrid180'):
  if method=='cg':
   path=base/'raw'/f'{key}_cg.json';rec=json.loads(path.read_text());pool=empty_pool(data)
  else:
   path=hybrid/f'n{n}_{method}'/'result.json';raw=json.loads(path.read_text());rec=raw['cg'];pool=columns_from_solution(data,raw['mip']['solution']) if raw['mip'].get('solution') else empty_pool(data)
  blocks=len(pool);added=0
  for idx,round_ in enumerate(rec['rounds']):
   if not round_['complete_pricing']:continue
   if idx+1>=len(rec['rounds']):continue
   for p in round_['pricing']:
    if p['rc']>1e-7:
     k=(p['line'],p['station']);col=make_column(lines[k[0]],k[1],p['assignments']);assert all(x.assignments!=col.assignments for x in pool[k]);pool[k].append(col);added+=1
  count=sum(map(len,pool.values()));missing=[]
  for k,cols in original_pool.items():
   col=cols[-1]
   if not any(c.assignments==col.assignments for c in pool[k]):missing.append({'line':k[0],'station':k[1],'assignments':col.assignments})
  for (l,s),cols in pool.items():
   for col in cols: coefficients(lines[l],s,col)
  item=dict(tasks=n,method=method,recorded_columns=rec['columns'],reconstructed_columns=count,columns_match=count==rec['columns'],initial_and_added=added,station_blocks=blocks,missing_original_stations=missing,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
  results.append(item); print(n,method,count,rec['columns'],'missing',len(missing),flush=True)
 (out/f'{n}_done.json').write_text(json.dumps([x for x in results if x['tasks']==n],indent=2))
(out/'pool_audit.json').write_text(json.dumps(dict(timestamp_utc=datetime.now(timezone.utc).isoformat(),results=results),indent=2))
