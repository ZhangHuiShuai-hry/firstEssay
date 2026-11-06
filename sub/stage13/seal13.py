"""Seal the new stage only; never alter historical inventories."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    target=HERE/'SHA256.json'
    if a.check:
        records=json.loads(target.read_bytes())
        for name,value in records.items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value,name
        print('PASS',len(records),'hashes')
    else:
        records={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest()
                 for f in sorted(HERE.rglob('*')) if f.is_file() and f!=target and '__pycache__' not in f.parts}
        with target.open('x',encoding='utf-8') as f:json.dump(records,f,indent=2)
        print('Sealed',len(records),'files')

if __name__=='__main__': main()
