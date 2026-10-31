"""Audit saved large-instance integer solutions and completed pricing bounds."""
import json,sys,math
from pathlib import Path
from datetime import datetime,timezone
from generate_instances import compact
from common import blocks,make_column,reduced_cost

def audit(root,n):
    key=f'total{n}_L2_s11'; data=json.loads((root/'instances'/f'{key}.json').read_text())
    ip=json.loads((root/'raw'/f'{key}_ip.json').read_text());cg=json.loads((root/'raw'/f'{key}_cg.json').read_text())
    compact.validate_data(data); sol=ip['solution']; lines={x['id']:x for x in data['lines']}; total=0.;h=r=0
    for line_sol in sol['lines']:
        line=lines[line_sol['id']]; station_of={}; selected=set(); recovery=0
        for station in line_sol['stations']:
            s=station['station']; assignments=[(a['task'],a['mode']) for a in station['assignments_in_order']]
            col=make_column(line,s,assignments); assert len({i for i,m in assignments})==len(assignments)
            assert (station['active'],station['human'],station['robot'])==(int(bool(assignments)),col.human,col.robot)
            for i,m in assignments:
                assert i not in selected;selected.add(i);station_of[i]=s
            h+=col.human;r+=col.robot;recovery+=col.recovery;total+=col.profit
        assert set(line['required_tasks'])<=selected and recovery>=line['min_recovery']-1e-6
        assert set(line_sol['selected_tasks'])==selected
        for i,j in line['precedence']:
            assert j not in selected or (i in selected and station_of[i]<=station_of[j])
    assert h<=data['human_limit'] and r<=data['robot_limit'] and abs(total-ip['incumbent'])<1e-5
    expected={(l['id'],s) for l,s in blocks(data)}; complete=[];maxdiff=0.;calls=0
    for rnd in cg['rounds']:
        if rnd['phase']!=2 or not rnd['complete_pricing']:continue
        dual={tuple(x['row']):x['value'] for x in rnd['duals']};ps=rnd['pricing']
        assert len(ps)==len(expected) and {(p['line'],p['station']) for p in ps}==expected
        for p in ps:
            assert p['status']=='optimal' and p['native_status']==101
            col=make_column(lines[p['line']],p['station'],p['assignments'],tolerance=1e-6)
            d=abs(reduced_cost(lines[p['line']],p['station'],col,dual,2)-p['rc']);maxdiff=max(maxdiff,d);calls+=1
            assert d<1e-5 and abs(p['best_bound']-p['rc'])<1e-5
        bound=rnd['objective']+sum(max(0,p['rc']) for p in ps)
        assert abs(bound-rnd['upper_bound'])<1e-5
        complete.append((bound,rnd))
    best,round_=min(complete,key=lambda x:x[0]);assert abs(best-cg['upper_bound'])<1e-6
    assert ip['incumbent']<=best+1e-6
    return dict(tasks=n,verified_integer_profit=total,human=h,robot=r,rmp_lower=cg['lower_bound'],upper=best,certificate_round=round_['round'],certificate_wall_time=round_['wall_time'],certificate_rmp=round_['objective'],stations=len(expected),checked_pp_calls=calls,max_rc_delta=maxdiff,combined_gap=(best-ip['incumbent'])/abs(ip['incumbent']),budgets_seconds={'direct_mip':600,'cg':600},cg_status=cg['status'],mip_status=ip['status'])

if __name__=='__main__':
    root=Path('experiments/runs/large_120_150_600_01'); result={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'scope':'Saved completed exact pricing rounds and reconstructed integer feasibility; no full enumeration', 'results':[audit(root,n) for n in (120,150)]}
    out=Path('experiments/runs/hybrid_baseline_audit_01');out.mkdir(exist_ok=False);(out/'certificate.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
