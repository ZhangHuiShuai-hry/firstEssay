"""Strict persisted-bundle entry: hashes, native proof contract, full arithmetic replay."""
import argparse,hashlib,json,math,zlib
from pathlib import Path
from audit import audit,ROOT

def native_contract(r):
    for c in r['pricing_audit_calls']:
        s=c['solver']
        if c['optimal']:
            assert s['backend']=='cplex_py' and s['native_status']==101 and s['optimal'] and c['status']=='optimal'
            assert c['column'] is not None
            for v in (c['reduced_cost'],s['objective'],s['best_bound']):assert v is not None and math.isfinite(v)
            assert abs(c['reduced_cost']-s['objective'])<=1e-5 and abs(s['best_bound']-s['objective'])<=1e-5
        elif c.get('bound_certified'):
            assert s['backend']=='proof_cache' and s['native_status'] is None and not s['optimal']
        if c['column'] is not None and not c.get('bound_certified'):
            assert s['objective'] is not None and abs(c['reduced_cost']-s['objective'])<=1e-5
            if s.get('best_bound') is not None:assert math.isfinite(s['best_bound']) and s['best_bound']>=s['objective']-1e-5

def verify(folder,enumerate_pricing):
    for name,h in json.loads((folder/'sources.json').read_bytes()).items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    data=json.loads((folder/'instance.json').read_bytes());r=json.loads(zlib.decompress((folder/'result.json.zlib').read_bytes()))
    native_contract(r);v=audit(data,r,enumerate_pricing=enumerate_pricing)
    v.update(source_hashes='PASS',native_contract='PASS',certificate_version=r['certificate_version'])
    return v

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--no-enumeration',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=verify(a.folder,not a.no_enumeration)
    with a.output.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps(r))
