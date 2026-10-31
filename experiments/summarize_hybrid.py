"""Summarize completed runs; event curves use only timestamped certified events."""
import csv,json,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path('experiments/runs/hybrid_large_01');baseline=Path('experiments/runs/large_120_150_600_01/raw');rows=[];events=[]
for n in (120,150):
    key=f'total{n}_L2_s11';ip=json.loads((baseline/(key+'_ip.json')).read_text());cg=json.loads((baseline/(key+'_cg.json')).read_text())
    for mode in ('direct','cg','hybrid60','hybrid120','hybrid180'):
        if mode=='direct':
            lb=ip['incumbent'];ub=ip['best_bound'];status=ip['status'];elapsed=ip['wall_time'];rmp=pp=cols=None
            events.append(dict(tasks=n,method=mode,time=elapsed,lower=lb,upper=ub,source='MIP result'))
        elif mode=='cg':
            lb=None;ub=cg['upper_bound'];status=cg['status'];elapsed=cg['wall_time'];rmp=cg['rmp_interface_time'];pp=cg['pp_time'];cols=cg['columns']
            for x in cg['rounds']:
                if x['phase']==2 and x['complete_pricing']:events.append(dict(tasks=n,method=mode,time=x['wall_time'],lower=None,upper=x['upper_bound'],source='completed exact pricing round'))
        else:
            path=root/f'n{n}_{mode}'/'result.json'
            if not path.exists():
                rows.append(dict(tasks=n,method=mode,status='not_completed'));continue
            x=json.loads(path.read_text());lb=x['integer_lower_bound'];ub=x['upper_bound'];status=x['cg_status'];elapsed=x['wall_time']; c=x['cg'];rmp=c['rmp_interface_time'] if c else None;pp=c['pp_time'] if c else None;cols=c['columns'] if c else None
            events.append(dict(tasks=n,method=mode,time=x['mip_elapsed'],lower=lb,upper=x['mip']['best_bound'],source='MIP phase completed'))
            if c:
                for z in c['rounds']:
                    if z['phase']==2 and z['complete_pricing']:events.append(dict(tasks=n,method=mode,time=x['mip_elapsed']+x['conversion_elapsed']+z['wall_time'],lower=None,upper=z['upper_bound'],source='completed exact pricing round'))
        rows.append(dict(tasks=n,method=mode,status=status,integer_profit=lb,upper=ub,gap=(ub-lb)/abs(lb) if lb not in (None,0) and ub is not None else None,wall_time=elapsed,rmp_time=rmp,pp_time=pp,columns=cols))
def save(name,items,fields):
    with (root/name).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(items)
save('summary.csv',rows,['tasks','method','status','integer_profit','upper','gap','wall_time','rmp_time','pp_time','columns'])
save('bound_events.csv',events,['tasks','method','time','lower','upper','source'])
for n in (120,150):
    for metric in ('lower','upper','gap'):
        fig,ax=plt.subplots(figsize=(7,4))
        for mode in ('direct','cg','hybrid60','hybrid120','hybrid180'):
            es=sorted((e for e in events if e['tasks']==n and e['method']==mode),key=lambda e:e['time']);lo=None;up=None;xs=[];ys=[]
            for e in es:
                if e['lower'] is not None:lo=e['lower'] if lo is None else max(lo,e['lower'])
                if e['upper'] is not None:up=e['upper'] if up is None else min(up,e['upper'])
                y=lo if metric=='lower' else up if metric=='upper' else (up-lo)/abs(lo) if lo not in (None,0) and up is not None else None
                if y is not None:xs.append(e['time']);ys.append(y)
            if xs:ax.step(xs,ys,where='post',label=mode);ax.scatter(xs,ys,s=5)
        ax.set_xlabel('Wall time (s)');ax.set_ylabel({'lower':'Integer feasible profit','upper':'Certified upper bound','gap':'Relative integer gap'}[metric]);ax.set_title(f'{n} tasks; observed certificate events');ax.legend();fig.tight_layout()
        for ext in ('pdf','png'):fig.savefig(root/f'{n}_{metric}.{ext}',dpi=200)
        plt.close(fig)
