"""复用独立算术/枚举验证器；轨迹是诊断记录，不是恢复checkpoint。"""
import argparse,json,sys,zlib,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(HERE.parent/'stage7'),str(HERE.parent/'stage6'),str(HERE.parent/'stage2')]
from verify7 import audit as demand_audit
from stage2_verify import audit as cg_audit
from validate import check_witness

def audit(folder):
    s=json.loads((folder/'summary.json').read_bytes());raw=(folder/'instance.json').read_bytes();blob=(folder/'result.json.zlib').read_bytes()
    assert hashlib.sha256(raw).hexdigest()==s['input_sha256']
    assert hashlib.sha256(blob).hexdigest()==s['evidence_sha256']
    for p,h in s['source_sha256'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    d=json.loads(raw);r=json.loads(zlib.decompress(blob));tiny=max(len(l['tasks']) for l in d['lines'])<=6
    if s['method'] in ('demand','root_first'):checks=demand_audit(d,r,enumerate_profiles=tiny)
    elif s['method']=='cg':checks=cg_audit(d,r,enumerate_pricing=tiny)
    else:
        if r['witness']:check_witness(d,r['witness'],r['global_lower_bound'])
        assert r['global_integer_optimal_proven']==r['solver_result']['optimal']
        checks=dict(status='PASS',scope='compact_native_status_and_original_witness')
    prev=-1
    for t in r['progress_trace']:
        assert t['seconds']>=prev;prev=t['seconds']
        if t['lower_bound'] is not None and t['upper_bound'] is not None:assert t['lower_bound']<=t['upper_bound']+1e-5
    return dict(run=folder.name,**checks)

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
    rows=[audit(f.parent) for f in sorted(a.directory.glob('*/result.json.zlib'))]
    with (a.directory/'replay.json').open('x',encoding='utf-8') as f:json.dump(rows,f,indent=2)
    print('PASS',len(rows))
if __name__=='__main__':main()
