"""Incremental RMP evidence: costs, paired completion speedups and censoring.

Figure contract: quantify measured engineering changes, without assuming speedup.
Separate single-panel quantitative plots, 183 x 100 mm; median/IQR across seeds.
All attempts remain in time summaries; exact speedups require both arms complete.
Python/matplotlib only; editable SVG/PDF and 600 dpi PNG, source CSV included.
"""
import argparse
import json
from pathlib import Path
import shutil
import statistics

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze_results import quantile
from plot_results import panel,COLORS,require_matplotlib_panel_alignment

plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],
                    'font.size':8,'svg.fonttype':'none','pdf.fonttype':42,'savefig.dpi':600})


def export(fig,ax,out,name):
    handles,labels=ax.get_legend_handles_labels()
    if handles:ax.legend(handles,labels,loc='upper left',bbox_to_anchor=(1.03,1),borderaxespad=0)
    fig.canvas.draw()
    if require_matplotlib_panel_alignment:
        require_matplotlib_panel_alignment(fig,json_out=out/(name+'.alignment.json'))
    fig.savefig(out/(name+'.svg'))
    fig.savefig(out/(name+'.pdf'))
    fig.savefig(out/(name+'.png'),dpi=600)
    plt.close(fig)


def draw(run):
    rows=json.loads((run/'summary.json').read_text())
    checks=json.loads((run/'paired_checks.json').read_text())
    out=run/'figures';out.mkdir(exist_ok=True)
    shutil.copy2(run/'summary.csv',out/'source_data.csv')
    sizes=sorted({r['n'] for r in rows})
    fig,ax=panel('Observed root time: CPLEX, 1 thread, 120 s budget',
                 'Tasks per line (2 lines)','Wall time (s; median and IQR)')
    for v,c,offset in zip(('V0','V1'),COLORS,(-.7,.7)):
        med=[];lo=[];hi=[]
        for n in sizes:
            vals=[r['wall_time'] for r in rows if r['n']==n and r['version']==v]
            m=statistics.median(vals);med.append(m);lo.append(m-quantile(vals,.25));hi.append(quantile(vals,.75)-m)
        ax.errorbar(np.array(sizes)+offset,med,yerr=[lo,hi],color=c,marker='o',capsize=3,label=v)
    ax.axhline(120,color='#B0B0B0',ls='--',lw=.7);ax.set_xticks(sizes);ax.set_ylim(0,132)
    note='LP completed (5 seeds): '+'; '.join(f"{n}: "+', '.join(v+' '+str(sum(r['converged'] for r in rows if r['n']==n and r['version']==v)) for v in ('V0','V1')) for n in sizes)
    fig.text(.12,.025,note,fontsize=6)
    export(fig,ax,out,'01_root_time')

    # Means sum exactly; medians of separate components generally do not.
    fig,ax=panel('Non-overlapping root time components: mean across 5 seeds',
                 'Tasks per line / version','Wall time (s; including truncated runs)')
    groups=[(n,v) for n in sizes for v in ('V0','V1')];x=np.arange(len(groups));bottom=np.zeros(len(groups))
    components=[('rmp_build_time','RMP build / append','#4378A1'),
                ('rmp_conversion_time','RMP full translation','#839BAE'),
                ('rmp_native_time','RMP native solve','#B88940'),
                ('pp_time','Exact pricing (PP)','#8B8E96'),
                ('residual','Readback / other','#D1D5DA')]
    for field,label,color in components:
        means=[]
        for n,v in groups:
            selected=[r for r in rows if r['n']==n and r['version']==v]
            vals=[r[field] if field!='residual' else r['wall_time']-sum(r[k] for k in ('rmp_build_time','rmp_conversion_time','rmp_native_time','pp_time')) for r in selected]
            if min(vals)<-1e-6:raise ValueError('Overlapping time decomposition')
            means.append(statistics.mean(vals))
        ax.bar(x,means,bottom=bottom,label=label,color=color,width=.7);bottom+=means
    ax.set_xticks(x,[f'{n}\n{v}' for n,v in groups]);ax.set_ylim(0,135)
    fig.text(.12,.025,'Native append costs are in build / append; no full-model translation in V1.',fontsize=6)
    export(fig,ax,out,'02_time_components')

    fig,ax=panel('Phase times: median and IQR across 5 seeds',
                 'Tasks per line / version','Wall time (s; including truncated runs)')
    for j,(field,label) in enumerate((('phase1_time','Phase I'),('phase2_time','Phase II'))):
        med=[];low=[];high=[]
        for n,v in groups:
            vals=[r[field] for r in rows if r['n']==n and r['version']==v];m=statistics.median(vals)
            med.append(m);low.append(m-quantile(vals,.25));high.append(quantile(vals,.75)-m)
        ax.errorbar(x+(-.1 if j==0 else .1),med,yerr=[low,high],marker='o',linestyle='none',capsize=3,color=COLORS[j],label=label)
    ax.set_xticks(x,[f'{n}\n{v}' for n,v in groups]);ax.set_ylim(bottom=0)
    export(fig,ax,out,'03_phase_times')

    fig,ax=panel('Paired root-time speedup: exact values and censoring',
                 'Tasks per line (2 lines)','Time ratio V0 / V1')
    for n in sizes:
        group=[c for c in checks if c['n']==n]
        for c in group:
            offset=([11,21,31,41,51].index(c['seed'])-2)*.8
            if c['speedup'] is not None:
                ax.scatter(n+offset,c['speedup'],s=20,color=COLORS[0],label='Both completed' if not any(t.get_label()=='Both completed' for t in ax.collections) else None)
            elif c['lower_bound'] is not None:
                ax.scatter(n+offset,c['lower_bound'],marker='^',s=25,facecolors='none',edgecolors=COLORS[2],label='Lower bound (V0 timeout)' if not any(t.get_label()=='Lower bound (V0 timeout)' for t in ax.collections) else None)
    ax.axhline(1,color='#B0B0B0',ls='--',lw=.7);ax.set_xticks(sizes);ax.margins(x=.15,y=.15)
    counts='No exact ratio when censored: '+'; '.join(f"{n}: {sum(c['n']==n and c['speedup'] is None for c in checks)}/5 pairs" for n in sizes)
    fig.text(.12,.025,counts,fontsize=6)
    export(fig,ax,out,'04_paired_speedup')
    (out/'FIGURE_QA_NOTES.json').write_text(json.dumps(dict(backend='python',archetype='quantitative single panels',
        samples='5 independent instance seeds; matched version pairs',runtime='median/IQR including censored observed runtime',
        components='arithmetic mean, so component means add to mean total',speedup='both completed only; timeout lower bounds shown separately',
        excluded_raw_observations=0,formats=['pdf','svg','png'],width_mm=183,height_mm=100),indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args();draw(a.run)
