"""探索性同输入串行配对实验；记录真实墙钟，不把软预算称为严格硬实时。

默认：单线程 CPLEX、seed11、30秒。每个方法独立进程；预算从worker读取数据前
开始，覆盖求解器模块导入、建模、求解、验证、落盘。预留2秒收尾，watchdog
允许5秒收尾后停止。超预算、硬停止均显式标记，不能参加预算内胜出统计。
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
import zlib

ROOT = Path(__file__).resolve().parents[1]


def write(path, data):
    raw = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf-8')
    path.write_bytes(raw)


def worker(instance, method, output, budget):
    start = time.perf_counter()
    output.mkdir(parents=True, exist_ok=False)
    raw = instance.read_bytes()
    (output/'instance.json').write_bytes(raw)
    data = json.loads(raw.decode('utf-8-sig'))
    result = {}
    evidence = None
    try:
        if method == 'line':
            from line_cg import run
        elif method == 'compact':
            from compact_solver import run
        else:
            sys.path[:0] = [str(ROOT/'code/dwcg'), str(ROOT/'code')]
            from root_diagnostics import run_root
            from evidence_store import EvidenceStore
            evidence = EvidenceStore(output/'certificate.sqlite')
        remaining = budget-(time.perf_counter()-start)-2.
        if remaining <= 0:
            raise TimeoutError('Import exhausted budget')
        if method == 'station':
            result = run_root(data, mode='recover', initial_seconds=0., recovery_every=5,
                              recovery_seconds=.3, time_limit=remaining, store=evidence)
            evidence.close(); evidence = None
            # 完整证书已存SQL，避免将对象再次复制为巨大JSON。
            result = {k:v for k,v in result.items() if k!='node'}
            result['status'] = result['root_status']
        else:
            result = run(data, time_limit=remaining, log_dir=output/'logs')
        if method=='line':
            result.update(global_lower_bound=result['lower_bound'], global_upper_bound=result['upper_bound'],
                          algorithm_seconds=result['wall_seconds'], timings=result['timing'],
                          columns_generated=result['columns'])
        tick = time.perf_counter()
        encoded = json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8')
        compressed = zlib.compress(encoded, 6)
        (output/'result.json.zlib').write_bytes(compressed)
        persistence = time.perf_counter()-tick
        summary = {k:result.get(k) for k in (
            'status', 'global_lower_bound', 'global_upper_bound', 'absolute_gap', 'relative_gap',
            'global_integer_optimal_proven', 'global_infeasibility_proven', 'first_integer_seconds',
            'first_verified_integer_seconds', 'algorithm_seconds', 'pricing_calls', 'columns_generated',
            'lp_objective', 'timings')}
        summary.update(method=method, input_sha256=hashlib.sha256(raw).hexdigest(),
                       nominal_budget=budget, finalization_reserve_seconds=2., persistence_seconds=persistence,
                       evidence_sha256=hashlib.sha256(compressed).hexdigest(),
                       result_uncompressed_bytes=len(encoded), result_bytes=len(compressed),
                       worker_seconds_before_accounting=time.perf_counter()-start,
                       proof_scope='solver_floating_tolerance; not rational proof')
        write(output/'summary.json', summary)
    except Exception as error:
        write(output/'error.json', dict(status='time_limit' if isinstance(error,TimeoutError) else 'solver_error',
                                       error=repr(error), traceback=traceback.format_exc(),
                                       elapsed=time.perf_counter()-start))
        raise
    finally:
        if evidence is not None:
            evidence.close()


def paired(suite, output, names=None, methods=('compact','station','line'), budget=15.):
    output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((suite/'manifest.json').read_text(encoding='utf-8'))
    records = []
    for case_no, spec in enumerate(manifest):
        if names and spec['name'] not in names:
            continue
        raw = (suite/spec['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==spec['sha256']
        # 确定性轮换方法次序，全部串行。
        ordering = list(methods[case_no % len(methods):])+list(methods[:case_no % len(methods)])
        for method in ordering:
            dest = output/(spec['name']+'__'+method)
            command = [sys.executable, str(Path(__file__).resolve()), '--worker', method,
                       '--instance', str((suite/spec['file']).resolve()), '--output', str(dest.resolve()),
                       '--budget', str(budget)]
            tick = time.perf_counter(); hard_stop = False
            with (output/(dest.name+'.stdout.txt')).open('w', encoding='utf-8') as stdout:
                process = subprocess.Popen(command, stdout=stdout, stderr=subprocess.STDOUT)
                try:
                    code = process.wait(timeout=budget+5.)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(); code=process.returncode; hard_stop=True
            elapsed = time.perf_counter()-tick
            summary = json.loads((dest/'summary.json').read_text(encoding='utf-8')) if (dest/'summary.json').exists() else {}
            if summary:
                assert summary['input_sha256']==spec['sha256']
                assert hashlib.sha256((dest/'result.json.zlib').read_bytes()).hexdigest()==summary['evidence_sha256']
            record = dict(case=spec['name'], **summary)
            record.update(method=method, end_to_end_seconds=elapsed, exit_code=code, hard_stop=hard_stop,
                          over_budget_seconds=max(0.,elapsed-budget), timely=code==0 and elapsed<=budget,
                          completed_evidence=bool(summary), variant=spec['variant'])
            records.append(record); write(output/'accounting.json', records)
            print(json.dumps({k:record.get(k) for k in ('case','method','status','global_lower_bound',
                                                       'global_upper_bound','end_to_end_seconds','timely')},
                             ensure_ascii=False), flush=True)
    return records


def cli(default_method=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--worker', choices=('compact','station','line'), default=default_method)
    p.add_argument('--instance', type=Path, default=ROOT/'code/data/tasks005_lines02_each03-02.json')
    p.add_argument('--suite', type=Path)
    p.add_argument('--names', nargs='+')
    p.add_argument('--methods', nargs='+', default=['compact','station','line'])
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--budget', type=float, default=30.)
    a = p.parse_args()
    if a.budget<=2:
        p.error('budget must exceed 2 seconds')
    if a.worker:
        worker(a.instance,a.worker,a.output,a.budget)
    elif a.suite:
        paired(a.suite,a.output,a.names,tuple(a.methods),a.budget)
    else:
        p.error('provide --worker or --suite')


if __name__ == '__main__':
    cli()
