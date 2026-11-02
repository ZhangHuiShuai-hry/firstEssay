"""Read-only historical inventory; writes only the requested audit output."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    out=Path(sys.argv[1]);report={'runs':[],'snapshots':[]}
    for run in sorted((ROOT/'experiments/runs').iterdir()):
        if not run.is_dir():continue
        item={'name':run.name,'top_files':[p.name for p in run.iterdir() if p.is_file()],
              'counts':{}}
        for folder in ('raw','logs','tasks','instances','source'):
            item['counts'][folder]=sum(p.is_file() for p in (run/folder).rglob('*'))
        for name in ('config.json','environment.json','provenance.json','requirements-lock.txt','summary.json'):
            item[name]=sha(run/name) if (run/name).is_file() else None
        provenance=run/'provenance.json'
        if provenance.exists():
            data=json.loads(provenance.read_text(encoding='utf-8-sig'));mismatches=[];missing=[];checked=0
            for rel,digest in data.get('source_sha256',{}).items():
                p=run/'source'/Path(rel)
                if not p.exists():missing.append(rel)
                elif sha(p)!=digest:mismatches.append(rel)
                checked+=1
            item['source_manifest']={'checked':checked,'missing':missing,'mismatches':mismatches}
        if (run/'summary.json').exists():
            data=json.loads((run/'summary.json').read_text(encoding='utf-8-sig'))
            item['summary_records']=len(data)
        report['runs'].append(item)
    for snap in sorted((ROOT/'experiments/snapshots').iterdir()):
        if not snap.is_dir():continue
        item={'name':snap.name,'top_files':[p.name for p in snap.iterdir() if p.is_file()]}
        manifest=snap/'manifest.json'
        if manifest.exists():
            data=json.loads(manifest.read_text(encoding='utf-8-sig'));item['manifest_sha256']=sha(manifest)
            if data and all(isinstance(v,str) and len(v)==64 for v in data.values()):
                data={'source_sha256':data}
            for key in ('source_sha256','data_sha256'):
                checked=0;missing=[];bad=[]
                for rel,digest in data.get(key,{}).items():
                    path=Path(rel)
                    p=snap/'source'/path if key=='source_sha256' else snap/'data'/Path(*path.parts[2:])
                    # Older snapshots can use a direct relative layout.
                    if not p.exists() and (snap/path).exists():p=snap/path
                    if not p.exists():missing.append(str(p.relative_to(snap)))
                    elif sha(p)!=digest:bad.append(str(p.relative_to(snap)))
                    checked+=1
                item[key]={'checked':checked,'missing':missing,'mismatches':bad}
        report['snapshots'].append(item)
    out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'runs':len(report['runs']),'snapshots':report['snapshots']},indent=2))

if __name__=='__main__':main()
