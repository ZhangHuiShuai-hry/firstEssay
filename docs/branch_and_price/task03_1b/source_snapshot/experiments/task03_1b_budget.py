"""External E2E deadline. Only a worker exiting within budget admits a final proof."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'code/dwcg')]
from evidence_store import EvidenceStore

def arm(source,out,version,budget):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);expected=hashlib.sha256(Path(source).read_bytes()).hexdigest()
    start=time.perf_counter();deadline=start+budget
    with (out/'worker.txt').open('w') as log:
        p=subprocess.Popen([sys.executable,str(ROOT/'experiments/task03_1b_worker.py'),str(Path(source).resolve()),str(out.resolve()),version,expected,str(deadline),str(start)],stdout=log,stderr=log,env=dict(os.environ,PYTHONHASHSEED='11'))
        hard=False
        try:p.wait(timeout=max(0,deadline-time.perf_counter()))
        except subprocess.TimeoutExpired:hard=True;p.kill();p.wait()
    worker_end=time.perf_counter();within=worker_end<=deadline and p.returncode==0 and not hard
    result=None;metrics=None;recovery_error=None
    try:
        s=EvidenceStore(out/'evidence.sqlite')
        try:
            if within:
                metrics=s.get('summary');result=metrics['result']
                root=s.db.execute("SELECT hash FROM roots WHERE kind='result' ORDER BY seq DESC LIMIT 1").fetchone()
                if root is None or root[0]!=metrics['result_root_sha256']:raise ValueError('Summary/result root mismatch')
            else:result=s.get('checkpoint')
        finally:s.close()
    except Exception as e:recovery_error=repr(e)
    # Recovery/accounting itself is charged. An over-budget artifact is never called timely optimal.
    end=time.perf_counter();timely=within and result is not None and metrics is not None and end<=deadline
    summary_keys=('status','global_lower_bound','global_upper_bound','absolute_gap','relative_gap','global_integer_optimal_proven','global_infeasibility_proven','first_integer_seconds','total_nodes_processed','total_pricing_calls','total_columns_generated','objective','best_bound','has_incumbent')
    operational='timely_result' if timely else 'hard_stop' if hard else 'solver_error' if p.returncode!=0 else 'missing_evidence' if recovery_error else 'late_result'
    record=dict(version=version,budget=budget,input_sha256=expected,worker_seconds=worker_end-start,
                operational_status=operational,recovery_kind='safe_summary_only',search_resume_supported=False,
                end_to_end_seconds=end-start,hard_stop=hard,soft_or_persistence_overrun=not timely,
                overrun=max(0,end-deadline),worker_returncode=p.returncode,final_admitted=timely,
                checkpoint_recovered=result is not None,status=result.get('status') if timely else 'solver_error' if p.returncode!=0 and not hard else 'time_limit',
                result={k:result[k] for k in summary_keys if k in result} if timely else None,
                metrics={k:v for k,v in metrics.items() if k!='exclusive_profile'} if metrics else None,recovery_error=recovery_error)
    if result is not None and not timely:record['recovered_checkpoint']=result
    record['parent_verification_seconds']=end-worker_end
    record['accounting_clock_before_write']=time.perf_counter()-start
    pending=out/'accounting.pending.json'
    with pending.open('x') as f:
        json.dump(dict(record,final_admitted=False,pending_final_admission=timely),f,indent=2);f.flush();os.fsync(f.fileno())
    os.replace(pending,out/'accounting.json')
    record['accounting_finished_seconds']=time.perf_counter()-start
    record['accounting_overrun']=max(0,record['accounting_finished_seconds']-budget)
    # Admission receipt is separate to avoid recursive self-timing of the final write.
    receipt=out/'admission.pending.json'
    with receipt.open('x') as f:
        json.dump(dict(end_to_end_seconds=record['accounting_finished_seconds'],proof_admitted=timely and record['accounting_finished_seconds']<=budget,accounting_sha256=hashlib.sha256((out/'accounting.json').read_bytes()).hexdigest()),f)
        f.flush();os.fsync(f.fileno())
    os.replace(receipt,out/'admission.json')
    if record['accounting_finished_seconds']>budget:
        record['final_admitted']=False;record['result']=None;record['status']='time_limit' if hard or p.returncode==0 else 'solver_error'
    return record

if __name__=='__main__':
    source,out,version,budget=sys.argv[1:5];r=arm(source,out,version,float(budget));print(json.dumps({k:v for k,v in r.items() if k not in ('result','metrics')},indent=2))
