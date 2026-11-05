import argparse,hashlib,json,sys,time,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from verify_economic import audit
from replay import module

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();rows=[];start=time.perf_counter()
    for f in sorted(a.directory.glob('*/result.json.zlib')):
        tick=time.perf_counter();folder=f.parent;s=json.loads((folder/'summary.json').read_bytes())
        if s['method']=='compact_plain':checks=module.audit(folder)
        else:
            blob=f.read_bytes();raw=(folder/'instance.json').read_bytes()
            assert hashlib.sha256(blob).hexdigest()==s['evidence_sha256'] and hashlib.sha256(raw).hexdigest()==s['input_sha256']
            for name,h in s['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
            checks=dict(run=folder.name,**audit(json.loads(raw),json.loads(zlib.decompress(blob))))
        checks['replay_wall_seconds']=time.perf_counter()-tick;rows.append(checks)
    with (a.directory/'replay.json').open('x',encoding='utf-8') as f:json.dump(dict(status='PASS',results=rows,replay_wall_seconds=time.perf_counter()-start),f,indent=2)
    print('PASS',len(rows))

if __name__=='__main__':main()
