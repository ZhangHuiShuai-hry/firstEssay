"""原问题的 CPLEX 求解入口：在 IDE 中直接运行本文件即可。

策略：完整构建原始紧凑 MILP，由 CPLEX Python API 执行整数分支定界。
不修改目标、约束或实例；不自动切换 CBC。只有求解器证明最优且原约束
检查通过，才报告整数最优；超时可保留可行整数解及有效 Best Bound。

在下方修改默认实例/参数，或命令行覆盖：
python code/milp/cplex_solver.py --help
需要 PuLP 和可用的 CPLEX Python API/许可证；本项目现有解释器为
experiments/.venv/Scripts/python.exe，IDE 中请选择已安装这些依赖的解释器。
"""
from __future__ import annotations
import argparse
from datetime import datetime
import hashlib,json,sys,time,uuid
from pathlib import Path

CODE_DIR=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(CODE_DIR))
from model import build_model,solution_report,number,integer
from solver_backend import BackendConfig,use_backend,make_solver

# ===== IDE 默认参数（路径以脚本位置解析，与 IDE 工作目录无关）=====
INSTANCE_PATH=CODE_DIR/'data/tasks005_lines02_each03-02.json'
TIME_LIMIT=120.0       # 秒；建模/求解软时限，写盘和展示可能额外耗时，并非硬实时保证
RELATIVE_GAP=0.0       # CPLEX 相对 MIP gap；0 表示要求证明最优，非零为允许误差停止
THREADS=1             # 固定单线程，便于科研对照
RANDOM_SEED=11        # 固定求解器随机种子
VERBOSE=False         # True 在控制台显示求解器过程；无论此值如何均保存日志
OUTPUT_DIR=CODE_DIR/'results/cplex'  # 每次建立独立子目录，不覆盖旧结果

def solve_instance(instance=INSTANCE_PATH,*,time_limit=TIME_LIMIT,gap=RELATIVE_GAP,
                   threads=THREADS,seed=RANDOM_SEED,verbose=VERBOSE,output_dir=OUTPUT_DIR):
    number(time_limit,'time_limit',0,strict=True);number(gap,'gap',0)
    integer(threads,'threads',1);integer(seed,'seed',0)
    instance=Path(instance).resolve();raw=instance.read_bytes();data=json.loads(raw.decode('utf-8-sig'))
    folder=Path(output_dir)/f'{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}'
    folder.mkdir(parents=True,exist_ok=False);(folder/'instance.json').write_bytes(raw)
    config=dict(instance=str(instance),input_sha256=hashlib.sha256(raw).hexdigest(),time_limit=time_limit,
                relative_gap=gap,threads=threads,seed=seed,backend='cplex_py',strategy='compact_MILP')
    (folder/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    started=time.perf_counter()
    try:
        with use_backend(BackendConfig(name='cplex_py',threads=threads,seed=seed,deadline=started+time_limit,log_dir=str(folder/'logs'))):
            model=build_model(data)
            model.problem.solve(make_solver(mip=True,role='compact_ip',gap=gap,msg=verbose))
            info=dict(model.problem.backend_result);solution=solution_report(model)
        has_solution=bool(info['has_incumbent'] and solution['has_feasible_solution'])
        solution['optimal']=bool(has_solution and info['optimal'])
        lb=solution['objective'] if has_solution else None;ub=info.get('best_bound')
        if lb is not None and ub is not None:
            if ub<lb-1e-5:raise RuntimeError('CPLEX上界低于已验证整数利润')
            ub=max(lb,ub)  # 仅将容差内的残差向外修正
        result=dict(config=config,status=info['status'],solver_result=info,solution=solution,
                    has_integer_incumbent=has_solution,global_integer_optimal_proven=bool(has_solution and info['optimal']),
                    global_infeasibility_proven=info['status']=='infeasible',
                    global_lower_bound=lb,global_upper_bound=ub,
                    absolute_gap=None if lb is None or ub is None else ub-lb,
                    relative_gap=None if lb is None or ub is None else (ub-lb)/max(1,abs(lb)),
                    seconds=time.perf_counter()-started)
    except Exception as error:
        (folder/'error.json').write_text(json.dumps(dict(status='time_limit' if isinstance(error,TimeoutError) else 'solver_error',error=repr(error)),ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    print('策略：原始紧凑MILP + CPLEX整数求解')
    print('状态：',result['status'],'；整数利润：',lb,'；有效上界：',ub,'；Gap：',result['absolute_gap'])
    print('原问题整数最优已证明：',result['global_integer_optimal_proven'])
    print('结果与日志：',folder.resolve())
    return result,folder

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('instance',nargs='?',type=Path,default=INSTANCE_PATH,help='共享数据JSON；省略则使用上方默认实例')
    p.add_argument('--time-limit',type=float,default=TIME_LIMIT,help='建模/求解软时限（秒）')
    p.add_argument('--gap',type=float,default=RELATIVE_GAP,help='CPLEX相对MIP gap')
    p.add_argument('--threads',type=int,default=THREADS);p.add_argument('--seed',type=int,default=RANDOM_SEED)
    p.add_argument('--output-dir',type=Path,default=OUTPUT_DIR);p.add_argument('--verbose',action='store_true',default=VERBOSE)
    a=p.parse_args(argv)
    try:r,_=solve_instance(a.instance,time_limit=a.time_limit,gap=a.gap,threads=a.threads,seed=a.seed,verbose=a.verbose,output_dir=a.output_dir)
    except Exception as e:print('求解中止：',e,file=sys.stderr);return 2 if isinstance(e,TimeoutError) else 1
    return 0 if r['global_integer_optimal_proven'] or r['status']=='infeasible' else 2

if __name__=='__main__':
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    raise SystemExit(main())
