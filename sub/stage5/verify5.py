"""沿用独立节点Oracle，额外核验显式MIP start的原模型及分支合法性。"""
import sys,json,zlib
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'stage4'),str(Path(__file__).resolve().parents[1])]
from bp_verify import audit as old_audit,legal
from validate import check_column

def audit(data,r,*,enumerate_pricing=True):
    checked=old_audit(data,r,enumerate_pricing=enumerate_pricing)
    lines={l['id']:l for l in data['lines']};count=0
    for n in r['node_history']:
        nr=n['result']
        if not nr:continue
        for cert in nr['initialization_fallback']+[c for h in nr['history'] for c in h['pricing']]:
            if not cert.get('persistent'):continue
            assert cert['restrictions']==n['restrictions']
            assert abs(sum(cert['profile'].values())-cert['total_seconds'])<1e-6
            if cert['mip_start_submitted']:
                col=cert['mip_start_column'];check_column(lines[cert['line']],col)
                assert legal(col,n['restrictions'])
                assert cert['mip_start_source'] in ('inherited_pool','previous_solution');count+=1
            else:assert cert['mip_start_column'] is None
    return dict(**checked,mip_starts_checked=count)

if __name__=='__main__':
    folder=Path(sys.argv[1]);print(json.dumps(audit(json.loads((folder/'instance.json').read_bytes()),
        json.loads(zlib.decompress((folder/'result.json.zlib').read_bytes())),enumerate_pricing='--no-enumeration' not in sys.argv)))
