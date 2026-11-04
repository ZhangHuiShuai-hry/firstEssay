"""新对照的独立算术与原始见证重放。"""
import hashlib,json,math,sys,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate import audit,check_column,check_witness

def main():
    root=Path(__file__).resolve().parent;rows=[]
    for folder in sorted((root/'evidence/paired30').iterdir()):
        if not folder.is_dir():continue
        s=json.loads((folder/'summary.json').read_text());raw=(folder/'instance.json').read_bytes();compressed=(folder/'result.json.zlib').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==s['input_sha256'];assert hashlib.sha256(compressed).hexdigest()==s['evidence_sha256']
        d=json.loads(raw);r=json.loads(zlib.decompress(compressed));lines={l['id']:l for l in d['lines']}
        if s['method']=='line':audit(d,r,enumerate_pricing=False)
        elif s['method']=='independent':
            init=r['initialization']
            for e in init:
                if e['column']:check_column(lines[e['line']],e['column'])
            if r['global_upper_bound'] is not None:
                assert len(init)==len(lines)
                bound=sum(e['column']['profit'] if e['optimal'] else e['solver']['best_bound'] for e in init)
                assert abs(bound-r['global_upper_bound'])<1e-5
            if r['witness']:check_witness(d,r['witness'],r['global_lower_bound'])
            if r['global_integer_optimal_proven']:assert r['witness'] and r['global_upper_bound']-r['global_lower_bound']<=1e-5
            if r['global_infeasibility_proven']:assert any(e['status']=='infeasible' for e in init)
        else:
            if r['witness']:check_witness(d,r['witness'],r['global_lower_bound'])
            if r['global_integer_optimal_proven']:assert r['solver_result']['optimal']
        rows.append(dict(path=str(folder.relative_to(root)),status='PASS',scope='independent_arithmetic_and_original_witness_with_native_bound_metadata'))
    with (root/'evidence/replay.json').open('x',encoding='utf-8') as f:json.dump(rows,f,indent=2)
    print(json.dumps(dict(total=len(rows),passed=len(rows))))

if __name__=='__main__':main()
