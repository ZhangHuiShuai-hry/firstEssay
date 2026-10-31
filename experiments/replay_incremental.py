"""Same-column-sequence LP replay: isolates RMP costs from CG path differences."""
import argparse
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'code/dwcg'))
from common import empty_pool,make_column,reduced_cost,coefficients,blocks
from master import build_master,solve_master
from incremental_master import IncrementalMaster
from solver_backend import BackendConfig,use_backend


def replay(run,out,instance_id='B1_20_s11'):
    raw=json.loads((run/'raw'/(instance_id+'_V0.json')).read_text());data=json.loads((run/'instances'/(instance_id+'.json')).read_text())
    lines={l['id']:l for l in data['lines']};pool=empty_pool(data)
    start=time.perf_counter();native=IncrementalMaster(data);initialization=time.perf_counter()-start
    # Secondary fixed-pool ablation only: same persistent matrix, do not use basis.
    cold=IncrementalMaster(data);cold.native.parameters.advance.set(0)
    records=[];events=[]
    with use_backend(BackendConfig(name='cplex_py'),events):
        for h in raw['cg']['history']:
            start=time.perf_counter()
            for line,s in blocks(data):
                for col in pool[line['id'],s]:coefficients(line,s,col)
            preparation=time.perf_counter()-start
            t=time.perf_counter();m=build_master(data,pool,phase=h['phase']);build=time.perf_counter()-t
            t=time.perf_counter();solve_master(m);v0solve=time.perf_counter()-t
            before=native.native_solve_seconds;t=time.perf_counter();native.sync(pool,h['phase']);update=time.perf_counter()-t
            start=time.perf_counter();native.solve();v1interface=time.perf_counter()-start
            v1solve=native.native_solve_seconds-before
            if abs(m.value()-native.value())>1e-5:raise RuntimeError('Same-pool replay objective mismatch')
            cold_before=cold.native_solve_seconds;cold.sync(pool,h['phase']).solve()
            if abs(m.value()-cold.value())>1e-5:raise RuntimeError('No-advance replay objective mismatch')
            snapshots=((native.duals(),native.variables),(m.duals(),m.variables),(cold.duals(),cold.variables))
            for l,s,p in native.variables:
                for dual,variables in snapshots:
                    rc=reduced_cost(lines[l],s,pool[l,s][p],dual,h['phase'])
                    if abs(rc-variables[l,s,p].dj)>1e-5 or rc>1e-5:raise RuntimeError('Same-pool replay reduced-cost mismatch')
            records.append(dict(instance_id=instance_id,phase=h['phase'],V0_build=build,V0_interface=v0solve,V1_update=update,
                                V1_native=v1solve,objective=m.value(),columns=sum(map(len,pool.values())),
                                V1_interface=v1interface,V1_initialization=initialization if not records else 0.,
                                shared_coefficient_preparation=preparation,
                                V0_native=events[-1]['solver_time'],V0_conversion=events[-1]['translation_time'],
                                native_advance0=cold.native_solve_seconds-cold_before,
                                basis_before=native.solve_records[-1]['basis_available_before']))
            for entry in h.get('pricing',[]):
                if entry['reduced_cost']>raw['cg']['epsilon']:
                    pool[entry['line'],entry['station']].append(make_column(lines[entry['line']],entry['station'],entry['assignments']))
    native.close();cold.close();out.write_text(json.dumps(records,indent=2),encoding='utf-8')
    print('Same-pool replay passed:',len(records),'LPs')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--instance-id',default='B1_20_s11');a=p.parse_args();replay(a.run,a.out,a.instance_id)
