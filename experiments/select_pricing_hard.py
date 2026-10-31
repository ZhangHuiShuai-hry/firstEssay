"""Predeclared deterministic escalation: one largest-size case where both hit 300 s."""
import argparse
import json
from pathlib import Path


def select(source,config_path):
    rows=json.loads((source/'summary.json').read_text());assert len(rows)==30
    pairs={}
    for r in rows:pairs.setdefault((r['n'],r['seed']),{})[r['version']]=r
    candidates=[dict(n=n,seed=seed,instance_id=p['V1']['instance_id']) for (n,seed),p in pairs.items()
                if len(p)==2 and all(not r['converged'] and r['status']=='time_limit' for r in p.values())]
    candidates.sort(key=lambda x:(-x['n'],x['seed']))
    if config_path.exists():raise FileExistsError(config_path)
    chosen=candidates[0] if candidates else None
    metadata=dict(rule='Largest n, then smallest seed, among pairs where both versions hit the 300-second time limit; at most one case.',
                  source=str(source),all_candidates=candidates,selected=chosen)
    config_path.with_suffix('.selection.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    if chosen:
        config=dict(design='persistent_pp_hard600',seeds=[chosen['seed']],sizes=[chosen['n']],size_lines=2,
                    base_n=chosen['n'],line_counts=[],fatigue_levels=[],resource_levels=[],budget=600)
        config_path.write_text(json.dumps(config,indent=2),encoding='utf-8')
        print('Selected one 600-second pair:',chosen)
    else:print('No pair with both versions timed out at 300 seconds; no escalation needed.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--config',type=Path,required=True)
    a=p.parse_args();select(a.source,a.config)
