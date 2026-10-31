"""Measured PP reuse: paired runtime, component attribution and LP convergence.

Figure contract: compare V1/V2 without presuming faster integer optimization.
Single-panel quantitative figures, 183 x 100 mm; editable PDF/SVG and PNG preview.
All timed-out observations retained; median/IQR across instance seeds for root
time, across dependent saved calls for descriptive per-call distributions only.
"""
import argparse
import json
from pathlib import Path
import shutil
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from analyze_results import quantile
from plot_results import panel,require_matplotlib_panel_alignment

plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],
                    'font.size':8,'svg.fonttype':'none','pdf.fonttype':42,'savefig.dpi':600})
COLORS=['#8B8E96','#4378A1']


def export(fig,ax,out,name):
    handles,labels=ax.get_legend_handles_labels()
    if handles:ax.legend(handles,labels,loc='upper left',bbox_to_anchor=(1.03,1),borderaxespad=0)
    fig.canvas.draw()
    if require_matplotlib_panel_alignment:require_matplotlib_panel_alignment(fig,json_out=out/(name+'.alignment.json'))
    fig.savefig(out/(name+'.pdf'));fig.savefig(out/(name+'.svg'));fig.savefig(out/(name+'.png'),dpi=600)
    plt.close(fig)


def plot(analysis,replay):
    rows=json.loads((analysis/'per_instance.json').read_text());calls=json.loads((replay/'calls.json').read_text())
    out=analysis/'figures';out.mkdir(exist_ok=True)
    shutil.copy2(analysis/'per_instance.csv',out/'root_source_data.csv')
    shutil.copy2(analysis/'fixed_dual_pp_statistics.csv',out/'pp_source_data.csv')
    for budget in sorted({r['budget'] for r in rows}):
        selected=[r for r in rows if r['budget']==budget];sizes=sorted({r['n'] for r in selected})
        fig,ax=panel(f'Observed root time: {budget} s budget, CPLEX, 1 thread',
                     'Tasks per line (2 lines)','Wall time (s; median and IQR)')
        notes=[]
        for version,color,offset in zip(('V1','V2'),COLORS,(-.6,.6)):
            centers=[];low=[];high=[]
            for n in sizes:
                group=[r for r in selected if r['version']==version and r['n']==n];vals=[r['wall_time'] for r in group]
                m=statistics.median(vals);centers.append(m);low.append(m-quantile(vals,.25));high.append(quantile(vals,.75)-m)
                notes.append(f"{n} {version}: {sum(r['converged'] for r in group)}/{len(group)}")
            ax.errorbar(np.array(sizes)+offset,centers,yerr=[low,high],marker='o',capsize=3,color=color,label=version)
        ax.axhline(budget,color='#B0B0B0',ls='--',lw=.7);ax.set_xticks(sizes);ax.set_ylim(0,budget*1.1)
        fig.text(.12,.025,'LP completed: '+'; '.join(notes),fontsize=6)
        export(fig,ax,out,f'root_time_{budget}')

        fig,ax=panel(f'Root cost components: {budget} s budget, arithmetic means',
                     'Tasks per line / version','Wall time (s; including censored runs)')
        groups=[(n,v) for n in sizes for v in ('V1','V2')];x=np.arange(len(groups));bottom=np.zeros(len(groups))
        components=[('RMP (complete)','#B88940',lambda r:r['rmp_build_time']+r['rmp_interface_time']),
                    ('PP build / API / update','#839BAE',lambda r:sum(r[k] for k in ('pp_build_time','pp_native_creation_time','pp_translation_time','pp_objective_update_time'))),
                    ('PP native MIP','#4378A1',lambda r:r['pp_native_time']),
                    ('PP readback / other','#8B8E96',lambda r:r['pp_other_time']),
                    ('Root other','#D1D5DA',lambda r:r['other_time'])]
        for label,color,fn in components:
            values=[statistics.mean(fn(r) for r in selected if (r['n'],r['version'])==(n,v)) for n,v in groups]
            if min(values)<-1e-6:raise ValueError('Overlapping root time intervals')
            ax.bar(x,values,bottom=bottom,color=color,label=label,width=.7);bottom+=values
        ax.set_xticks(x,[f'{n}\n{v}' for n,v in groups]);ax.set_ylim(0,budget*1.15)
        fig.text(.12,.025,'Non-overlapping components; first native PP creation included.',fontsize=6)
        export(fig,ax,out,f'root_components_{budget}')

    sizes=sorted({r['n'] for r in calls})
    fig,ax=panel('Fixed-dual PP calls: descriptive median and IQR',
                 'Tasks per line (2 lines)','PP call wall time (ms)')
    for version,color,offset in zip(('V1','V2'),COLORS,(-.6,.6)):
        med=[];low=[];high=[]
        for n in sizes:
            vals=[1000*r[version+'_time'] for r in calls if r['n']==n];m=statistics.median(vals)
            med.append(m);low.append(m-quantile(vals,.25));high.append(quantile(vals,.75)-m)
        ax.errorbar(np.array(sizes)+offset,med,yerr=[low,high],marker='o',capsize=3,color=color,label=version)
    ax.set_xticks(sizes);ax.set_ylim(bottom=0)
    fig.text(.12,.025,'One saved complete seed-11 history per size; calls are dependent, not independent replicates.',fontsize=6)
    export(fig,ax,out,'fixed_dual_pp_time')

    fig,ax=panel('Fixed-dual PP cost components: arithmetic mean per call',
                 'Tasks per line / version','PP call wall time (ms)')
    groups=[(n,v) for n in sizes for v in ('V1','V2')];x=np.arange(len(groups));bottom=np.zeros(len(groups))
    labels=['Python structure','Create / translate','Objective update','Native MIP','Readback / other']
    colors=['#4378A1','#839BAE','#B88940','#8B8E96','#D1D5DA']
    for index,(label,color) in enumerate(zip(labels,colors)):
        values=[]
        for n,v in groups:
            group=[r for r in calls if r['n']==n]
            if v=='V1':fn=lambda r:[r['V1_build'],r['V1_translation'],0.,r['V1_native'],r['V1_other']][index]
            else:fn=lambda r:[r['V2_build'],r['V2_native_creation'],r['V2_update'],r['V2_native'],r['V2_other']][index]
            values.append(1000*statistics.mean(fn(r) for r in group))
        ax.bar(x,values,bottom=bottom,color=color,label=label,width=.7);bottom+=values
    ax.set_xticks(x,[f'{n}\n{v}' for n,v in groups]);ax.set_ylim(bottom=0)
    fig.text(.12,.025,'V1 objective assembly is in structure; V2 first creation is amortized over all calls.',fontsize=6)
    export(fig,ax,out,'fixed_dual_pp_components')

    representative=[r for r in rows if r['budget']==300 and r['instance_id']=='B1_40_s11']
    if len(representative)==2:
        fig,ax=panel('LP bounds: 40 tasks per line, seed 11, 300 s budget',
                     'Elapsed root wall time (s)','DW-LP net profit (model units)')
        for r,color in zip(sorted(representative,key=lambda r:r['version']),COLORS):
            raw=json.loads((Path(r['run'])/'raw'/(r['instance_id']+'_'+r['version']+'.json')).read_text())
            history=[h for h in raw['rounds'] if h['phase']==2]
            ax.step([h['wall_time'] for h in history],[h['objective'] for h in history],where='post',color=color,ls='--',label=r['version']+' RMP lower')
            priced=[h for h in history if h['complete_pricing']]
            ax.step([h['wall_time'] for h in priced],np.minimum.accumulate([h['upper_bound'] for h in priced]),where='post',color=color,label=r['version']+' valid upper')
        ax.set_xlim(0,300)
        fig.text(.12,.025,'Upper bounds require complete exact pricing; lower bounds include solved RMPs.',fontsize=6)
        export(fig,ax,out,'representative_lp_bounds')
    (out/'FIGURE_QA_NOTES.json').write_text(json.dumps(dict(backend='python',width_mm=183,height_mm=100,
        root_statistics='Median/IQR across paired instance seeds; censored observed wall times retained.',
        PP_statistics='Descriptive median/IQR across all dependent calls of selected complete histories.',
        components='Arithmetic means of non-overlapping intervals; no uncertainty inference.',
        convergence='Single actual trajectory per version; no uncertainty, smoothing or fabricated completion points.',
        exclusions='No failed/timed-out root runs dropped. Invalid/incomplete pricing rounds do not define an upper bound.',
        formats=['pdf','svg','png']),indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('analysis',type=Path);p.add_argument('--replay',type=Path,required=True)
    a=p.parse_args();plot(a.analysis,a.replay)
