"""冻结探索实例；变体只写入 sub，不改原数据或原数学实现。"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
from generate_instances import generate


def variant(data, name):
    result = copy.deepcopy(data)
    if name == 'no_precedence':
        for line in result['lines']:
            line['precedence'] = []
    elif name == 'no_fatigue':
        for line in result['lines']:
            for task in line['tasks']:
                for mode in task['modes'].values():
                    mode['beta'] = 0.
    elif name == 'resource_ample':
        count = sum(len(line['stations']) for line in result['lines'])
        result['human_limit'] = result['robot_limit'] = count
    elif name == 'resource_tight':
        for key in ('human_limit', 'robot_limit'):
            result[key] = math.ceil(.6 * result[key])
    elif name != 'original':
        raise ValueError(name)
    return result


def freeze(destination):
    """预先固定全部变体，不能根据实验胜负筛除不利输入。"""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    manifest = []

    def save(name, raw, metadata):
        (destination / (name + '.json')).write_bytes(raw)
        data = json.loads(raw.decode('utf-8-sig'))
        manifest.append(dict(name=name, file=name+'.json', sha256=hashlib.sha256(raw).hexdigest(),
                             total_tasks=sum(len(l['tasks']) for l in data['lines']),
                             lines=len(data['lines']), **metadata))

    for name, filename in (
        ('tiny5', 'tasks005_lines02_each03-02.json'),
        ('tiny6', 'tasks006_lines01_each06_seed13.json'),
        ('existing20', 'tasks020_lines02_each10_seed11.json'),
        ('existing40', 'tasks040_lines02_each20_seed11.json'),
    ):
        source = ROOT / 'code/data' / filename
        raw = source.read_bytes()
        save(name+'_original', raw, dict(variant='original', source=str(source.relative_to(ROOT))))
        if name.startswith('existing'):
            for change in ('no_precedence', 'no_fatigue', 'resource_ample', 'resource_tight'):
                transformed = variant(json.loads(raw.decode('utf-8-sig')), change)
                save(name+'_'+change, (json.dumps(transformed, ensure_ascii=False, indent=2)+'\n').encode(),
                     dict(variant=change, source=str(source.relative_to(ROOT)),
                          source_sha256=hashlib.sha256(raw).hexdigest()))
    # 规模结构敏感性：相同任务参数库，不同分线会改变线内边/必做/回收，不能当成同一问题。
    for seed in (11, 12, 13):
        for lines in (2, 4):
            data, metadata = generate(total_tasks=40, total_stations=16, lines=lines, seed=seed)
            save(f'tasks040_lines{lines:02d}_seed{seed}',
                 (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode(),
                 dict(variant='original', source='experiments/generate_instances.py', seed=seed,
                      task_bank_hash=metadata['base_task_parameter_hash']))
    (destination/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('destination', type=Path)
    a = p.parse_args()
    print(json.dumps(freeze(a.destination), ensure_ascii=False, indent=2))
