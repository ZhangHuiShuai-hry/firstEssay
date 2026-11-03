"""Generate each input once, freeze bytes, then run alternating paired arms."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'experiments'))
from task03_1b_budget import arm
from generate_instances import generate

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);stage=sys.argv[2];budget=float(sys.argv[3]);rows=[]
    specs=[(10,11),(20,11)] if stage=='scout' else [(20,s) for s in (11,21,31,41,51)]
    manifest={}
    for idx,(n,seed) in enumerate(specs):
        d,_=generate(n=n,lines=2,seed=seed);source=out/f'n{n}_s{seed}.json';source.write_text(json.dumps(d,indent=2),encoding='utf-8')
        manifest[source.name]=hashlib.sha256(source.read_bytes()).hexdigest();(out/'inputs_sha256.json').write_text(json.dumps(manifest,indent=2))
        versions=['V0','V1','V2','V3','Compact']
        if idx%2:versions.reverse()
        for version in versions:
            r=arm(source,out/f'n{n}_s{seed}_{version}',version,budget);r.update(n=n,seed=seed)
            assert r['input_sha256']==manifest[source.name]
            rows.append(r);(out/'summary.json').write_text(json.dumps(rows,indent=2));print(n,seed,version,r['status'],r['final_admitted'],round(r['end_to_end_seconds'],3),flush=True)
if __name__=='__main__':main()
