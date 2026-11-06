import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];target=HERE/'SHA256.json'
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
if a.check:
    values=json.loads(target.read_bytes())
    for name,h in values.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    print('PASS',len(values),'hashes')
else:
    values={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(HERE.rglob('*')) if f.is_file() and f!=target and '__pycache__' not in f.parts}
    with target.open('x') as out:json.dump(values,out,indent=2)
    print('Sealed',len(values),'files')
