"""Independent chronology and cell-bound reconstruction, never imports proof_cache."""
import argparse,hashlib,json,math,sys,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'sub'))
from validate import check_column

def verify(folder):
    for name,h in json.loads((folder/'sources.json').read_bytes()).items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h
    result=json.loads((folder/'results.json').read_bytes());n=0;skips=0
    for case in result['runs']:
        path=ROOT/case['source'];raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==case['sha256']
        inp=(path.parent/'instance.json').read_bytes();assert hashlib.sha256(inp).hexdigest()==case['instance_sha256']
        data=json.loads(inp);cg=json.loads(zlib.decompress(raw))['base_result']['cg'];lines={l['id']:l for l in data['lines']}
        expected={(i,j) for i,h in enumerate(cg['history']) if h['phase']==2 for j,c in enumerate(h['pricing'])}
        assert len(case['rows'])==len(expected) and {(r['history_index'],r['pricing_index']) for r in case['rows']}==expected
        for row in case['rows']:
            n+=1;i,j=row['history_index'],row['pricing_index'];h=cg['history'][i];c=h['pricing'][j];line=lines[c['line']];q=row['query']
            assert row['line']==c['line'] and row['sigma']==h['rmp']['duals']['convexity'][c['line']]
            domain=hashlib.sha256(json.dumps(line,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
            assert q['domain']==domain and q['padding']==1e-8
            p=[h['rmp']['duals'][v] for v in ('human','robot')];assert q['price']==p
            candidates=[(f'initialization/{k}',v) for k,v in enumerate(cg['initialization']) if v['line']==c['line'] and v['optimal']]
            candidates += [(f'history/{a}/pricing/{b}',v) for a,old in enumerate(cg['history'][:i]) if old['phase']==2 for b,v in enumerate(old['pricing']) if v['line']==c['line'] and v['optimal']]
            assert len(q['sources'])==len(candidates)
            for s,(name,v) in zip(q['sources'],candidates):
                assert s['source']==name and s['domain']==domain
                assert v['phase']==2 and v['caps'] is None and not v.get('restrictions') and v['solver']['native_status']==101 and v['solver']['backend']=='cplex_py'
                col=v['column'];check_column(line,col);val=col['profit']-v['human_price']*col['human']-v['robot_price']*col['robot']
                assert abs(s['q']-val)<1e-9 and s['human']==v['human_price'] and s['robot']==v['robot_price']
                for key in ('objective','best_bound'):assert abs(v['solver'][key]+v['sigma']-val)<=1e-5
                assert abs(v['reduced_cost']+v['sigma']-val)<=1e-5
            cells=[]
            if candidates:
                for human in range(len(line['stations'])+1):
                    for robot in range(len(line['stations'])+1):
                        vals=[s['q']+s['human']*human+s['robot']*robot+1e-8 for s in q['sources']];idx=min(range(len(vals)),key=vals.__getitem__)
                        cells.append(dict(human=human,robot=robot,upper=vals[idx]-p[0]*human-p[1]*robot,source_index=idx))
            assert cells==q['cells'];upper=max(v['upper'] for v in cells) if cells else None;assert upper==q['upper']
            prefix=cg['pool'][c['line']][:h['rmp']['pool_sizes'][c['line']]]
            for col in prefix:check_column(line,col)
            low=max(col['profit']-p[0]*col['human']-p[1]*col['robot'] for col in prefix);assert abs(low-q['lower'])<1e-9
            skip=upper is not None and upper-row['sigma']<=1e-7;assert row['skip_certified']==skip;skips+=skip
            if c['column']:assert upper is None or c['reduced_cost']<=upper-row['sigma']+1e-5
    assert n==result['summary']['phase2_blocks'] and skips==result['summary']['certified_skips']
    return dict(status='PASS',blocks=n,skips=skips,scope='independent arithmetic/chronology/domain/coverage replay; native CPLEX optimal status trusted')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=verify(a.folder)
    with a.output.open('x') as f:json.dump(r,f,indent=2)
    print(r)
