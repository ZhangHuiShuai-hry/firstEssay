import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');p.add_argument('--manifest',default='SHA256.v2.json');a=p.parse_args()
target=HERE/a.manifest
if a.check:
    records=json.loads(target.read_bytes())
    for name,h in records.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    print('PASS',len(records),'draft hashes')
else:
    records={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(HERE.rglob('*')) if f.is_file() and f!=target and not any(x in f.relative_to(HERE).parts for x in ('build','__pycache__'))}
    with target.open('x',encoding='utf-8') as out:json.dump(records,out,indent=2)
    print('Sealed',len(records),'files')
