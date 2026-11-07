"""Original manuscript diagrams and archived-data plots. No optimization runs.

Run with a Python environment containing matplotlib/numpy/Pillow. Exported text
remains editable in PDF/SVG; TIFF/PNG are secondary raster renderings.
"""
import argparse,csv,importlib.util,json,math,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch,Circle,Polygon,Arc
HERE=Path(__file__).resolve().parents[1]
OUT=HERE/'img';QA=HERE/'qa/figures';OUT.mkdir(exist_ok=True);QA.mkdir(parents=True,exist_ok=True)
BLUE='#236A99';GREEN='#287D64';GREY='#62676B';LIGHT='#EDF4F8';ORANGE='#B56B22'
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['DejaVu Sans'],'font.size':10,'axes.labelsize':10,
 'xtick.labelsize':10,'ytick.labelsize':10,'legend.fontsize':10,'pdf.fonttype':42,
 'ps.fonttype':42,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})

def canvas(w,h):
    fig=plt.figure(figsize=(w,h));ax=fig.add_axes([0,0,1,1]);ax.set(xlim=(0,w*72),ylim=(0,h*72));ax.axis('off');return fig,ax
def box(ax,x,y,text,w=100,h=30,color=BLUE,fill=LIGHT,diamond=False):
    if diamond:patch=Polygon([(x-w/2,y),(x,y+h/2),(x+w/2,y),(x,y-h/2)],closed=True,edgecolor=color,facecolor=fill,lw=1)
    else:patch=FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=1.5,rounding_size=3',edgecolor=color,facecolor=fill,lw=1)
    ax.add_patch(patch);ax.text(x,y,text,ha='center',va='center',fontsize=10,linespacing=1.1);return patch
def arrow(ax,p,q,color=GREY,dashed=False,style='-|>',rad=0):
    ax.add_patch(FancyArrowPatch(p,q,arrowstyle=style,mutation_scale=9,lw=.9,color=color,
                               linestyle='--' if dashed else '-',connectionstyle=f'arc3,rad={rad}'))
def line(ax,points,color=GREY,dashed=False):
    xs,ys=zip(*points);ax.plot(xs,ys,lw=.9,color=color,ls='--' if dashed else '-',zorder=0)
def save(fig,name,panels=None):
    fig.canvas.draw()
    if panels and ALIGNMENT_TOOL:
        spec=importlib.util.spec_from_file_location('figure_alignment',ALIGNMENT_TOOL)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        module.require_matplotlib_panel_alignment(fig,json_out=QA/(name+'_alignment.json'),strict=True)
    fig.savefig(OUT/(name+'.pdf'))
    fig.savefig(OUT/(name+'.svg'))
    svg=OUT/(name+'.svg')
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    fig.savefig(OUT/(name+'.tiff'),dpi=600,pil_kwargs={'compression':'tiff_lzw'})
    fig.savefig(OUT/(name+'.png'),dpi=300)
    if panels:
        fw,fh=fig.get_size_inches()*72
        manifest={'schema_version':1,'backend':'matplotlib','figure':{'width_pt':float(fw),'height_pt':float(fh)},'panels':[]}
        for k,ax in enumerate(panels):
            b=ax.get_window_extent();scale=72/fig.dpi
            manifest['panels'].append({'id':chr(97+k),'bbox_pt':[float(v*scale) for v in (b.x0,b.y0,b.x1,b.y1)],
                                      'grid_id':'main','row_start':0,'row_stop':1,'col_start':k,'col_stop':k+1})
        (QA/(name+'_layout.json')).write_text(json.dumps(manifest,indent=2))
    plt.close(fig)

def product():
    fig,ax=canvas(3.5,3.8)
    # Containment links, deliberately distinct from directed precedence arcs.
    for x in (43,126,209):line(ax,[(126,245),(126,231),(x,231),(x,222)])
    box(ax,126,255,'Electric fan unit',w=130,h=21)
    for x,name in [(43,'Enclosure'),(126,'Drive'),(209,'Electrical')]:box(ax,x,207,name,w=72,h=24)
    for x in (43,209):
        line(ax,[(x,193),(x-36,193),(x-36,91),(x-32,91)])
        line(ax,[(x-36,152),(x-32,152)])
    box(ax,43,152,'Front guard\nT1',w=63,h=32)
    box(ax,43,91,'Rear cover\nT3',w=63,h=32)
    box(ax,209,152,'Controller\nT4',w=63,h=32)
    box(ax,209,91,'Power lead\nT8',w=63,h=32)
    line(ax,[(126,193),(90,193),(90,151),(94,151)])
    line(ax,[(90,151),(90,105),(94,105)])
    box(ax,126,151,'Impeller\nT2',w=63,h=32)
    box(ax,126,105,'Motor unit\nT5',w=63,h=32)
    line(ax,[(126,87),(126,67),(94,67),(94,55)])
    line(ax,[(126,67),(158,67),(158,55)])
    box(ax,94,38,'Rotor\nT6',w=53,h=31)
    box(ax,158,38,'Stator\nT7',w=53,h=31)
    save(fig,'product_structure')

def rings():
    fig,ax=canvas(3.5,3.65)
    box(ax,126,242,'Shared human / robot pools',w=228,h=25)
    for idx,cx in enumerate((65,187),1):
        arrow(ax,(cx,227),(cx,192),dashed=True)
        ax.text(cx,180,'Entry',ha='center',va='center')
        cy=118;rr=39
        pts=[(cx+rr*math.cos(math.radians(a)),cy+rr*math.sin(math.radians(a))) for a in (135,45,-45,-135)]
        arrow(ax,(cx-27,170),(pts[0][0],pts[0][1]+11),color=BLUE)
        for j,(p,q) in enumerate(zip(pts,pts[1:]+pts[:1])):
            ax.add_patch(FancyArrowPatch(p,q,arrowstyle='-|>',mutation_scale=9,lw=.9,
                         color=BLUE if j<3 else GREY,linestyle='-' if j<3 else '--',
                         connectionstyle='arc3,rad=-.32',shrinkA=12,shrinkB=12))
        for j,(x,y) in enumerate(pts,1):
            ax.add_patch(Circle((x,y),11,ec=BLUE,fc='white',lw=1,zorder=3))
            ax.text(x,y,f'S{j}',ha='center',va='center',zorder=4)
        ax.text(cx,cy,'H / R / J',ha='center',va='center')
        arrow(ax,(pts[3][0],pts[3][1]-11),(cx-27,62),color=BLUE)
        ax.text(cx-27,50,'Exit',ha='center',va='center')
        ax.text(cx,24,f'Line {idx}',ha='center',va='center',fontweight='bold')
    save(fig,'circular_lines')

def andor():
    fig,ax=canvas(7.16,2.5)
    ax.text(8,167,'(a) AND task dependencies',va='center',fontweight='bold')
    pos={1:(25,127),3:(25,57),2:(100,127),4:(100,57),5:(184,127),6:(255,127),7:(326,127),8:(184,57)}
    edges=[(1,2),(3,4),(2,5),(4,5),(5,6),(6,7),(4,8)]
    for i,j in edges:
        x,y=pos[i];xx,yy=pos[j];dx=xx-x;dy=yy-y;d=math.hypot(dx,dy)
        arrow(ax,(x+13*dx/d,y+13*dy/d),(xx-13*dx/d,yy-13*dy/d),color=BLUE)
    for i,(x,y) in pos.items():
        ax.add_patch(Circle((x,y),13,ec=BLUE,fc=LIGHT,lw=1));ax.text(x,y,f'T{i}',ha='center',va='center')
    ax.text(173,98,'AND',ha='center',va='center',color=BLUE)
    ax.text(173,18,'Every selected successor needs all predecessors.',ha='center',va='center')
    line(ax,[(357,20),(357,172)],color='#CCD2D5')
    ax.text(370,167,'(b) Mode OR',va='center',fontweight='bold')
    box(ax,395,93,'Selected\nT5',w=49,h=35)
    for y,label in [(137,'H'),(93,'R'),(49,'J')]:
        arrow(ax,(421,93),(463,y),color=GREEN);box(ax,483,y,label,w=30,h=23,color=GREEN,fill='#EFF6F1')
    ax.text(443,18,'Choose exactly one.',ha='center',va='center')
    save(fig,'and_mode_or')

def flow():
    fig,ax=canvas(7.16,4.1)
    # A compact overview; the Mermaid source gives every failure/stop branch.
    for x,t in [(80,'Frozen input'),(255,'One feasible plan\nper line + local bounds'),(435,'Elastic Phase I\nExact line pricing')]:box(ax,x,264,t,w=136,h=35)
    arrow(ax,(150,264),(185,264));arrow(ax,(325,264),(365,264));arrow(ax,(435,244),(435,216))
    box(ax,435,197,'Zero artificials +\nfeasible hard RMP',w=136,h=35)
    arrow(ax,(365,197),(325,197))
    box(ax,255,197,'Phase II RMP\nVerified integer recovery',w=136,h=35)
    arrow(ax,(185,197),(150,197))
    box(ax,80,197,'Validated LB / valid UB\nBounds closed?',w=137,h=39)
    arrow(ax,(80,176),(80,144));ax.text(90,159,'No',va='center')
    box(ax,80,123,'Price every line\nSame current duals',w=136,h=35)
    arrow(ax,(150,123),(185,123))
    box(ax,255,123,'Complete exact pricing?\nRepair UB if proven',w=136,h=39)
    # Positive columns cause another RMP solve, not a new integer proof.
    arrow(ax,(255,145),(255,177));ax.text(268,159,'New columns',ha='left',va='center')
    arrow(ax,(325,123),(365,123))
    box(ax,435,123,'CG done / incomplete:\nResource-profile MILPs\nand lower / upper DP',w=136,h=47)
    arrow(ax,(435,97),(435,68));ax.text(411,82,'Budget / closure',ha='right',va='center')
    box(ax,435,47,'Return verified plan,\nbounds and proof state',w=136,h=35,color=GREEN,fill='#EFF6F1')
    line(ax,[(10,197),(4,197),(4,47),(365,47)],color=GREEN)
    arrow(ax,(345,47),(365,47),color=GREEN)
    ax.text(40,73,'Yes',ha='center',va='center',color=GREEN)
    ax.text(245,13,'Unproven solves retain valid bounds; they never imply infeasibility.',ha='center',va='center')
    save(fig,'algorithm_flowchart')

def performance():
    data=json.loads((HERE/'data/formal600.json').read_text())
    cases=sorted({r['case'] for r in data})
    assert len(cases)==6 and len(data)==12
    by={(r['case'],r['method']):r for r in data}
    labels=[f"{by[c,'balanced_bound']['total_tasks']}/{c[-2:]}" for c in cases]
    fig,axes=plt.subplots(1,2,figsize=(7.16,3.25))
    fig.subplots_adjust(left=.095,right=.985,bottom=.23,top=.76,wspace=.34)
    for method,color,marker,style,label in [('compact_plain',GREY,'^','--','Compact CPLEX (time limit)'),('balanced_bound',BLUE,'o','-','Whole-line CG (integer proof)')]:
        rows=[by[c,method] for c in cases]
        for ax,values in zip(axes,[[r['seconds'] for r in rows],[100*r['relative_gap'] for r in rows]]):
            ax.plot(range(6),values,color=color,marker=marker,ls=style,lw=1.3,ms=5,
                    markerfacecolor='white' if method=='compact_plain' else color,label=label)
    for ax in axes:
        ax.set_xticks(range(6),labels,rotation=40,ha='right',rotation_mode='anchor');ax.set_xlabel('Total tasks / seed')
        ax.grid(axis='y',color='#E2E5E7',lw=.6);ax.set_axisbelow(True);ax.margins(x=.06)
    axes[0].set_ylim(-15,635);axes[0].set_ylabel('End-to-end time (s)')
    axes[1].set_ylim(-.35,9);axes[1].set_ylabel('Certified relative gap (%)')
    axes[0].set_title('(a) Recorded time',loc='left',fontsize=10,pad=10)
    axes[1].set_title('(b) Certified gap',loc='left',fontsize=10,pad=10)
    handles,labels2=axes[0].get_legend_handles_labels();fig.legend(handles,labels2,loc='upper center',bbox_to_anchor=(.51,.995),ncol=1,frameon=False)
    save(fig,'performance_lines',list(axes))
    with (HERE/'data/performance_lines.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['case','method','seconds','relative_gap_percent','integer_optimal_proven']);writer.writeheader()
        for c in cases:
            for m in ['compact_plain','balanced_bound']:
                r=by[c,m];writer.writerow(dict(case=c,method=m,seconds=r['seconds'],relative_gap_percent=100*r['relative_gap'],integer_optimal_proven=r['proven']))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--alignment-tool',type=Path,
        help='Optional external audit_panel_alignment.py; blocks export on alignment failure')
    ALIGNMENT_TOOL=parser.parse_args().alignment_tool
    product();rings();andor();flow();performance();print('Exported five original figures: PDF/SVG/TIFF/PNG.')
