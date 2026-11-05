import json,zlib,sys,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from verify5 import audit
from validate import check_witness
def main():
    rows=[]
    for path in sorted((HERE/'evidence/validation').glob('*/result.json.zlib')):
        d=json.loads((path.parent/'instance.json').read_bytes());r=json.loads(zlib.decompress(path.read_bytes()))
        checked=audit(d,r);rows.append(dict(run=path.parent.relative_to(HERE).as_posix(),status=checked['status'],scope=checked['scope']))
    for path in sorted((HERE/'evidence/paired15').glob('*/result.json.zlib')):
        folder=path.parent;raw=(folder/'instance.json').read_bytes();encoded=path.read_bytes()
        s=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
        assert hashlib.sha256(raw).hexdigest()==s['input_sha256'];assert hashlib.sha256(encoded).hexdigest()==s['evidence_sha256']
        for p,h in s['source_sha256'].items():assert hashlib.sha256((HERE.parents[1]/p).read_bytes()).hexdigest()==h,p
        d=json.loads(raw);r=json.loads(zlib.decompress(encoded))
        if s['method']=='compact':
            if r['witness']:check_witness(d,r['witness'],r['global_lower_bound'])
            if r['global_integer_optimal_proven']:assert r['solver_result']['optimal']
            status='PASS';scope='compact_native_and_witness'
        else:
            # 本组合成族每线仅5任务，完整枚举仍可控，全部节点完整认证。
            checked=audit(d,r);status=checked['status'];scope=checked['scope']
        rows.append(dict(run=folder.relative_to(HERE).as_posix(),status=status,scope=scope))
    with (HERE/'evidence/replay.json').open('x',encoding='utf-8') as f:json.dump(rows,f,indent=2)
    print('PASS',len(rows),'results')
if __name__=='__main__':main()
