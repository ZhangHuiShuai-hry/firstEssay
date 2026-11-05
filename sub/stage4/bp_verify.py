"""独立完整列节点Oracle与树证书核验。不调用生产节点PP生成期望值。"""
import json,sys,zlib,math
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'stage2')]
from validate import enumerate_all,solve_full,check_witness,close,signature
from stage2_verify import audit as arithmetic_audit

def legal(column,fixes):
    selected={(column['stations'][0]['line'],i,s['station'],m) for s in column['stations'] for i,m in s['assignments']}
    return all(int(tuple(f['variable']) in selected)==f['value'] for f in fixes
               if f['variable'][0]==column['stations'][0]['line'])

def node_audit(data,r,*,enumerate_pricing=True):
    arithmetic_audit(data,r,enumerate_pricing=False)
    fixes=r['restrictions'];full=enumerate_all(data) if enumerate_pricing else None
    filtered={l:[c for c in cols if legal(c,fixes)] for l,cols in full.items()} if full is not None else None
    for l,cols in r['pool'].items():assert all(legal(c,fixes) for c in cols)
    for h in r['history']:
        m=h['rmp']
        if not m['solver']['optimal']:continue
        if 'dual_repair' not in m:continue # 初版保守停止证据仍可重放。
        repair=m['dual_repair'];before=repair['before'];after=m['duals']
        close(repair['before_objective'],sum(before['convexity'].values())+sum(data[k+'_limit']*before[k] for k in ('human','robot')))
        for k in ('human','robot'):close(before[k],after[k])
        for l,size in m['pool_sizes'].items():
            violation=max((c['profit'] if h['phase']==2 else 0)-before['human']*c['human']-before['robot']*c['robot']-before['convexity'][l] for c in r['pool'][l][:size])
            expected=math.nextafter(before['convexity'][l]+violation,math.inf) if violation>0 else before['convexity'][l]
            close(after['convexity'][l],expected,1e-10)
            close(repair['shifts'][l],expected-before['convexity'][l],1e-10)
    certs=r['initialization_fallback']+[c for h in r['history'] for c in h['pricing']]
    for c in certs:
        assert c['restrictions']==fixes
        if c['column']:assert legal(c['column'],fixes)
        if filtered is not None:
            candidates=filtered[c['line']]
            if c['status']=='infeasible':assert not candidates
            if c['optimal']:
                assert candidates
                close(c['reduced_cost'],max((p['profit'] if c['phase']==2 else 0)
                    -c['human_price']*p['human']-c['robot_price']*p['robot']-c['sigma'] for p in candidates))
    if r['lp_optimal_proven']:
        last=r['history'][-1]
        assert last['phase']==2 and last['complete_exact_pricing']
        assert max(c['reduced_cost'] for c in last['pricing'])<=r['policy']['reduced_cost_epsilon']+1e-8
        assert r['solution']==last['rmp']['solution'];close(r['lp_objective'],last['rmp']['objective'])
        x={(l['id'],t['id'],s,m):0. for l in data['lines'] for t in l['tasks']
           for s in range(1,len(l['stations'])+1) for m in t['modes']}
        for e in r['solution']:
            for s in r['pool'][e['line']][e['column']]['stations']:
                for i,m in s['assignments']:x[e['line'],i,s['station'],m]+=e['weight']
        assert len(r['x_values'])==len(x)
        assert {tuple(e['variable']) for e in r['x_values']}==set(x)
        for e in r['x_values']:close(e['value'],x[tuple(e['variable'])])
    oracle={}
    if filtered is not None:
        for name,integer in [('LP',False),('IP',True)]:oracle[name]=solve_full(data,filtered,integer)
        if r['lp_optimal_proven']:
            assert oracle['LP']['optimal'];close(r['lp_objective'],oracle['LP']['objective'])
        if r['global_infeasibility_proven']:assert oracle['LP']['status']=='infeasible'
        if r['upper_bound'] is not None and oracle['LP']['optimal']:assert r['upper_bound']>=oracle['LP']['objective']-1e-5
    return dict(status='PASS',oracle=oracle)

def audit(data,r,*,enumerate_pricing=True):
    nodes=r['node_history'];assert [n['node_id'] for n in nodes]==list(range(len(nodes)))
    assert nodes and nodes[0]['parent_id'] is None and nodes[0]['restrictions']==[] and nodes[0]['inherited_upper_bound'] is None
    child_ids=[];checked=[];terminal=[];opens=[]
    for n in nodes:
        i=n['node_id'];parent=n['parent_id'];fix=n['restrictions']
        assert len({tuple(f['variable']) for f in fix})==len(fix)
        if parent is not None:
            p=nodes[parent];assert i in p['children'];assert n['depth']==p['depth']+1
            assert n['inherited_upper_bound']==p['safe_upper_bound']
            f=n['branch_from_parent'];assert f['variable']==p['branching_variable']['variable']
            expected=p['restrictions']+[f]
            assert sorted(fix,key=lambda f:str(f['variable']))==sorted(expected,key=lambda f:str(f['variable']))
        nr=n['result'];computed=n['inherited_upper_bound']
        if nr:
            assert nr['restrictions']==fix;checked.append(node_audit(data,nr,enumerate_pricing=enumerate_pricing))
            assert n['node_lp_upper_bound']==nr['upper_bound']
            if nr['upper_bound'] is not None:computed=nr['upper_bound'] if computed is None else min(computed,nr['upper_bound'])
        else:assert n['node_lp_upper_bound'] is None
        assert n['safe_upper_bound']==computed
        status=n['status']
        if status=='branched':
            assert nr and nr['lp_optimal_proven'] and len(n['children'])==2
            assert [nodes[c]['branch_from_parent']['value'] for c in n['children']]==[0,1]
            child_ids+=n['children'];variable=n['branching_variable']['variable']
            value=next(e['value'] for e in nr['x_values'] if e['variable']==variable)
            close(value,n['branching_variable']['lp_value'])
            assert r['policy']['branch_integrality_tolerance']<value<1-r['policy']['branch_integrality_tolerance']
        else:assert not n['children']
        if status=='infeasible_pruned':assert nr and nr['global_infeasibility_proven']
        elif status in ('bound_pruned','integral_pruned'):
            w=n['prune_witness'];check_witness(data,w,n['prune_lower_bound'])
            assert computed is not None and computed<=w['objective']+max(r['policy']['global_absolute_tolerance'],r['policy']['global_relative_tolerance']*max(1,abs(w['objective'])))+1e-8
            terminal.append(computed)
            if status=='integral_pruned':
                assert nr and nr['lp_optimal_proven'];close(w['objective'],nr['lp_objective'])
                assert all(legal(dict(stations=[s for s in w['stations'] if s['line']==l['id']]),fix) for l in data['lines'])
        elif status in ('pending','processing','unresolved'):
            opens.append(dict(node_id=i,restrictions=fix,upper_bound=computed));terminal.append(computed)
        elif status!='branched':raise AssertionError('Unknown node status')
    assert sorted(child_ids)==list(range(1,len(nodes)))
    assert opens==r['open_nodes']
    lb=r['global_lower_bound']
    if lb is not None:check_witness(data,r['witness'],lb);terminal.append(lb)
    else:assert r['witness'] is None
    ub=None if not terminal or any(b is None for b in terminal) else max(terminal)
    assert ub==r['global_upper_bound']
    if lb is not None and ub is not None:close(ub-lb,r['absolute_gap'])
    if r['global_integer_optimal_proven']:
        assert not opens and lb is not None and ub is not None
        assert ub-lb<=max(r['policy']['global_absolute_tolerance'],r['policy']['global_relative_tolerance']*max(1,abs(lb)))+1e-8
        assert r['status']=='optimal_within_tolerance'
    if r['global_infeasibility_proven']:
        assert not opens and lb is None and all(n['status'] in ('branched','infeasible_pruned') for n in nodes)
    full_results={}
    if enumerate_pricing:
        full=enumerate_all(data)
        full_results={name:solve_full(data,full,integer) for name,integer in [('LP',False),('IP',True)]}
        if r['global_integer_optimal_proven']:assert full_results['IP']['optimal'];close(lb,full_results['IP']['objective'])
        if r['global_infeasibility_proven']:assert full_results['IP']['status']=='infeasible'
    return dict(status='PASS',scope='complete_enumeration_and_tree' if enumerate_pricing else 'arithmetic_tree_native_status',
                nodes=len(nodes),node_results=checked,full=full_results)

if __name__=='__main__':
    path=Path(sys.argv[1]);d=json.loads((path/'instance.json').read_bytes());r=json.loads(zlib.decompress((path/'result.json.zlib').read_bytes()))
    print(json.dumps(audit(d,r,enumerate_pricing='--no-enumeration' not in sys.argv)))
