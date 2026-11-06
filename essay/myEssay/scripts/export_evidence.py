"""Build manuscript tables from frozen records. No optimization or data generation."""
import csv,hashlib,json,shutil,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
sources={}
def read(path):
    p=ROOT/path;raw=p.read_bytes();sources[str(path)]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
def table(path,caption,label,head,rows,spec,wide=False,foot=''):
    env='table*' if wide else 'table'
    s=f'\\begin{{{env}}}[!t]\n\\caption{{{caption}}}\\label{{{label}}}\\centering\\small\n'
    s+=f'\\begin{{tabular}}{{{spec}}}\\toprule\n'+head+r'\\\midrule'+'\n'
    s+='\n'.join(' & '.join(map(str,r))+r'\\' for r in rows)+'\n\\bottomrule\\end{tabular}\n'
    if foot:s+='\\par\\smallskip\\begin{minipage}{'+('\\textwidth' if wide else '\\columnwidth')+'}\\footnotesize '+foot+'\\end{minipage}\n'
    s+=f'\\end{{{env}}}\n';(HERE/path).write_text(s,encoding='utf-8')
def main():
    for name in ('data','tables','SFimg','photo','build'): (HERE/name).mkdir(exist_ok=True)
    formal=[r for r in read('sub/stage12/evidence/analysis/rows.json') if r['batch']=='formal600']
    robust=read('sub/stage13/evidence/analysis/diagnostics.json')
    structure=[r for r in read('sub/stage11/evidence/analysis/rows.json') if r['method'] in ('compact_plain','balanced_bound')]
    diag=[r for r in read('sub/stage12/evidence/analysis/diagnostics.json') if r['batch']=='formal600' and r['method']=='balanced_bound']
    selected=[('formal600',formal),('robust180',robust),('structure',structure)]
    for group,rows in selected:
        folder=HERE/'data'/group;folder.mkdir(exist_ok=True);out=[];hashes={}
        for r in rows:
            method=r['method'];name=r['case'];batch=r.get('batch','robust180');stage='stage12' if group=='formal600' else 'stage13' if group=='robust180' else 'stage11'
            base=Path(f'sub/{stage}/evidence/{batch}/{name}__{method}');raw=(ROOT/base/'instance.json').read_bytes();sha=hashlib.sha256(raw).hexdigest()
            assert name not in hashes or hashes[name]==sha;hashes[name]=sha;sources[str(base/'instance.json')]=sha
            (folder/(name+'.json')).write_bytes(raw)
            objpath=ROOT/base/'result.json.zlib';blob=objpath.read_bytes();sources[str(base/'result.json.zlib')]=hashlib.sha256(blob).hexdigest()
            obj=json.loads(zlib.decompress(blob));low=obj.get('global_lower_bound');up=obj.get('global_upper_bound')
            if low is not None:assert abs(low-r['lb'])<1e-5
            if up is not None:assert abs(up-r['ub'])<1e-5
            data=json.loads(raw);d=dict(r);d.update(total_tasks=sum(len(l['tasks']) for l in data['lines']),lines=len(data['lines']),
                stations=sum(len(l['stations']) for l in data['lines']),human_limit=data['human_limit'],robot_limit=data['robot_limit'],input_sha256=sha,
                source_certificate=str(base/'result.json.zlib'),certificate_sha256=sources[str(base/'result.json.zlib')]);out.append(d)
        (HERE/'data'/f'{group}.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
        keys=['case','method','total_tasks','lines','stations','human_limit','robot_limit','lb','ub','seconds','proven','input_sha256']
        with (HERE/'data'/f'{group}.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(out)
        if group=='formal600':F=out
        if group=='robust180':R=out
    frows=[]
    for name in sorted({r['case'] for r in F}):
        a=next(r for r in F if r['case']==name and r['method']=='compact_plain');b=next(r for r in F if r['case']==name and r['method']=='balanced_bound');seed=name[-2:]
        gap=100*max(0,a['ub']-a['lb'])/max(1,abs(a['lb']))
        frows.append([f"{a['total_tasks']}/{a['lines']}/{seed}",f"{a['lb']:.2f}",f"{a['ub']:.2f}",f'{gap:.2f}',f"{a['seconds']:.2f}",f"{b['lb']:.2f}",f"{b['ub']:.2f}",f"{b['seconds']:.2f}"])
    table('tables/formal.tex','Profit and Bounds Under the 600-Second Protocol','tab:formal',r'Instance $N/L$/seed & \multicolumn{4}{c}{Compact CPLEX} & \multicolumn{3}{c}{Whole-line framework}\\\cmidrule(lr){2-5}\cmidrule(lr){6-8}& LB & UB & Gap (\%) & Time (s) & LB & UB & Time (s)',frows,'lrrrrrrr',True,'The whole-line framework proves integer optimality in every listed row. Compact CPLEX remains time-limited and unproven. Times include required evidence persistence. Rounded equal bounds indicate closure within the recorded tolerances.')
    rrows=[]
    for name in sorted({r['case'] for r in R}):
        a=next(r for r in R if r['case']==name and r['method']=='compact_plain');b=next(r for r in R if r['case']==name and r['method']=='balanced_bound')
        rrows.append([f"{a['total_tasks']}/{a['lines']}/{name[-2:]}",f"{a['human_limit']}/{a['robot_limit']}",f"{a['lb']:.2f}",f"{a['ub']:.2f}",f"{a['seconds']:.2f}",f"{b['lb']:.2f}",f"{b['ub']:.2f}",f"{b['seconds']:.2f}",'Yes' if b['proven'] else 'No'])
    table('tables/robust.tex','Resource-Constrained and Large-Block Cases Under the 180-Second Protocol','tab:robust',r'Instance $N/L$/seed & $h^{\max}/r^{\max}$ & \multicolumn{3}{c}{Compact CPLEX} & \multicolumn{4}{c}{Whole-line framework}\\\cmidrule(lr){3-5}\cmidrule(lr){6-9}& & LB & UB & Time (s) & LB & UB & Time (s) & Proven',rrows,'llrrrrrrl',True,'The 120-task inputs use 80\% of calibrated independent resource use, rounded upward. The 80-task two-line row is the retained large-block boundary. Compact CPLEX is unproven in all four rows.')
    drows=[]
    for d in sorted(diag,key=lambda r:r['case']):
        drows.append([f"{d['total_tasks']}/{d['lines']}/{d['case'][-2:]}",d['phase1_pricing_rounds'],d['phase2_pricing_rounds'],d['pp_calls'],d['final_columns'],f"{d['timing']['PP_native_seconds']:.2f}",f"{d['timing']['RMP_native_seconds']:.4f}"])
    table('tables/iterations.tex','Pricing Rounds and Native Solver Costs in the Main Experiment','tab:iterations',r'$N/L$/seed & $i_I$ & $i_{II}$ & PP & Cols. & PP (s) & RMP (s)',drows,'lrrrrrr',True,'A pricing round includes an RMP solution and at least one pricing attempt under its duals. PP includes economic initialization. RMP-only transition and bound-closure records do not count as pricing rounds. Resource-profile query counts are zero in these six runs.')
    with (HERE/'data/runtime.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['index','compact','line'])
        for i,name in enumerate(sorted({r['case'] for r in F}),1):
            w.writerow([i,next(r['seconds'] for r in F if r['case']==name and r['method']=='compact_plain'),next(r['seconds'] for r in F if r['case']==name and r['method']=='balanced_bound')])
    small=[];(HERE/'data/correctness').mkdir(exist_ok=True)
    for name in ('tiny5_original','tiny6_original','gap','lp_yes_ip_no'):
        base=Path(f'sub/stage7/evidence/validation/{name}_cplex_py');raw=(ROOT/base/'instance.json').read_bytes()
        sources[str(base/'instance.json')]=hashlib.sha256(raw).hexdigest();(HERE/'data/correctness'/f'{name}.json').write_bytes(raw)
        blob=(ROOT/base/'result.json.zlib').read_bytes();sources[str(base/'result.json.zlib')]=hashlib.sha256(blob).hexdigest();r=json.loads(zlib.decompress(blob))
        small.append(dict(case=name,line_lp=r['cg']['lp_objective'],integer_lb=r['global_lower_bound'],integer_ub=r['global_upper_bound'],status=r['status'],profile_calls=r['profile_calls']))
    (HERE/'data/correctness.json').write_text(json.dumps(small,indent=2))
    (HERE/'data/source_manifest.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
    print('Exported',len(F),'main,',len(R),'robustness,',len(structure),'structure rows;',len(sources),'source hashes')
if __name__=='__main__':main()
