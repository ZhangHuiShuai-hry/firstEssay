"""Recompute pilot table and independently validate every available integer witness."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'code/dwcg')]
from evidence_store import EvidenceStore
from bp_solution import verify_integer_assignments
B=ROOT/'docs/branch_and_price/task03_1b'
rows=[];audit=[]
base=B/'evidence/pilot30'
for r in json.loads((base/'summary.json').read_text()):
    n,seed,version=r['n'],r['seed'],r['version'];source=base/f'n{n}_s{seed}.json';d=json.loads(source.read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest()==r['input_sha256']
    oldsource=ROOT/f'docs/branch_and_price/task03_1/evidence/pilot30/n{n}_s{seed}.json'
    assert source.read_bytes()==oldsource.read_bytes()
    armfolder=base/f'n{n}_s{seed}_{version}'
    receipt=json.loads((armfolder/'admission.json').read_text())
    assert receipt['accounting_sha256']==hashlib.sha256((armfolder/'accounting.json').read_bytes()).hexdigest()
    assert receipt['proof_admitted']==r['final_admitted']
    s=EvidenceStore(base/f'n{n}_s{seed}_{version}'/'evidence.sqlite')
    value=s.get('result' if r['final_admitted'] else 'checkpoint');metrics=s.get('metrics') if r['final_admitted'] else None;s.close()
    w=value.get('integer_incumbent_solution');lb=value.get('global_lower_bound');ub=value.get('global_upper_bound')
    if version=='Compact' and r['final_admitted']:
        lb=value['objective'] if value['has_incumbent'] else None;ub=value['best_bound']
        if lb is not None:
            stations=[dict(line=l['id'],station=p['station'],assignments=[(a['task'],a['mode']) for a in p['assignments_in_order']]) for l in value['solution']['lines'] for p in l['stations']]
            w=verify_integer_assignments(d,stations,expected=lb)
    elif w:verify_integer_assignments(d,w['stations'],expected=lb)
    if not r['final_admitted']:assert not value.get('global_integer_optimal_proven',False)
    gap=None if lb is None or ub is None else ub-lb
    if gap is not None:assert gap>=-1e-5
    total=metrics and sum(e['exclusive'] for e in metrics['exclusive_profile'])
    row=dict(n=n,seed=seed,version=version,status=r['status'],lb=lb,ub=ub,absolute_gap=gap,relative_gap=None if gap is None else max(0,gap)/max(1,abs(lb)),seconds=r['accounting_finished_seconds'],hard_stop=r['hard_stop'],overrun=max(0,r['accounting_finished_seconds']-r['budget']),final_admitted=r['final_admitted'],first_integer_algorithm_seconds=(r.get('result') or {}).get('first_integer_seconds'),profile_exclusive_seconds=total,peak_memory_bytes=(r.get('metrics') or {}).get('peak_memory_bytes'),evidence_bytes=sum(p.stat().st_size for p in (base/f'n{n}_s{seed}_{version}').glob('*.sqlite')))
    m=r.get('metrics') or {}
    row['first_integer_end_to_end_seconds']=m.get('first_integer_end_to_end_seconds')
    row['persistence_components']=m.get('persistence_components')
    if version!='Compact' and r['final_admitted']:
        row['root_lp_status']=value['root_lp_status'];row['nodes_processed']=value['total_nodes_processed']
        root_rounds=value['node_history'][0].get('certificate',{}).get('rounds',[])
        row['root_phase1_rounds']=sum(e['phase']==1 for e in root_rounds)
        row['root_phase2_rounds']=sum(e['phase']==2 for e in root_rounds)
        row['root_lp_objective']=value['root_lp_objective'];row['root_lp_upper_bound']=value['root_lp_upper_bound']
    if m:
        row['exclusive_coarse_seconds']=dict(algorithm_net=m['algorithm_excluding_node_persistence'],node_persistence=m['node_persist_seconds'],final_persistence=m['final_persist_seconds'],other=row['seconds']-m['algorithm_seconds']-m['final_persist_seconds'])
        assert abs(sum(row['exclusive_coarse_seconds'].values())-row['seconds'])<1e-7
    rows.append(row);audit.append(dict(seed=seed,version=version,passed=True,witness_verified=w is not None))
text=['# Task03.1b 30秒受控 pilot','', '输入每例只生成一次，worker 校验同一份冻结 JSON 的原始字节 SHA，并在离线审计确认与Task03.1五个冻结输入字节相同。源码快照为 source_snapshot。全部方法单线程CPLEX、seed11、相同数值政策，串行独立进程，交替方法次序。时间含导入和可复核结果落盘；admission回执绑定accounting SHA。外层非硬实时：超限如实记录。','',
      '|seed|方法|状态|LB|UB|绝对Gap|相对Gap|实际秒(含accounting)|超秒|硬停止|最终结果采纳|证据bytes|','|---|---|---|---|---|---|---|---|---|---|---|---|']
def fmt(x):return 'null' if x is None else f'{x:.5f}' if isinstance(x,float) else str(x)
for r in rows:text.append('|'+'|'.join(fmt(r[k]) for k in ('seed','version','status','lb','ub','absolute_gap','relative_gap','seconds','overrun','hard_stop','final_admitted','evidence_bytes'))+'|')
text+=['','完整数据、内存和exclusive profile总和见 FAIR_BENCHMARK.json；逐函数profile位于每臂 SQLite 的 metrics 根。first_integer_end_to_end_seconds 加入进程偏移；Compact内部首解时刻未知为null。',
       '', '被停止的方法只采纳已提交的初始保守checkpoint；可能只有V3的已验证整数LB，而没有UB。不能把没有及时完整证书解释为数学不可行，也不能假设根LP已收敛或树太大。未运行n30/40和120秒扩展；应先解决轮级checkpoint及剖析缺项。',
       '', '完整恢复NOT IMPLEMENTED，没有把初始LB摘要当可恢复搜索。总墙钟定义包括accounting完成；独立admission回执属于观测日志，其自身发布时间不递归计量，不声称绝对硬实时。cProfile开销计费，不能把不同树的总时间差全部归为接口优化。']
(B/'FAIR_BENCHMARK.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
(B/'FAIR_BENCHMARK.json').write_text(json.dumps(rows,indent=2));(B/'evidence/pilot_audit.json').write_text(json.dumps(audit,indent=2))
print(len(rows),'pilot records audited;',sum(x['witness_verified'] for x in audit),'witnesses checked')
for seed in (11,21,31,41,51):
    group=[r for r in rows if r['seed']==seed];best=max(r['lb'] for r in group if r['lb'] is not None)
    assert all(r['ub'] is None or r['ub']>=best-1e-5 for r in group)
