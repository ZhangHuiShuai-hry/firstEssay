"""独立枚举资源档与独立整数主问题核验DP，不调用生产DP。"""
import sys,math
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'stage4')]
from validate import enumerate_all,solve_full,check_column,check_witness,close
from bp_verify import legal

def audit(data,r,enumerate_profiles=True):
    full=enumerate_all(data) if enumerate_profiles else None
    low={};upper={};unknown={};filtered={}
    assert set(r['table'])=={l['id'] for l in data['lines']}
    for line in data['lines']:
        l=line['id'];entries=r['table'][l]
        expected={(h,robot) for h in range(min(len(line['stations']),data['human_limit'])+1) for robot in range(min(len(line['stations']),data['robot_limit'])+1)}
        assert len(entries)==len(expected) and {(e['human'],e['robot']) for e in entries}==expected
        low[l]=[];upper[l]=[];unknown[l]=[]
        if full is not None:filtered[l]=[c for c in full[l] if legal(c,r['restrictions'])]
        for e in entries:
            c=e['column'];cert=e['certificate'];h,robot=e['human'],e['robot']
            if c:
                check_column(line,c);assert c['human']==h and c['robot']==robot and legal(c,r['restrictions']);low[l].append(c)
            if cert:
                assert cert['profile']==[h,robot] and cert['restrictions']==r['restrictions']
                assert cert['column']==c and cert['status']==e['status'] and cert['phase']==2
                assert cert['human_price']==cert['robot_price']==cert['sigma']==0
                if cert['optimal']:assert c and cert['solver']['optimal'];close(e['upper_bound'],c['profit'])
                elif e['status']!='infeasible':assert e['upper_bound']==cert['solver'].get('best_bound') or e['upper_bound'] is None
            else:assert e['status']=='not_run' and c is None and e['upper_bound'] is None
            if full is not None:
                candidates=[p for p in filtered[l] if p['human']==h and p['robot']==robot]
                if e['status']=='infeasible':assert not candidates
                if cert and cert['optimal']:assert candidates;close(c['profit'],max(p['profit'] for p in candidates))
                if e['upper_bound'] is not None and candidates:assert e['upper_bound']>=max(p['profit'] for p in candidates)-1e-5
            if e['status']!='infeasible':
                upper[l].append(dict(human=h,robot=robot,profit=e['upper_bound'] or 0))
                unknown[l].append(dict(human=h,robot=robot,profit=int(e['upper_bound'] is None)))
    low_result=solve_full(data,low,True);unknown_result=solve_full(data,unknown,True)
    lb=low_result['objective'] if low_result['optimal'] else None
    if unknown_result['status']=='infeasible':ub=None;possible=False
    else:
        possible=True
        ub=None if unknown_result['objective']>.5 else solve_full(data,upper,True)['objective']
    assert r['upper_dp']['feasible']==possible
    if lb is None:assert r['global_lower_bound'] is None
    else:close(lb,r['global_lower_bound']);check_witness(data,r['witness'],lb)
    if ub is None:assert r['global_upper_bound'] is None
    else:close(ub,r['global_upper_bound'])
    if r['global_integer_optimal_proven']:
        assert lb is not None and ub is not None and ub-lb<=max(r['policy']['global_absolute_tolerance'],r['policy']['global_relative_tolerance']*max(1,abs(lb)))+1e-8
    if r['global_infeasibility_proven']:assert not possible and lb is None
    oracle=solve_full(data,filtered,True) if full is not None else None
    if oracle and r['global_integer_optimal_proven']:assert oracle['optimal'];close(lb,oracle['objective'])
    if oracle and r['global_infeasibility_proven']:assert oracle['status']=='infeasible'
    return dict(status='PASS',scope='independent_profiles_and_IP' if full else 'native_profiles_and_independent_IP',oracle=oracle)
