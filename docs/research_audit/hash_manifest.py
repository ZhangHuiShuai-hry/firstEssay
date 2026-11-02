"""Seal Task01 files without touching git metadata or historical experiments."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
GIT=Path('C:/Users/Hrychang/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    base=json.loads((HERE/'baseline.json').read_text())
    cmd=[str(GIT),'-c','safe.directory='+ROOT.as_posix()]
    initial=set(base['files'])
    changed={rel for rel,digest in base['files'].items() if sha(ROOT/rel)!=digest}
    expected={'code/solver_backend.py','code/dwcg/common.py','code/dwcg/pricing.py','code/dwcg/persistent_pricing.py','code/dwcg/solve.py','code/dwcg/verify.py','code/dwcg/verify_checked.py'}
    assert changed==expected,changed
    targets={ROOT/rel for rel in initial}|{ROOT/'experiments/test_research_audit.py'}
    targets|={p for p in HERE.iterdir() if p.is_file() and p.name not in ('HASHES_FINAL.tsv','EVIDENCE_HASHES.tsv','seal_receipt.json')}
    (HERE/'HASHES_FINAL.tsv').write_text('sha256\tpath\n'+''.join(f'{sha(p)}\t{p.relative_to(ROOT).as_posix()}\n' for p in sorted(targets)),encoding='utf-8')
    evidence=sorted(p for p in (HERE/'evidence').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    (HERE/'EVIDENCE_HASHES.tsv').write_text('sha256\tpath\n'+''.join(f'{sha(p)}\t{p.relative_to(ROOT).as_posix()}\n' for p in evidence),encoding='utf-8')
    status=subprocess.check_output(cmd+['status','--porcelain=v1','--untracked-files=no'],text=True,cwd=ROOT)
    output={'commit':subprocess.check_output(cmd+['rev-parse','HEAD'],text=True,cwd=ROOT).strip(),
            'modified_original_files':sorted(changed),'original_tracked_files_unchanged':len(initial)-len(changed),
            'final_manifest_files':len(targets),'evidence_files':len(evidence),
            'evidence_bytes':sum(p.stat().st_size for p in evidence),'tracked_status':status,
            'final_manifest_sha256':sha(HERE/'HASHES_FINAL.tsv'),'evidence_manifest_sha256':sha(HERE/'EVIDENCE_HASHES.tsv')}
    print(json.dumps(output,indent=2))

if __name__=='__main__':main()
