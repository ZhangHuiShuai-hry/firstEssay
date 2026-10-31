"""Retain every attempt; summarize observed runtimes and success separately."""
import argparse
from collections import Counter,defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'code/dwcg'))
from common import enumerate_pool


def quantile(values,p):
    values=sorted(values);position=(len(values)-1)*p;lo=math.floor(position);hi=math.ceil(position)
    return values[lo]+(values[hi]-values[lo])*(position-lo)


def distribution(values):
    values=[v for v in values if isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v)]
    if not values:return dict(count=0,mean=None,median=None,std=None,q1=None,q3=None)
    return dict(count=len(values),mean=statistics.mean(values),median=statistics.median(values),
                std=statistics.stdev(values) if len(values)>1 else None,q1=quantile(values,.25),q3=quantile(values,.75))


def enrich(row,run):
    row=dict(row);key=row['instance_id']+'__'+row['solver_combo'];path=run/'raw'/(key+'.json')
    if not path.exists():return row
    raw=json.loads(path.read_text());cg=raw.get('cg',{});entry=raw['task']['entry']
    row['precedence_density']=entry['metadata']['precedence_density']
    row['mode_counts']=entry['metadata']['mode_counts'];row['input_sha256']=entry['metadata']['input_sha256']
    data=json.loads((run/'instances'/entry['instance']).read_text())
    # Counting small local pattern sets requires no optimization; never enumerate
    # larger instances silently. These counts can expose fatigue effects even
    # when an integer knapsack load is not exactly equal to its budget.
    if max(len(l['tasks']) for l in data['lines'])<=8:
        local=enumerate_pool(data,max_combinations=100000)
        row['enumerated_local_columns_total']=sum(map(len,local.values()))
    else:row['enumerated_local_columns_total']=None
    if cg.get('lp_converged'):
        duals={tuple(d['row']):d['value'] for d in cg.get('final_duals',[])}
        row['human_dual']=duals.get(('human',));row['robot_dual']=duals.get(('robot',))
        lines={l['id']:l for l in data['lines']};usage=defaultdict(lambda:dict(h=0.,r=0.,d=0.,time=0.))
        for column in cg.get('lp_solution',[]):
            l=column['line'];s=column['station'];weight=column['weight'];modes={m for _,m in column['assignments']}
            station=usage[l,s];station['h']+=weight*bool(modes&{'H','J'});station['r']+=weight*bool(modes&{'R','J'})
            tasks={t['id']:t for t in lines[l]['tasks']}
            for i,m in column['assignments']:
                params=tasks[i]['modes'][m];station['d']+=weight*params['beta']*params['time'];station['time']+=weight*params['time']
        row['lp_humans']=sum(u['h'] for u in usage.values());row['lp_robots']=sum(u['r'] for u in usage.values())
        row['lp_fatigue_binding_stations']=sum(u['h']>1e-7 and abs(u['d']+math.log1p(-lines[l]['fatigue_limit'])*u['h'])<1e-6 for (l,s),u in usage.items())
    # Backend timings form a decomposition *inside* each interface call. Do not
    # add them to the root RMP/PP wall timers; those already include these calls.
    events=[e for e in raw.get('events',[]) if e.get('role') in ('pricing','rmp')]
    row['cg_solver_native_time']=sum(e['solver_time'] for e in events if e.get('solver_time') is not None)
    row['cg_translation_time']=sum(e['translation_time'] for e in events if e.get('translation_time') is not None)
    row['cg_solver_interface_wall']=sum(e['wall_time'] for e in events)
    row['cg_interface_other_time']=max(0,row['cg_solver_interface_wall']-row['cg_solver_native_time']-row['cg_translation_time'])
    pp=[e for e in events if e['role']=='pricing']
    row['pricing_native_time']=sum(e['solver_time'] for e in pp if e.get('solver_time') is not None)
    row['pricing_translation_time']=sum(e['translation_time'] for e in pp if e.get('translation_time') is not None)
    row['pricing_python_interface_other']=max(0,(row.get('pricing_wall_time') or 0)-row['pricing_native_time']-row['pricing_translation_time'])
    return row


def analyze(run):
    rows=[enrich(row,run) for row in json.loads((run/'summary.json').read_text())]
    out=run/'analysis';out.mkdir(exist_ok=True)
    (out/'analysis_provenance.json').write_text(json.dumps(dict(script=Path(__file__).name,
        sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2),encoding='utf-8')
    (out/'enriched_summary.json').write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    columns=sorted({k for r in rows for k in r})
    with (out/'enriched_summary.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
        writer.writerows({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows)
    groups=defaultdict(list)
    for row in rows:groups[row['group'],str(row['factor']),row['solver_combo']].append(row)
    stats=[]
    numeric=('cg_wall_time','pricing_wall_time','rmp_build_time','rmp_solve_time','cg_other_time',
             'compact_lp_wall_time','milp_wall_time','pricing_ratio','phase1_wall_time','phase2_wall_time',
             'cg_iterations','columns_generated','cg_lp_obj','restricted_integer_obj','lp_humans','lp_robots',
             'human_dual','robot_dual','lp_fatigue_binding_stations','cg_solver_native_time','cg_translation_time',
             'pricing_native_time','pricing_translation_time','pricing_python_interface_other',
             'enumerated_local_columns_total')
    for (group,factor,solver),entries in groups.items():
        item=dict(group=group,factor=factor,solver_combo=solver,attempts=len(entries),
                  converged=sum(bool(r.get('cg_converged')) for r in entries),
                  success_fraction=sum(bool(r.get('cg_converged')) for r in entries)/len(entries),
                  cg_status_counts=dict(Counter(r.get('cg_status','missing') for r in entries)),
                  milp_status_counts=dict(Counter(r.get('milp_status','missing') for r in entries)),
                  verification_status_counts=dict(Counter(r.get('verification_status','missing') for r in entries)))
        for field in numeric:item[field]=distribution([r.get(field) for r in entries])
        item['cg_wall_success_only']=distribution([r.get('cg_wall_time') for r in entries if r.get('cg_converged')])
        stats.append(item)
    (out/'group_statistics.json').write_text(json.dumps(stats,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    timing=[]
    for row in rows:
        if row.get('cg_wall_time') is None:continue
        phases=(row.get('phase1_wall_time') or 0)+(row.get('phase2_wall_time') or 0)
        components=sum(row.get(k) or 0 for k in ('rmp_build_time','rmp_solve_time','pricing_wall_time'))
        valid=abs(phases-row['cg_wall_time'])<1e-7 and components<=row['cg_wall_time']+1e-7
        timing.append(dict(instance_id=row['instance_id'],solver_combo=row['solver_combo'],passed=valid))
    (out/'timing_validation.json').write_text(json.dumps(timing,indent=2),encoding='utf-8')
    if any(not item['passed'] for item in timing):raise RuntimeError('Overlapping or inconsistent CG timing intervals')
    manifest=json.loads((run/'instances/manifest.json').read_text());by_id=defaultdict(list)
    for row in rows:by_id[row['instance_id']].append(row)
    audit=dict(generated_instances=len(manifest),unique_input_hashes=len({e['metadata']['input_sha256'] for e in manifest}),
               valid_schema_instances=len(manifest),discarded_instances=0,planned_infeasible=sum(e['planned_infeasible'] for e in manifest),
               milp_proven_feasible=0,milp_proven_infeasible=0,milp_unresolved=0,
               note='Identical control inputs reused across different factor families are not independent replicates; never pool families.')
    for entry in manifest:
        attempts=by_id[entry['instance_id']]
        if any(r.get('milp_incumbent') is not None for r in attempts):audit['milp_proven_feasible']+=1
        elif attempts and all(r.get('milp_status')=='infeasible' for r in attempts):audit['milp_proven_infeasible']+=1
        else:audit['milp_unresolved']+=1
    recovered=[r for r in rows if r.get('recovered_mode_counts')]
    audit['recovered_runs']=len(recovered)
    audit['all_human_recoveries']=sum(r['recovered_mode_counts']['R']==r['recovered_mode_counts']['J']==0 for r in recovered)
    audit['all_robot_recoveries']=sum(r['recovered_mode_counts']['H']==r['recovered_mode_counts']['J']==0 for r in recovered)
    audit['runs_with_positive_resource_dual']=sum((r.get('human_dual') or 0)>1e-7 or (r.get('robot_dual') or 0)>1e-7 for r in rows)
    audit['runs_with_binding_LP_fatigue']=sum((r.get('lp_fatigue_binding_stations') or 0)>0 for r in rows)
    (out/'dataset_audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
    # Solver combinations may differ in chosen optima under degeneracy; compare
    # mathematical objectives and statuses, not exact assignments or iteration counts.
    cross=[]
    for case,entries in by_id.items():
        item=dict(instance_id=case,combinations=len(entries),passed=True)
        for field in ('cg_lp_obj','milp_incumbent','compact_lp_obj'):
            values=[r[field] for r in entries if r.get(field) is not None]
            spread=max(values)-min(values) if values else None
            item[field+'_spread']=spread
            if spread is not None and spread>1e-5:item['passed']=False
        item['verification_all_passed']=all(r.get('verification_status')=='passed' for r in entries)
        cross.append(item)
    (out/'cross_solver_comparison.json').write_text(json.dumps(cross,indent=2)+'\n',encoding='utf-8')
    calls=[];iterations=[]
    for row in rows:
        path=run/'raw'/(row['instance_id']+'__'+row['solver_combo']+'.json')
        if not path.exists():continue
        raw=json.loads(path.read_text());data=json.loads((run/'instances'/raw['task']['entry']['instance']).read_text())
        lines={l['id']:l for l in data['lines']}
        native_calls=[event for event in raw.get('events',[]) if event.get('role')=='pricing']
        for index,call in enumerate(raw.get('pricing_calls',[])):
            native=native_calls[index] if index<len(native_calls) else {}
            line=lines[call['line']]
            calls.append(dict(instance_id=row['instance_id'],group=row['group'],factor=row['factor'],seed=row['seed'],
                solver_combo=row['solver_combo'],**call,n_tasks=len(line['tasks']),
                allowed_modes=sum(len(t['modes']) for t in line['tasks']),fatigue_limit=line['fatigue_limit'],
                graph=raw['task']['entry']['generation'].get('graph'),
                mode_profile=raw['task']['entry']['generation'].get('mode_profile'),
                native_time=native.get('solver_time'),translation_time=native.get('translation_time'),
                native_status=native.get('status')))
        for iteration in raw.get('cg',{}).get('history',[]):
            iterations.append(dict(instance_id=row['instance_id'],solver_combo=row['solver_combo'],**iteration))
    (out/'pricing_calls.json').write_text(json.dumps(calls,indent=2),encoding='utf-8')
    if calls:
        with (out/'pricing_calls.csv').open('w',newline='',encoding='utf-8-sig') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(calls[0]));writer.writeheader();writer.writerows(calls)
    pp_groups=defaultdict(list)
    for call in calls:pp_groups[call['group'],str(call['factor']),call['solver_combo'],call['line'],call['station'],call['phase']].append(call)
    pp_stats=[dict(group=g,factor=f,solver_combo=solver,line=l,station=s,phase=phase,
                   wall_time=distribution([c['wall_time'] for c in values]),
                   native_time=distribution([c['native_time'] for c in values]),
                   status_counts=dict(Counter(c['status'] for c in values)),
                   interpretation='Descriptive call distribution; iterations are not independent random instances.')
              for (g,f,solver,l,s,phase),values in pp_groups.items()]
    (out/'pricing_statistics.json').write_text(json.dumps(pp_stats,indent=2),encoding='utf-8')
    (out/'iteration_logs.json').write_text(json.dumps(iterations,indent=2),encoding='utf-8')
    return rows,stats,audit


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();_,_,audit=analyze(a.run);print(json.dumps(audit,indent=2))
