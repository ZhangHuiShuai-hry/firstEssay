"""事后诊断：原始Compact连续松弛和已证整线DW-LP；不计入性能实验。"""
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from line_cg import compact,BackendConfig,use_backend
from solver_backend import make_solver

def main():
    base=HERE/'evidence/final120';rows=[]
    for path in sorted((base/'inputs').glob('*.json')):
        data=json.loads(path.read_bytes());events=[]
        with use_backend(BackendConfig(name='cplex_py',threads=1,seed=11,log_dir=str(HERE/'evidence/lp_diagnostic'/path.stem)),events):
            model=compact.build_model(data)
            for v in model.problem.variables():v.cat='Continuous'
            model.problem.solve(make_solver(mip=False,role='verification',time_limit=30))
        info=dict(model.problem.backend_result);assert info['optimal'],info
        import zlib
        cg=json.loads(zlib.decompress((base/(path.stem+'__cg')/'result.json.zlib').read_bytes()))
        assert cg['lp_optimal_proven'] or cg['global_integer_optimal_proven']
        dw=cg['lp_objective'] if cg['lp_optimal_proven'] else cg['upper_bound']
        assert info['objective']>=dw-1e-5
        rows.append(dict(case=path.stem,compact_lp=info['objective'],whole_line_lp=dw,verified_integer_profit=cg['lower_bound'],solver=info,scope='LP_relaxation_before_CPLEX_MIP_cuts_not_native_root_node_bound'))
    with (HERE/'evidence/lp_diagnostic.json').open('x',encoding='utf-8') as f:json.dump(rows,f,indent=2)
    print([(r['case'],r['compact_lp'],r['whole_line_lp']) for r in rows])

if __name__=='__main__':main()
