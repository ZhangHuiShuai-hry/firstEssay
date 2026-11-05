import sys,json,zlib,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'stage6'),str(HERE.parent/'stage2')]
from verify7 import audit
from verify6 import audit as profile_audit
from stage2_verify import audit as cg_audit
from validate import check_witness
def main():
    rows=[]
    for path in sorted((HERE/'evidence/paired20').glob('*/result.json.zlib')):
        f=path.parent;s=json.loads((f/'summary.json').read_text(encoding='utf-8'));raw=(f/'instance.json').read_bytes();encoded=path.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==s['input_sha256'] and hashlib.sha256(encoded).hexdigest()==s['evidence_sha256']
        for p,h in s['source_sha256'].items():assert hashlib.sha256((HERE.parents[1]/p).read_bytes()).hexdigest()==h,p
        d=json.loads(raw);r=json.loads(zlib.decompress(encoded));tiny=len(d['lines'][0]['tasks'])<=6
        if s['method']=='demand':c=audit(d,r,enumerate_profiles=tiny)
        elif s['method']=='profiles':c=profile_audit(d,r,enumerate_profiles=tiny)
        elif s['method']=='cg':c=cg_audit(d,r,enumerate_pricing=tiny)
        else:
            if r['witness']:check_witness(d,r['witness'],r['global_lower_bound'])
            c=dict(status='PASS',scope='compact_native_and_witness')
        rows.append(dict(run=f.name,**c))
    with (HERE/'evidence/replay.json').open('x',encoding='utf-8') as f:json.dump(rows,f,indent=2)
    print('PASS',len(rows))
if __name__=='__main__':main()
