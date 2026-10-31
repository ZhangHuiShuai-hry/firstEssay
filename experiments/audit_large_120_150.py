import csv,hashlib,json,sys
from pathlib import Path
from generate_instances import compact
from common import make_column,reduced_cost,blocks

def main(out):
    provenance=json.loads((out/'provenance.json').read_text());root=Path(__file__).resolve().parents[1]
    for rel,sha in provenance['source_sha256'].items():
        assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==sha,rel
    iterations=[];calls=0;delta=0.;runs=[]
    for e in json.loads((out/'instances/manifest.json').read_text()):
        data=json.loads((out/'instances'/e['instance']).read_text());compact.validate_data(data)
        cg=json.loads((out/'raw'/(e['instance_id']+'_cg.json')).read_text());lines={l['id']:l for l in data['lines']}
        expected={(l['id'],s) for l,s in blocks(data)}
        for rnd in cg['rounds']:
            duals={tuple(d['row']):d['value'] for d in rnd['duals']}
            priced=[p for p in rnd['pricing'] if p['status']=='optimal']
            for p in priced:
                assert p['native_status']==101
                col=make_column(lines[p['line']],p['station'],p['assignments'],tolerance=1e-6)
                diff=abs(reduced_cost(lines[p['line']],p['station'],col,duals,rnd['phase'])-p['rc'])
                assert diff<1e-5;delta=max(delta,diff);calls+=1
            if rnd['complete_pricing']:
                assert len(priced)==len(expected) and {(p['line'],p['station']) for p in priced}==expected
                assert abs(rnd['upper_bound']-(rnd['objective']+sum(max(0,p['rc']) for p in priced)))<1e-6
            iterations.append(dict(instance_id=e['instance_id'],**{k:v for k,v in rnd.items() if k not in ('duals','pricing')}))
        assert not cg['converged'] and cg['status']=='time_limit' and cg['lp_objective'] is None
        assert cg['lower_bound']<=cg['upper_bound']+1e-5
        runs.append(dict(instance_id=e['instance_id'],rmp_native_time=cg['rmp_native_time'],rmp_build_time=cg['rmp_build_time'],rmp_interface_time=cg['rmp_interface_time'],other_time=cg['other_time']))
    with (out/'iterations.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(iterations[0]));w.writeheader();w.writerows(iterations)
    result=dict(passed=True,scope='Source unchanged, data validation, every returned optimal PP column and independent reduced cost, full-round coverage and bound arithmetic; not full column enumeration',exact_pricing_calls_checked=calls,max_reduced_cost_delta=delta,runs=runs)
    (out/'audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':main(Path(sys.argv[1]))
