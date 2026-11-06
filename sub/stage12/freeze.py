"""Freeze a preregistered scale family; never pass calibration witnesses to workers."""
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SEEDS = (32, 33, 34)
SIZES = ((80, 4, 32), (120, 6, 48))
spec = importlib.util.spec_from_file_location('stage12_original_generator', ROOT/'experiments/generate_instances.py')
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def plan(cases, phase, budget):
    p = json.loads((HERE.parent/'stage11/calibration_plan.json').read_bytes())
    p.update(phase=phase, cases=cases, expected_runs=sum(len(c['methods']) for c in cases),
             budget_seconds_per_run=budget, algorithm_baseline='c23b75fc',
             nominal_budget_sum_seconds=budget*sum(len(c['methods']) for c in cases),
             prerequisite='stage12/PROTOCOL.md; unchanged audited algorithms and valid frozen inputs')
    return p


def base():
    out = HERE/'evidence/base_inputs'
    out.mkdir(parents=True, exist_ok=False)
    rows, cases = [], []
    for seed in SEEDS:
        for n, lines, stations in SIZES:
            data, meta = gen.generate(lines=lines, seed=seed, total_tasks=n,
                                      total_stations=stations, graph='layered',
                                      mode_profile='mixed', fatigue=.6)
            data['human_limit'] = data['robot_limit'] = stations
            name = f'tasks{n:03d}_lines{lines:02d}_ample_seed{seed}.json'
            path = out/name
            save(path, data)
            rows.append(dict(file=name, sha256=digest(path.read_bytes()),
                             task_bank_hash=meta['base_task_parameter_hash'],
                             metadata=gen.metadata(data),
                             constructed_witness_exported=False))
            cases.append(dict(input=str(path.relative_to(ROOT)), methods=['independent']))
    save(out/'manifest.json', dict(instances=rows,
         generator_sha256=digest((ROOT/'experiments/generate_instances.py').read_bytes()),
         rule='N80/L4 and N120/L6; 20 tasks and 8 stations per line; seeds32/33/34'))
    save(HERE/'calibration_plan.json', plan(cases, 'stage12_capacity_calibration', 120))


def final():
    batch = HERE/'evidence/calibration'
    assert json.loads((batch/'COMPLETED.json').read_bytes())['runs'] == 6
    assert json.loads((batch/'replay.json').read_bytes())['status'] == 'PASS'
    out = HERE/'evidence/inputs'
    out.mkdir(parents=True, exist_ok=False)
    rows, cases = [], []
    for seed in SEEDS:
        for n, lines, stations in SIZES:
            name = f'tasks{n:03d}_lines{lines:02d}_ample_seed{seed}'
            raw = (HERE/f'evidence/base_inputs/{name}.json').read_bytes()
            result = json.loads(zlib.decompress((batch/f'{name}__independent/result.json.zlib').read_bytes()))
            cols = [v['column'] for v in result['initialization']]
            assert len(cols) == lines and all(cols), 'Missing calibration plans; stop without guessing capacity'
            h, r = sum(c['human'] for c in cols), sum(c['robot'] for c in cols)
            data = deepcopy(json.loads(raw))
            data.update(human_limit=max(0, h-1), robot_limit=max(0, r-1))
            gen.compact.validate_data(data)
            path = out/f'tasks{n:03d}_lines{lines:02d}_conflict_candidate_seed{seed}.json'
            save(path, data)
            rows.append(dict(file=path.name, sha256=digest(path.read_bytes()),
                             base_input_sha256=digest(raw), calibration_human=h, calibration_robot=r,
                             all_calibration_local_optimal=all(v['optimal'] for v in result['initialization']),
                             assignments_provided_to_worker=False, metadata=gen.metadata(data)))
            methods = ['compact_plain', 'balanced_bound']
            if len(cases) % 2:
                methods.reverse()
            cases.append(dict(input=str(path.relative_to(ROOT)), methods=methods))
    save(out/'manifest.json', dict(instances=rows, capacity_rule='calibration_sum_minus_one_in_each_resource',
                                   scope='new seeds32/33/34, no selection by formal outcomes'))
    pilot_case = next(c for c in cases if 'tasks120' in c['input'] and 'seed32' in c['input'])
    save(HERE/'pilot_plan.json', plan([pilot_case], 'stage12_n120_pilot', 120))
    save(HERE/'formal_plan.json', plan(cases, 'stage12_scale_confirmation', 600))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--final', action='store_true')
    args = parser.parse_args()
    final() if args.final else base()
    print('Frozen', 6, 'formal inputs' if args.final else 'calibration inputs')
