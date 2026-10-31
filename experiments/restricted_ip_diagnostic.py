"""Rebuild saved pure CG pool and solve its integer master, optionally add Direct columns."""
import argparse,csv,hashlib,json,time,sys
from pathlib import Path
from datetime import datetime,timezone
from hybrid import columns_from_solution
from common import compact,empty_pool,make_column,coefficients
from master import build_master,decode_integer
from solver_backend import load_cplex,BackendConfig,use_backend,make_solver

BASE=Path('experiments/runs/large_120_150_600_01')
def reconstruct(data,rec):
    pool=empty_pool(data);lines={l['id']:l for l in data['lines']}
    for j,r in enumerate(rec['rounds']):
        if not r['complete_pricing'] or j+1>=len(rec['rounds']):continue
        for p in r['pricing']:
            if p['rc']>1e-7:
                k=p['line'],p['station'];col=make_column(lines[k[0]],k[1],p['assignments'])
                if any(c.assignments==col.assignments for c in pool[k]):raise ValueError('Duplicate CG column')
                pool[k].append(col)
    assert sum(map(len,pool.values()))==rec['columns']
    for (l,s),cs in pool.items():
        for c in cs:
            assert c==make_column(lines[l],s,c.assignments);coefficients(lines[l],s,c)
    return pool

def run(n,mode,out):
    out.mkdir(parents=True,exist_ok=False);key=f'total{n}_L2_s11';instance=BASE/'instances'/f'{key}.json';ipfile=BASE/'raw'/f'{key}_ip.json';cgfile=BASE/'raw'/f'{key}_cg.json'
    data=json.loads(instance.read_text());ip=json.loads(ipfile.read_text());cg=json.loads(cgfile.read_text());original=ip['solution'];start=time.perf_counter();pool=reconstruct(data,cg);initial=sum(map(len,pool.values()));direct=columns_from_solution(data,original);origin={};selected={};added=0
    for k,cs in pool.items():
        for col in cs:origin[k,col.assignments]='original_CG'
    for k,cs in direct.items():
        col=cs[-1];ix=next((i for i,c in enumerate(pool[k]) if c.assignments==col.assignments),None)
        if ix is None and mode=='augmented':
            ix=len(pool[k]);pool[k].append(col);origin[k,col.assignments]='direct_added';added+=1
        if ix is not None:selected[k]=ix
    missing=len(pool)-len(selected)
    assert initial==cg['columns'] and (mode!='augmented' or missing==0)
    build_start=time.perf_counter();master=build_master(data,pool,integer=True);start_ok=False
    if mode=='augmented':
        for (l,s,p),v in master.variables.items():v.varValue=int(selected[l,s]==p)
        assert master.problem.valid(1e-6) and abs(master.value()-ip['incumbent'])<1e-5
        start_ok=True
    build_time=time.perf_counter()-build_start;cplex=load_cplex();logs=out/'solver_logs';events=[]
    with use_backend(BackendConfig(name='cplex_py',threads=1,seed=11,time_limit=120,log_dir=str(logs)),events):
        solver=make_solver(role='recovery');tick=time.perf_counter();solver.buildSolverModel(master.problem);translation=time.perf_counter()-tick;native=solver.solverModel
        if mode=='augmented':
            names=[v.name for v in master.variables.values()];vals=[v.varValue for v in master.variables.values()]
            native.MIP_starts.add(cplex.SparsePair(ind=names,val=vals),native.MIP_starts.effort_level.check_feasibility,'direct_solution')
            assert native.MIP_starts.get_num()==1
        tick=time.perf_counter();solver.callSolver(master.problem);solver_time=time.perf_counter()-tick
        sol=native.solution;code=sol.get_status();status_text=sol.get_status_string();feasible=bool(sol.is_primal_feasible());solver.findSolutionValues(master.problem)
        objective=float(sol.get_objective_value()) if feasible else None
        try:bound=float(sol.MIP.get_best_objective());bound=bound if abs(bound)<1e19 else None
        except cplex.exceptions.CplexSolverError:bound=None
        try:gap=float(sol.MIP.get_mip_relative_gap()) if feasible else None
        except cplex.exceptions.CplexSolverError:gap=None
        status='optimal' if code==101 and feasible else 'infeasible' if code==103 else 'time_limit' if code in (107,108) else 'feasible_unproven' if feasible else 'unknown'
        if status=='infeasible':bound=None
        solution=decode_integer(data,pool,master) if feasible else None
        chosen=[];changes=[]
        if feasible:
            assert master.problem.valid(1e-6) and abs(master.value()-objective)<1e-5
            for (l,s,p),v in master.variables.items():
                if v.value()>.5:
                    col=pool[l,s][p];chosen.append(dict(line=l,station=s,assignments=col.assignments,source=origin[(l,s),col.assignments],profit=col.profit,coefficients=[dict(row=list(k),value=x) for k,x in coefficients(next(x for x in data['lines'] if x['id']==l),s,col).items()]))
                    dc=direct[l,s][-1]
                    if col.assignments!=dc.assignments:changes.append(dict(line=l,station=s,direct=dc.assignments,result=col.assignments))
        native.end()
        if getattr(solver,'_log_handle',None):solver._log_handle.close()
    logpath=next(logs.glob('*.log'));log=logpath.read_text(errors='replace');loglow=log.lower();accepted= ('mip start' in loglow and ('defined initial solution' in loglow or 'provided solution with objective' in loglow)) if mode=='augmented' else None
    result=dict(tasks=n,mode=mode,status=status,native_status=code,native_status_text=status_text,has_feasible=feasible,objective=objective,restricted_best_bound=bound,restricted_gap=gap,direct_objective=ip['incumbent'],external_direct_lower_bound=ip['incumbent'] if mode=='augmented' else None,original_global_upper_bound=cg['upper_bound'],initial_columns=initial,added_columns=added,total_columns=sum(map(len,pool.values())),direct_missing=missing,direct_mapping_valid=start_ok,mip_start_accepted=accepted,mip_start_log_checked=str(logpath),model_build_time=build_time,translation_time=translation,solver_time=solver_time,wall_time=time.perf_counter()-start,selected_columns=chosen,changed_stations=changes,independent_compact_validation=bool(solution),solution=solution,sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (instance,ipfile,cgfile)},started_utc=datetime.now(timezone.utc).isoformat())
    (out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps({k:v for k,v in result.items() if k not in ('solution','selected_columns','changed_stations')},indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tasks',type=int,required=True);p.add_argument('--mode',choices=('cg_only','augmented'),required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.tasks,a.mode,a.out)
