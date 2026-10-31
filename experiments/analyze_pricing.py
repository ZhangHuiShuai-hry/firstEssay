"""Paired, censoring-aware analysis for native PP reuse; no solver calls."""
import argparse
from collections import Counter,defaultdict
import csv
import json
from pathlib import Path
import statistics

from analyze_results import distribution,quantile


def write_csv(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fields);writer.writeheader();writer.writerows(rows)


def duplicate_objectives(data,rounds):
    """Exact float equality, same-line constraints; station constant excluded.

    Read-only diagnostic, not a pricing cache or an implemented speedup.
    Cross-check equal objectives using the saved exact optimal values.
    """
    lines={line['id']:line for line in data['lines']}
    result=dict(priced_calls=0,duplicate_calls=0,priced_native_time=0.,duplicate_native_time=0.,max_value_difference=0.,
                partial_failed_goals_already_proven=0,partial_failed_redundant_native_time=0.)
    for h in rounds:
        if h['phase']!=2:continue
        dual={tuple(d['row']):d['value'] for d in h['duals']};seen={}
        for p in h['pricing']:
            line=lines[p['line']];l=line['id'];s=p['station'];sigma={t['id']:0. for t in line['tasks']}
            for e,(i,j) in enumerate(line.get('precedence',[])):
                suffix=sum(dual['precedence',l,e,k] for k in range(s,len(line['stations'])+1))
                sigma[i]+=suffix;sigma[j]-=suffix
            rewards=tuple((t['value']-m['cost'])+(-dual['task',l,t['id']]+dual['recovery',l]*t.get('weight',0)+sigma[t['id']])
                          for t in line['tasks'] for m in t['modes'].values())
            cost=line['stations'][s-1]
            key=(l,rewards,-cost['fixed_cost'],-(cost['human_cost']+dual['human',]),-(cost['robot_cost']+dual['robot',]))
            if not h['complete_pricing']:
                if p['status']=='optimal':
                    adjusted=p['rc']+dual['station',l,s]
                    if key in seen and abs(adjusted-seen[key])>1e-5:raise RuntimeError('Partial-round equal PP objectives disagree')
                    seen[key]=adjusted
                elif key in seen:
                    result['partial_failed_goals_already_proven']+=1
                    result['partial_failed_redundant_native_time']+=p['native_time']
                continue
            adjusted=p['rc']+dual['station',l,s]
            result['priced_calls']+=1;result['priced_native_time']+=p['native_time']
            if key in seen:
                delta=abs(adjusted-seen[key]);result['max_value_difference']=max(result['max_value_difference'],delta)
                if delta>1e-5:raise RuntimeError('Equal PP variable objectives disagree on exact optimal value')
                result['duplicate_calls']+=1;result['duplicate_native_time']+=p['native_time']
            else:seen[key]=adjusted
    return result


def analyze(runs,replay,out):
    out.mkdir(parents=True,exist_ok=True);rows=[];iteration_rows=[];root_pp=[];duplicates=[]
    for run in runs:
        for item in json.loads((run/'summary.json').read_text()):
            row=dict(item,run=str(run));rows.append(row)
            path=run/'raw'/(row['instance_id']+'_'+row['version']+'.json')
            if not path.exists():continue
            raw=json.loads(path.read_text());calls=raw['pricing_log']
            data=json.loads((run/'instances'/(row['instance_id']+'.json')).read_text())
            duplicates.append(dict(instance_id=row['instance_id'],budget=row['budget'],version=row['version'],n=row['n'],
                                   **duplicate_objectives(data,raw['rounds'])))
            for r in raw['rounds']:
                iteration_rows.append(dict(instance_id=row['instance_id'],budget=row['budget'],version=row['version'],
                    round=r['round'],phase=r['phase'],objective=r['objective'],upper_bound=r['upper_bound'],
                    maximum_reduced_cost=r['maximum_reduced_cost'],complete_pricing=r['complete_pricing'],
                    pricing_calls=len(r['pricing']),wall_time=r['wall_time']))
            successful=[p for p in calls if p['status']=='optimal'];native=[p['native_time'] for p in successful]
            nodes=[p['nodes'] for p in successful if 'nodes' in p]
            root_pp.append(dict(instance_id=row['instance_id'],budget=row['budget'],version=row['version'],n=row['n'],
                completed_calls=len(successful),failed_calls=len(calls)-len(successful),
                failed_native_time=sum(p['native_time'] for p in calls if p['status']!='optimal'),
                mean=statistics.mean(p['wall_time'] for p in successful) if successful else None,
                median=statistics.median(p['wall_time'] for p in successful) if successful else None,
                native_mean=statistics.mean(native) if native else None,
                native_p95=quantile(native,.95) if native else None,
                nodes_median=statistics.median(nodes) if nodes else None,
                zero_node_fraction=sum(n==0 for n in nodes)/len(nodes) if nodes else None,
                positive_calls=sum(p['rc']>1e-7 for p in successful),
                nonpositive_native_time=sum(p['native_time'] for p in successful if p['rc']<=1e-7)))
    write_csv(out/'per_instance.csv',rows);write_csv(out/'iterations.csv',iteration_rows);write_csv(out/'root_pp_calls_summary.csv',root_pp)
    write_csv(out/'duplicate_objectives.csv',duplicates)
    (out/'per_instance.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    targets=defaultdict(list)
    for r in rows:
        if r['converged']:targets[r['instance_id']].append(r['lp_objective'])
    max_delta=0.
    bound_checks=[]
    for name in sorted({r['instance_id'] for r in rows}):
        group=[r for r in rows if r['instance_id']==name]
        lower=[r['lower_bound'] for r in group if r.get('lower_bound') is not None]
        upper=[r['upper_bound'] for r in group if r.get('upper_bound') is not None]
        if lower and upper and max(lower)>min(upper)+1e-5:raise RuntimeError(f'Cross-version/budget bounds disjoint: {name}')
        bound_checks.append(dict(instance_id=name,best_lower=max(lower) if lower else None,best_upper=min(upper) if upper else None,
                                 converged_target_available=name in targets))
    write_csv(out/'bound_checks.csv',bound_checks)
    for name,values in targets.items():
        delta=max(values)-min(values);max_delta=max(max_delta,delta)
        if delta>1e-5:raise RuntimeError(f'Cross-version/budget LP mismatch {name}: {values}')
    for r in rows:
        if r.get('upper_bound') is not None and r.get('lower_bound') is not None:
            if r['upper_bound']+1e-5<r['lower_bound']:raise RuntimeError('Crossed LP lower/upper bounds')
        if r['instance_id'] not in targets:continue
        optimum=targets[r['instance_id']][0]
        if r.get('upper_bound') is not None and r['upper_bound']+1e-5<optimum:raise RuntimeError('Invalid LP upper bound')
        if r.get('lower_bound') is not None and r['lower_bound']-1e-5>optimum:raise RuntimeError('Invalid LP lower bound')
    pairs=defaultdict(dict);paired=[]
    for r in rows:pairs[r['budget'],r['n'],r['seed']][r['version']]=r
    for (budget,n,seed),p in sorted(pairs.items()):
        if len(p)!=2:continue
        a,b=p['V1'],p['V2'];entry=dict(budget=budget,n=n,seed=seed,V1_status=a['status'],V2_status=b['status'],
            V1_time=a.get('wall_time'),V2_time=b.get('wall_time'),speedup=None,speedup_lower_bound=None,speedup_upper_bound=None,
            objective_delta=None,V1_upper=a.get('upper_bound'),V2_upper=b.get('upper_bound'))
        if a['converged'] and b['converged']:
            entry.update(speedup=a['wall_time']/b['wall_time'],objective_delta=abs(a['lp_objective']-b['lp_objective']))
        elif b['converged'] and a['status']=='time_limit':entry['speedup_lower_bound']=budget/b['wall_time']
        elif a['converged'] and b['status']=='time_limit':entry['speedup_upper_bound']=a['wall_time']/budget
        paired.append(entry)
    write_csv(out/'paired_speedups.csv',paired)
    stats=[];speedups=[]
    for budget in sorted({r['budget'] for r in rows}):
        for n in sorted({r['n'] for r in rows if r['budget']==budget}):
            ps=[p for p in paired if p['budget']==budget and p['n']==n];d=distribution([p['speedup'] for p in ps])
            speedups.append(dict(budget=budget,n=n,paired_instances=len(ps),both_completed=d['count'],median=d['median'],mean=d['mean'],
                q1=d['q1'],q3=d['q3'],std=d['std'],V2_only_completed=sum(p['speedup_lower_bound'] is not None for p in ps),
                V1_only_completed=sum(p['speedup_upper_bound'] is not None for p in ps)))
            for version in ('V1','V2'):
                group=[r for r in rows if (r['budget'],r['n'],r['version'])==(budget,n,version)]
                item=dict(budget=budget,n=n,version=version,attempts=len(group),converged=sum(r['converged'] for r in group),
                          statuses=dict(Counter(r['status'] for r in group)))
                for k in ('wall_time','phase1_time','phase2_time','rmp_build_time','rmp_interface_time','rmp_native_time','pp_time',
                          'pp_build_time','pp_native_creation_time','pp_translation_time','pp_objective_update_time','pp_native_time','pp_other_time',
                          'iterations','columns','pricing_calls','final_lp_gap'):
                    item[k]=distribution([r.get(k) for r in group])
                for label,fn in (('pp_fraction',lambda r:r['pp_time']/r['wall_time']),
                                 ('native_pp_fraction',lambda r:r['pp_native_time']/r['wall_time']),
                                 ('rmp_fraction',lambda r:(r['rmp_build_time']+r['rmp_interface_time'])/r['wall_time'])):
                    item[label]=distribution([fn(r) for r in group if r.get('wall_time')])
                stats.append(item)
    write_csv(out/'speedup_summary.csv',speedups)
    replay_rows=json.loads((replay/'calls.json').read_text());check=json.loads((replay/'validation.json').read_text());assert check['passed']
    replay_stats=[]
    for n in sorted({r['n'] for r in replay_rows}):
        for phase in ('all',1,2):
            group=[r for r in replay_rows if r['n']==n and (phase=='all' or r['phase']==phase)]
            if not group:continue
            item=dict(n=n,phase=phase,calls=len(group),max_rc_difference=max(r['delta'] for r in group))
            for v in ('V1','V2'):
                d=distribution([r[v+'_time'] for r in group])
                for k,value in d.items():item[v+'_'+k]=value
            item['mean_reduction_pct']=100*(1-item['V2_mean']/item['V1_mean'])
            item['median_reduction_pct']=100*(1-item['V2_median']/item['V1_median'])
            item['ratio_of_total_times']=sum(r['V1_time'] for r in group)/sum(r['V2_time'] for r in group)
            for k in ('V1_build','V1_translation','V1_native','V1_other','V2_build','V2_native_creation','V2_update','V2_native','V2_other'):
                item[k+'_mean']=statistics.mean(r[k] for r in group)
            replay_stats.append(item)
    write_csv(out/'fixed_dual_pp_statistics.csv',replay_stats)
    polarity=[]
    for n in sorted({r['n'] for r in replay_rows}):
        for label,positive in (('positive',True),('nonpositive',False)):
            group=[r for r in replay_rows if r['n']==n and r['phase']==2 and (r['reported_rc']>1e-7)==positive]
            if not group:continue
            item=dict(n=n,phase=2,rc_class=label,calls=len(group))
            for v in ('V1','V2'):
                item[v+'_native_total']=sum(r[v+'_native'] for r in group)
                item[v+'_native_mean']=statistics.mean(r[v+'_native'] for r in group)
                item[v+'_wall_total']=sum(r[v+'_time'] for r in group)
            polarity.append(item)
    write_csv(out/'fixed_dual_rc_classes.csv',polarity)
    (out/'statistics.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
    (out/'paired_speedups.json').write_text(json.dumps(paired,indent=2),encoding='utf-8')
    (out/'fixed_dual_pp_statistics.json').write_text(json.dumps(replay_stats,indent=2),encoding='utf-8')
    (out/'validation.json').write_text(json.dumps(dict(passed=True,converged_objective_max_delta=max_delta,
        checked_runs=len(rows),complete_pairs=sum(p['speedup'] is not None for p in paired),fixed_dual_pairs=check['paired_calls'],
        all_root_runs_converged=all(r['converged'] for r in rows),converged_runs=sum(r['converged'] for r in rows),
        status_counts=dict(Counter(r['status'] for r in rows)),
        passed_means='Analysis consistency checks passed; not a claim that every CG run converged.',
        scope='All converged LP targets across budgets/versions and truncated LP bounds checked; full enumeration remains restricted to small tests.'),indent=2),encoding='utf-8')
    return rows,stats,paired,replay_stats


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runs',nargs='+',type=Path,required=True);p.add_argument('--replay',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();analyze(a.runs,a.replay,a.out)
