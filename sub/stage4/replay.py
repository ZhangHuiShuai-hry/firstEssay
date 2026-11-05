"""重放所有保存树，包含早期未闭合/失败记录；不覆盖原证据。"""
import json,sys,zlib,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from bp_verify import audit

def main():
    rows=[]
    for group in ('validation','validation_v2','validation_v3'):
        folder=HERE/'evidence'/group
        for path in sorted(folder.glob('*/result.json.zlib')):
            d=json.loads((path.parent/'instance.json').read_bytes());r=json.loads(zlib.decompress(path.read_bytes()))
            checked=audit(d,r)
            rows.append(dict(path=path.parent.relative_to(HERE).as_posix(),status=checked['status'],
                result_status=r['status'],evidence_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                input_sha256=hashlib.sha256((path.parent/'instance.json').read_bytes()).hexdigest()))
    hashes=json.loads((HERE/'evidence/validation_v3/SOURCE_SHA256.json').read_text(encoding='utf-8'))
    for p,h in hashes.items():assert hashlib.sha256((HERE.parents[1]/p).read_bytes()).hexdigest()==h,p
    with (HERE/'evidence/replay.json').open('x',encoding='utf-8') as f:json.dump(rows,f,indent=2)
    print('PASS',len(rows),'saved trees; final runtime source hashes unchanged')

if __name__=='__main__':main()
