"""固定输入、单线程根节点消融；软预算诊断，不用于声称严格性能优势。"""
from pathlib import Path
import hashlib,json,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'code')]
from root_diagnostics import run_root,solution_structure
from evidence_store import EvidenceStore
from solver_backend import BackendConfig,use_backend,make_solver
from common import compact,blocks
from bp_solution import verify_integer_assignments

def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'docs/root_diagnostics/pilot')
    parser.add_argument('--only-n40',action='store_true')
    args=parser.parse_args();out=args.output
    out.mkdir(parents=True,exist_ok=False)
    source={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ('code/dwcg','code/milp') for p in (ROOT/folder).glob('*.py')}
    source['code/solver_backend.py']=hashlib.sha256((ROOT/'code/solver_backend.py').read_bytes()).hexdigest()
    (out/'source_hashes.json').write_text(json.dumps(source,indent=2),encoding='utf-8')
    names=['tasks005_lines02_each03-02.json','tasks006_lines01_each06_seed13.json',
           'tasks020_lines02_each10_seed11.json','tasks040_lines02_each20_seed11.json']
    table=[]
    for ix,name in enumerate(names):
        if args.only_n40 and ix!=3:continue
        raw=(ROOT/'code/data'/name).read_bytes();data=json.loads(raw);budget=10 if ix<2 else 15
        folder=out/Path(name).stem;folder.mkdir();(folder/'instance.json').write_bytes(raw)
        for mode in (['baseline','seed','recover','compact'] if ix%2==0 else ['compact','recover','seed','baseline']):
            target=folder/mode;target.mkdir();tick=time.perf_counter()
            try:
                if mode=='compact':
                    with use_backend(BackendConfig(name='cplex_py',deadline=tick+budget,threads=1,seed=11,log_dir=str(target/'logs'))):
                        m=compact.build_model(data);m.problem.solve(make_solver(role='compact_ip'))
                    info=dict(m.problem.backend_result);w=None
                    if info['has_incumbent']:
                        stations=[dict(line=l['id'],station=s,assignments=[(i,mode) for (li,i,ss,mode),v in m.x.items() if li==l['id'] and ss==s and v.value()>.5]) for l,s in blocks(data)]
                        w=verify_integer_assignments(data,stations,expected=info['objective'])
                    lb=w['objective'] if w else None;ub=info.get('best_bound')
                    r=dict(root_status=info['status'],global_lower_bound=lb,global_upper_bound=ub,
                           absolute_gap=None if lb is None or ub is None else ub-lb,
                           global_integer_optimal_proven=info['optimal'],solver_result=info,
                           integer_incumbent_solution=w,integer_structure=None if not w else solution_structure(data,[dict(e,weight=1.) for e in w['stations']]))
                else:
                    store=EvidenceStore(target/'certificate.sqlite')
                    try:r=run_root(data,mode=mode,time_limit=budget,initial_seconds=.75,recovery_every=10,recovery_seconds=.5,store=store)
                    finally:store.close()
                    r={k:v for k,v in r.items() if k!='node'}
                r.update(input_sha256=hashlib.sha256(raw).hexdigest(),nominal_soft_budget=budget)
                (target/'summary.json').write_text(json.dumps(r,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
                row=dict(instance=name,method=mode,**{k:r.get(k) for k in ('root_status','global_lower_bound','global_upper_bound','absolute_gap','global_integer_optimal_proven','first_integer_seconds')},end_to_end_seconds=time.perf_counter()-tick)
                row['phase1_rounds']=sum(e['phase']==1 for e in r.get('round_diagnostics',[]));row['phase2_rounds']=sum(e['phase']==2 for e in r.get('round_diagnostics',[]))
                row['recovery_attempts']=len(r.get('recoveries',[]))
            except Exception as e:
                row=dict(instance=name,method=mode,error=repr(e));(target/'error.json').write_text(json.dumps(row),encoding='utf-8')
            table.append(row);print(json.dumps(row),flush=True)
            (out/'table.json').write_text(json.dumps(table,indent=2),encoding='utf-8')

if __name__=='__main__':main()
