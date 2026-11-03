"""Seal this task's additive evidence without rewriting any previous seal."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];B=ROOT/'docs/branch_and_price/task03_1'
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
frozen=json.loads((B/'source_snapshot/SHA256.json').read_text())
assert all(h(ROOT/p)==digest for p,digest in frozen.items()),'Pilot source differs from frozen source'
old=json.loads((ROOT/'docs/branch_and_price/task03/CODE_AND_BASELINE.json').read_text())['source_sha256']
changed=[p for p,digest in old.items() if h(ROOT/p)!=digest]
assert changed==['code/dwcg/branch_price_engine.py'],changed
rows=json.loads((B/'FAIR_BENCHMARK.json').read_text());assert len(rows)==25
g='C:/Users/Hrychang/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
head=subprocess.check_output([g,'-c','safe.directory='+ROOT.as_posix(),'rev-parse','HEAD'],cwd=ROOT,text=True).strip()
with (B/'BASELINE_CHECK.json').open('x') as f:json.dump(dict(audit_commit='198799c42f9fee61842edd33332f7aaec456ff50',precommit_head=head,changed_original_sources=changed,model_unchanged=True,frozen_pilot_sources_match=True,status='PARTIAL'),f,indent=2)
files=[p for p in B.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
files+=list((ROOT/'experiments').glob('task03_1*.py'))+[ROOT/'code/dwcg/evidence_store.py',ROOT/'code/dwcg/test_evidence_store.py',ROOT/'code/dwcg/branch_price_engine.py',ROOT/'.gitattributes']
manifest={p.relative_to(ROOT).as_posix():dict(sha256=h(p),bytes=p.stat().st_size) for p in sorted(set(files))}
with (B/'SHA256.json').open('x') as f:json.dump(manifest,f,indent=2)
assert all(h(ROOT/p)==v['sha256'] for p,v in manifest.items())
print('PASS',len(manifest),'files;',sum(v['bytes'] for v in manifest.values()),'bytes; frozen pilot code matches')
