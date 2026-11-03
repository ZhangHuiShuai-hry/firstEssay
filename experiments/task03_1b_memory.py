import sys,time,tracemalloc,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'code/dwcg'),str(ROOT/'docs/branch_and_price/task03')]
from task03_verify import oracle
from common import enumerate_pool,empty_pool
from node_state import pool_snapshot
from incremental_evidence import ColumnLedger,materialize
data=dict(oracle.cases())['generator_n6_L1_s13'];complete=enumerate_pool(data);key=max(complete,key=lambda k:len(complete[k]));columns=complete[key][:150];result=[];histories=[]
for incremental in (False,True):
    p=empty_pool(data);p[key]=[];ledger=ColumnLedger();tracemalloc.start();tick=time.perf_counter();history=[]
    for col in columns:
        p[key].append(col);history.append(ledger.capture(p) if incremental else pool_snapshot(p))
    elapsed=time.perf_counter()-tick;peak=tracemalloc.get_traced_memory()[1];tracemalloc.stop();histories.append(history)
    result.append(dict(incremental=incremental,snapshots=len(history),peak_bytes=peak,seconds=elapsed))
from evidence_store import canonical
assert canonical(histories[0])==canonical(materialize(histories[1]))
Path(sys.argv[1]).write_text(json.dumps(result,indent=2));print(result)
