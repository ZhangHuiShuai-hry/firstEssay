"""Freeze additive Task03 artifacts, after checking exact tested source hashes."""
import hashlib,json,subprocess,sys
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/branch_and_price/task03'
sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'code')]
from node_state import NumericPolicy

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
def read(p):return json.loads(p.read_text())
def dump(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,indent=2,allow_nan=False)
def main():
    if '--check' in sys.argv:
        items=read(BASE/'ARTIFACT_SHA256.json')
        for name,meta in items.items():assert digest(ROOT/name)==meta['sha256'],name
        receipt=read(BASE/'SEAL_RECEIPT.json')
        assert digest(BASE/'ARTIFACT_SHA256.json')==receipt['manifest_sha256']
        print(len(items),'sealed files rehashed: PASS');return
    original=read(BASE/'V0_SHA256.json')
    assert all(digest(ROOT/name)==h for name,h in original.items()),'Baseline source changed'
    result_files=sorted((BASE/'evidence/sealed_validation').glob('*/result.json'))
    assert len(result_files)==116
    for p in result_files:
        r=read(p)
        for name,h in r['adapter_sha256'].items():assert digest(ROOT/'code/dwcg'/name)==h,name
        for name,h in r['code_version']['source_sha256'].items():assert digest(ROOT/name)==h,name
        assert read(p.parent/'verification.json')['passed']
    g=Path('C:/Users/Hrychang/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
    def git(*args):return subprocess.check_output([str(g),'--no-optional-locks','-c','safe.directory='+ROOT.as_posix(),*args],cwd=ROOT,text=True).strip()
    tracked=git('diff','--name-only');assert not tracked,tracked
    sources=list((ROOT/'code/dwcg').glob('*.py'))+list((ROOT/'code/milp').glob('*.py'))+[ROOT/'code/solver_backend.py']
    sources+=list((ROOT/'experiments').glob('task03*.py'))+[BASE/'task03_verify.py']
    baseline=dict(git_head=git('rev-parse','HEAD'),branch=git('branch','--show-current'),
       task02_reference='4c3b67c0de70e090a4d0e96b558c2c91805ad60a',
       task02_to_HEAD_diff=git('diff','--stat','4c3b67c0de70e090a4d0e96b558c2c91805ad60a','HEAD'),
       status=git('status','--short'),tracked_diff=tracked,original_sources_unchanged=True,
       sealed_tree_source_hashes_match=True,numeric_policy=asdict(NumericPolicy()),
       source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in sources},commit_push_PR_performed=False)
    dump(BASE/'CODE_AND_BASELINE.json',baseline)
    added=['branch_price_engine','branch_price_v0','node_incremental_master','node_master_optimized','node_master_v0','node_persistent_pricing','task03','test_task03','test_task03_faults']
    files={ROOT/'code/dwcg'/(n+'.py') for n in added}|set((ROOT/'experiments').glob('task03*.py'))
    files|={p for p in BASE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ('ARTIFACT_SHA256.json','SEAL_RECEIPT.json')}
    manifest={p.relative_to(ROOT).as_posix():dict(sha256=digest(p),bytes=p.stat().st_size) for p in sorted(files)}
    dump(BASE/'ARTIFACT_SHA256.json',manifest)
    receipt=dict(created_utc=datetime.now(timezone.utc).isoformat(),files=len(manifest),total_bytes=sum(v['bytes'] for v in manifest.values()),
       manifest_sha256=digest(BASE/'ARTIFACT_SHA256.json'),baseline_sources_unchanged=True,tested_source_matches=True,
       scope='byte_integrity_not_rational_optimality_certificate',task03_status='PARTIAL',commit_push_PR_performed=False)
    dump(BASE/'SEAL_RECEIPT.json',receipt);print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
