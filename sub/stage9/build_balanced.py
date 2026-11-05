"""生成独立的轮内预算对照副本；历史与已运行源码不写入。"""
from pathlib import Path
HERE=Path(__file__).resolve().parent

def main():
    s=(HERE.parent/'stage8/cg_traced.py').read_text(encoding='utf-8')
    s=s.replace('progress=None):','progress=None, price_override=None):')
    s=s.replace('price = session.solve if session else solve_line','price = price_override or (session.solve if session else solve_line)')
    old='                        for line in data["lines"]:'
    assert s.count(old)==1
    s=s.replace(old,'                        for price_position, line in enumerate(data["lines"]):')
    s=s.replace('                                policy=policy)\n                            result["pricing_calls"]', '                                policy=policy, time_limit=max(.001,(deadline-time.perf_counter())/(len(data["lines"])-price_position)))\n                            result["pricing_calls"]')
    old='result.update(status=cert["status"], termination_reason="pricing_not_proven_optimal")\n                                break'
    assert s.count(old)==1
    s=s.replace(old,'result.update(status=cert["status"], termination_reason="pricing_not_proven_optimal")\n                                # 继续尝试本轮其他块；不完整轮仍终止CG，不能标精确最优。')
    (HERE/'cg_balanced.py').write_text(s,encoding='utf-8')
    s=(HERE.parent/'stage8/demand_traced.py').read_text(encoding='utf-8').replace("HERE/'cg_traced.py'", "HERE/'cg_balanced.py'")
    (HERE/'demand_balanced.py').write_text(s,encoding='utf-8')
    s=(HERE/'bound_worker.py').read_text(encoding='utf-8').replace('from economic_bound import run','from balanced_bound import run').replace("a.worker=='economic_bound'", "a.worker=='balanced_bound'")
    (HERE/'balanced_worker.py').write_text(s,encoding='utf-8')
    s=(HERE/'benchmark_bound.py').read_text(encoding='utf-8').replace("HERE/'bound_worker.py'", "HERE/'balanced_worker.py'").replace("'economic_bound'", "'balanced_bound'")
    s=s.replace("names=['tasks060_lines02_r90_seed21.json','tasks080_lines02_r90_seed21.json']", "names=['tasks080_lines02_r90_seed21.json']")
    s=s.replace("    if a.suite=='pilot':names.append('tasks060_lines02_r50_seed21.json')", "    # 此消融只复验已定位预算饥饿的80任务输入，全部既有结果保留。")
    s=s.replace("methods=['compact_plain','balanced_bound'] if n%2==0 else ['balanced_bound','compact_plain']", "methods=['balanced_bound']")
    (HERE/'benchmark_balanced.py').write_text(s,encoding='utf-8')

if __name__=='__main__':main()
