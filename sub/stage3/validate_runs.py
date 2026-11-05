"""新证书沿用独立Oracle；不使用生产PP构造期望答案。"""
import json,sys,zlib,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'stage2')]
from solver import run
from stage2_verify import audit
from validate import check_witness

def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def main():
    out=HERE/'evidence/oracle';out.mkdir(exist_ok=False)
    paths=[HERE.parent/'evidence/inputs_v1/tiny5_original.json',HERE.parent/'evidence/inputs_v1/tiny6_original.json',
           HERE.parent/'stage1/evidence/analytic_gap/instance.json',HERE.parent/'stage1/evidence/pool_counterexample/instance.json',
           HERE.parents[1]/'docs/research_audit/evidence/independent_final/lp_yes_ip_no_cplex_py/instance.json']
    rows=[]
    for n,path in enumerate(paths):
        raw=path.read_bytes();data=json.loads(raw.decode('utf-8-sig'))
        for method in ('rebuild','reuse','warm'):
            folder=out/f'{n}_{method}';folder.mkdir();(folder/'instance.json').write_bytes(raw)
            r=run(data,time_limit=10,init_seconds=.5,pricing=method,log_dir=folder/'logs')
            (folder/'result.json.zlib').write_bytes(zlib.compress(json.dumps(r).encode()))
            checked=audit(data,r);rows.append(dict(case=n,method=method,**checked))
    dump(out/'summary.json',rows);print('Oracle:',len(rows),'PASS')

def replay(folder):
    rows=[]
    for path in sorted(folder.glob('*/summary.json')):
        s=json.loads(path.read_text(encoding='utf-8'));raw=(path.parent/'instance.json').read_bytes();encoded=(path.parent/'result.json.zlib').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==s['input_sha256']
        assert hashlib.sha256(encoded).hexdigest()==s['evidence_sha256']
        for p,h in s['source_sha256'].items():assert hashlib.sha256((HERE.parents[1]/p).read_bytes()).hexdigest()==h,p
        d=json.loads(raw);r=json.loads(zlib.decompress(encoded))
        if s['method']=='compact':
            if r['witness']:check_witness(d,r['witness'],r['global_lower_bound'])
            if r['global_integer_optimal_proven']:assert r['solver_result']['optimal']
            checked={'status':'PASS','scope':'witness_and_native_bound'}
        else:checked=audit(d,r,enumerate_pricing=False)
        rows.append(dict(case=path.parent.name,**checked))
    dump(folder/'replay.json',rows);print('Replay:',len(rows),'PASS')

if __name__=='__main__':
    if len(sys.argv)>1:replay(Path(sys.argv[1]))
    else:main()
