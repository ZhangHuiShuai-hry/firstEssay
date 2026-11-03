"""DW 分解统一入口：在 IDE 中直接运行，无需填写命令行参数。

默认策略 branch_price：Dantzig–Wolfe分解 + 广义两阶段列生成 + 精确
Branch-and-Price（原始x二元分支、DFS、逐站精确定价、验证整数LB及安全UB）。
使用V2：节点内持久化CPLEX定价 + 增量原生RMP；启用增量证书，完整证明保存
SQLite，JSON保存易读摘要和整数方案。只有完整搜索安全闭合才报告整数最优。

可选策略 cg：只求根节点完整列LP，再求受限列池整数主问题；LP最优及受限IP
最优一般都不等于原问题整数最优。采用重建式、精确定价的稳定根CG入口。

修改下方参数后直接运行，或 python code/dwcg/dwcg_solver.py --help。
依赖：PuLP、CPLEX Python API和许可证；推荐选择现有 experiments/.venv 解释器。
"""
from __future__ import annotations
import argparse
from datetime import datetime
import hashlib,json,sys,time,uuid
from pathlib import Path
from dataclasses import asdict

HERE=Path(__file__).resolve().parent;CODE_DIR=HERE.parent
sys.path[:0]=[str(HERE),str(CODE_DIR)]
from solver_backend import BackendConfig,use_backend
from node_state import NumericPolicy
from evidence_store import EvidenceStore

# ===== IDE 默认参数 =====
INSTANCE_PATH=CODE_DIR/'data/tasks005_lines02_each03-02.json'
STRATEGY='branch_price' # branch_price：原整数问题；cg：根LP+受限整数恢复
TIME_LIMIT=120.0        # 秒；软时限，后处理/持久化可能超时；不是硬实时实验runner
NODE_LIMIT=10000        # B&P最大处理节点数；达到限制保留未解决节点及继承界
MAX_CG_ITERATIONS=1000  # 每个阶段的最大RMP求解轮数
BACKEND_VERSION='V2'    # V0重建；V1持久化PP；V2再增量RMP；V3再获取早期整数LB
RECOVER_INTEGER=True   # 仅cg策略：求生成列池上的整数解，不作为原IP全局证明
POLICY=NumericPolicy() # 沿用审计容差：RC=1e-7、分支整数=1e-7、全局绝对gap=1e-5
CG_RANDOM_SEED=11      # cg策略随机种子；B&P内部固定单线程、seed11
VERBOSE=False
OUTPUT_DIR=CODE_DIR/'results/dwcg'

def solve_instance(instance=INSTANCE_PATH,*,strategy=STRATEGY,time_limit=TIME_LIMIT,
                   node_limit=NODE_LIMIT,max_iterations=MAX_CG_ITERATIONS,version=BACKEND_VERSION,
                   recover_integer=RECOVER_INTEGER,verbose=VERBOSE,output_dir=OUTPUT_DIR):
    from common import compact
    compact.number(time_limit,'time_limit',0,strict=True);compact.integer(node_limit,'node_limit',0)
    compact.integer(max_iterations,'max_iterations',1)
    if strategy not in ('branch_price','cg'):raise ValueError('strategy必须是branch_price或cg')
    if version not in ('V0','V1','V2','V3'):raise ValueError('未知的B&P版本')
    instance=Path(instance).resolve();raw=instance.read_bytes();data=json.loads(raw.decode('utf-8-sig'));compact.validate_data(data)
    folder=Path(output_dir)/f'{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}'
    folder.mkdir(parents=True,exist_ok=False);(folder/'instance.json').write_bytes(raw)
    config=dict(instance=str(instance),input_sha256=hashlib.sha256(raw).hexdigest(),strategy=strategy,
                time_limit=time_limit,node_limit=node_limit,max_cg_iterations=max_iterations,
                version=version if strategy=='branch_price' else None,backend='cplex_py',threads=1,seed=11 if strategy=='branch_price' else CG_RANDOM_SEED,
                recover_integer=recover_integer if strategy=='cg' else None,numeric_policy=asdict(POLICY))
    (folder/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    started=time.perf_counter();store=EvidenceStore(folder/'certificate.sqlite')
    try:
        if strategy=='branch_price':
            from task03 import run
            result=run(data,version,solver='cplex_py',time_limit=time_limit,node_limit=node_limit,
                       max_cg_iterations=max_iterations,policy=POLICY,verbose=verbose,
                       evidence_sink=store,incremental_evidence=True)
            fields=('status','proof_scope','global_integer_optimal_proven','global_infeasibility_proven',
                    'global_lower_bound','global_upper_bound','absolute_gap','relative_gap','integer_incumbent_solution',
                    'root_lp_status','root_lp_objective','root_lp_upper_bound','total_nodes_processed',
                    'total_pricing_calls','termination_reason','first_integer_seconds')
            summary={k:result[k] for k in fields}
        else:
            from solve import run_cg
            with use_backend(BackendConfig(name='cplex_py',threads=1,seed=CG_RANDOM_SEED,deadline=started+time_limit,log_dir=str(folder/'logs'))):
                result,_=run_cg(data,epsilon=POLICY.reduced_cost_epsilon,feasibility_tolerance=POLICY.artificial_tolerance,
                                max_iterations=max_iterations,recover=recover_integer,verbose=verbose)
            ip=result.get('integer_recovery',{})
            summary=dict(status=result['status'],proof_scope=result['proof_scope'],lp_optimal_proven=result['lp_converged'],
                         lp_objective=result['lp_objective'],lp_upper_bound=result['lp_upper_bound'],
                         restricted_integer_recovery=ip,global_integer_optimal_proven=False,
                         termination_reason=result['termination_reason'])
        store.put(result);summary.update(config=config,certificate=str((folder/'certificate.sqlite').resolve()),seconds=time.perf_counter()-started)
        (folder/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    except Exception as error:
        partial=getattr(error,'cg_result',None)
        if partial is not None:store.put(partial)
        failure_status=partial.get('status') if partial else 'time_limit' if isinstance(error,TimeoutError) else 'solver_error'
        (folder/'error.json').write_text(json.dumps(dict(status=failure_status,error=repr(error),has_partial_cg_certificate=partial is not None),ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    finally:store.close()
    print('策略：',strategy,'；状态：',summary['status'])
    if strategy=='branch_price':
        print('整数利润：',summary['global_lower_bound'],'；有效上界：',summary['global_upper_bound'],'；Gap：',summary['absolute_gap'])
    else:print('完整列LP：',summary['lp_objective'],'；受限整数恢复利润：',ip.get('objective'),'（不是原IP全局证明）')
    print('原问题整数最优已证明：',summary['global_integer_optimal_proven'])
    print('摘要与完整证书：',folder.resolve())
    return summary,folder

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('instance',nargs='?',type=Path,default=INSTANCE_PATH)
    p.add_argument('--strategy',choices=('branch_price','cg'),default=STRATEGY)
    p.add_argument('--time-limit',type=float,default=TIME_LIMIT);p.add_argument('--node-limit',type=int,default=NODE_LIMIT)
    p.add_argument('--max-iterations',type=int,default=MAX_CG_ITERATIONS)
    p.add_argument('--version',choices=('V0','V1','V2','V3'),default=BACKEND_VERSION)
    p.add_argument('--no-integer',action='store_true',help='cg策略关闭受限整数恢复')
    p.add_argument('--verbose',action='store_true',default=VERBOSE);p.add_argument('--output-dir',type=Path,default=OUTPUT_DIR)
    a=p.parse_args(argv)
    try:r,_=solve_instance(a.instance,strategy=a.strategy,time_limit=a.time_limit,node_limit=a.node_limit,
                           max_iterations=a.max_iterations,version=a.version,recover_integer=not a.no_integer and RECOVER_INTEGER,
                           verbose=a.verbose,output_dir=a.output_dir)
    except Exception as e:
        print('求解中止：',e,file=sys.stderr)
        return 2 if isinstance(e,TimeoutError) or hasattr(e,'cg_result') else 1
    if a.strategy=='branch_price':proven=r.get('global_integer_optimal_proven') or r.get('global_infeasibility_proven')
    else:proven=r.get('lp_optimal_proven') or r['status']=='infeasible_full_column_LP'
    return 0 if proven else 1 if r['status']=='solver_error' else 2

if __name__=='__main__':
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    raise SystemExit(main())
