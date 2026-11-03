"""Replay Task03 trees and reject ten forged proof categories, offline."""
import copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'docs/branch_and_price/task03')]
from task03_verify import verify_tree,CertificateRejected

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    base,out=[Path(p).resolve() for p in sys.argv[1:3]];out.mkdir(parents=True,exist_ok=False)
    rows=[]
    for f in sorted(base.glob('*/result.json')):
        v=verify_tree(read(f.parent/'instance.json'),read(f),solve_oracles=False)
        rows.append(dict(path=str(f.relative_to(ROOT)),passed=v['passed'],nodes=v['nodes_checked']))
    original=read(base/'two_lines_V2/result.json');data=read(base/'two_lines_V2/instance.json');forged=[]
    for name in ('bound','branch','unproven_pricing','integer','lost_child','invalid_dual','wrong_pricing_domain','initial_pool','artificial_sign','hidden_open_node'):
        r=copy.deepcopy(original);root=r['node_history'][0]
        complete=next(x for x in root['certificate']['rounds'] if x['complete_pricing'])
        if name=='bound':r['global_upper_bound']-=1
        if name=='branch':r['node_history'][1]['restrictions'][0]['value']^=1
        if name=='unproven_pricing':complete['pricing'][0]['optimal']=False
        if name=='integer':r['integer_incumbent_solution']['stations'][0]['assignments'].append(['unknown','H'])
        if name=='lost_child':root['children'].pop()
        if name=='invalid_dual':next(e for e in complete['duals'] if e['row'][0]=='human')['value']=-1
        if name=='wrong_pricing_domain':complete['pricing'][0]['fixed_variables']=[{'task':'unknown','mode':'H','value':1}]
        if name=='initial_pool':root['certificate']['initial_pool'][0]['patterns']=[]
        if name=='artificial_sign':root['certificate']['rounds'][0]['artificials'][0]['sign']=99
        if name=='hidden_open_node':r['open_nodes']=[dict(node_id=999,status='open',safe_upper_bound=100,restrictions=[])]
        (out/(name+'.json')).write_text(json.dumps(r,indent=2))
        try:verify_tree(data,r,solve_oracles=False)
        except (CertificateRejected,KeyError,AssertionError) as e:forged.append(dict(name=name,rejected=True,reason=str(e)))
        else:raise AssertionError('Forged certificate accepted: '+name)
    result=dict(offline_trees=rows,forged_certificates=forged)
    (out/'summary.json').write_text(json.dumps(result,indent=2));print(len(rows),'replayed;',len(forged),'forgeries rejected')
if __name__=='__main__':main()
