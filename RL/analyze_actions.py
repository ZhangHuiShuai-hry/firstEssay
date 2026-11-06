import argparse,json
from pathlib import Path
def main():
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    rows=json.loads((a.folder/'results.json').read_bytes())['rows'];summary=[]
    md=['|状态|α|平均setup+target秒|平均已证块|平均有用新列|完整精确轮/2|有效UB（未证为空）|','|---|---:|---:|---:|---:|---:|---|']
    for state in sorted({r['state'] for r in rows}):
        for alpha in (1.,.75,.5,.25):
            rs=[r for r in rows if r['state']==state and r['alpha']==alpha];v=dict(state=state,alpha=alpha,mean_seconds=sum(r['total_seconds'] for r in rs)/2,mean_proven_blocks=sum(r['proven_blocks'] for r in rs)/2,mean_new_positive=sum(r['new_positive_columns'] for r in rs)/2,complete_rounds=sum(r['complete_exact'] for r in rs),upper_bounds=[r['exact_lp_upper_bound'] for r in rs]);summary.append(v)
            md.append(f"|{state}|{alpha}|{v['mean_seconds']:.3f}|{v['mean_proven_blocks']}|{v['mean_new_positive']}|{v['complete_rounds']}|{v['upper_bounds']}|")
    (a.output/'ACTIONS.md').write_text('\n'.join(md)+'\n',encoding='utf-8');(a.output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print('Summarized',len(rows),'trials')
if __name__=='__main__':main()
