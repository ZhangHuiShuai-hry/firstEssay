"""Independent saved-result audit; no solver calls or full enumeration of large cases."""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/'experiments/snapshots/CG_V0_20261030_134805'


def audit(run):
    original=json.loads((FROZEN/'manifest.json').read_text())
    paths=['code/milp/model.py','code/dwcg/common.py','code/dwcg/master.py','code/dwcg/pricing.py',
           'code/dwcg/solve.py','code/dwcg/verify.py','code/solver_backend.py']
    invariance={}
    for p in paths:
        checksum=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
        assert checksum==original[p.replace('/','\\')],f'Protected source changed: {p}'
        assert checksum==hashlib.sha256((run/'source'/p).read_bytes()).hexdigest()
        invariance[p]=checksum
    implementation={}
    for p in ('code/dwcg/incremental_master.py','experiments/compare_incremental.py'):
        checksum=hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
        assert checksum==hashlib.sha256((run/'source'/p).read_bytes()).hexdigest()
        implementation[p]=checksum
    records=[]
    for row in json.loads((run/'summary.json').read_text()):
        data=json.loads((run/'instances'/(row['instance_id']+'.json')).read_text())
        raw=json.loads((run/'raw'/(row['instance_id']+'_'+row['version']+'.json')).read_text())
        expected={(line['id'],s) for line in data['lines'] for s in range(1,len(line['stations'])+1)}
        for event in raw['events']:
            assert event['options']['threads']==1 and event['options']['seed']==11
            if event['role']=='pricing' and event['optimal']:assert event['relative_gap_requested']==0
        assert abs(row['phase1_time']+row['phase2_time']-row['wall_time'])<.01
        assert row['other_time']>=-1e-6
        check=dict(instance_id=row['instance_id'],version=row['version'],status=row['status'],
                   converged=row['converged'],certificate_record_checked=False)
        if row['converged']:
            cg=raw['cg'];h=cg['history'][-1]
            assert h['phase']==2
            stations=[(p['line'],p['station']) for p in h['pricing']]
            assert len(stations)==len(set(stations)) and set(stations)==expected
            numbers=[p['reduced_cost'] for p in h['pricing']]
            assert all(math.isfinite(x) for x in numbers)
            assert abs(max(numbers)-h['maximum_reduced_cost'])<1e-7
            assert h['maximum_reduced_cost']<=cg['epsilon']+1e-8
            assert abs(h['objective']-cg['lp_objective'])<1e-5
            assert abs(h['lp_upper_bound']-cg['lp_upper_bound'])<1e-5
            assert abs(h['lp_upper_bound']-h['objective']-sum(max(0,x) for x in numbers))<1e-5
            assert abs(row['lp_objective']-cg['lp_objective'])<1e-5
            assert row['upper_bound']+1e-5>=cg['lp_objective']
            check['certificate_record_checked']=True
        else:assert row['lp_objective'] is None
        if row['version']=='V1':
            basis=raw['basis_records']
            assert all(a['variables']<=b['variables'] for a,b in zip(basis,basis[1:]))
            assert all(a['advance']==1 for a in basis)
            check.update(solves=len(basis),available_basis=sum(b['basis_available_before'] for b in basis))
        records.append(check)
    result=dict(passed=True,source_invariance=invariance,execution_source_unchanged=implementation,records=records,
                scope='Large cases: saved final exact-pricing coverage/termination records; full-column enumeration only in small regression tests.')
    (run/'AUDIT_INCREMENTAL.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Source invariance / result audit passed:',len(records),'runs')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();audit(a.run)
