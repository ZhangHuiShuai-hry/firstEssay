"""Offline replay and mutation checks, with no solver calls."""
import copy
import hashlib
import json
from pathlib import Path
from independent_validation import certificate,enumerate_patterns,ROOT

HERE=Path(__file__).resolve().parent

def main():
    records=[]
    for run in ('acceptance_rebuilt','acceptance_native','acceptance_extra','acceptance_extra_native'):
        folder=HERE/'evidence'/run
        config=json.loads((folder/'config.json').read_text())
        # Every acceptance run must have used the delivered production source.
        for rel,digest in config['source_sha256'].items():
            if rel.startswith('code'):
                assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==digest,rel
        for row in json.loads((folder/'summary.json').read_text()):
            f=folder/f"{row['name']}_{row['backend']}"
            data=json.loads((f/'instance.json').read_text());raw=json.loads((f/'result.json').read_text())
            pool=enumerate_patterns(data);rounds=certificate(data,pool,raw['cg'])
            records.append({'run':run,'case':row['name'],'backend':row['backend'],'rounds':len(rounds),'status':'PASS'})
    f=HERE/'evidence/acceptance_rebuilt/two_lines_cplex_py'
    data=json.loads((f/'instance.json').read_text());result=json.loads((f/'result.json').read_text())['cg'];pool=enumerate_patterns(data)
    mutations=[]
    for kind in ('upper','dual','coverage','unproven','primal','nonfinite'):
        r=copy.deepcopy(result)
        if kind=='upper':r['lp_upper_bound']-=1
        if kind=='dual':r['final_duals'][0]['value']+=1
        if kind=='coverage':r['history'][-1]['pricing'].pop()
        if kind=='unproven':r['history'][-1]['pricing'][0]['optimal']=False
        if kind=='primal':r['lp_solution'][0]['weight']+=.1
        if kind=='nonfinite':r['history'][-1]['duals'][0]['value']=float('nan')
        try:certificate(data,pool,r)
        except (AssertionError,KeyError):mutations.append({'mutation':kind,'rejected':True})
        else:raise AssertionError(f'Accepted corrupted {kind}')
    output={'certificate_runs':records,'tamper_tests':mutations,'production_hashes_match':True}
    (HERE/'evidence/offline_all_certificates.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
    print(len(records),'offline certificates PASS;',len(mutations),'tampered certificates rejected')

if __name__=='__main__':main()
