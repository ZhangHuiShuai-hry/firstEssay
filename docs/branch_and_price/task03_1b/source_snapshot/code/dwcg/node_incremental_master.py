"""Native append-only LP per node; generalized elastic schema from node RMP.

PuLP row objects remain as independent primal/certificate validation mirrors.
The optimization model is native, appended rather than rebuilt.
"""
import math
import time
import pulp
from solver_backend import load_cplex


class NodeIncrementalMaster:
    def __init__(self,config,log_path=None):
        self.cplex=load_cplex();self.native=self.cplex.Cplex();self.indices={};self.row_names=None;self.phase=1
        self.log=open(log_path,'w',encoding='utf-8') if log_path else None
        for stream in ('results','warning','error','log'):getattr(self.native,'set_'+stream+'_stream')(self.log)
        p=self.native.parameters;p.threads.set(1);p.randomseed.set(config.seed);p.parallel.set(1);p.advance.set(1)
        p.simplex.tolerances.feasibility.set(config.primal_tolerance);p.simplex.tolerances.optimality.set(config.dual_tolerance)
        self.native.objective.set_sense(self.native.objective.sense.maximize)
        self.native.set_problem_type(self.native.problem_type.LP)
        self.deadline=config.deadline;self.records=[]

    def sync(self,m):
        rows=list(m.rows.values());names=[r.name for r in rows]
        if self.row_names is None:
            self.row_names=names
            self.native.linear_constraints.add(rhs=[-r.constant for r in rows],senses=''.join('E' if r.sense==0 else 'L' for r in rows),names=names)
        if names!=self.row_names:raise RuntimeError('Node row schema changed')
        if m.phase<self.phase:raise RuntimeError('Backward RMP phase switch')
        if m.phase!=self.phase:
            arts=[(name,j) for name,j in self.indices.items() if name.startswith('elastic_')]
            self.native.variables.set_upper_bounds([(j,0.) for name,j in arts])
            self.native.objective.set_linear([(j,0.) for name,j in self.indices.items()])
            self.phase=m.phase
        for v in m.problem.variables():
            if v.name=='__dummy':continue
            if v.name not in self.indices:
                j=self.native.variables.get_num();self.indices[v.name]=j
                entries=[(i,float(row.get(v,0))) for i,row in enumerate(rows) if row.get(v,0)]
                self.native.variables.add(names=[v.name],lb=[0.],ub=[self.cplex.infinity],obj=[float(m.objective.get(v,0))],
                    columns=[self.cplex.SparsePair(ind=[i for i,c in entries],val=[c for i,c in entries])])
            self.native.objective.set_linear(self.indices[v.name],float(m.objective.get(v,0)))
        m.native_adapter=self
        return m

    def solve_mirror(self,m):
        remaining=self.deadline-time.perf_counter() if self.deadline else self.cplex.infinity
        if remaining<=0:raise TimeoutError('Native node RMP deadline')
        self.native.parameters.timelimit.set(remaining)
        tick=time.perf_counter();self.native.solve();elapsed=time.perf_counter()-tick
        read_started=time.perf_counter()
        code=self.native.solution.get_status()
        if code!=1:
            if code in (10,11,12):raise TimeoutError('Native node LP time limit')
            raise RuntimeError('Native node LP not optimal: '+self.native.solution.get_status_string())
        vals=self.native.solution.get_values();dj=self.native.solution.get_reduced_costs();dual=self.native.solution.get_dual_values()
        if not all(math.isfinite(v) for v in vals+dj+dual):raise RuntimeError('Nonfinite native LP')
        for v in m.problem.variables():
            if v.name=='__dummy':v.varValue=0;continue
            j=self.indices[v.name];v.varValue=vals[j];v.dj=dj[j]
        for row,value in zip(m.rows.values(),dual):row.pi=value
        m.problem.assignStatus(pulp.LpStatusOptimal,pulp.LpSolutionOptimal)
        m.problem.backend_result=dict(status='optimal',optimal=True,objective=self.native.solution.get_objective_value(),
            best_bound=self.native.solution.get_objective_value(),has_incumbent=True,native_status=code,
            backend='incremental_node_cplex',wall_time=elapsed,solver_time=elapsed)
        m.problem.backend_result['native_read_seconds']=time.perf_counter()-read_started
        self.records.append(dict(m.problem.backend_result))

    def close(self):
        self.native.end()
        if self.log:self.log.close()
