import argparse,importlib.util,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('independent_replay8',HERE.parent/'stage8/replay_v2.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();rows=[];start=time.perf_counter()
    for f in sorted(a.directory.glob('*/result.json.zlib')):
        tick=time.perf_counter();r=module.audit(f.parent);r['replay_wall_seconds']=time.perf_counter()-tick;rows.append(r)
    result=dict(status='PASS',results=rows,replay_wall_seconds=time.perf_counter()-start)
    with (a.directory/'replay.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print('PASS',len(rows),'certificates',result['replay_wall_seconds'],'seconds')
if __name__=='__main__':main()
