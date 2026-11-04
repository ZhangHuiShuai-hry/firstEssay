"""生成/核验源码及完整证据字节哈希，不改历史实验。"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent
GIT=Path('C:/Users/Hrychang/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def create():
    source=list(HERE.glob('*.py'))+list((ROOT/'code/dwcg').glob('*.py'))+[
        ROOT/p for p in ('code/milp/model.py','code/solver_backend.py','experiments/generate_instances.py',
            'problem/main.tex','problem/dwcg/main.tex','docs/root_diagnostics/verify_root.py',
            'docs/research_audit/independent_validation.py','docs/branch_and_price/independent_bp_verify.py')]
    hashes={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(set(source))}
    with (HERE/'SOURCE_SHA256.json').open('x',encoding='utf-8') as stream:
        json.dump(hashes,stream,ensure_ascii=False,indent=2)
    def git(*args):
        return subprocess.check_output([str(GIT),'-c','safe.directory='+str(ROOT),*args],cwd=ROOT,text=True).strip()
    sys.path.insert(0,str(ROOT/'code'))
    import pulp
    from solver_backend import load_cplex
    metadata=dict(created_utc=datetime.now(timezone.utc).isoformat(),baseline_commit=git('rev-parse','HEAD'),
        branch=git('branch','--show-current'),working_state_before_commit=git('status','--short'),
        python=sys.version,pulp=pulp.__version__,cplex=load_cplex().__version__,platform=platform.platform(),
        threads=1,seed=11,relative_mip_gap=0,proof_scope='solver floating point tolerances',
        measured_versions=dict(pilot_v1='certificate1; 0.5s reserve; three overtime runs retained',
            ablation_v2='certificate2; economic initialization native bounds; 2s reserve',
            line_counts_v2='same V2 runtime solver sources',resource_stress_v2='same V2 runtime solver sources'),
        note='Final source snapshot; V1 exploratory runtime was not fully source-hash frozen. V2 solver sources were unchanged across the three benchmark groups.')
    with (HERE/'PROVENANCE.json').open('x',encoding='utf-8') as stream:json.dump(metadata,stream,ensure_ascii=False,indent=2)
    files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts
           and p.name!='EVIDENCE_SHA256.json' and p.suffix not in ('.pyc','.pyo')]
    with (HERE/'EVIDENCE_SHA256.json').open('x',encoding='utf-8') as stream:
        json.dump({str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(files)},stream,ensure_ascii=False,indent=2)
    print(json.dumps(dict(sources=len(hashes),evidence_files=len(files))))


def check():
    count=0
    for name in ('SOURCE_SHA256.json','EVIDENCE_SHA256.json'):
        records=json.loads((HERE/name).read_text(encoding='utf-8'))
        for relative,expected in records.items():
            assert sha(ROOT/relative)==expected,relative
            count+=1
    print(json.dumps(dict(status='PASS',hashes_checked=count)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    check() if a.check else create()
