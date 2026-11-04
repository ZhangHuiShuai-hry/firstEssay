"""可解析的整线LP正整数间隙：可选J线与必做H/R线争夺1H/1R。"""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate import enumerate_all,solve_full,audit
from line_cg import run
from compact_solver import run as direct

def instance():
    def mode():return dict(time=1,cost=1,beta=0)
    def line(l,modes,required,value):
        return dict(id=l,cycle_time=2,fatigue_limit=.5,stations=[dict(fixed_cost=1,human_cost=1,robot_cost=1)],
                    tasks=[dict(id='t',value=value,weight=1,modes={m:mode() for m in modes})],
                    required_tasks=['t'] if required else [],min_recovery=0,precedence=[])
    return dict(human_limit=1,robot_limit=1,lines=[line('A',['J'],False,13),line('B',['H','R'],True,5)])

def main():
    dest=Path(__file__).resolve().parent/'evidence/analytic_gap';dest.mkdir(parents=True,exist_ok=False)
    data=instance();pool=enumerate_all(data)
    lp=solve_full(data,pool);ip=solve_full(data,pool,True)
    assert abs(lp['objective']-6.5)<1e-6 and abs(ip['objective']-2)<1e-6
    cg=run(data,time_limit=10);checked=audit(data,cg);compact=direct(data,time_limit=10)
    assert cg['lp_optimal_proven'] and not cg['global_integer_optimal_proven']
    assert abs(cg['lower_bound']-2)<1e-6 and abs(cg['upper_bound']-6.5)<1e-6
    for name,obj in [('instance',data),('full_pool',pool),('LP',lp),('IP',ip),('cg',cg),('compact',compact),('verification',checked)]:
        (dest/(name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(LP=lp['objective'],IP=ip['objective'],CG_status=cg['status'],proof=cg['global_integer_optimal_proven'])))

if __name__=='__main__':main()
