"""一次性生成可审查的历史求解器副本；不写入历史目录。"""
from pathlib import Path
HERE=Path(__file__).resolve().parent
SUB=HERE.parent

def main():
    s=(SUB/'stage3/solver.py').read_text(encoding='utf-8')
    s=s.replace('pricing="rebuild"):', 'pricing="rebuild", progress=None):')
    s=s.replace('    def add(column):', '''    def notify(kind):
        if progress: progress(kind, result.get("lower_bound"), result.get("upper_bound"),
                              dict(columns=sum(map(len,pool.values()))))

    def add(column):''')
    s=s.replace('            result["witness"] = witness','            result["witness"] = witness\n            notify("verified_integer")')
    s=s.replace('                initial = [pool', '                notify("initial_economic_bound")\n                initial = [pool')
    s=s.replace('                        if phase == 2 and (iteration', '                        notify("complete_pricing_bound")\n                        if phase == 2 and (iteration')
    s=s.replace('    return result','    notify("cg_finished")\n    return result')
    (HERE/'cg_traced.py').write_text(s,encoding='utf-8')
    s=(SUB/'stage7/demand_profiles.py').read_text(encoding='utf-8')
    s=s.replace("HERE.parent/'stage3/solver.py'", "HERE/'cg_traced.py'")
    s=s.replace("solver='cplex_py',log_dir=None):", "solver='cplex_py',log_dir=None,progress=None):")
    s=s.replace("quota=False,", "quota=False,progress=progress,")
    s=s.replace("        r['global_upper_bound']=ub;r['lower_dp']=low;r['upper_dp']=up", "        r['global_upper_bound']=ub;r['lower_dp']=low;r['upper_dp']=up\n        if progress:progress('profile_account',r['global_lower_bound'],ub,dict(queries=len(queries)))")
    (HERE/'demand_traced.py').write_text(s,encoding='utf-8')
    s=(SUB/'compact_solver.py').read_text(encoding='utf-8')
    s=s.replace("ROOT = Path(__file__).resolve().parents[1]", "ROOT = Path(__file__).resolve().parents[2]")
    s=s.replace("log_dir=None):", "log_dir=None,progress=None):")
    s=s.replace("            model.problem.solve(make_solver(role='compact_ip'))", '''            from solver_backend import load_cplex
            import math
            cplex=load_cplex()
            variables=model.problem.variables()
            indices={v.name:i for i,v in enumerate(variables)}
            last=[None,-1.]
            class Observe(cplex.callbacks.MIPInfoCallback):
                def __call__(self):
                    now=time.perf_counter()-start
                    if now-last[1]<1.:return
                    last[1]=now
                    bound=float(self.get_best_objective_value())+float(model.problem.objective.constant)
                    if not math.isfinite(bound) or abs(bound)>=1e19:bound=None
                    if self.has_incumbent():
                        value=float(self.get_incumbent_objective_value())+float(model.problem.objective.constant)
                        if last[0] is None or value>last[0]:
                            values=self.get_incumbent_values()
                            records=[dict(line=l['id'],station=s,assignments=[(i,m)
                                for (li,i,ss,m),v in model.x.items()
                                if li==l['id'] and ss==s and values[indices[v.name]]>.5]) for l,s in blocks(data)]
                            witness=verify_integer_assignments(data,records,expected=value)
                            last[0]=witness['objective']
                            if result['first_integer_seconds'] is None:result['first_integer_seconds']=time.perf_counter()-start
                    if progress:progress('compact_native',last[0],bound,{})
            model.problem.solve(make_solver(role='compact_ip'),callback=[Observe] if progress else None)''')
    s=s.replace('    return result', "    if progress:progress('compact_finished',result['global_lower_bound'],result['global_upper_bound'],{})\n    return result")
    (HERE/'compact_traced.py').write_text(s,encoding='utf-8')

if __name__=='__main__':main()
