"""Bounded audit of medium witnesses/provenance; no exponential domain oracle."""
import json,sys,hashlib,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'code')]
from bp_solution import verify_integer_assignments

def read(p):return json.loads(p.read_text())
def main():
    base=ROOT/'docs/branch_and_price/task03';medium=base/'evidence/medium';rows=read(medium/'summary.json');checked=[]
    for row in rows:
        prefix=f"n{row['n']}_s{row['seed']}";version=row['version']
        folder=medium/('arm_'+prefix+'_'+version);data=read(folder/(f'input_{prefix}.json'))
        assert data==read(medium/(f'input_{prefix}.json'))
        r=read(folder/(prefix+'_'+version)/'result.json')
        if version=='Compact':
            stations=[dict(line=l['id'],station=s['station'],assignments=[(a['task'],a['mode']) for a in s['assignments_in_order']]) for l in r['solution']['lines'] for s in l['stations']]
            witness=verify_integer_assignments(data,stations,expected=row['lb'])
        else:
            assert not r['global_integer_optimal_proven'] and not r['global_infeasibility_proven'] and r['open_nodes']
            digest=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            assert digest==r['input_sha256']
            for name,value in r['adapter_sha256'].items():
                assert hashlib.sha256((base/'source_snapshot/code/dwcg'/name).read_bytes()).hexdigest()==value
            witness=None
            if r['has_integer_incumbent']:witness=verify_integer_assignments(data,r['integer_incumbent_solution']['stations'],expected=row['lb'])
            expected={(l['id'],s) for l in data['lines'] for s in range(1,len(l['stations'])+1)}
            for node in r['node_history']:
                for rnd in node.get('certificate',{}).get('rounds',[]):
                    if rnd['complete_pricing']:
                        pp=rnd['pricing'];assert len(pp)==len(expected) and {(p['line'],p['station']) for p in pp}==expected
                        assert all(p['optimal'] and p['status']=='optimal' for p in pp)
        if row['lb'] is not None:
            assert witness is not None and row['ub']>=row['lb']-1e-5
            assert abs(row['absolute_gap']-(row['ub']-row['lb']))<1e-6
        checked.append(dict(n=row['n'],seed=row['seed'],version=version,check='PASS',integer_witness_verified=witness is not None))
    result=dict(scope='medium_input_and_snapshot_hashes_integer_witnesses_complete_pricing_flags_no_full_domain_LP_oracle',checks=checked)
    out=base/'evidence/medium_audit.json'
    with out.open('x') as f:json.dump(result,f,indent=2)
    print(len(checked),'records;',sum(r['integer_witness_verified'] for r in checked),'integer witnesses independently checked; no full-domain oracle claim')
if __name__=='__main__':main()
