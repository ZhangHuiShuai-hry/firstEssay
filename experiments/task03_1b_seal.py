"""Check frozen pilot sources and hash additive evidence; never rewrite old seals."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'docs/branch_and_price/task03_1b'
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
frozen=json.loads((B/'source_snapshot/SHA256.json').read_text())
assert all(h(ROOT/p)==v for p,v in frozen.items())
rows=json.loads((B/'FAIR_BENCHMARK.json').read_text());assert len(rows)==25
assert all(r['final_admitted'] and not r['hard_stop'] for r in rows)
old=json.loads((ROOT/'docs/branch_and_price/task03_1/source_snapshot/SHA256.json').read_text())
changed=[p for p,v in old.items() if h(ROOT/p)!=v]
expected={'code/dwcg/branch_price_engine.py','code/dwcg/evidence_store.py','code/dwcg/node_incremental_master.py','code/dwcg/node_master_optimized.py','code/dwcg/task03.py'}
assert {p.replace(chr(92),'/') for p in changed}==expected,changed
check=dict(base_commit='8166dc33d5961450116aa7728071fc95c6eab659',frozen_sources_match=True,changed_original_sources=changed,model_unchanged=True,full_search_resume='NOT IMPLEMENTED',overall_status='PARTIAL',pilot_attempts=25)
with (B/'BASELINE_CHECK.json').open('x') as f:json.dump(check,f,indent=2)
files=[p for p in B.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
files+=list((ROOT/'experiments').glob('task03_1b*.py'))
names=['incremental_evidence','search_checkpoint','test_budget_semantics','test_checkpoint_contract','test_incremental_evidence','branch_price_engine','evidence_store','node_incremental_master','node_master_optimized','task03']
files+=[ROOT/'code/dwcg'/(n+'.py') for n in names]+[ROOT/'.gitattributes']
manifest={p.relative_to(ROOT).as_posix():dict(sha256=h(p),bytes=p.stat().st_size) for p in sorted(set(files))}
with (B/'SHA256.json').open('x') as f:json.dump(manifest,f,indent=2)
assert all(h(ROOT/p)==v['sha256'] for p,v in manifest.items())
print('PASS',len(manifest),'files;',sum(v['bytes'] for v in manifest.values()),'bytes; pilot code frozen; full resume NOT IMPLEMENTED')
