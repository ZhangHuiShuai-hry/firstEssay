"""Small-instance independent B&P oracle. Never imported by production search.

Enumeration, local arithmetic, full DW model and row vectors come from Task01's
independent oracle, not production column/pricing/master functions.
"""
from __future__ import annotations

import json
import math
import hashlib
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'docs/research_audit'),str(ROOT/'code/dwcg'),str(ROOT/'code')]
import independent_validation as oracle
import pulp
from solver_backend import make_solver,objective_value


def allowed(column,line,station,records):
    pairs=set(column.assignments)
    for e in records:
        l,i,s,m=e['variable'];b=e['value']
        if l==line and s==station and int((i,m) in pairs)!=b:return False
    return True


def node_pool(data,records,complete=None):
    complete=complete if complete is not None else oracle.enumerate_patterns(data)
    return {key:[p for p in ps if allowed(p,key[0],key[1],records)] for key,ps in complete.items()}


def full_node(data,records,integer=False,complete=None,phase=2):
    pool=node_pool(data,records,complete)
    if any(not ps for ps in pool.values()):
        return {'status':'infeasible','objective':None,'local_empty':True},None,pool
    # Assemble with the independent Task01 full model. Add generalized elastic
    # rows independently of production node_master's schema/row coefficients.
    p,variables=oracle.full_model(data,pool,integer,phase=2)
    if phase==1:
        artificial=[]
        for index,(key,(sense,rhs)) in enumerate(oracle.rowspec(data).items()):
            if key[0]=='station':continue
            for sign in ((1,-1) if sense=='=' else (-1,)):
                a=pulp.LpVariable(f'oracle_elastic_{index}_{sign}',0)
                p.constraints[f'row_{index}'].addInPlace(sign*a);artificial.append(a)
        p.setObjective(-pulp.lpSum(artificial))
    p.solve(make_solver(mip=integer,role='verification'))
    info=dict(p.backend_result)
    if not info['optimal'] and info['status']!='infeasible':
        raise RuntimeError('Independent full node not solved: '+info['status'])
    return info,(p,variables),pool


class CertificateRejected(RuntimeError):
    pass


def require(condition,message):
    if not condition:raise CertificateRejected(message)


def finite(x):
    require(not isinstance(x,bool) and isinstance(x,(int,float)) and math.isfinite(x),'Nonfinite/missing numeric certificate value')
    return x


def near(a,b,tol=1e-5):
    if a is None or b is None:
        require(a is None and b is None,'Missing/inconsistent numeric field');return
    require(abs(finite(a)-finite(b))<=tol,f'Numeric certificate mismatch {a} / {b}')


def fixes(data,records):
    known={(l['id'],t['id'],s,m) for l in data['lines'] for s in range(1,len(l['stations'])+1)
           for t in l['tasks'] for m in t['modes']}
    result={};ones=set()
    for entry in records:
        q=tuple(entry['variable']);b=entry['value']
        require(len(q)==4 and type(q[2]) is int and q in known and q not in result,'Unknown/duplicate branch coordinate')
        require(type(b) is int and b in (0,1),'Invalid branch value')
        if b:require(q[:2] not in ones,'Conflicting selected task');ones.add(q[:2])
        result[q]=b
    return result


def read_pool(data,records,snapshot):
    expected={(l['id'],s) for l in data['lines'] for s in range(1,len(l['stations'])+1)}
    lines={l['id']:l for l in data['lines']};result={}
    for entry in snapshot:
        key=entry['line'],entry['station']
        require(key in expected and key not in result,'Unknown/duplicate pool block')
        ps=[];seen=set()
        for assignments in entry['patterns']:
            try:p=oracle.pattern(lines[key[0]],key[1],assignments)
            except (AssertionError,KeyError):raise CertificateRejected('Illegal local column')
            require(allowed(p,*key,records),'Column violates branch')
            require(p.assignments not in seen,'Duplicate pool column');seen.add(p.assignments);ps.append(p)
        require(bool(ps),'Empty pool in a solved RMP');result[key]=ps
    require(set(result)==expected,'Pool does not cover all stations')
    return result


def primal(data,records,pool,solution,phase,artificials,policy,objective):
    spec=oracle.rowspec(data);lhs=dict.fromkeys(spec,0.);profit=0.;seen=set()
    lines={l['id']:l for l in data['lines']}
    for e in solution:
        key=e['line'],e['station'];index=e['column'];weight=finite(e['weight'])
        require(key in pool and type(index) is int and 0<=index<len(pool[key]),'Invalid primal column index')
        require((key,index) not in seen and weight>=-policy['primal_validation_tolerance'],'Invalid lambda')
        seen.add((key,index));p=pool[key][index]
        require(tuple(sorted(tuple(a) for a in e['assignments']))==p.assignments,'Primal assignment/index mismatch')
        profit+=weight*p.profit
        for k,a in oracle.vector(lines[key[0]],key[1],p).items():lhs[k]+=weight*a
    require(len(seen)==sum(map(len,pool.values())),'Missing lambda primal values')
    required_art={(k,s) for k,(sense,rhs) in spec.items() if k[0]!='station'
                  for s in ((1,-1) if sense=='=' else (-1,))} if phase==1 else set()
    actual=set();total=0.
    for e in artificials:
        key,sign=tuple(e['row']),e['sign'];value=finite(e['value'])
        require((key,sign) in required_art and (key,sign) not in actual and value>=-policy['primal_validation_tolerance'],'Invalid/missing elastic artificial')
        actual.add((key,sign));total+=value;lhs[key]+=sign*value
    require(actual==required_art,'Elastic row coverage incomplete')
    for k,(sense,rhs) in spec.items():
        ok=abs(lhs[k]-rhs)<=policy['primal_validation_tolerance'] if sense=='=' else lhs[k]<=rhs+policy['primal_validation_tolerance']
        require(ok,f'Primal violates global/convexity row {k}')
    near(objective,-total if phase==1 else profit,policy['bound_consistency_tolerance'])
    return total


def duals(data,entries,phase,policy):
    spec=oracle.rowspec(data);d={}
    for e in entries:
        k=tuple(e['row']);v=finite(e['value'])
        require(k in spec and k not in d,'Invalid/duplicate dual row');d[k]=v
        if spec[k][0]=='<=':require(v>=0,'Effective dual sign is invalid')
        if phase==1 and k[0]!='station':
            require(v<=1 and (spec[k][0]!='=' or v>=-1),'Artificial dual inequality invalid')
    require(d.keys()==spec.keys(),'Dual coverage incomplete')
    return d


def verify_node(data,n,complete,policy,solve_oracles=True):
    records=n['restrictions'];fixes(data,records)
    legal=node_pool(data,records,complete);nr=n.get('node_result');cert=n.get('certificate')
    full_lp=full_ip=None
    if solve_oracles:
        full_lp,_,_=full_node(data,records,complete=complete)
        full_ip,_,_=full_node(data,records,integer=True,complete=complete)
    if nr is None:
        require(n['node_status'] in ('open','pruned_bound','unresolved_solver_error'),'Missing node solve certificate')
        return {'node_id':n['node_id'],'rounds':0,'full_lp':full_lp,'full_ip':full_ip}
    require(cert and cert['restrictions']==records,'Node certificate restrictions mismatch')
    if cert['rounds']:
        initial=read_pool(data,records,cert['initial_pool'])
        first=read_pool(data,records,cert['rounds'][0]['pool'])
        require(initial==first,'Initial pool differs from first RMP')
        init_keys=set()
        for e in cert['initialization']:
            key=e['line'],e['station']
            require(key in initial and key not in init_keys,'Initialization block coverage invalid');init_keys.add(key)
            require(0<=e['legal_inherited_count']<=e['inherited_count'],'Invalid inherited column counts')
            count=e['legal_inherited_count']
            if count==0:
                pp=e.get('feasibility',{})
                require(pp.get('optimal') is True and pp.get('status')=='optimal' and pp.get('purpose')=='local_feasibility','Local seed not proven feasible')
                require(pp.get('solver_result',{}).get('optimal') is True,'Local seed solver status unproven')
                if 'fixed_variables' in pp:
                    expected=[{'task':i,'mode':m,'value':b} for (l,i,s,m),b in sorted(fixes(data,records).items()) if (l,s)==key]
                    require(pp['fixed_variables']==expected,'Local initialization domain metadata mismatch')
                require(len(initial[key])==1 and initial[key][0].assignments==tuple(sorted(tuple(a) for a in pp['assignments'])),'Local seed differs from initial pool')
            else:require(len(initial[key])==count,'Inherited legal column count mismatch')
        require(init_keys==initial.keys(),'Initialization did not cover all blocks')
    computed=[];last=None;last_pool=None;count=0
    for record in cert['rounds']:
        pool=read_pool(data,records,record['pool'])
        if last_pool is not None:
            expected={k:[p.assignments for p in ps] for k,ps in last_pool.items()}
            for e in last.get('columns_added',[]):expected[e['line'],e['station']].append(tuple(tuple(a) for a in e['assignments']))
            require(expected=={k:[p.assignments for p in ps] for k,ps in pool.items()},'Node pool evolution mismatch')
        last,last_pool=record,pool
        if record.get('rmp_status')!='optimal':
            require(not record['complete_pricing'] and 'repaired_upper_bound' not in record,'Unproven RMP has a bound')
            continue
        require(record['rmp_solver_result']['optimal'] is True,'RMP optimal status unproven')
        phase=record['phase'];require(phase in (1,2),'Invalid phase')
        artificial_sum=primal(data,records,pool,record['solution'],phase,record['artificials'],policy,record['objective'])
        if phase==1:near(artificial_sum,record['artificial_sum'],policy['bound_consistency_tolerance'])
        d=duals(data,record['duals'],phase,policy)
        raw={tuple(e['row']):finite(e['value']) for e in record['raw_duals']}
        require(raw.keys()==d.keys() and len(raw)==len(record['raw_duals']),'Raw dual coverage invalid')
        for k,v in raw.items():
            lo=0. if oracle.rowspec(data)[k][0]=='<=' else -math.inf;hi=math.inf
            if phase==1 and k[0]!='station':
                hi=1.
                if oracle.rowspec(data)[k][0]=='=':lo=-1.
            require(v>=lo-policy['lp_dual_tolerance'] and v<=hi+policy['lp_dual_tolerance'],'Raw dual outside repair tolerance')
            near(d[k],min(hi,max(lo,v)),1e-12)
        dobj=sum(oracle.rowspec(data)[k][1]*v for k,v in d.items())
        near(dobj,record['dual_objective'],policy['bound_consistency_tolerance'])
        near(dobj,record['objective'],policy['bound_consistency_tolerance'])
        if record.get('event')=='attempt_phase2_without_artificials':
            require(phase==1 and artificial_sum<=policy['artificial_tolerance'] and not record['pricing'],'Invalid Phase I transition')
        if not record['complete_pricing']:
            require('repaired_upper_bound' not in record,'Incomplete pricing has a bound')
            continue
        require(all(legal.values()),'Complete pricing on empty allowed domain')
        maxima={};lines={l['id']:l for l in data['lines']}
        for e in record['pricing']:
            key=e['line'],e['station']
            require(key in legal and key not in maxima,'Pricing coverage duplicated/unknown')
            require(e['status']=='optimal' and e['optimal'] is True and e['solver_result'].get('optimal') is True,'Unproven pricing used for node bound')
            require(e['phase']==phase and e['purpose']=='pricing','Pricing phase/purpose mismatch')
            if 'fixed_variables' in e:
                expected=[{'task':i,'mode':m,'value':b} for (l,i,s,m),b in sorted(fixes(data,records).items()) if (l,s)==key]
                require(e['fixed_variables']==expected,'Pricing fixed-variable domain mismatch')
            rho=max(oracle.rc(lines[key[0]],key[1],p,d,phase) for p in legal[key])
            try:p=oracle.pattern(lines[key[0]],key[1],e['assignments'])
            except (AssertionError,KeyError):raise CertificateRejected('Pricing incumbent locally illegal')
            require(allowed(p,*key,records),'Pricing incumbent violates branch')
            near(oracle.rc(lines[key[0]],key[1],p,d,phase),rho,policy['bound_consistency_tolerance'])
            near(e['reduced_cost'],rho,policy['bound_consistency_tolerance']);near(e['objective'],rho,policy['bound_consistency_tolerance'])
            maxima[key]=rho
        require(maxima.keys()==legal.keys(),'Complete pricing flag with missing blocks')
        correction=sum(max(0.,v) for v in maxima.values());upper=max(dobj,record['objective'])+correction
        near(upper,record['repaired_upper_bound'],policy['bound_consistency_tolerance'])
        near(record['objective']+correction,record['rmp_formula_upper_bound'],policy['bound_consistency_tolerance'])
        near(max(maxima.values()),record['maximum_reduced_cost'],policy['bound_consistency_tolerance'])
        if phase==2:computed.append(upper)
        for e in record['columns_added']:
            key=e['line'],e['station'];p=oracle.pattern(lines[key[0]],key[1],e['assignments'])
            require(allowed(p,*key,records) and oracle.rc(lines[key[0]],key[1],p,d,phase)>policy['reduced_cost_epsilon'],'Nonpositive/illegal added column')
        count+=1
    near(nr['lp_upper_bound'],min(computed) if computed else None,policy['bound_consistency_tolerance'])
    if solve_oracles and computed and full_lp['status']=='optimal':
        require(min(computed)>=full_lp['objective']-policy['bound_consistency_tolerance'],'Node bound below full node LP')
    if nr['status']=='local_infeasible_proven':
        empty={k for k,ps in legal.items() if not ps};require(bool(empty),'False local infeasibility pruning')
        proofs=[e for e in cert['initialization'] if e.get('feasibility',{}).get('status')=='infeasible']
        require(any((e['line'],e['station']) in empty and e['feasibility']['solver_result']['status']=='infeasible' for e in proofs),'Missing local infeasibility solve')
    elif nr['status']=='phase1_infeasible_proven':
        require(last is not None and last['phase']==1 and last['complete_pricing'],'Missing complete Phase I termination')
        require(last['repaired_upper_bound'] < -policy['artificial_tolerance'],'Phase I bound not strictly negative')
        require(last['maximum_reduced_cost']<=policy['reduced_cost_epsilon']+1e-9,'Phase I pricing did not converge')
        if solve_oracles:require(full_lp['status']=='infeasible','Full node LP contradicts Phase I pruning')
    elif nr['status']=='node_lp_optimal_proven':
        require(last is not None and last['phase']==2 and last['complete_pricing'],'Missing complete Phase II termination')
        require(last['maximum_reduced_cost']<=policy['reduced_cost_epsilon']+1e-9,'Phase II pricing did not converge')
        require(cert['phase1_status']=='feasible_real_RMP_confirmed','Missing real Phase II feasibility confirmation')
        near(nr['lp_objective'],last['objective'],policy['bound_consistency_tolerance'])
        require(nr['lp_solution']==last['solution'],'Final primal not equal to last RMP solution')
        expected={(l['id'],t['id'],s,m):0. for l in data['lines'] for s in range(1,len(l['stations'])+1) for t in l['tasks'] for m in t['modes']}
        for e in nr['lp_solution']:
            for i,m in e['assignments']:expected[e['line'],i,e['station'],m]+=e['weight']
        actual={tuple(e['variable']):finite(e['value']) for e in nr['x_values']}
        require(actual.keys()==expected.keys() and len(actual)==len(nr['x_values']),'Recovered x coverage invalid')
        for q,value in actual.items():near(value,expected[q],policy['primal_validation_tolerance'])
        if solve_oracles:
            require(full_lp['optimal'],'Node CG says feasible but full node LP infeasible')
            near(full_lp['objective'],nr['lp_objective'],max(policy['bound_consistency_tolerance'],len(legal)*policy['reduced_cost_epsilon']))
    return {'node_id':n['node_id'],'rounds':count,'full_lp':full_lp,'full_ip':full_ip}


def integer_witness(data,records,witness,policy):
    entries=[];seen=set();profit=0.;lines={l['id']:l for l in data['lines']}
    for e in witness['stations']:
        key=e['line'],e['station'];require(key not in seen,'Duplicate integer station');seen.add(key)
        try:p=oracle.pattern(lines[key[0]],key[1],e['assignments'])
        except (AssertionError,KeyError):raise CertificateRejected('Integer local feasibility failed')
        require(allowed(p,*key,records),'Integer witness violates node branch')
        for name in ('active','human','robot','duration','fatigue','recovery','profit'):near(e[name],getattr(p,name),policy['bound_consistency_tolerance'])
        profit+=p.profit;entries.append({'line':key[0],'station':key[1],'assignments':p.assignments,'weight':1.})
    require(seen=={(l['id'],s) for l in data['lines'] for s in range(1,len(l['stations'])+1)},'Incomplete integer station witness')
    try:oracle.witness(data,entries,profit)
    except AssertionError:raise CertificateRejected('Integer global coupling/profit feasibility failed')
    near(profit,witness['objective'],policy['bound_consistency_tolerance'])
    return witness['objective']


def verify_tree(data,result,*,solve_oracles=True):
    policy=result['numeric_policy'];tol=policy['bound_consistency_tolerance']
    require(result['status'] in ('optimal_within_tolerance','infeasible_proven','time_limit','node_limit','numerical_uncertain','solver_error'),'Unknown global status')
    digest=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    require(result['input_sha256']==digest,'Saved instance hash mismatch')
    allowance=lambda v:max(policy['global_absolute_tolerance'],policy['global_relative_tolerance']*max(1.,abs(v)))
    complete=oracle.enumerate_patterns(data)
    history=result['node_history'];nodes={n['node_id']:n for n in history}
    require(len(nodes)==len(history) and set(nodes)==set(range(len(nodes))),'Node IDs missing/duplicated')
    require(nodes[0]['parent_id'] is None and not nodes[0]['restrictions'] and nodes[0]['inherited_upper_bound'] is None,'Invalid root')
    checked=[]
    for n in history:
        r=fixes(data,n['restrictions'])
        if n['node_id']:
            p=nodes[n['parent_id']];parent=fixes(data,p['restrictions']);q=tuple(n['branching_variable'])
            require(n['node_id'] in p['children'] and p['node_status']=='branched','Orphan child')
            require(len(r)==len(parent)+1 and all(r.get(k)==v for k,v in parent.items()) and r.get(q)==n['branching_value'],'Parent-child fixed domain inconsistent')
            near(n['inherited_upper_bound'],p['safe_upper_bound'],tol)
        checked.append(verify_node(data,n,complete,policy,solve_oracles))
        computed=n.get('node_result',{}).get('lp_upper_bound')
        near(computed,n['node_lp_upper_bound'],tol)
        known=[v for v in (n['inherited_upper_bound'],computed) if v is not None]
        near(n['safe_upper_bound'],min(known) if known else None,tol)
    stack=[0];best=None;best_witness=None;best_node=None;visited=[]
    for node_id in result['processing_order']:
        require(stack and stack.pop()==node_id,'DFS coverage/order inconsistent')
        n=nodes[node_id];require(node_id not in visited,'Node processed twice');visited.append(node_id)
        near(n['lower_bound_before'],best,tol)
        status=n['node_status'];safe=n['safe_upper_bound'];nr=n.get('node_result',{})
        if status=='branched':
            require(nr.get('status')=='node_lp_optimal_proven','Branching without solved node LP')
            fixed=fixes(data,n['restrictions']);candidates=[]
            for e in nr['x_values']:
                q=tuple(e['variable']);x=e['value'];eps=policy['branch_integrality_tolerance']
                if eps<x<1-eps:
                    require(q not in fixed,'Fixed variable fractional')
                    candidates.append((abs(x-.5),(q[0],q[2],q[1],q[3]),q,x))
            require(bool(candidates),'Branched without fractional original x')
            _,_,q,x=min(candidates)
            require(n['branch_decision']['variable']==list(q),'Not most-fractional deterministic branching')
            near(n['branch_decision']['lp_value'],x,tol)
            children=n['children'];require(len(children)==2 and nodes[children[0]]['branching_value']==0 and nodes[children[1]]['branching_value']==1,'Missing/disjoint branches')
            require(all(nodes[c]['branching_variable']==list(q) for c in children),'Child branch variables mismatch')
            stack.extend(reversed(children))
        elif status in ('pruned_local_infeasible','pruned_phase1_infeasible'):
            require(nr.get('status') in ('local_infeasible_proven','phase1_infeasible_proven'),'Infeasible pruning without proof')
        elif status=='pruned_bound':
            require(best is not None and safe is not None and safe<=best+allowance(best),'Unsafe upper-bound prune')
            near(n['pruning']['integer_lower_bound'],best,tol);near(n['pruning']['upper_bound'],safe,tol)
        elif status=='pruned_integer':
            require(nr.get('status')=='node_lp_optimal_proven','Integer leaf lacks node LP proof')
            for e in nr['x_values']:require(abs(e['value']-round(e['value']))<=policy['branch_integrality_tolerance'],'Integer leaf has fractional x')
            value=integer_witness(data,n['restrictions'],n['integer_witness'],policy)
            near(value,nr['lp_objective'],tol)
            require(safe is not None and value<=safe+tol and safe<=value+allowance(value),'Integer leaf did not close upper bound')
            if best is None or value>best:require('incumbent_update' in n,'Missing incumbent update')
        elif status.startswith('unresolved_'):
            require(node_id==result['processing_order'][-1],'Search continued after unresolved node')
            stack.append(node_id)
        else:raise CertificateRejected('Invalid processed node status')
        if 'incumbent_update' in n:
            value=integer_witness(data,n['restrictions'],n['incumbent_update']['solution'],policy)
            require(best is None or value>best,'Incumbent update did not improve verified lower bound')
            best=value;best_witness=n['incumbent_update']['solution'];best_node=node_id
            near(n['incumbent_update']['objective'],best,tol)
        near(n['lower_bound_after'],best,tol)
    active={i for i,n in nodes.items() if n['node_status']=='open' or n['node_status'].startswith('unresolved_')}
    require(set(stack)==active and len(stack)==len(active),'Lost/duplicated unresolved nodes')
    require({e['node_id'] for e in result['open_nodes']}==active and len(result['open_nodes'])==len(active),'Open-node certificate mismatch')
    for e in result['open_nodes']:near(e['safe_upper_bound'],nodes[e['node_id']]['safe_upper_bound'],tol)
    near(result['global_lower_bound'],best,tol);near(result['integer_incumbent_objective'],best,tol)
    require(result['has_integer_incumbent']==(best is not None),'Incumbent existence flag inconsistent')
    if best is not None:
        near(integer_witness(data,[],result['integer_incumbent_solution'],policy),best,tol)
    terminal=[n for n in history if n['node_status'] in ('pruned_integer','pruned_bound')]
    frontier=[nodes[i] for i in active]+terminal
    upper=None if any(n['safe_upper_bound'] is None for n in frontier) else max([n['safe_upper_bound'] for n in frontier],default=best)
    if upper is not None and best is not None:
        require(upper>=best-tol,'Upper/lower bounds inconsistent');upper=max(upper,best)
    near(result['global_upper_bound'],upper,tol)
    near(result['absolute_gap'],None if upper is None or best is None else upper-best,tol)
    near(result['relative_gap'],None if upper is None or best is None else max(0.,upper-best)/max(1.,abs(best)),tol)
    proven=result['status']=='optimal_within_tolerance'
    infeasible=result['status']=='infeasible_proven'
    require(result['global_integer_optimal_proven']==proven and result['global_infeasibility_proven']==infeasible,'Global proof flags inconsistent')
    if proven:require(not active and best is not None and upper is not None and upper-best<=allowance(best),'False global optimum')
    if infeasible:
        require(not active and best is None and all(n['node_status']=='branched' or n['node_status'] in ('pruned_local_infeasible','pruned_phase1_infeasible') for n in history),'False global infeasibility')
    require(result['total_nodes_created']==len(nodes) and result['total_nodes_processed']==len(visited),'Node counts inconsistent')
    require(result['total_nodes_pruned']==sum(n['node_status'].startswith('pruned_') for n in history),'Pruned count inconsistent')
    require(result['total_pricing_calls']==sum(n.get('pricing_calls',0) for n in history),'Pricing counts inconsistent')
    root=nodes[0].get('node_result',{})
    require(result['root_lp_status']==root.get('status','not_run'),'Root LP status mismatch')
    near(result['root_lp_objective'],root.get('lp_objective'),tol);near(result['root_lp_upper_bound'],root.get('lp_upper_bound'),tol)
    if solve_oracles:
        ip,_,_=full_node(data,[],integer=True,complete=complete)
        if proven:require(ip['optimal'],'Full-IP contradicts B&P incumbent');near(ip['objective'],best,tol)
        if infeasible:require(ip['status']=='infeasible','Full-IP contradicts B&P infeasibility')
    return {'passed':True,'scope':'independent_enumerated_node_domains_and_full_LP_IP' if solve_oracles else 'offline_enumerated_node_primal_dual_and_tree_proof',
            'nodes_checked':len(nodes),'rounds_checked':sum(n['rounds'] for n in checked),'node_oracles':checked,
            'global_conclusion_verified':proven or infeasible,'unresolved_nodes_verified':len(active)}


def main():
    import argparse
    from solver_backend import BackendConfig,use_backend
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--instance',type=Path,required=True);p.add_argument('--result',type=Path,required=True)
    p.add_argument('--solver',choices=('cbc','cplex_py'),default='cbc');p.add_argument('--offline',action='store_true');p.add_argument('--output',type=Path)
    args=p.parse_args();data=json.loads(args.instance.read_text(encoding='utf-8-sig'));result=json.loads(args.result.read_text(encoding='utf-8-sig'))
    if args.output and args.output.exists():raise FileExistsError(args.output)
    with use_backend(BackendConfig(name=args.solver)):
        report=verify_tree(data,result,solve_oracles=not args.offline)
    rendered=json.dumps(report,indent=2,allow_nan=False)
    if args.output:args.output.write_text(rendered,encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='node_oracles'},indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
