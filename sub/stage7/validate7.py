import sys,json,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'stage1'),str(HERE.parent/'stage4')]
from demand_profiles import run
from verify7 import audit
from gap_case import instance
from cases import lp_yes_ip_no
def main():
    out=HERE/'evidence/validation';out.mkdir(exist_ok=False);rows=[]
    ds={'gap':instance(),'lp_yes_ip_no':lp_yes_ip_no()}
    for name in ('tiny5_original','tiny6_original'):ds[name]=json.loads((HERE.parent/f'evidence/inputs_v1/{name}.json').read_bytes())
    for name,d in ds.items():
        for solver in ('cplex_py','cbc'):
            f=out/f'{name}_{solver}';f.mkdir();(f/'instance.json').write_text(json.dumps(d),encoding='utf-8')
            r=run(d,time_limit=15,solver=solver,log_dir=f/'logs');(f/'result.json.zlib').write_bytes(zlib.compress(json.dumps(r).encode()))
            rows.append(dict(case=name,solver=solver,**audit(d,r)))
    (out/'summary.json').write_text(json.dumps(rows,indent=2),encoding='utf-8');print('PASS',len(rows))
if __name__=='__main__':main()
