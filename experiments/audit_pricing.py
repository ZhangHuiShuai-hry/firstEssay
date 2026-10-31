"""Audit immutable V1 source/data and V2 saved exact-pricing termination records."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def audit(runs,out,check_data=False):
    pointer=json.loads((ROOT/'experiments/CG_V1_FROZEN.json').read_text());snapshot=ROOT/pointer['snapshot']
    frozen=json.loads((snapshot/'manifest.json').read_text());protected={}
    replay=ROOT/'experiments/runs/pricing_replay_02'
    assert json.loads((replay/'validation.json').read_text())['passed']
    for p in ('code/dwcg/persistent_pricing.py','experiments/pricing_profile.py'):
        assert (ROOT/p).read_bytes()==(replay/'source'/p).read_bytes(),'Formal replay implementation mismatch'
    for p in ('code/milp/model.py','code/dwcg/common.py','code/dwcg/master.py','code/dwcg/pricing.py','code/dwcg/solve.py',
              'code/dwcg/verify.py','code/dwcg/incremental_master.py','code/solver_backend.py'):
        actual=hashlib.sha256((ROOT/p).read_bytes()).hexdigest();assert actual==frozen['source_sha256'][p.replace('/','\\')]
        protected[p]=actual
    data_count=0
    if check_data:
        for p,wanted in frozen['data_sha256'].items():
            assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==wanted,f'V1 data changed: {p}'
            data_count+=1
    records=[]
    for run in runs:
        for p in ('code/dwcg/persistent_pricing.py','experiments/pricing_profile.py','experiments/compare_pricing.py'):
            assert (ROOT/p).read_bytes()==(run/'source'/p).read_bytes(),f'Execution source changed {p}'
        for row in json.loads((run/'summary.json').read_text()):
            assert row.get('python_hash_seed')=='11'
            raw=json.loads((run/'raw'/(row['instance_id']+'_'+row['version']+'.json')).read_text())
            data=json.loads((run/'instances'/(row['instance_id']+'.json')).read_text())
            baseline=ROOT/'experiments/runs/incremental_rmp_01/instances'/(row['instance_id']+'.json')
            assert baseline.read_bytes()==(run/'instances'/(row['instance_id']+'.json')).read_bytes()
            expected={(line['id'],s) for line in data['lines'] for s in range(1,len(line['stations'])+1)}
            assert abs(row['phase1_time']+row['phase2_time']-row['wall_time'])<.01
            assert row['other_time']>=-1e-6
            if row.get('upper_bound') is not None and row.get('lower_bound') is not None:
                assert row['upper_bound']+1e-5>=row['lower_bound']
            for call in raw['pricing_log']:
                assert call['other_time']>=-1e-6
                if call['status']=='optimal':assert call['native_status']==101
            for event in raw['events']:
                assert event['options']['threads']==1 and event['options']['seed']==11
                if event['role']=='pricing':assert event['relative_gap_requested']==0
            if row['converged']:
                cg=raw['cg'];h=cg['history'][-1];assert h['phase']==2
                stations=[(p['line'],p['station']) for p in h['pricing']]
                assert len(stations)==len(set(stations)) and set(stations)==expected
                rc=[p['reduced_cost'] for p in h['pricing']]
                assert abs(max(rc)-h['maximum_reduced_cost'])<1e-7
                assert h['maximum_reduced_cost']<=cg['epsilon']+1e-8
                assert abs(h['objective']-row['lp_objective'])<1e-5
                assert abs(h['lp_upper_bound']-h['objective']-sum(max(0,x) for x in rc))<1e-5
                assert abs(h['lp_upper_bound']-cg['lp_upper_bound'])<1e-5
            else:assert row['lp_objective'] is None
            records.append(dict(run=str(run),instance_id=row['instance_id'],version=row['version'],budget=row['budget'],
                                status=row['status'],converged=row['converged']))
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(dict(passed=True,protected_source_sha256=protected,V1_data_files_checked=data_count,
        same_implementation_as_fixed_dual_replay=True,records=records),indent=2),encoding='utf-8')
    print('V1 invariance / V2 saved-result audit passed:',len(records),'runs;',data_count,'old files unchanged')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runs',nargs='+',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--check-frozen-data',action='store_true')
    a=p.parse_args();audit(a.runs,a.out,a.check_frozen_data)
