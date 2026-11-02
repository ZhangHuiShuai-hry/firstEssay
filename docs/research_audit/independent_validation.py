"""Task01 independent finite oracle and certificate audit; no production builders
are used to enumerate patterns, assemble the full DW model, or compute row vectors.
Production modules are imported only as systems under test. Run from any cwd.
"""
from __future__ import annotations
import argparse
import copy
from dataclasses import dataclass, asdict
import hashlib
import itertools
import json
import math
from pathlib import Path
import random
import sys
import time
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'code/dwcg'), str(ROOT/'code'), str(ROOT/'experiments')]
import pulp
import common
import master as production_master
import pricing
import solve as cg
from solver_backend import BackendConfig, use_backend, make_solver, objective_value

TOL = 1e-5

def close(a, b):
    assert math.isfinite(a) and math.isfinite(b) and abs(a-b) <= TOL, (a, b)

@dataclass(frozen=True)
class Pattern:
    assignments: tuple
    active: int
    human: int
    robot: int
    duration: float
    fatigue: float
    recovery: float
    profit: float

def pattern(line, s, assignments):
    """Independent arithmetic and local predicate, including exact OR flags."""
    task = {t['id']: t for t in line['tasks']}
    a = tuple(sorted(tuple(x) for x in assignments))
    assert len({i for i, m in a}) == len(a)
    assert all(i in task and m in task[i]['modes'] for i,m in a)
    h = int(any(m != 'R' for i,m in a))
    r = int(any(m != 'H' for i,m in a))
    u = int(len(a) > 0)
    duration = sum(task[i]['modes'][m]['time'] for i,m in a)
    load = sum(task[i]['modes'][m]['time']*task[i]['modes'][m]['beta'] for i,m in a)
    assert duration <= line['cycle_time']*u+1e-10
    assert load <= -math.log(1-line['fatigue_limit'])*h+1e-10
    costs = line['stations'][s-1]
    profit = sum(task[i]['value']-task[i]['modes'][m]['cost'] for i,m in a)
    profit -= costs['fixed_cost']*u + costs['human_cost']*h + costs['robot_cost']*r
    return Pattern(a,u,h,r,duration,load,sum(task[i].get('weight',0) for i,m in a),profit)

def enumerate_patterns(data):
    result = {}
    for line in data['lines']:
        options = [[None]+[(t['id'],m) for m in t['modes']] for t in line['tasks']]
        assert math.prod(map(len,options)) <= 100000
        for s in range(1,len(line['stations'])+1):
            columns = []
            for choice in itertools.product(*options):
                try: columns.append(pattern(line,s,[a for a in choice if a is not None]))
                except AssertionError: continue
            result[line['id'],s] = columns
    return result

def rowspec(data):
    rows = {}
    for line in data['lines']:
        l = line['id']
        for s in range(1,len(line['stations'])+1): rows['station',l,s] = ('=',1)
        for t in line['tasks']:
            rows['task',l,t['id']] = ('=' if t['id'] in line.get('required_tasks',[]) else '<=',1)
        for e,edge in enumerate(line.get('precedence',[])):
            for k in range(1,len(line['stations'])+1): rows['precedence',l,e,k] = ('<=',0)
        rows['recovery',l] = ('<=',-line.get('min_recovery',0))
    rows['human',] = ('<=',data['human_limit'])
    rows['robot',] = ('<=',data['robot_limit'])
    return rows

def vector(line, s, p):
    present = {i for i,m in p.assignments}
    v = {('station',line['id'],s):1, ('human',):p.human, ('robot',):p.robot,
         ('recovery',line['id']):-p.recovery}
    for t in line['tasks']: v['task',line['id'],t['id']] = int(t['id'] in present)
    for e,(i,j) in enumerate(line.get('precedence',[])):
        for k in range(1,len(line['stations'])+1):
            v['precedence',line['id'],e,k] = (int(j in present)-int(i in present)) if s<=k else 0
    return {k:x for k,x in v.items() if x != 0}

def rc(line, s, p, duals, phase):
    return (p.profit if phase==2 else 0)-sum(duals[k]*a for k,a in vector(line,s,p).items())

def full_model(data, pool, integer=False, phase=2):
    problem = pulp.LpProblem('independent_full_DW',pulp.LpMaximize)
    variables = {(l,s,i):pulp.LpVariable(f'w_{b}_{i}',0,cat='Binary' if integer else 'Continuous')
                 for b,((l,s),ps) in enumerate(pool.items()) for i,p in enumerate(ps)}
    expressions = {k:pulp.LpAffineExpression() for k in rowspec(data)}
    profit = pulp.LpAffineExpression()
    lines = {l['id']:l for l in data['lines']}
    for (l,s,i),v in variables.items():
        p = pool[l,s][i]
        profit += p.profit*v
        for key,a in vector(lines[l],s,p).items(): expressions[key] += a*v
    arts = []
    for n,(k,(sense,rhs)) in enumerate(rowspec(data).items()):
        if phase==1 and (k[0]=='recovery' or (k[0]=='task' and sense=='=')):
            art=pulp.LpVariable(f'audit_art_{n}',0); arts.append(art)
            expressions[k] += (-art if k[0]=='recovery' else art)
        problem += (expressions[k]==rhs if sense=='=' else expressions[k]<=rhs), f'row_{n}'
    problem += profit if phase==2 else -pulp.lpSum(arts)
    return problem,variables

def solve_problem(problem, mip):
    problem.solve(make_solver(mip=mip,role='verification'))
    info = dict(problem.backend_result)
    assert info['optimal'] or info['status']=='infeasible', info
    return info

def witness(data, entries, expected, phase=2, artificials=None):
    """Check primal feasibility without any PuLP constraints."""
    lines={l['id']:l for l in data['lines']}; lhs=dict.fromkeys(rowspec(data),0.)
    profit=0.; weights={}
    for e in entries:
        l,s=e['line'],e['station']; weight=e['weight']
        assert math.isfinite(weight) and weight>=-TOL
        p=pattern(lines[l],s,e['assignments']);profit+=weight*p.profit
        weights[l,s]=weights.get((l,s),0)+weight
        for k,v in vector(lines[l],s,p).items():lhs[k]+=v*weight
    if artificials:
        for k,v in artificials.items():
            assert math.isfinite(v) and v>=-TOL
            lhs[k] += -v if k[0]=='recovery' else v
    for k,(sense,rhs) in rowspec(data).items():
        assert abs(lhs[k]-rhs)<=TOL if sense=='=' else lhs[k]<=rhs+TOL, (k,lhs[k],rhs)
    close(profit if phase==2 else -sum((artificials or {}).values()),expected)

def projection(data, entries, expected, relaxed=False):
    model=common.compact.build_model(data)
    for v in model.problem.variables():
        v.varValue=0
        if relaxed: v.cat=pulp.LpContinuous
    lines={l['id']:l for l in data['lines']}
    for e in entries:
        l,s,w=e['line'],e['station'],e['weight'];p=pattern(lines[l],s,e['assignments'])
        model.u[l,s].varValue+=w*p.active;model.h[l,s].varValue+=w*p.human;model.r[l,s].varValue+=w*p.robot
        for i,m in p.assignments:
            model.x[l,i,s,m].varValue+=w;model.y[l,i].varValue+=w
    assert model.problem.valid(TOL)
    close(objective_value(model.problem),expected)

def certificate(data, pool, result):
    """Replay every saved dual/pricing round against all independently enumerated columns."""
    lines={l['id']:l for l in data['lines']};spec=rowspec(data);reports=[]
    for record in result['history']:
        if 'pricing' not in record: continue
        if 'complete_pricing' in record: assert record['complete_pricing'] is True
        if 'rmp_status' in record: assert record['rmp_status']=='optimal'
        dual={tuple(e['row']):e['value'] for e in record['duals']}
        assert len(dual)==len(record['duals']) and dual.keys()==spec.keys()
        assert all(math.isfinite(x) for x in dual.values())
        assert all(dual[k]>=-TOL for k,(sense,b) in spec.items() if sense=='<=')
        if record['phase']==1:
            assert all(dual[k]>=-1-TOL for k,(sense,b) in spec.items() if k[0]=='task' and sense=='=')
            assert all(dual[k]<=1+TOL for k in spec if k[0]=='recovery')
        dobj=sum(spec[k][1]*v for k,v in dual.items());close(dobj,record['objective'])
        maxima={key:max(rc(lines[key[0]],key[1],p,dual,record['phase']) for p in cols) for key,cols in pool.items()}
        seen=set()
        for pp in record['pricing']:
            key=pp['line'],pp['station'];assert key in pool and key not in seen;seen.add(key)
            close(pp['reduced_cost'],maxima[key])
            close(rc(lines[key[0]],key[1],pattern(lines[key[0]],key[1],pp['assignments']),dual,record['phase']),maxima[key])
            if 'optimal' in pp: assert pp['optimal'] is True
            if 'status' in pp: assert pp['status']=='optimal'
        assert seen==pool.keys()
        upper=dobj+sum(max(0,x) for x in maxima.values());close(upper,record['lp_upper_bound'])
        if 'rmp_solution' in record:
            arts={tuple(e['row']):e['value'] for e in record.get('artificial_rows',[])}
            witness(data,record['rmp_solution'],record['objective'],record['phase'],arts)
        # Independently repair alpha and verify ALL dual inequalities.
        repaired=dict(dual)
        for (l,s),rho in maxima.items():repaired['station',l,s]+=max(0,rho)
        for (l,s),ps in pool.items():
            assert max(rc(lines[l],s,p,repaired,record['phase']) for p in ps)<=TOL
        reports.append(dict(phase=record['phase'],iteration=record['iteration'],dual_objective=dobj,
                            upper=upper,maximum=max(maxima.values()),blocks=len(seen)))
    assert reports
    final_duals={tuple(e['row']):e['value'] for e in result['final_duals']}
    assert final_duals.keys()==dual.keys()
    for k in dual:close(final_duals[k],dual[k])
    if result['lp_converged']:
        assert result['status']=='LP_optimal_within_tolerance' and reports[-1]['phase']==2
        close(result['lp_objective'],result['history'][-1]['objective'])
        close(result['lp_upper_bound'],reports[-1]['upper'])
        assert max(r['maximum'] for r in reports[-1:])<=result['epsilon']+TOL
        witness(data,result['lp_solution'],result['lp_objective'])
    elif result['status']=='infeasible_full_column_LP':
        assert reports[-1]['phase']==1 and reports[-1]['upper'] < -result['feasibility_tolerance']
        close(result['phase_I_lp_upper_bound'],reports[-1]['upper'])
    else:raise AssertionError('No complete termination proof')
    return reports

def cases():
    items=[]
    for name in ('single_line','two_lines'):
        items.append((name,json.loads((ROOT/'code/milp/examples'/f'{name}.json').read_text())))
    def task(i, modes=('H','R','J'), time_=2, beta=.1, value=6, weight=1):
        return dict(id=str(i),value=value,weight=weight,modes={m:dict(time=time_,cost=1,beta=0 if m=='R' else beta) for m in modes})
    def base(name,n=2,k=2):
        return dict(name=name,human_limit=k,robot_limit=k,lines=[dict(id='A',cycle_time=3,fatigue_limit=.5,
            stations=[dict(fixed_cost=1,human_cost=1,robot_cost=1) for _ in range(k)],
            tasks=[task(i) for i in range(n)],precedence=[],required_tasks=[],min_recovery=0)])
    for name in ('human_only','robot_only','joint_only','zero_fatigue','tight_fatigue','human_scarce','robot_scarce',
                 'tight_recovery','zero_profit','negative_profit','phase1_impossible','multi_optimum','heterogeneous_gap'):
        d=base(name);l=d['lines'][0]
        if name.endswith('_only'):
            mode={'human_only':'H','robot_only':'R','joint_only':'J'}[name];l['tasks']=[task(i,(mode,)) for i in range(2)]
        if name=='zero_fatigue':l['fatigue_limit']=0
        if name=='tight_fatigue':l['fatigue_limit']=1-math.exp(-.19)
        if name=='human_scarce':d['human_limit']=0
        if name=='robot_scarce':d['robot_limit']=0
        if name=='tight_recovery':l['min_recovery']=2
        if name in ('zero_profit','negative_profit'):
            for t in l['tasks']:t['value']=0 if name=='negative_profit' else 1
            l['stations']=[dict(fixed_cost=0,human_cost=0,robot_cost=0) for _ in l['stations']]
        if name=='phase1_impossible':l['required_tasks']=['0'];d.update(human_limit=0,robot_limit=0)
        if name=='multi_optimum':l['stations']=[dict(fixed_cost=0,human_cost=0,robot_cost=0)]*2
        if name=='heterogeneous_gap':l['tasks']=[task(0)];l['required_tasks']=['0'];l['stations'][0]['fixed_cost']=100
        items.append((name,d))
    d=base('and_diamond',4,3);l=d['lines'][0];l['precedence']=[['0','2'],['1','2'],['2','3']];l['required_tasks']=['3'];items.append((d['name'],d))
    d=base('chain',4,3);l=d['lines'][0];l['cycle_time']=4;l['precedence']=[['0','1'],['1','2'],['2','3']];l['required_tasks']=['3'];items.append((d['name'],d))
    perm=copy.deepcopy(d);perm['name']='chain_permuted';perm['lines'][0]['tasks'].reverse();items.append((perm['name'],perm))
    d=base('lp_yes_ip_no',1,1);d['human_limit']=1;d['robot_limit']=1
    d['lines'][0]['tasks']=[task(0,('H','R'))];d['lines'][0]['required_tasks']=['0']
    l=copy.deepcopy(d['lines'][0]);l.update(id='B',required_tasks=[],min_recovery=1);l['tasks']=[task(0,('J',),weight=2)];d['lines'].append(l);items.append((d['name'],d))
    d=base('overlong_required',2,1);d['lines'][0]['tasks'][0]=task(0,time_=4);d['lines'][0]['required_tasks']=['0'];items.append((d['name'],d))
    d=base('impossible_recovery',2,1);d['lines'][0]['min_recovery']=3;items.append((d['name'],d))
    from generate_instances import generate
    for n,L,seed in ((2,1,11),(4,1,12),(6,1,13),(3,2,14),(5,2,15)):
        d,meta=generate(n=n,lines=L,seed=seed);items.append((f'generator_n{n}_L{L}_s{seed}',d))
    d=base('zero_human_load');d['lines'][0]['fatigue_limit']=0
    d['lines'][0]['tasks']=[task(i,('H',),beta=0) for i in range(2)]
    d['lines'][0]['required_tasks']=['0','1'];items.append((d['name'],d))
    d=base('dual_degenerate');l=d['lines'][0];l.update(cycle_time=4,required_tasks=['0','1'],precedence=[['0','1']]);items.append((d['name'],d))
    return items

def run_case(data, backend, folder, native=False):
    folder.mkdir(parents=True,exist_ok=False)
    (folder/'instance.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    events=[];settings=BackendConfig(name=backend,time_limit=30,log_dir=str(folder/'solver_logs'))
    output=dict(backend=backend,native=native,checks={},status='FAIL')
    try:
        with use_backend(settings,events):
            pool=enumerate_patterns(data)
            output['columns']={f'{l}:{s}':len(ps) for (l,s),ps in pool.items()}
            output['enumerated_patterns']=[dict(line=l,station=s,patterns=[asdict(p) for p in ps]) for (l,s),ps in pool.items()]
            # Compare complete production enumeration and every individual row vector.
            tested=common.enumerate_pool(data)
            for (l,s),ps in pool.items():
                line=next(x for x in data['lines'] if x['id']==l)
                assert {p.assignments for p in ps}=={p.assignments for p in tested[l,s]}
                for p in ps:
                    prod=common.make_column(line,s,p.assignments)
                    for attr in ('active','human','robot','duration','fatigue','recovery','profit'):close(getattr(p,attr),getattr(prod,attr))
                    assert vector(line,s,p)==common.coefficients(line,s,prod)
            output['checks']['complete_enumeration_and_vectors']='PASS'
            full={};models={}
            for kind,integer in (('full_ip',True),('full_lp',False)):
                model,vs=full_model(data,pool,integer);full[kind]=solve_problem(model,integer);models[kind]=(model,vs)
            for kind,integer in (('compact_ip',True),('compact_lp',False)):
                model=common.compact.build_model(data)
                if not integer:
                    for v in model.problem.variables():v.cat=pulp.LpContinuous
                full[kind]=solve_problem(model.problem,integer);models[kind]=model
            output['models']=full
            assert full['full_ip']['status']==full['compact_ip']['status']
            if full['full_ip']['optimal']:
                close(full['full_ip']['objective'],full['compact_ip']['objective'])
                assert full['full_ip']['objective']<=full['full_lp']['objective']+TOL
                original=models['compact_ip'];entries=[]
                for line in data['lines']:
                    for s in range(1,len(line['stations'])+1):
                        a=[(i,m) for (l,i,ss,m),v in original.x.items() if l==line['id'] and ss==s and v.value()>.5]
                        p=pattern(line,s,a);assert p in pool[line['id'],s]
                        close(p.active,original.u[line['id'],s].value());close(p.human,original.h[line['id'],s].value());close(p.robot,original.r[line['id'],s].value())
                        entries.append(dict(line=line['id'],station=s,weight=1,assignments=a))
                witness(data,entries,full['compact_ip']['objective'])
                output['checks']['compact_to_full_mapping']='PASS'
            for kind in ('full_ip','full_lp'):
                if full[kind]['optimal']:
                    model,vs=models[kind];entries=[dict(line=l,station=s,weight=v.value(),assignments=pool[l,s][i].assignments) for (l,s,i),v in vs.items() if v.value()>1e-10]
                    witness(data,entries,full[kind]['objective']);projection(data,entries,full[kind]['objective'],kind=='full_lp')
                    output['checks'][kind+'_to_compact_mapping']='PASS'
            if full['full_lp']['optimal']:
                assert full['compact_lp']['optimal']
                assert full['full_lp']['objective']<=full['compact_lp']['objective']+TOL
            output['checks']['four_models']='PASS'
            native_master=None;pps={}
            try:
                if native:
                    from incremental_master import IncrementalMaster
                    from persistent_pricing import PersistentPricing
                    native_master=IncrementalMaster(data,settings,str(folder/'native_rmp.txt'))
                    for line in data['lines']:
                        for s in range(1,len(line['stations'])+1):pps[line['id'],s]=PersistentPricing(line,s,settings,str(folder/f'pp_{line["id"]}_{s}.txt'))
                    def pp(line,s,duals,phase,verbose):return pps[line['id'],s].solve(duals,phase)
                    with patch.object(cg,'build_master',side_effect=lambda d,p,phase:native_master.sync(p,phase)),patch.object(cg,'solve_master',side_effect=lambda m,**kw:m.solve()),patch.object(cg,'price',side_effect=pp):
                        result,restricted=cg.run_cg(data,recover=False)
                    if result['lp_objective'] is not None:
                        result['integer_recovery']=cg.recover_integer(data,restricted)
                else:result,restricted=cg.run_cg(data)
                output['cg']=result
                if full['full_lp']['optimal']:
                    assert result['lp_converged'];close(result['lp_objective'],full['full_lp']['objective'])
                else:assert result['status']=='infeasible_full_column_LP'
                output['certificate_rounds']=certificate(data,pool,result)
                for rec in output['certificate_rounds']:
                    if rec['phase']==2:
                        assert rec['upper']+TOL>=full['full_lp']['objective']
                output['checks']['cg_and_independent_certificate']='PASS'
                # Deliberately arbitrary free equality duals; both stages, every block.
                rng=random.Random(1701);comparisons=[]
                for phase in (1,2):
                    dual={k:rng.uniform(0,4) if sense=='<=' else rng.uniform(-4,4) for k,(sense,b) in rowspec(data).items()}
                    for (l,s),ps in pool.items():
                        line=next(x for x in data['lines'] if x['id']==l)
                        c,value=pps[l,s].solve(dual,phase) if native else pricing.price(line,s,dual,phase)
                        expected=max(rc(line,s,p,dual,phase) for p in ps);close(value,expected)
                        close(rc(line,s,pattern(line,s,c.assignments),dual,phase),expected)
                        comparisons.append(dict(phase=phase,line=l,station=s,solver=value,enumerated=expected))
                output['pricing_comparisons']=comparisons;output['checks']['pricing_both_phases']='PASS'
                # Test the bound theorem with deliberately loose valid PP upper
                # bounds and a dual unrelated to the optimal RMP. Use D, not Z_RMP.
                maxima={key:max(rc(next(l for l in data['lines'] if l['id']==key[0]),key[1],p,dual,2) for p in ps) for key,ps in pool.items()}
                loose={key:rho+.75 for key,rho in maxima.items()}
                dobj=sum(rowspec(data)[k][1]*x for k,x in dual.items())
                upper=dobj+sum(max(0,x) for x in loose.values())
                if full['full_lp']['optimal']:assert upper+TOL>=full['full_lp']['objective']
                repaired=dict(dual)
                for (l,s),value in loose.items():repaired['station',l,s]+=max(0,value)
                for (l,s),ps in pool.items():
                    line=next(x for x in data['lines'] if x['id']==l)
                    assert max(rc(line,s,p,repaired,2) for p in ps)<=TOL
                output['loose_bound_test']={'dual_objective':dobj,'upper':upper,'bounds':[{"line":l,"station":s,"bound":v} for (l,s),v in loose.items()]}
                output['checks']['general_best_bound_theorem']='PASS'
            finally:
                if native_master: native_master.close()
                for p in pps.values():p.close()
            output['status']='PASS'
    except Exception:
        output['error']=traceback.format_exc()
    output['solver_events']=events
    (folder/'result.json').write_text(json.dumps(output,indent=2,allow_nan=False),encoding='utf-8')
    return {k:v for k,v in output.items() if k in ('backend','native','status','checks','error','columns')} | {'models':{k:{x:v[x] for x in ('status','objective','best_bound','relative_gap')} for k,v in output.get('models',{}).items()}}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path);parser.add_argument('--native',action='store_true');parser.add_argument('--limit',type=int)
    parser.add_argument('--certificate',type=Path);parser.add_argument('--instance',type=Path);parser.add_argument('--case',action='append');args=parser.parse_args()
    if args.certificate:
        if not args.instance:parser.error('--certificate requires --instance')
        data=json.loads(args.instance.read_text(encoding='utf-8-sig'));result=json.loads(args.certificate.read_text(encoding='utf-8-sig'))
        result=result.get('cg',result)
        print(json.dumps(certificate(data,enumerate_patterns(data),result),indent=2))
        return 0
    if not args.out:parser.error('--out is required for experiments')
    args.out.mkdir(parents=True,exist_ok=False)
    config=dict(tolerance=TOL,solver_limit=30,native=args.native,seed=1701,python=sys.executable)
    config['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__)]+list((ROOT/'code/dwcg').glob('*.py'))+[ROOT/'code/solver_backend.py',ROOT/'code/milp/model.py']}
    (args.out/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    results=[]
    for name,data in cases()[:args.limit]:
        if args.case and name not in args.case:continue
        for backend in (('cplex_py',) if args.native else ('cbc','cplex_py')):
            start=time.perf_counter();r=run_case(data,backend,args.out/f'{name}_{backend}',args.native)
            r.update(name=name,seconds=time.perf_counter()-start);results.append(r)
            (args.out/'summary.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
            print(name,backend,r['status'],round(r['seconds'],2),flush=True)
    return 0 if all(r['status']=='PASS' for r in results) else 1

if __name__=='__main__':raise SystemExit(main())
