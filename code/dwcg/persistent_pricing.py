"""Exact persistent native CPLEX station pricing; identical local MILP to pricing.py."""
from __future__ import annotations

import math
from pathlib import Path
import time

from common import make_column,reduced_cost
from solver_backend import BackendConfig,load_cplex


class PersistentPricing:
    def __init__(self,line,station,config=None,log_path=None):
        started=time.perf_counter()
        self.line=line;self.station=station;self.config=config or BackendConfig(name='cplex_py')
        self.cplex=load_cplex();self.log=None;self.records=[]
        keys={(task['id'],m):f'z_{i}_{m}' for i,task in enumerate(line['tasks']) for m in task['modes']}
        # Match PuLP's lexicographic variable order, avoiding an incidental ordering change.
        names=sorted(['u','h','r']+list(keys.values()));index={name:i for i,name in enumerate(names)}
        self.z={key:index[name] for key,name in keys.items()};self.u=index['u'];self.h=index['h'];self.r=index['r']
        n=len(line['tasks']);duration={self.u:-line['cycle_time']};fatigue={self.h:math.log1p(-line['fatigue_limit'])}
        count={};nh={};nr={};rows=[];rhs=[]
        for task in line['tasks']:
            choices={self.z[task['id'],m]:1. for m in task['modes']}
            rows.append(choices);rhs.append(1.)
            for m,p in task['modes'].items():
                j=self.z[task['id'],m];count[j]=1.;duration[j]=p['time']
                if p['time']*p['beta']:fatigue[j]=p['time']*p['beta']
                if m in ('H','J'):nh[j]=1.
                if m in ('R','J'):nr[j]=1.
        rows.append(duration);rhs.append(0.)
        for variable,total in ((self.u,count),(self.h,nh),(self.r,nr)):
            rows.append({variable:1.,**{j:-a for j,a in total.items()}});rhs.append(0.)
            rows.append({variable:-n,**total});rhs.append(0.)
        rows.append(fatigue);rhs.append(0.)
        self.structure_seconds=time.perf_counter()-started
        tick=time.perf_counter();self.native=self.cplex.Cplex()
        if log_path:
            Path(log_path).parent.mkdir(parents=True,exist_ok=True);self.log=open(log_path,'w',encoding='utf-8')
        for stream in ('results','log','warning','error'):getattr(self.native,'set_'+stream+'_stream')(self.log)
        p=self.native.parameters
        p.threads.set(self.config.threads);p.randomseed.set(self.config.seed);p.parallel.set(1)
        p.simplex.tolerances.feasibility.set(self.config.primal_tolerance)
        p.simplex.tolerances.optimality.set(self.config.dual_tolerance)
        p.mip.tolerances.integrality.set(self.config.mip_integrality_tolerance)
        p.mip.tolerances.mipgap.set(0.);p.mip.tolerances.absmipgap.set(0.)
        self.native.objective.set_sense(self.native.objective.sense.maximize)
        # PuLP's binary variables are translated as bounded CPLEX integer variables.
        self.native.variables.add(names=names,lb=[0.]*len(names),ub=[1.]*len(names),types='I'*len(names))
        self.native.linear_constraints.add(lin_expr=[self.cplex.SparsePair(ind=list(row),val=list(row.values())) for row in rows],
                                           senses='L'*len(rows),rhs=rhs,names=[f'_C{i+1}' for i in range(len(rows))])
        self.native_creation_seconds=time.perf_counter()-tick
        self.creation_seconds=time.perf_counter()-started

    def solve(self,duals,phase=2,deadline=None):
        if phase not in (1,2):raise ValueError('Pricing phase must be 1 or 2')
        tick=time.perf_counter();line=self.line;l=line['id'];station=self.station
        sigma={task['id']:0. for task in line['tasks']}
        for e,(i,j) in enumerate(line.get('precedence',[])):
            suffix=sum(duals['precedence',l,e,k] for k in range(station,len(line['stations'])+1))
            sigma[i]+=suffix;sigma[j]-=suffix
        objective=[]
        for task in line['tasks']:
            i=task['id']
            for m,p in task['modes'].items():
                reward=(task['value']-p['cost']) if phase==2 else 0.
                reward+=-duals['task',l,i]+duals['recovery',l]*task.get('weight',0)+sigma[i]
                objective.append((self.z[i,m],reward))
        costs=line['stations'][station-1]
        objective.extend([(self.u,-costs['fixed_cost'] if phase==2 else 0.),
                          (self.h,-((costs['human_cost'] if phase==2 else 0.)+duals['human',])),
                          (self.r,-((costs['robot_cost'] if phase==2 else 0.)+duals['robot',]))])
        if not all(math.isfinite(v) for _,v in objective):raise RuntimeError('Nonfinite pricing objective')
        self.native.objective.set_linear(objective)
        # Match CPLEX_PY: optimize variable terms and add the station constant back.
        self.objective_constant=-duals['station',l,station]
        if not math.isfinite(self.objective_constant):raise RuntimeError('Nonfinite pricing constant')
        record=dict(phase=phase,line=l,station=station,objective_update_time=time.perf_counter()-tick,
                    native_time=0.,read_time=0.,status='unproven',native_status=None,rc=None,best_bound=None,optimal=False)
        try:
            remaining=deadline-time.perf_counter() if deadline is not None else self.cplex.infinity
            if remaining<=0:record['status']='time_limit';raise TimeoutError('Root budget exhausted before pricing solve')
            self.native.parameters.timelimit.set(remaining)
            tick=time.perf_counter()
            try:self.native.solve()
            finally:record['native_time']=time.perf_counter()-tick
            solution=self.native.solution;code=solution.get_status();record['native_status']=code
            record['native_status_text']=solution.get_status_string()
            try:
                bound=float(solution.MIP.get_best_objective())
                record['best_bound']=bound+self.objective_constant if math.isfinite(bound) and abs(bound)<1e19 else None
            except self.cplex.exceptions.CplexSolverError:pass
            if code!=101:
                record['status']='time_limit' if code in (10,11,12,107,108) else 'unproven'
                if record['status']=='time_limit':raise TimeoutError(f'Exact native PP time limit: {code}')
                raise RuntimeError(f'Exact native PP not proven optimal: {record["native_status_text"]}')
            tick=time.perf_counter();values=solution.get_values()
            if not all(math.isfinite(v) for v in values):raise RuntimeError('Nonfinite native PP solution')
            if any(abs(v-round(v))>1e-6 for v in values) or min(solution.get_linear_slacks()) < -1e-6:
                raise RuntimeError('Native PP primal/integrality violation')
            col=make_column(line,station,[key for key,j in self.z.items() if values[j]>.5])
            rc=reduced_cost(line,station,col,duals,phase);value=solution.get_objective_value()+self.objective_constant
            if not math.isfinite(rc) or abs(rc-value)>1e-5:
                raise RuntimeError('Native PP objective disagrees with explicit reduced cost')
            record.update(status='optimal',optimal=True,rc=rc,objective=value,nodes=solution.progress.get_num_nodes_processed(),
                          mip_gap=solution.MIP.get_mip_relative_gap(),read_time=time.perf_counter()-tick)
            return col,rc
        finally:self.records.append(record)

    def close(self):
        self.native.end()
        if self.log:self.log.close()
