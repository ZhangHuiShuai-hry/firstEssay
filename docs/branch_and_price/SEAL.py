"""Task02 delivery hashes and immutable Task01 baseline check. No git writes."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    baseline=json.loads((HERE/'BASELINE.json').read_text())
    changed=[rel for rel,digest in baseline['tracked_sha256'].items() if sha(ROOT/rel)!=digest]
    if changed:raise RuntimeError('Preexisting tracked files modified: '+str(changed))
    tests=[ROOT/'code/dwcg'/name for name in ('test_node_state.py','test_node_cg.py','test_branch_price.py')]
    sources=[ROOT/'code/dwcg'/name for name in ('node_state.py','node_pricing.py','node_master.py','bp_solution.py','branch_price.py')]
    old=[ROOT/'code/dwcg/common.py',ROOT/'code/dwcg/master.py',ROOT/'code/milp/model.py',ROOT/'code/solver_backend.py']
    newdocs=[p for p in HERE.iterdir() if p.is_file() and p.name not in ('SOURCE_SHA256.tsv','EVIDENCE_SHA256.tsv','SEAL_RECEIPT.json')]
    targets=sorted(tests+sources+old+newdocs)
    evidence=sorted(p for p in (HERE/'evidence').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for filename,files in (('SOURCE_SHA256.tsv',targets),('EVIDENCE_SHA256.tsv',evidence)):
        (HERE/filename).write_text('sha256\tpath\n'+''.join(sha(p)+'\t'+p.relative_to(ROOT).as_posix()+'\n' for p in files),encoding='utf-8')
    result={'baseline_head':baseline['head'],'preexisting_tracked_files_checked':len(baseline['tracked_sha256']),
            'modified_preexisting_files':changed,'source_documents_files':len(targets),'evidence_files':len(evidence),
            'evidence_bytes':sum(p.stat().st_size for p in evidence),
            'source_manifest_sha256':sha(HERE/'SOURCE_SHA256.tsv'),'evidence_manifest_sha256':sha(HERE/'EVIDENCE_SHA256.tsv'),
            'task02_commit_created':False,'task02_pushed':False}
    (HERE/'SEAL_RECEIPT.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
