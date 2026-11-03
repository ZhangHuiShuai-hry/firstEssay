"""Seeded, paired synthetic benchmarks with an explicit all-task feasible witness.

Witnesses are constructive evidence, not a substitute for MILP validation.
Input JSON stays compatible with the original strict data schema; metadata is separate.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code/dwcg'))
from common import compact, make_column


def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def generate(n=10, lines=2, seed=11, graph='layered', mode_profile='mixed', total_tasks=None,
             total_stations=None, fatigue=0.6, cycle_time=15):
    rng=random.Random(seed)
    count=total_tasks or n*lines
    # Parameters are sampled globally before partitioning; fixed-total comparisons
    # retain the exact task multiset. Witness modes depend on global task rank.
    task_bank=[]; witness_modes=[]
    for i in range(count):
        preferred=('H','R','J')[(i//3)%3]
        htime=rng.randint(2,4); rtime=max(1,round(htime*rng.uniform(.8,1.25)))
        jtime=max(1,round(htime*rng.uniform(.5,.8)))
        dh=rng.uniform(.10,.15) if preferred=='H' else rng.uniform(.28,.48)
        dj=rng.uniform(.08,.13)
        candidates={'H':dict(time=htime,cost=round(1.8*htime,2),beta=dh/htime),
                    'R':dict(time=rtime,cost=round(1.2*rtime+1.5,2),beta=0),
                    'J':dict(time=jtime,cost=round(1.5*jtime+2,2),beta=dj/jtime)}
        modes={preferred:candidates[preferred]}
        for mode in ('H','R','J'):
            probability={'sparse':.15,'mixed':.55,'rich':1.0}[mode_profile]
            if mode!=preferred and rng.random()<probability:
                modes[mode]=candidates[mode]
        margin=rng.uniform(6,18) if rng.random()>.2 else -rng.uniform(1,5)
        task_bank.append(dict(id=str(i+1),value=round(candidates[preferred]['cost']+margin,2),
                              weight=rng.randint(1,4),modes=modes))
        witness_modes.append(preferred)
    # Fixed latent random scores; only within-line forward arcs are retained.
    scores={(i,j):rng.random() for i in range(count) for j in range(i+1,count)}
    out=[]; witnesses=[]; offset=0
    total_stations=total_stations or sum(math.ceil((count//lines+(l<count%lines))/3) for l in range(lines))
    for l in range(lines):
        length=count//lines+int(l<count%lines)
        k=total_stations//lines+int(l<total_stations%lines)
        if k<1 or length<1: raise ValueError('Need at least one task and station per line')
        tasks=copy.deepcopy(task_bank[offset:offset+length]); groups=[[] for _ in range(k)]
        for rank,task in enumerate(tasks):
            s=min(k-1,rank*k//length)
            groups[s].append((task['id'],witness_modes[offset+rank]))
        edges=[]
        for i in range(offset,offset+length):
            for j in range(i+1,offset+length):
                include=(j==i+1 if graph=='chain' else
                         scores[i,j]<(.22 if graph=='dense' else .12) and (j-i<=6 if graph=='layered' else True))
                if include: edges.append([str(i+1),str(j+1)])
        # Constant across a fixed-total family; witness groups contain at most 4
        # tasks for the standard 60-task/20-station L=1,2,3,5 design.
        cycle=20 if total_tasks is not None else cycle_time
        line=dict(id=f'L{l+1}',cycle_time=cycle,fatigue_limit=fatigue,
                  stations=[dict(fixed_cost=6,human_cost=3,robot_cost=4) for _ in range(k)],
                  tasks=tasks,precedence=edges,
                  required_tasks=[t['id'] for t in tasks[:max(1,round(.2*length))]],
                  min_recovery=math.ceil(.35*sum(t['weight'] for t in tasks)))
        for s,group in enumerate(groups,1):
            # Check at the strictest standard fatigue threshold. 4-task fixed-total
            # groups can exceed it; their baseline F=.6 witness is checked instead.
            make_column(line,s,group)
        out.append(line);witnesses.append(groups);offset+=length
    h=r=0
    for line,groups in zip(out,witnesses):
        for s,group in enumerate(groups,1):
            col=make_column(line,s,group);h+=col.human;r+=col.robot
    data=dict(name=f'synthetic_{count}_L{lines}_seed{seed}',human_limit=h,robot_limit=r,lines=out)
    compact.validate_data(data)
    return data, dict(witness=witnesses,witness_humans=h,witness_robots=r,
                      generator_version='witness-paired-v2.1',required_ratio_target=.2,
                      recovery_fraction=.35,graph=graph,mode_profile=mode_profile,
                      generation_seed=seed,base_task_parameter_hash=digest(task_bank))


def metadata(data):
    tasks=[t for l in data['lines'] for t in l['tasks']]
    possible=sum(len(l['tasks'])*(len(l['tasks'])-1)/2 for l in data['lines'])
    edges=sum(len(l.get('precedence',[])) for l in data['lines'])
    return dict(lines=len(data['lines']),total_tasks=len(tasks),total_stations=sum(len(l['stations']) for l in data['lines']),
                precedence_edges=edges,precedence_density=edges/possible if possible else 0,
                mode_counts={m:sum(m in t['modes'] for t in tasks) for m in ('H','R','J')},
                fatigue_limit=[l['fatigue_limit'] for l in data['lines']],
                cycle_time=[l['cycle_time'] for l in data['lines']],human_limit=data['human_limit'],robot_limit=data['robot_limit'],
                required_ratio=sum(len(l.get('required_tasks',[])) for l in data['lines'])/len(tasks),
                min_recovery=[l.get('min_recovery',0) for l in data['lines']],input_sha256=digest(data))


def specifications(config):
    seeds=config['seeds']; design=config['design']
    if design=='stage_a':
        for seed in seeds: yield dict(group='correctness',seed=seed,n=3,lines=1,factor='n3')
        yield dict(group='correctness',seed=seeds[0],n=3,lines=2,factor='L2')
        return
    for seed in seeds:
        for n in config['sizes']: yield dict(group='B1',seed=seed,n=n,lines=config.get('size_lines',1),factor=n)
        for l in config['line_counts']:
            yield dict(group='B2_per_line',seed=seed,n=config['base_n'],lines=l,factor=l)
            yield dict(group='B2_fixed_total',seed=seed,n=config['base_n'],lines=l,factor=l,
                       total_tasks=config['fixed_total_tasks'],total_stations=config['fixed_total_stations'])
        for f in config['fatigue_levels']: yield dict(group='B3',seed=seed,n=config['base_n'],lines=2,factor=f,fatigue=f)
        for level in config.get('resource_levels',('ample','medium','tight')): yield dict(group='B4',seed=seed,n=config['base_n'],lines=2,factor=level)
        for profile in config.get('mode_profiles',[]): yield dict(group='C_modes',seed=seed,n=config['base_n'],lines=2,factor=profile,mode_profile=profile)
        for graph in config.get('graph_profiles',[]): yield dict(group='C_graph',seed=seed,n=config['base_n'],lines=2,factor=graph,graph=graph)


def write_suite(config, destination):
    destination.mkdir(parents=True,exist_ok=False)
    manifest=[]
    for spec in specifications(config):
        factor=spec['factor']; base={k:v for k,v in spec.items() if k in ('n','lines','seed','total_tasks','total_stations','mode_profile','graph')}
        base['cycle_time']=config.get('cycle_time',15)
        # Generate all fatigue twins against the same baseline first; alter only F.
        data,meta=generate(**base)
        witness_preserved=True
        if spec['group']=='B3':
            for line in data['lines']: line['fatigue_limit']=spec['fatigue']
            try:
                for line,groups in zip(data['lines'],meta['witness']):
                    for s,group in enumerate(groups,1): make_column(line,s,group)
            except ValueError: witness_preserved=False
        if spec['group']=='B4':
            scale={'ample':1.25,'medium':1,'tight':.8}[factor]
            stations=sum(len(l['stations']) for l in data['lines'])
            rounding=math.floor if factor=='tight' else math.ceil
            data['human_limit']=min(stations,rounding(meta['witness_humans']*scale))
            data['robot_limit']=min(stations,rounding(meta['witness_robots']*scale))
            witness_preserved=scale>=1
        if spec['group']=='B2_fixed_total':
            data['human_limit']=data['robot_limit']=math.ceil(.8*spec['total_stations'])
            witness_preserved=data['human_limit']>=meta['witness_humans'] and data['robot_limit']>=meta['witness_robots']
        compact.validate_data(data)
        name=f"{spec['group']}_{factor}_s{spec['seed']}"
        path=destination/(name+'.json');path.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
        manifest.append(dict(instance_id=name,group=spec['group'],factor=factor,seed=spec['seed'],
                             instance=path.name,metadata=metadata(data),generation=meta,
                             witness_preserved=witness_preserved,planned_infeasible=False))
    if config.get('include_infeasible'):
        data,meta=generate(n=3,lines=1,seed=config['seeds'][0]);data['human_limit']=data['robot_limit']=0
        name='planned_infeasible';(destination/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
        manifest.append(dict(instance_id=name,group='infeasible_control',factor='zero_resources',seed=config['seeds'][0],
                             instance=name+'.json',metadata=metadata(data),generation=meta,witness_preserved=False,planned_infeasible=True))
    if config['design']=='stage_a':
        for name in ('single_line','two_lines'):
            data=json.loads((ROOT/'code/milp/examples'/(name+'.json')).read_text())
            (destination/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf-8')
            manifest.append(dict(instance_id=name,group='reference',factor=name,seed=0,instance=name+'.json',metadata=metadata(data),
                                 generation={'source':'original synthetic reference'},witness_preserved=False,planned_infeasible=False))
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();manifest=write_suite(json.loads(args.config.read_text()),args.out)
    print(f'Generated {len(manifest)} instances; discarded=0 (generation errors are fatal).')
