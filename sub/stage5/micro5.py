"""从同一基线树提取固定节点/对偶/合法列池，逐项比较PP。"""
import sys,json,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'stage4')]
from branch_price import run as baseline
from native_node_pp import LinePricing
from line_bp_pricing import solve_line,allows,NodeRestrictions
from line_cg import BackendConfig,use_backend
from bp_verify import legal
from validate import enumerate_all
def main():
    out=HERE/'evidence/micro';out.mkdir(exist_ok=False)
    d=json.loads((HERE/'evidence/inputs/tasks010_lines02_tight_seed11.json').read_bytes())
    r=baseline(d,time_limit=15);(out/'base_tree.json.zlib').write_bytes(zlib.compress(json.dumps(r).encode()))
    full=enumerate_all(d);rows=[]
    for n in r['node_history'][:4]:
        if not n['result']:continue
        fixes=NodeRestrictions.from_records(d,n['restrictions']);seed=n['result']['pool']
        objectives=[(1,1,.3,-2),(2,0,0,0),(2,2,3,17)]
        for repeat in range(3):
            methods=['rebuild','reuse','warm'];methods=methods[repeat:]+methods[:repeat]
            for strategy in methods:
                folder=out/f'n{n["node_id"]}_r{repeat}_{strategy}';folder.mkdir()
                cfg=BackendConfig(name='cplex_py',log_dir=str(folder/'logs'));events=[];certs=[]
                session=LinePricing(cfg,events,restrictions=fixes,seed_pool=seed,warm_start=strategy=='warm')
                try:
                    with use_backend(cfg,events):
                        for phase,h,robot,sigma in objectives:
                            for line in d['lines']:
                                f=solve_line if strategy=='rebuild' else session.solve
                                _,c=f(line,phase=phase,human_price=h,robot_price=robot,sigma=sigma,restrictions=fixes,time_limit=5)
                                candidates=[p for p in full[line['id']] if legal(p,n['restrictions'])]
                                if not candidates:assert c['status']=='infeasible'
                                else:
                                    assert c['optimal'];expected=max((p['profit'] if phase==2 else 0)-h*p['human']-robot*p['robot']-sigma for p in candidates)
                                    assert abs(c['reduced_cost']-expected)<1e-6
                                certs.append(c)
                finally:session.close()
                (folder/'certificates.json.zlib').write_bytes(zlib.compress(json.dumps(certs).encode()))
                rows.append(dict(node=n['node_id'],restrictions=n['restrictions'],repeat=repeat,strategy=strategy,
                    total_seconds=sum(c['total_seconds'] for c in certs),create_seconds=sum(c['build_seconds'] for c in certs),
                    native_seconds=sum(c['solver']['solver_time'] for c in certs),certs=len(certs)))
    (out/'summary.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');print('PASS',len(rows),'node/dual sequences')
if __name__=='__main__':main()
