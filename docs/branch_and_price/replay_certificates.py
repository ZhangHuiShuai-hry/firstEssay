"""Offline replay of final Task02 evidence, provenance checks, and forged proofs."""
import copy
import hashlib
import json
from pathlib import Path

from independent_bp_verify import ROOT,verify_tree,verify_node,oracle,CertificateRejected
from node_state import NumericPolicy
from dataclasses import asdict

HERE=Path(__file__).resolve().parent


def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False)


def main():
    base=HERE/'evidence/validation_final';out=HERE/'evidence/certificate_replay'
    out.mkdir(exist_ok=False);reports=[]
    files=sorted(base.glob('*/result.json'))+sorted((base/'additional').glob('*/result.json'))+sorted((base/'interruptions').glob('*/result.json'))
    for f in files:
        data=read(f.parent/'instance.json');result=read(f)
        for rel,digest in result['code_version']['source_sha256'].items():
            if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=digest:raise RuntimeError('Delivered production source differs from tested source: '+rel)
        report=verify_tree(data,result,solve_oracles=False)
        reports.append({'path':str(f.relative_to(ROOT)),'status':'PASS','nodes':report['nodes_checked'],
                        'rounds':report['rounds_checked'],'global_conclusion_verified':report['global_conclusion_verified']})
    nodes=[]
    for f in sorted((base/'node_scenarios').glob('*/node.json')):
        data=read(f.parent/'instance.json');n=read(f)
        checked=verify_node(data,n,oracle.enumerate_patterns(data),asdict(NumericPolicy()),False)
        nodes.append({'path':str(f.relative_to(ROOT)),'status':'PASS','rounds':checked['rounds']})
    folder=base/'two_lines_cplex_py';data=read(folder/'instance.json');original=read(folder/'result.json')
    forged=[]
    for name in ('bound','branch','unproven_pricing','integer','lost_child','invalid_dual','wrong_pricing_domain','initial_pool','artificial_sign'):
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
        dump(out/(name+'.json'),r)
        try:verify_tree(data,r,solve_oracles=False)
        except (CertificateRejected,KeyError,AssertionError) as error:forged.append({'name':name,'rejected':True,'reason':str(error)})
        else:raise RuntimeError('Accepted forged certificate '+name)
    folder=base/'interruptions/node_limit';data=read(folder/'instance.json');r=read(folder/'result.json');r['open_nodes'].pop()
    dump(out/'hidden_open_node.json',r)
    try:verify_tree(data,r,solve_oracles=False)
    except CertificateRejected as error:forged.append({'name':'hidden_open_node','rejected':True,'reason':str(error)})
    else:raise RuntimeError('Accepted hidden open node')
    baseline=read(HERE/'BASELINE.json')
    changes=[p for p,h in baseline['tracked_sha256'].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
    if changes:raise RuntimeError('Unexpected modification to Task01 tracked files: '+str(changes))
    result={'offline_trees':reports,'offline_standalone_nodes':nodes,'forged_certificates':forged,
            'production_hashes_match':True,'preexisting_tracked_files_modified':changes,
            'verifier_sha256':hashlib.sha256((HERE/'independent_bp_verify.py').read_bytes()).hexdigest()}
    dump(out/'summary.json',result)
    print(len(reports),'offline trees;',len(nodes),'standalone nodes;',len(forged),'forged certificates rejected; original tracked files unchanged')


if __name__=='__main__':main()
