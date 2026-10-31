"""Replay every PP in selected saved complete V1 dual histories, paired and alternating."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

from pricing_profile import ROOT,PricingOracle
from solver_backend import BackendConfig,use_backend,load_cplex


def replay(out):
    out.mkdir(parents=True,exist_ok=False);(out/'logs').mkdir();(out/'source').mkdir()
    load_cplex();all_rows=[];snapshots=[];metadata=[]
    selection=[('incremental_rmp_01','B1_20_s11'),('incremental_rmp_01','B1_30_s11'),('incremental_rmp_hard300_01','B1_40_s11')]
    hashes={}
    for path in (ROOT/'code/dwcg/persistent_pricing.py',Path(__file__).resolve(),ROOT/'experiments/pricing_profile.py',ROOT/'code/dwcg/pricing.py'):
        rel=path.relative_to(ROOT);target=out/'source'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        hashes[str(rel)]=hashlib.sha256(path.read_bytes()).hexdigest()
    (out/'provenance.json').write_text(json.dumps(dict(started_utc=datetime.now(timezone.utc).isoformat(),source_sha256=hashes,
        python=sys.executable,selection=selection,per_call_limit=60,threads=1,solver_seed=11),indent=2),encoding='utf-8')
    fields=['instance_id','n','round','phase','line','station','V1_rc','V2_rc','delta','reported_rc','V1_time','V2_time',
            'V1_build','V1_translation','V1_native','V1_other','V2_build','V2_native_creation','V2_update','V2_native','V2_other','speedup']
    with (out/'calls.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fields);writer.writeheader()
        for folder,name in selection:
            source=ROOT/'experiments/runs'/folder
            path=source/'raw'/(name+'_V1.json');data_path=source/'instances'/(name+'.json')
            raw=json.loads(path.read_text());data=json.loads(data_path.read_text());lines={l['id']:l for l in data['lines']}
            events=[];configs={v:BackendConfig(name='cplex_py',threads=1,seed=11,log_dir=str(out/'logs'/name/v)) for v in ('V1','V2')}
            oracles={v:PricingOracle(v,configs[v],events if v=='V1' else []) for v in configs}
            metadata.append(dict(instance_id=name,raw=str(path.relative_to(ROOT)),raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                 input_sha256=hashlib.sha256(data_path.read_bytes()).hexdigest()))
            for i,h in enumerate(raw['cg']['history'],1):
                if not h.get('pricing'):continue
                duals={tuple(d['row']):d['value'] for d in h['duals']}
                snapshots.append(dict(instance_id=name,round=i,phase=h['phase'],duals=h['duals'],reported_pricing=h['pricing']))
                for p in h['pricing']:
                    answers={};versions=('V1','V2') if len(all_rows)%2==0 else ('V2','V1')
                    for version in versions:
                        config=configs[version];config.deadline=time.perf_counter()+60
                        with use_backend(config,events if version=='V1' else []):
                            _,rc=oracles[version](lines[p['line']],p['station'],duals,h['phase'])
                        answers[version]=(rc,oracles[version].records[-1])
                    a,ta=answers['V1'];b,tb=answers['V2'];delta=abs(a-b)
                    if delta>1e-5 or abs(a-p['reduced_cost'])>1e-5:raise RuntimeError(f'Fixed-dual PP mismatch: {name}, {i}, {p}, {a}, {b}')
                    row=dict(instance_id=name,n=len(data['lines'][0]['tasks']),round=i,phase=h['phase'],line=p['line'],station=p['station'],
                             V1_rc=a,V2_rc=b,delta=delta,reported_rc=p['reduced_cost'],V1_time=ta['wall_time'],V2_time=tb['wall_time'],
                             V1_build=ta['build_time'],V1_translation=ta['translation_time'],V1_native=ta['native_time'],V1_other=ta['other_time'],
                             V2_build=tb['build_time'],V2_native_creation=tb['native_creation_time'],V2_update=tb['objective_update_time'],
                             V2_native=tb['native_time'],V2_other=tb['other_time'],speedup=ta['wall_time']/tb['wall_time'])
                    writer.writerow(row);all_rows.append(row)
                stream.flush()
                if i%20==0:print(name,'round',i,'paired PP calls',len(all_rows),flush=True)
            for oracle in oracles.values():oracle.close()
            (out/(name+'_V1_events.json')).write_text(json.dumps(events,indent=2),encoding='utf-8')
            print('Passed entire saved history:',name,'paired calls so far',len(all_rows),flush=True)
    (out/'calls.json').write_text(json.dumps(all_rows,indent=2),encoding='utf-8')
    (out/'dual_snapshots.json').write_text(json.dumps(snapshots,indent=2),encoding='utf-8')
    (out/'validation.json').write_text(json.dumps(dict(passed=True,paired_calls=len(all_rows),max_delta=max(r['delta'] for r in all_rows),
        cases=metadata,finished_utc=datetime.now(timezone.utc).isoformat()),indent=2),encoding='utf-8')
    print('Every saved PP verified:',len(all_rows),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();replay(a.out)
