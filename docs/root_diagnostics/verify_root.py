"""独立算术重放；--enumerate 在极小实例额外验证全部定价最优值。"""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'code'),str(ROOT/'code/dwcg'),str(ROOT/'docs/branch_and_price')]
from evidence_store import load_result
from independent_bp_verify import (oracle,verify_node,integer_witness,primal,duals,
                                  read_pool,near,require)

def verify(data,result,enumerate_all=False):
    p=result['numeric_policy'];n=result['node'];computed=[];count=0
    for row in n['certificate']['rounds']:
        if row.get('rmp_status')!='optimal':
            require(not row['complete_pricing'],'Unsolved RMP used for bound');continue
        pool=read_pool(data,[],row['pool']);phase=row['phase']
        primal(data,[],pool,row['solution'],phase,row['artificials'],p,row['objective'])
        d=duals(data,row['duals'],phase,p)
        dobj=sum(oracle.rowspec(data)[k][1]*v for k,v in d.items())
        near(dobj,row['objective'],p['bound_consistency_tolerance'])
        if not row['complete_pricing']:
            require('repaired_upper_bound' not in row,'Incomplete pricing emitted bound');continue
        seen=set();correction=0.;lines={l['id']:l for l in data['lines']}
        for e in row['pricing']:
            key=e['line'],e['station'];require(key in pool and key not in seen,'Invalid pricing coverage');seen.add(key)
            require(e['phase']==phase and e['purpose']=='pricing' and not e['fixed_variables'],'Wrong pricing domain')
            require(e['optimal'] and e['status']=='optimal' and e['solver_result']['optimal'],'Missing exact PP proof metadata')
            pattern=oracle.pattern(lines[key[0]],key[1],e['assignments'])
            rc=oracle.rc(lines[key[0]],key[1],pattern,d,phase)
            near(rc,e['reduced_cost'],p['bound_consistency_tolerance']);near(rc,e['objective'],p['bound_consistency_tolerance'])
            correction+=max(0,rc)
        require(seen==pool.keys(),'Missing station pricing')
        ub=max(dobj,row['objective'])+correction
        near(ub,row['repaired_upper_bound'],p['bound_consistency_tolerance'])
        if phase==2:computed.append(ub)
        count+=1
    near(min(computed) if computed else None,result['global_upper_bound'],p['bound_consistency_tolerance'])
    witnesses=[result['acquisition'].get('witness')]+[x['witness'] for x in result['recoveries']]
    values=[integer_witness(data,[],w,p) for w in witnesses if w]
    near(max(values) if values else None,result['global_lower_bound'],p['bound_consistency_tolerance'])
    if result['integer_incumbent_solution']:
        near(integer_witness(data,[],result['integer_incumbent_solution'],p),result['global_lower_bound'],p['bound_consistency_tolerance'])
    if result['global_integer_optimal_proven']:
        require(bool(values) and computed,'No closing bound/witness')
        require(min(computed)-max(values)<=max(p['global_absolute_tolerance'],p['global_relative_tolerance']*max(1,abs(max(values)))),'Unclosed integer gap')
    if enumerate_all:
        verify_node(data,n,oracle.enumerate_patterns(data),p)
    else:require(not result['global_infeasibility_proven'],'Infeasibility needs full oracle replay in this checker')
    return dict(passed=True,complete_rounds=count,witnesses=len(values),
                scope='full_enumeration' if enumerate_all else 'independent_arithmetic_and_witness_with_solver_PP_optimality_metadata')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('folder',type=Path);parser.add_argument('--enumerate',action='store_true')
    a=parser.parse_args();data=json.loads((a.folder/'instance.json').read_text(encoding='utf-8-sig'))
    print(json.dumps(verify(data,load_result(a.folder/'certificate.sqlite'),a.enumerate)))
