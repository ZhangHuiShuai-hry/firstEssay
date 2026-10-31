"""Persistent native CPLEX LP master. Local pricing remains unchanged."""
from __future__ import annotations
import math
import time
from dataclasses import dataclass

import pulp
from common import empty_pool, blocks, coefficients
from master import build_master
from solver_backend import load_cplex, BackendConfig


@dataclass
class NativeVariable:
    name: str
    index: int
    varValue: float | None = None
    dj: float | None = None

    def value(self): return self.varValue


class IncrementalMaster:
    def __init__(self,data,config=None,log_path=None):
        self.data=data;self.config=config or BackendConfig(name='cplex_py')
        self.cplex=load_cplex();self.native=self.cplex.Cplex()
        self.log=open(log_path,'w',encoding='utf-8') if log_path else None
        for stream in ('results','log','warning','error'):getattr(self.native,'set_'+stream+'_stream')(self.log)
        p=self.native.parameters;p.threads.set(self.config.threads);p.randomseed.set(self.config.seed);p.parallel.set(1)
        p.simplex.tolerances.feasibility.set(self.config.primal_tolerance)
        p.simplex.tolerances.optimality.set(self.config.dual_tolerance)
        p.advance.set(1)
        self.native.objective.set_sense(self.native.objective.sense.maximize)
        self.native.set_problem_type(self.native.problem_type.LP)
        # Build the canonical row schema once, preserving order/names/RHS.
        template=build_master(data,empty_pool(data),phase=1)
        self.rows=template.rows
        self.row_indices={key:i for i,key in enumerate(self.rows)}
        self.native.linear_constraints.add(rhs=[-r.constant for r in self.rows.values()],
            senses=''.join('E' if r.sense==0 else 'L' for r in self.rows.values()),
            names=[r.name for r in self.rows.values()])
        self.variables={};self.artificials=[];self.profits={};self.phase=1;self._value=None
        for variable in template.artificials:
            entries=[(self.row_indices[key],row.get(variable,0)) for key,row in self.rows.items() if row.get(variable,0)]
            index=self.native.variables.get_num()
            self.native.variables.add(obj=[-1.],lb=[0.],ub=[self.cplex.infinity],names=[variable.name],
                columns=[self.cplex.SparsePair(ind=[i for i,v in entries],val=[v for i,v in entries])])
            self.artificials.append(NativeVariable(variable.name,index))
        self.solve_records=[];self.update_seconds=0.;self.native_solve_seconds=0.;self.read_seconds=0.

    def sync(self,pool,phase):
        tick=time.perf_counter()
        if phase not in (1,2) or phase<self.phase:raise ValueError('Invalid phase transition')
        if phase!=self.phase:
            # Fix all artificials at zero, remove their penalties, restore real profits.
            self.native.variables.set_upper_bounds([(v.index,0.) for v in self.artificials])
            self.native.objective.set_linear([(v.index,0.) for v in self.artificials]+
                [(self.variables[key].index,value) for key,value in self.profits.items()])
            self.phase=phase
        objs=[];cols=[];names=[]
        for bi,(line,s) in enumerate(blocks(self.data)):
            l=line['id']
            for pi,col in enumerate(pool[l,s]):
                key=(l,s,pi)
                if key in self.variables:continue
                index=self.native.variables.get_num()+len(objs)
                name=f'lambda_{bi}_{pi}';self.variables[key]=NativeVariable(name,index);self.profits[key]=col.profit
                vector=coefficients(line,s,col)
                cols.append(self.cplex.SparsePair(ind=[self.row_indices[row] for row in vector],val=list(vector.values())))
                objs.append(col.profit if phase==2 else 0.);names.append(name)
        if objs:self.native.variables.add(obj=objs,lb=[0.]*len(objs),ub=[self.cplex.infinity]*len(objs),names=names,columns=cols)
        self.update_seconds+=time.perf_counter()-tick
        return self

    def solve(self,deadline=None):
        remaining=deadline-time.perf_counter() if deadline is not None else self.cplex.infinity
        if remaining<=0:raise TimeoutError('Root time budget exhausted before RMP solve')
        self.native.parameters.timelimit.set(remaining)
        basis_before=False
        try:self.native.solution.basis.get_basis();basis_before=True
        except self.cplex.exceptions.CplexSolverError:pass
        tick=time.perf_counter();self.native.solve();elapsed=time.perf_counter()-tick
        self.native_solve_seconds+=elapsed
        code=self.native.solution.get_status()
        record=dict(phase=self.phase,status=code,native_seconds=elapsed,variables=self.native.variables.get_num(),
                    basis_available_before=basis_before,advance=1,iterations=self.native.solution.progress.get_num_iterations())
        self.solve_records.append(record)
        if code!=1:
            if code in (10,11,12):raise TimeoutError(f'Native RMP LP limit: {code}')
            raise RuntimeError(f'Native RMP not optimal: {self.native.solution.get_status_string()}')
        tick=time.perf_counter()
        values=self.native.solution.get_values();dj=self.native.solution.get_reduced_costs()
        dual=self.native.solution.get_dual_values();self._value=self.native.solution.get_objective_value()
        if not all(math.isfinite(x) for x in [self._value]+dual+values+dj):raise RuntimeError('Nonfinite native LP solution')
        for variable in list(self.variables.values())+self.artificials:
            variable.varValue=values[variable.index];variable.dj=dj[variable.index]
        for key,i in self.row_indices.items():
            self.rows[key].pi=dual[i]
            if self.rows[key].sense==-1 and dual[i]<-1e-6:raise RuntimeError('Invalid native dual sign')
        self.read_seconds+=time.perf_counter()-tick
        return self

    def value(self):return self._value

    def duals(self):return {key:row.pi for key,row in self.rows.items()}

    def close(self):
        self.native.end()
        if self.log:self.log.close()
