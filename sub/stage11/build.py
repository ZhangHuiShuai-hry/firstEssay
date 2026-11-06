"""Create stage11-only orchestration copies; historical source stays byte-identical."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
def write(name,text):
    with (HERE/name).open('x',encoding='utf-8') as f:f.write(text)
worker=(HERE.parent/'stage9/balanced_worker.py').read_text(encoding='utf-8')
worker=worker.replace("elif a.worker=='compact':from compact_traced import run", "elif a.worker=='independent':\n            sys.path.insert(0,str(HERE.parent/'stage1'))\n            from independent_solver import run\n        elif a.worker=='compact':from compact_traced import run")
worker=worker.replace("if a.worker=='compact_plain' else dict(progress=progress)","if a.worker in ('compact_plain','independent') else dict(progress=progress)")
write('worker.py',worker)
runner=(HERE.parent/'stage10/run_plan.py').read_text(encoding='utf-8')
runner=runner.replace("HERE.parent / 'stage9/balanced_worker.py'","HERE / 'worker.py'")
runner=runner.replace("if summary['method'] == 'compact_plain':","if summary['method'] == 'independent':\n        from audit_independent import audit as independent\n        check = independent(json.loads(raw), json.loads(zlib.decompress(blob)), enumerate_profiles=enumerate_profiles)\n    elif summary['method'] == 'compact_plain':")
runner=runner.replace("['compact_plain', 'balanced_bound']","['compact_plain', 'balanced_bound', 'independent']")
runner=runner.replace("('compact_plain', 'balanced_bound')","('compact_plain', 'balanced_bound', 'independent')")
runner=runner.replace("worker='sub/stage9/balanced_worker.py'","worker='sub/stage11/worker.py', independent_baseline='sub/stage1/independent_solver.py'")
write('run_plan.py',runner)
verify=(HERE.parent/'stage10/verify10.py').read_text(encoding='utf-8')
write('verify11.py',verify)
