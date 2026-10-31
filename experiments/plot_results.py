"""Reproducible quantitative plots: median/IQR, all observed runtimes retained.

Figure contract: compare cost and bound strength of distinct solve targets;
describe the measured pilot, without a speed-superiority or RL-benefit claim.
Archetype: separate single-panel quantitative comparisons at 183 mm width.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from analyze_results import analyze,quantile

SKILL=Path('C:/Users/Hrychang/.codex/skills/nature-figure/scripts')
if SKILL.exists():sys.path.insert(0,str(SKILL))
try:from audit_panel_alignment import require_matplotlib_panel_alignment
except ImportError:require_matplotlib_panel_alignment=None

plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],
    'font.size':8,'axes.titlesize':9,'axes.labelsize':8,'xtick.labelsize':8,'ytick.labelsize':8,
    'legend.fontsize':8,'legend.frameon':False,'axes.spines.top':False,'axes.spines.right':False,
    'svg.fonttype':'none','pdf.fonttype':42,'savefig.dpi':600})
COLORS=['#4378A1','#8B8E96','#B88940','#A7BAC9']


def panel(title,xlabel,ylabel):
    fig,ax=plt.subplots(figsize=(7.2047244,3.9370079))  # 183 x 100 mm
    fig.subplots_adjust(left=.12,right=.70,bottom=.18,top=.82)
    fig.suptitle(title,y=.95,fontsize=9)
    ax.set(xlabel=xlabel,ylabel=ylabel)
    return fig,ax


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


def trend(rows,group,series,title,xlabel,ylabel,out,name,categorical=False,log=False):
    subset=[r for r in rows if r['group']==group]
    if not subset:return
    factors=sorted({r['factor'] for r in subset},key=lambda x: {'tight':0,'medium':1,'ample':2}.get(x,x))
    fig,ax=panel(title,xlabel,ylabel)
    availability={str(f):[] for f in factors}
    for index,(field,label) in enumerate(series):
        x=[];med=[];low=[];high=[]
        for i,factor in enumerate(factors):
            values=[r[field] for r in subset if r['factor']==factor and r.get(field) is not None]
            availability[str(factor)].append(len(values))
            if not values:continue
            if log and any(value <= 0 for value in values):
                raise ValueError('Log-time plots require strictly positive observations')
            center=statistics.median(values);x.append(i if categorical else float(factor));med.append(center)
            low.append(center-quantile(values,.25));high.append(quantile(values,.75)-center)
        if med:ax.errorbar(x,med,yerr=[low,high],marker='o',markersize=3,capsize=3,color=COLORS[index%len(COLORS)],label=label)
    if categorical:ax.set_xticks(range(len(factors)),[str(f) for f in factors])
    else:ax.set_xticks([float(f) for f in factors])
    if log:ax.set_yscale('log')
    ax.margins(x=.1,y=.18)
    note='Available values (legend order): '+'; '.join(f'{f}: '+','.join(map(str,counts)) for f,counts in availability.items())
    fig.text(.12,.025,note,fontsize=6)
    export(fig,ax,out,name)


def plot(run):
    rows,stats,audit=analyze(run);out=run/'figures';out.mkdir(exist_ok=True)
    shutil.copy2(run/'analysis/enriched_summary.csv',out/'source_data.csv')
    trend(rows,'B1',[('cg_wall_time','CG root LP'),('compact_lp_wall_time','Compact LP'),('milp_wall_time','Compact IP')],
          'Observed wall time: CPLEX, 1 thread, 5 seeds (median and IQR)',
          'Tasks per line','Wall time (s; different solve targets)',out,'01_size_runtime',log=True)
    trend(rows,'B1',[('cg_iterations','CG iterations')],'CG iterations: median and IQR across 5 seeds',
          'Tasks per line','RMP solves (count)',out,'03_size_iterations')
    trend(rows,'B1',[('columns_generated','Stored columns')],'Column pool size: median and IQR across 5 seeds',
          'Tasks per line','Columns (including empty patterns)',out,'04_size_columns')
    trend(rows,'B3',[('cg_lp_obj','CG root LP'),('milp_incumbent','Compact IP')],'Fatigue treatment: paired inputs, median and IQR',
          'Maximum fatigue level (synthetic)','Net profit (model units)',out,'06_fatigue_profit')
    trend(rows,'B3',[('lp_humans','Workers'),('lp_robots','Robots')],'Fatigue treatment: fractional root-LP resource use',
          'Maximum fatigue level (synthetic)','Resources (fractional LP count)',out,'07_fatigue_resources')
    trend(rows,'B3',[('cg_wall_time','CG root LP')],'Fatigue treatment: median and IQR across 5 seeds',
          'Maximum fatigue level (synthetic)','Root wall time (s)',out,'08_fatigue_time')
    trend(rows,'B4',[('cg_lp_obj','CG root LP'),('milp_incumbent','Compact IP')],'Resource budgets: paired inputs, median and IQR',
          'Resource availability','Net profit (model units)',out,'09_resource_profit',categorical=True)
    trend(rows,'B4',[('cg_wall_time','CG root LP')],'Resource budgets: median and IQR across 5 seeds',
          'Resource availability','Root wall time (s)',out,'10_resource_time',categorical=True)
    trend(rows,'B1',[('relaxation_bound_improvement','Compact LP - DW LP')],'Relaxation bound tightening (maximization)',
          'Tasks per line','Upper-bound decrease (profit units)',out,'11_bound_strength')
    trend(rows,'B2_per_line',[('cg_wall_time','CG root LP')],'Line count: fixed tasks per line, median and IQR',
          'Disassembly lines','Root wall time (s)',out,'12_lines_per_line')
    trend(rows,'B2_fixed_total',[('cg_wall_time','CG root LP')],'Line count: fixed total tasks/stations/budgets',
          'Disassembly lines','Root wall time (s)',out,'13_lines_fixed_total')
    trend(rows,'B3',[('enumerated_local_columns_total','Feasible patterns')],'Fatigue changes the local integer pattern set',
          'Maximum fatigue level (synthetic)','Enumerated patterns (all station blocks)',out,'14_fatigue_patterns')
    # Show within-seed changes as well as marginal profit levels. The latter can
    # hide small treatment effects behind large differences between instances.
    for group,baseline,name in [('B3',.4,'06b_fatigue_paired_gain'),('B4','tight','09b_resource_paired_gain')]:
        paired=[dict(r) for r in rows if r['group']==group]
        if not paired:continue
        anchors={r['seed']:r for r in paired if r['factor']==baseline}
        for r in paired:
            for field in ('cg_lp_obj','milp_incumbent'):
                a=anchors.get(r['seed'],{}).get(field);b=r.get(field)
                r[field+'_gain']=b-a if a is not None and b is not None else None
        trend(paired,group,[('cg_lp_obj_gain','CG root LP gain'),('milp_incumbent_gain','Compact IP gain')],
              'Within-seed profit change: median and IQR (5 matched inputs)',
              'Maximum fatigue level' if group=='B3' else 'Resource availability',
              'Profit change from strict / tight control',out,name,categorical=group=='B4')
    # Component shares and phase shares are separate figures: Phase I includes PP
    # and RMP work and must never be stacked alongside those components.
    subset=[r for r in rows if r['group']=='B1'];factors=sorted({r['factor'] for r in subset})
    for name,title,fields in [
        ('02_root_components','Nonoverlapping root components: mean per-run shares',
         [('pricing_wall_time','PP call wall'),('rmp_solve_time','RMP solve interface'),('rmp_build_time','RMP build'),('cg_other_time','Other root work')]),
        ('02b_root_phases','Root phases: mean per-run shares',
         [('phase1_wall_time','Phase I'),('phase2_wall_time','Phase II')])]:
        fig,ax=panel(title,'Tasks per line','Root wall time (%)');bottom=np.zeros(len(factors))
        for index,(field,label) in enumerate(fields):
            share=[100*statistics.mean(r[field]/r['cg_wall_time'] for r in subset if r['factor']==factor) for factor in factors]
            ax.bar(range(len(factors)),share,bottom=bottom,color=COLORS[index],label=label,width=.55);bottom+=share
        ax.set_xticks(range(len(factors)),[str(f) for f in factors]);ax.set_ylim(0,105)
        export(fig,ax,out,name)
    # Representative is predefined by ID, not selected for a visually favourable curve.
    representative=next((r for r in rows if r['group']=='B1' and r['factor']==10 and r['seed']==11),None)
    if representative:
        raw=json.loads((run/'raw'/(representative['instance_id']+'__'+representative['solver_combo']+'.json')).read_text())
        history=[h for h in raw['cg']['history'] if h['phase']==2]
        fig,ax=panel(f"Representative: n=10, L={representative['lines']}, seed=11 (Phase II only)",'Phase II iteration','Full-column LP objective / bound')
        ax.plot([h['iteration'] for h in history],[h['objective'] for h in history],color=COLORS[0],label='RMP objective')
        ax.plot([h['iteration'] for h in history],[h['lp_upper_bound'] for h in history],color=COLORS[2],label='Repaired LP bound')
        ax.margins(y=.18);export(fig,ax,out,'05_convergence')
        fig,ax=panel('Representative exact pricing: Phase II progress','Phase II iteration','Maximum reduced cost (profit units)')
        ax.plot([h['iteration'] for h in history],[h['maximum_reduced_cost'] for h in history],color=COLORS[0])
        ax.margins(y=.18);export(fig,ax,out,'15_pricing_reduced_cost')
        fig,ax=panel('Representative columns added: Phase II progress','Phase II iteration','New columns (count)')
        ax.bar([h['iteration'] for h in history],[h['columns_added'] for h in history],color=COLORS[0])
        export(fig,ax,out,'16_columns_per_iteration')
        calls=[c for c in raw['pricing_calls'] if c['phase']==2]
        stations=sorted({(c['line'],c['station']) for c in calls})
        fig,ax=panel('Representative station PP cost: Phase II call distribution','PP call wall time (s)','Station')
        ax.boxplot([[c['wall_time'] for c in calls if (c['line'],c['station'])==station] for station in stations],
                   vert=False,tick_labels=[f'{l} S{s}' for l,s in stations],showfliers=True)
        fig.text(.12,.025,'Boxes: Q1-Q3; line: median; whiskers: 1.5 IQR. Calls are not independent replicates.',fontsize=6)
        export(fig,ax,out,'17_station_pricing_cost')
    contract=dict(archetype='single-panel quantitative comparisons',backend='python/matplotlib',
        source_rows=len(rows),excluded_rows=0,summary='Median and IQR; time charts retain observed completed and censored attempts. Status counts are in analysis tables.',
        n='5 distinct generation seeds per factor level; control inputs reused across families are not pooled.',
        interpretation='Pilot only; compact IP and root LP are different solve targets. No significance test or superiority claim.',
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'FIGURE_CONTRACT.json').write_text(json.dumps(contract,indent=2),encoding='utf-8')
    print(f'Wrote {len(list(out.glob("*.pdf")))} PDFs with SVG and PNG counterparts to {out}')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run',type=Path);args=parser.parse_args();plot(args.run)
