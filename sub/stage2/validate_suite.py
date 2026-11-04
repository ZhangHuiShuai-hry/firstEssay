"""V3小规模完整枚举证据，以及中等规模保存结果的算术重放。"""
import hashlib,json,sys,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from solver import run
from stage2_verify import audit
ROOT=Path(__file__).resolve().parents[1]

def main():
    out=Path(__file__).resolve().parent/'evidence/validation';out.mkdir(parents=True,exist_ok=False)
    rows=[]
    paths=[ROOT/'../code/data/tasks005_lines02_each03-02.json',ROOT/'../code/data/tasks006_lines01_each06_seed13.json',
           ROOT/'stage1/evidence/analytic_gap/instance.json',ROOT/'stage1/evidence/pool_counterexample/instance.json',
           ROOT/'../docs/research_audit/evidence/independent_final/lp_yes_ip_no_cplex_py/instance.json']
    for n,path in enumerate(paths):
        raw=path.read_bytes();d=json.loads(raw.decode('utf-8-sig'))
        for name,short,quota in [('baseline',None,False),('short',.5,False),('quota',None,True),('short_quota',.5,True)]:
            folder=out/f'{n}_{name}';folder.mkdir();(folder/'instance.json').write_bytes(raw)
            r=run(d,time_limit=15,init_seconds=short,quota=quota)
            (folder/'result.json.zlib').write_bytes(zlib.compress(json.dumps(r,ensure_ascii=False).encode()))
            checked=audit(d,r);rows.append(dict(case=n,method=name,**checked))
    for folder in sorted((Path(__file__).resolve().parent/'evidence/paired30').iterdir()):
        if not folder.is_dir():continue
        summary=json.loads((folder/'summary.json').read_text(encoding='utf-8'));raw=(folder/'instance.json').read_bytes();compressed=(folder/'result.json.zlib').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==summary['input_sha256'];assert hashlib.sha256(compressed).hexdigest()==summary['evidence_sha256']
        for source,expected in summary['source_sha256'].items():assert hashlib.sha256((ROOT.parent/source).read_bytes()).hexdigest()==expected
        d=json.loads(raw);r=json.loads(zlib.decompress(compressed))
        if summary['method']=='compact':
            from validate import check_witness
            if r['witness']:check_witness(d,r['witness'],r['global_lower_bound'])
            if r['global_integer_optimal_proven']:assert r['solver_result']['optimal']
            checked=dict(status='PASS',scope='independent_integer_witness_and_native_MIP_bound')
        else:checked=audit(d,r,enumerate_pricing=False)
        rows.append(dict(case=folder.name,**checked))
    (out/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(total=len(rows),passed=sum(r['status']=='PASS' for r in rows))))

if __name__=='__main__':main()
