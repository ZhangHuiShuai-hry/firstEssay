"""独立算术验证修复列和全部整数witness；不使用生产定价/列验证函数。"""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'docs/branch_and_price'),str(ROOT/'code/dwcg'),str(ROOT/'code')]
from independent_bp_verify import oracle,integer_witness
from node_state import NumericPolicy
from dataclasses import asdict
from evidence_store import load_result
def main():
    folder=ROOT/'docs/root_diagnostics/repair_experiments';reports=[]
    for path in sorted(folder.glob('*/result.json')):
        result=json.loads(path.read_text(encoding='utf-8'));data=json.loads((path.parent/'instance.json').read_bytes())
        lines={l['id']:l for l in data['lines']};count=0;witnesses=0
        source=load_result(ROOT/'docs/root_diagnostics/no_compact_tasks040/certificate.sqlite')
        row=next(e for e in source['node']['certificate']['rounds'] if e['phase']==2 and e['iteration']==result['iteration'])
        patterns={(e['line'],e['station']):{tuple(sorted(tuple(a) for a in p)) for p in e['patterns']} for e in row['pool']}
        assert sum(map(len,patterns.values()))==result['initial_columns']
        for e in result['history']:
            for c in e.get('columns',[]):
                independent=oracle.pattern(lines[c['line']],c['station'],c['assignments'])
                assert abs(independent.profit-c['profit'])<1e-5
                key=c['line'],c['station'];assignment=tuple(sorted(tuple(a) for a in c['assignments']))
                assert assignment not in patterns[key];patterns[key].add(assignment)
                count+=1
            a=e.get('integer_recovery',e.get('result',{}));w=a.get('witness')
            if w:integer_witness(data,[],w,asdict(NumericPolicy()));witnesses+=1
            if 'incumbent_before' in e:assert e['incumbent_after']>=e['incumbent_before']-1e-6
        assert count==result['final_columns']-result['initial_columns']
        if result['witness']:
            integer_witness(data,[],result['witness'],asdict(NumericPolicy()))
            assert all(tuple(sorted(tuple(a) for a in e['assignments'])) in patterns[e['line'],e['station']] for e in result['witness']['stations'])
        assert not result['global_integer_optimal_proven']
        reports.append(dict(file=str(path.relative_to(folder)),added_columns=count,witnesses=witnesses,passed=True))
    (folder/'independent_validation.json').write_text(json.dumps(reports,indent=2),encoding='utf-8');print(json.dumps(reports))
if __name__=='__main__':main()
