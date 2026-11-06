"""Chronological frozen-trajectory feasibility study, not a speedup benchmark."""
import argparse,hashlib,json,time,zlib
from pathlib import Path
from proof_cache import ROOT,ProofCache

def sources():
    return sorted((ROOT/'sub/stage12/evidence/formal600').glob('*__balanced_bound/result.json.zlib'))+sorted((ROOT/'sub/stage13/evidence/robust180').glob('*__balanced_bound/result.json.zlib'))

def run(path):
    blob=path.read_bytes();data=json.loads((path.parent/'instance.json').read_bytes());cg=json.loads(zlib.decompress(blob))['base_result']['cg']
    lines={l['id']:l for l in data['lines']};cache={l:ProofCache(v) for l,v in lines.items()};rows=[]
    for i,c in enumerate(cg['initialization']):
        if c['optimal']:cache[c['line']].add(lines[c['line']],c,f'initialization/{i}')
    for i,h in enumerate(cg['history']):
        if h['phase']!=2:continue
        d=h['rmp']['duals']
        for j,c in enumerate(h['pricing']):
            lid=c['line'];line=lines[lid];prefix=cg['pool'][lid][:h['rmp']['pool_sizes'][lid]]
            tick=time.perf_counter();q=cache[lid].query(line,[d['human'],d['robot']],prefix);elapsed=time.perf_counter()-tick
            ub=q['upper'];sigma=d['convexity'][lid];skip=ub is not None and ub-sigma<=1e-7
            actual=c['reduced_cost'] if c['optimal'] else None
            if actual is not None and ub is not None and actual>ub-sigma+1e-5:raise ValueError('Historical exact solution violates reuse bound')
            if skip and c['reduced_cost'] is not None and c['reduced_cost']>1e-7+1e-5:raise ValueError('Invalid no-positive-RC decision')
            rows.append(dict(history_index=i,pricing_index=j,line=lid,sigma=sigma,query=q,query_seconds=elapsed,
                skip_certified=skip,actual_proven_rc=actual,original_native_seconds=c['solver']['solver_time'],
                original_optimal=c['optimal']))
        # Strictly earlier rounds only, never use current-round or future answers.
        for j,c in enumerate(h['pricing']):
            if c['optimal']:cache[c['line']].add(lines[c['line']],c,f'history/{i}/pricing/{j}')
    return dict(source=str(path.relative_to(ROOT)),sha256=hashlib.sha256(blob).hexdigest(),
        instance_sha256=hashlib.sha256((path.parent/'instance.json').read_bytes()).hexdigest(),rows=rows)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    paths=sources();assert len(paths)==10,len(paths)
    (a.output/'sources.json').write_text(json.dumps({str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((ROOT/'RL/reuse_v1').glob('*.py'))},indent=2))
    runs=[run(path) for path in paths];rows=[r for case in runs for r in case['rows']]
    summary=dict(status='PASS',instances=len(runs),phase2_blocks=len(rows),certified_skips=sum(r['skip_certified'] for r in rows),
        historical_native_seconds=sum(r['original_native_seconds'] for r in rows),
        skippable_historical_native_seconds=sum(r['original_native_seconds'] for r in rows if r['skip_certified']),
        query_seconds=sum(r['query_seconds'] for r in rows),scope='counterfactual arithmetic screening on frozen trajectories; no online speedup claim')
    with (a.output/'results.json').open('x') as f:json.dump(dict(summary=summary,runs=runs),f,indent=2,allow_nan=False)
    print(json.dumps(summary))
if __name__=='__main__':main()
