"""Explicit frozen-input plans; reuse stage9 workers and independent auditors."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / 'stage9'))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


worker_module = load_module('frozen_stage9_worker', HERE / 'worker_v2.py')
dump = worker_module.dump
sha = worker_module.sha


def audit(folder, enumerate_profiles=False):
    start = time.perf_counter()
    summary = json.loads((folder / 'summary.json').read_bytes())
    blob = (folder / 'result.json.zlib').read_bytes()
    raw = (folder / 'instance.json').read_bytes()
    assert sha(blob) == summary['evidence_sha256'], 'evidence hash mismatch'
    assert sha(raw) == summary['input_sha256'], 'input hash mismatch'
    for name, expected in summary['source_sha256'].items():
        assert sha((ROOT / name).read_bytes()) == expected, name
    if summary['method'] == 'independent':
        from audit_independent import audit as independent
        check = independent(json.loads(raw), json.loads(zlib.decompress(blob)), enumerate_profiles=enumerate_profiles)
    elif summary['method'] == 'compact_plain':
        replay = load_module('stage9_compact_auditor', HERE.parent / 'stage9/replay.py')
        check = replay.module.audit(folder)
    else:
        from verify_economic import audit as independent
        check = independent(json.loads(raw), json.loads(zlib.decompress(blob)),
                            enumerate_profiles=enumerate_profiles)
    return dict(check, run=folder.name, replay_wall_seconds=time.perf_counter()-start)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--worker', choices=['compact_plain', 'balanced_bound', 'independent'])
    p.add_argument('--instance', type=Path)
    p.add_argument('--sources', type=Path)
    p.add_argument('--budget', type=float)
    p.add_argument('--audit', type=Path)
    p.add_argument('--enumerate', action='store_true')
    a = p.parse_args()
    if a.audit:
        r = audit(a.audit, a.enumerate)
        dump(a.audit / 'replay-check.json', r)
        print(json.dumps(r), flush=True)
        return
    if a.worker:
        return worker_module.worker(a)
    if not a.plan or not a.output:
        p.error('--plan and --output required')
    plan = json.loads(a.plan.read_bytes())
    assert plan['budget_seconds_per_run'] > 5
    assert plan['persistence_reserve_seconds'] == 5
    assert plan['solver_threads'] == 1 and plan['solver_seed'] == 11 and plan['mip_gap'] == 0
    assert plan['solver'] == 'cplex_py' and plan['serial_execution']
    assert sum(len(c['methods']) for c in plan['cases']) == plan['expected_runs']
    assert all(m in ('compact_plain', 'balanced_bound', 'independent') for c in plan['cases'] for m in c['methods'])
    a.output = a.output.resolve()
    a.output.mkdir(parents=True, exist_ok=False)
    dump(a.output / 'manifest.json', plan)
    frozen = a.output / 'inputs'
    frozen.mkdir()
    input_rows = []
    for c in plan['cases']:
        source = ROOT / c['input']
        target = frozen / (source.parent.name+'.json' if source.name == 'instance.json' else source.name)
        assert not target.exists(), 'duplicate input basename'
        raw = source.read_bytes()
        target.write_bytes(raw)
        input_rows.append(dict(source=c['input'], frozen=target.name, sha256=sha(raw)))
    dump(a.output / 'input_hashes.json', input_rows)
    tick = time.perf_counter()
    paths = []
    for directory in (ROOT/'sub', ROOT/'code'):
        for base, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in ('evidence', '__pycache__', '.venv')]
            paths.extend(Path(base)/n for n in files if n.endswith('.py'))
    paths.append(ROOT/'experiments/generate_instances.py')
    sources = a.output / 'sources.json'
    dump(sources, {str(f.relative_to(ROOT)): sha(f.read_bytes()) for f in sorted(set(paths))})
    dump(a.output/'preparation.json', dict(source_freeze_seconds=time.perf_counter()-tick))
    dump(a.output/'ENVIRONMENT.json', dict(python=sys.version, executable=sys.executable,
         platform=platform.platform(), cpu=platform.processor(), logical_cpus=os.cpu_count()))
    dump(a.output/'CONFIG.json', dict(worker='sub/stage11/worker_v2.py', independent_baseline='sub/stage1/independent_solver.py', reserve=5,
         balanced_bound=dict(cg_fraction=.9, cg_cap_seconds=1000000,
             per_profile_seconds=2, pricing='warm', init_seconds=.5, quota=False,
             max_iterations=100, recovery_seconds=.5, wrapper_refinement_reserve=.25),
         backend=dict(name='cplex_py', threads=1, seed=11, gap=0),
         proof_scope='solver_floating_point_tolerances',
         budget_scope='parent_process_start_to_worker_exit; includes evidence persistence'))
    rows, checks = [], []
    for c in plan['cases']:
        instance = frozen / next(x['frozen'] for x in input_rows if x['source'] == c['input'])
        expected = next(x['sha256'] for x in input_rows if x['frozen'] == instance.name)
        for method in c['methods']:
            assert sha(instance.read_bytes()) == expected
            dest = a.output / (instance.stem+'__'+method)
            cmd = [sys.executable, str(Path(__file__).resolve()), '--worker', method,
                   '--instance', str(instance), '--output', str(dest), '--sources', str(sources),
                   '--budget', str(plan['budget_seconds_per_run'])]
            print(json.dumps(dict(event='starting', case=instance.stem, method=method)), flush=True)
            started = time.perf_counter()
            hard = False
            with (a.output / (dest.name+'.stdout.txt')).open('x', encoding='utf-8') as log:
                proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
                try:
                    code = proc.wait(timeout=plan['budget_seconds_per_run']+plan['watchdog_grace_seconds'])
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
                    code, hard = proc.returncode, True
            elapsed = time.perf_counter()-started
            summary = json.loads((dest/'summary.json').read_bytes()) if (dest/'summary.json').exists() else {}
            if summary:
                assert summary['input_sha256'] == expected
            row = dict(case=instance.stem, **summary, end_to_end_seconds=elapsed,
                       timely=elapsed <= plan['budget_seconds_per_run'] and code == 0,
                       hard_stop=hard, exit_code=code)
            rows.append(row)
            dump(a.output/'accounting.json', rows)
            print(json.dumps({k:v for k,v in row.items() if k != 'source_sha256'}), flush=True)
            # Audit in a fresh process; audit time is outside algorithm E2E.
            replay_cmd = [sys.executable, str(Path(__file__).resolve()), '--audit', str(dest)]
            if plan.get('enumerate_profiles'):
                replay_cmd.append('--enumerate')
            with (dest/'replay.stdout.txt').open('x', encoding='utf-8') as log:
                replay = subprocess.run(replay_cmd, stdout=log, stderr=subprocess.STDOUT)
            check = json.loads((dest/'replay-check.json').read_bytes()) if replay.returncode == 0 else dict(run=dest.name,status='FAIL')
            checks.append(check)
            dump(a.output/'replay.json', dict(status='PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL',results=checks))
            if replay.returncode or code or hard or summary.get('status') in ('solver_error','numerical_uncertain'):
                dump(a.output/'STOPPED.json', dict(reason='invalid_or_uncertain_result', run=dest.name,
                     remaining_runs=plan['expected_runs']-len(rows)))
                raise RuntimeError('Stopping: evidence/solver failure; inspect preserved run')
    dump(a.output/'COMPLETED.json', dict(runs=len(rows), replay='PASS',
         timely_runs=sum(r['timely'] for r in rows)))


if __name__ == '__main__':
    main()
