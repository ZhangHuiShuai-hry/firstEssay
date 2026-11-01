"""Audit exact objective equality in previously saved fixed-dual PP replays."""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / 'experiments/runs/pricing_replay_02'
SOURCES = {'B1_20_s11': 'incremental_rmp_01', 'B1_30_s11': 'incremental_rmp_01',
           'B1_40_s11': 'incremental_rmp_hard300_01'}


def vector(line, station, duals, phase):
    lid = line['id']
    sigma = {task['id']: 0.0 for task in line['tasks']}
    for e, (i, j) in enumerate(line.get('precedence', [])):
        suffix = sum(duals['precedence', lid, e, k] for k in range(station, len(line['stations']) + 1))
        sigma[i] += suffix
        sigma[j] -= suffix
    values = []
    for task in line['tasks']:
        for mode, param in task['modes'].items():
            reward = (task['value'] - param['cost']) if phase == 2 else 0.
            reward += -duals['task', lid, task['id']] + duals['recovery', lid] * task.get('weight', 0) + sigma[task['id']]
            values.append(reward)
    costs = line['stations'][station - 1]
    values.extend((-(costs['fixed_cost'] if phase == 2 else 0.),
                   -((costs['human_cost'] if phase == 2 else 0.) + duals['human',]),
                   -((costs['robot_cost'] if phase == 2 else 0.) + duals['robot',])))
    return tuple(values)


def main():
    snapshots = json.loads((REPLAY / 'dual_snapshots.json').read_text(encoding='utf-8'))
    inputs = {name: json.loads((ROOT / 'experiments/runs' / folder / 'instances' / (name + '.json')).read_text(encoding='utf-8'))
              for name, folder in SOURCES.items()}
    with (REPLAY / 'calls.csv').open(newline='', encoding='utf-8') as stream:
        calls = {(r['instance_id'], int(r['round']), r['line'], int(r['station'])): r for r in csv.DictReader(stream)}
    totals = defaultdict(lambda: dict(round_lines=0, stations=0, distinct=0, duplicates=0, total_time=0., duplicate_time=0., max_rc_difference=0.))
    for snap in snapshots:
        name, rnd, phase = snap['instance_id'], snap['round'], snap['phase']
        duals = {tuple(d['row']): d['value'] for d in snap['duals']}
        for line in inputs[name]['lines']:
            lid = line['id']; grouped = defaultdict(list); summary = totals[name]
            for station in range(1, len(line['stations']) + 1):
                row = calls[name, rnd, lid, station]
                grouped[vector(line, station, duals, phase)].append((station, row))
                summary['stations'] += 1
                summary['total_time'] += float(row['V2_time'])
            summary['round_lines'] += 1; summary['distinct'] += len(grouped)
            for group in grouped.values():
                base_station, base = group[0]
                base_variable_opt = float(base['V2_rc']) + duals['station', lid, base_station]
                for station, row in group[1:]:
                    diff = abs(base_variable_opt - (float(row['V2_rc']) + duals['station', lid, station]))
                    summary['max_rc_difference'] = max(summary['max_rc_difference'], diff)
                    if diff > 1e-5:
                        raise RuntimeError(f'Equivalent objective mismatch: {name}, {rnd}, {lid}, {station}: {diff}')
                    summary['duplicates'] += 1; summary['duplicate_time'] += float(row['V2_time'])
    out = ROOT / 'experiments/runs/equivalent_pricing_audit_01'
    out.mkdir(parents=True, exist_ok=False)
    for result in totals.values():
        result['duplicate_time_fraction'] = result['duplicate_time'] / result['total_time'] if result['total_time'] else None
    (out / 'summary.json').write_text(json.dumps(totals, indent=2), encoding='utf-8')
    print(json.dumps(totals, indent=2))


if __name__ == '__main__':
    main()
