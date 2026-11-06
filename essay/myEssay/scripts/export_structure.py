import json
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
rows=json.loads((HERE/'data/structure.json').read_bytes());out=[]
for batch,name in sorted({(r['batch'],r['case']) for r in rows}):
    a=next(r for r in rows if r['batch']==batch and r['case']==name and r['method']=='compact_plain');b=next(r for r in rows if r['batch']==batch and r['case']==name and r['method']=='balanced_bound')
    group='Ample' if '_ample_' in name else 'Conflict';budget=120 if batch=='pilot120' else 600
    out.append(f"{budget} & {a['lines']} & {group} & {a['lb']:.2f} & {a['ub']:.2f} & {a['seconds']:.2f} & {b['lb']:.2f} & {b['ub']:.2f} & {b['seconds']:.2f} & {'Yes' if b['proven'] else 'No'}"+r'\\')
s=r'''\begin{table*}[!t]
\caption{Complete Compact/Decomposition Structure Pairs at 80 Total Tasks, Seed 31}\label{tab:structure}\centering\small
\begin{tabular}{rllrrrrrrl}\toprule
Budget (s)&Lines&Resources&\multicolumn{3}{c}{Compact CPLEX}&\multicolumn{4}{c}{Whole-line framework}\\\cmidrule(lr){4-6}\cmidrule(lr){7-10}
&&&LB&UB&Time (s)&LB&UB&Time (s)&Proven\\\midrule
'''+ '\n'.join(out)+r'''
\bottomrule\end{tabular}
\end{table*}
'''
(HERE/'tables/structure.tex').write_text(s)
print('Exported',len(out),'structure pairs')
