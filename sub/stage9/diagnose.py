"""读取已完成证据分析PP覆盖及互不重叠的原生PP计时；不调用求解器。"""
import json,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent

def main():
    rows=[]
    for suite in ('pilot120','confirm600','balanced600'):
        for p in sorted((HERE/'evidence'/suite).glob('*/result.json.zlib')):
            r=json.loads(zlib.decompress(p.read_bytes()));b=r.get('base_result',r)
            if 'cg' not in b:continue
            cg=b['cg'];certs=cg['initialization']+cg.get('initialization_fallback',[])+[c for h in cg['history'] for c in h['pricing']]
            timings={k:sum(c.get('profile',{}).get(k,0) for c in certs) for k in ('create_seconds','objective_start_update_seconds','pre_solve_seconds','native_seconds','read_seconds','validate_seconds')}
            total=sum(timings.values());assert total<=cg['wall_seconds']+1e-5
            rows.append(dict(suite=suite,run=p.parent.name,cg_status=cg['status'],cg_wall_seconds=cg['wall_seconds'],pp_components_nonoverlapping=timings,
                pp_total_seconds=total,cg_non_pp_residual_seconds=cg['wall_seconds']-total,
                pricing_rounds=[dict(phase=h['phase'],lines=[c['line'] for c in h['pricing']],optimal=[c['optimal'] for c in h['pricing']],
                    pp_solve_seconds=[c['solver'].get('solver_time') for c in h['pricing']],resource_prices=h['rmp']['duals'],complete_exact=h['complete_exact_pricing']) for h in cg['history']],
                resources_used=b['witness']['resources_used'] if b['witness'] else None,
                line_profits={line:sum(s['profit'] for s in b['witness']['stations'] if s['line']==line) for line in cg['pool']} if b['witness'] else None,
                initial_profile_recombination_objective=b['incumbent_history'][0]['objective'] if b['incumbent_history'] else None,
                final_objective=b['global_lower_bound'],base_upper_bound=b['global_upper_bound'],final_upper_bound=r['global_upper_bound'],
                profile_calls=b['profile_calls'],query_seconds=sum(q['certificate']['total_seconds'] for q in b['queries'] if q['certificate'])))
    (HERE/'evidence/diagnostics.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    for r in rows:print(r['suite'],r['run'],r['cg_wall_seconds'],r['line_profits'],r['resources_used'],r['initial_profile_recombination_objective'],r['final_objective'])

if __name__=='__main__':main()
