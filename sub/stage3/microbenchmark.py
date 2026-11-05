"""同一线、同一对偶序列；重建/复用/显式start，禁止把不同树归因于接口。"""
import json,sys,time,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent)]
from persistent_line import LinePricing
from line_cg import solve_line,BackendConfig,use_backend
from validate import enumerate_all

def main():
    out=HERE/'evidence/micro';out.mkdir(exist_ok=False)
    paths=[HERE.parent/'evidence/inputs_v1/tiny6_original.json',HERE.parent/'evidence/inputs_v1/existing20_original.json']
    results=[]
    for case,path in enumerate(paths):
        data=json.loads(path.read_bytes());(out/f'instance{case}.json').write_bytes(path.read_bytes())
        full=enumerate_all(data) if case==0 else None
        for repeat in range(3):
            methods=['rebuild','reuse','warm'];methods=methods[repeat:]+methods[:repeat]
            for method in methods:
                folder=out/f'{case}_{repeat}_{method}';folder.mkdir()
                cfg=BackendConfig(name='cplex_py',log_dir=str(folder/'logs'))
                events=[];session=LinePricing(cfg,events,warm_start=method=='warm')
                certs=[]
                try:
                    with use_backend(cfg,events):
                        for phase,h,r,sigma in [(2,0,0,0),(1,1,.5,-3),(2,2,3,11),(2,0,0,-2)]:
                            for line in data['lines']:
                                f=solve_line if method=='rebuild' else session.solve
                                _,c=f(line,phase=phase,human_price=h,robot_price=r,sigma=sigma,time_limit=10)
                                assert c['optimal'],c['status']
                                if full:
                                    expected=max((p['profit'] if phase==2 else 0)-h*p['human']-r*p['robot']-sigma for p in full[line['id']])
                                    assert abs(c['reduced_cost']-expected)<1e-6
                                certs.append(c)
                finally:session.close()
                (folder/'certificates.json.zlib').write_bytes(zlib.compress(json.dumps(certs).encode()))
                results.append(dict(case=case,repeat=repeat,method=method,values=[c['reduced_cost'] for c in certs],
                    total_seconds=sum(c['total_seconds'] for c in certs),build_seconds=sum(c['build_seconds'] for c in certs),
                    native_seconds=sum(c['solver']['solver_time'] for c in certs),
                    profiles=[c.get('profile') for c in certs]))
    for case in range(2):
        expected=next(x['values'] for x in results if x['case']==case)
        for row in results:
            if row['case']==case:assert all(abs(a-b)<1e-6 for a,b in zip(row['values'],expected))
    (out/'summary.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print('PASS:',len(results),'fixed-dual sequences')

if __name__=='__main__':main()
