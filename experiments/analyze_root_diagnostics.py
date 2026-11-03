"""重放全部根节点诊断证据，并提取解与迭代统计。"""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/root_diagnostics'
sys.path[:0]=[str(OUT),str(ROOT/'code/dwcg'),str(ROOT/'code')]
from evidence_store import load_result
from verify_root import verify

def main():
    replay=[];analysis=[]
    for path in sorted(OUT.rglob('certificate.sqlite')):
        r=load_result(path);folder=path.parent
        instance=folder/'instance.json'
        if not instance.exists():instance=folder.parent/'instance.json'
        data=json.loads(instance.read_bytes());n=sum(len(l['tasks']) for l in data['lines'])
        v=verify(data,r,enumerate_all=n<=6)
        replay.append(dict(file=str(path.relative_to(OUT)),**v))
        rounds=r['round_diagnostics'];phase2=[x for x in rounds if x['phase']==2]
        final=phase2[-1] if phase2 else None
        summary={k:r[k] for k in ('mode','root_status','global_lower_bound','global_upper_bound','absolute_gap','integer_structure','first_integer_seconds','timings')}
        summary.update(file=str(path.relative_to(OUT)),last_round=final,
            phase1_rounds=sum(x['phase']==1 for x in rounds),phase2_rounds=len(phase2),
            recovery_objectives=[dict(iteration=x['iteration'],objective=x['witness']['objective'] if x['witness'] else None,
                                      status=x.get('solver_result',{}).get('status',x.get('status')),seconds=x['seconds']) for x in r['recoveries']],
            stagnation_rounds=sum(abs(b['objective']-a['objective'])<1e-7 for a,b in zip(phase2,phase2[1:])))
        analysis.append(summary)
    (OUT/'REPLAY.json').write_text(json.dumps(replay,indent=2),encoding='utf-8')
    (OUT/'ANALYSIS.json').write_text(json.dumps(analysis,indent=2),encoding='utf-8')
    print(json.dumps(dict(replayed=len(replay),full_enumeration=sum(x['scope']=='full_enumeration' for x in replay))))

if __name__=='__main__':main()
