import json,zlib,hashlib,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'stage5')]
from verify6 import audit
from verify5 import audit as tree_audit
from validate import check_witness
def main():
    rows=[]
    for path in sorted((HERE/'evidence/paired20').glob('*/result.json.zlib')):
        folder=path.parent;s=json.loads((folder/'summary.json').read_text(encoding='utf-8'));raw=(folder/'instance.json').read_bytes();encoded=path.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==s['input_sha256'];assert hashlib.sha256(encoded).hexdigest()==s['evidence_sha256']
        for p,h in s['source_sha256'].items():assert hashlib.sha256((HERE.parents[1]/p).read_bytes()).hexdigest()==h,p
        d=json.loads(raw);r=json.loads(zlib.decompress(encoded));tiny=len(d['lines'][0]['tasks'])<=6
        if s['method']=='profiles':checked=audit(d,r,enumerate_profiles=tiny)
        elif s['method']=='reuse':checked=tree_audit(d,r,enumerate_pricing=tiny)
        else:
            if r['witness']:check_witness(d,r['witness'],r['global_lower_bound'])
            checked=dict(status='PASS',scope='compact_native_and_witness')
        rows.append(dict(run=folder.name,**checked))
    with (HERE/'evidence/replay.json').open('x',encoding='utf-8') as f:json.dump(rows,f,indent=2)
    print('PASS',len(rows),'runs')
if __name__=='__main__':main()
