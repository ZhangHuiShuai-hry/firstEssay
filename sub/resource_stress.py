"""第二轮诊断：首轮20任务经济最优实际用H=3,R=2，0.6倍容量仍不紧。

因此另冻结构不变、容量为(2,2)/(1,2)/(1,1)的三例，专门检验资源价格协调。
这是观察首轮后的自适应诊断组，不冒称事前注册；三例全部保留。
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path


def freeze(destination):
    source=Path(__file__).resolve().parents[1]/'code/data/tasks020_lines02_each10_seed11.json'
    raw=source.read_bytes(); data=json.loads(raw.decode('utf-8-sig'))
    destination.mkdir(parents=True,exist_ok=False)
    manifest=[]
    for h,r in ((2,2),(1,2),(1,1)):
        case=deepcopy(data); case['human_limit']=h; case['robot_limit']=r
        name=f'tasks020_resource_H{h}_R{r}'; path=destination/(name+'.json')
        encoded=(json.dumps(case,ensure_ascii=False,indent=2)+'\n').encode('utf-8');path.write_bytes(encoded)
        manifest.append(dict(name=name,file=path.name,sha256=hashlib.sha256(encoded).hexdigest(),
                             source_sha256=hashlib.sha256(raw).hexdigest(),variant='resource_stress',
                             human_limit=h,robot_limit=r,total_tasks=20,lines=2))
    (destination/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('destination',type=Path)
    freeze(p.parse_args().destination)
