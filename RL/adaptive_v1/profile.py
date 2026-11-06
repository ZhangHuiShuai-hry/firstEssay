"""Non-overlapping native call buckets and incumbent traces from saved evidence."""
import json,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
rows=[]
for f in sorted((HERE/'evidence/medium').glob('*/result.json.zlib')):
    r=json.loads(zlib.decompress(f.read_bytes()));buckets={k:0. for k in ('initialization','candidate','certification')}
    for c in r['pricing_audit_calls']:
        if c['solver']['backend']=='proof_cache':continue
        role='candidate' if c.get('purpose')=='candidate' else 'initialization' if c.get('purpose') in ('initialization','initial_feasibility') else 'certification'
        buckets[role]+=c['solver']['solver_time']
    assert abs(sum(buckets.values())-r['timing']['PP_native_seconds'])<1e-7
    rm=r['timing']['RMP_native_seconds'];ip=r['timing']['restricted_IP_native_seconds'];other=r['online_wall_seconds']-sum(buckets.values())-rm-ip
    assert other>=-1e-5
    rows.append(dict(case=f.parent.name,PP_native_buckets=buckets,RMP_native_seconds=rm,restricted_IP_native_seconds=ip,
        other_seconds=other,algorithm_seconds=r['online_wall_seconds'],candidate_total_seconds=r['candidate_seconds'],
        candidate_note='candidate_total includes native candidate bucket; never add both',
        incumbent_history=r['incumbent_history'],accounting=json.loads((f.parent/'accounting.json').read_bytes())))
with (HERE/'evidence/profile.json').open('x') as f:json.dump(rows,f,indent=2)
print('PASS',len(rows),'non-overlapping native/accounting records')
