"""Independent reproducible audit harness for model.py.

Uses a minimal linear-expression adapter to execute the uploaded PuLP *model builder*
against SciPy/HiGHS MILP (not against PuLP/CBC), then independently checks answers
by exhaustive enumeration. No production solver code is edited.

Run: python audit_dlbp.py
"""
from __future__ import annotations
import importlib.util, itertools, json, math, random, sys, types
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint

# Small PuLP-compatible algebraic facade for tests only.
vars_=[]
class Exp:
    def __init__(self, c=None, k=0.): self.c=dict(c or {}); self.k=float(k)
    @staticmethod
    def into(z):
        if isinstance(z,Exp): return z
        if isinstance(z,(int,float,np.number)): return Exp(k=z)
        raise TypeError(type(z))
    def __add__(self,o):
        o=self.into(o); d=self.c.copy()
        for i,v in o.c.items(): d[i]=d.get(i,0.)+v
        return Exp(d,self.k+o.k)
    def __radd__(self,o): return self+o
    def __neg__(self): return Exp({i:-v for i,v in self.c.items()},-self.k)
    def __sub__(self,o): return self+-self.into(o)
    def __rsub__(self,o): return self.into(o)+-self
    def __mul__(self,o):
        if not isinstance(o,(int,float,np.number)): raise TypeError('only scalar multiplication')
        return Exp({i:o*v for i,v in self.c.items()},o*self.k)
    def __rmul__(self,o): return self*o
    def __le__(self,o): return Constraint(self-self.into(o),'<=')
    def __ge__(self,o): return Constraint(self-self.into(o),'>=')
    def __eq__(self,o): return Constraint(self-self.into(o),'==')
    def eval(self): return sum(vars_[i]._v*v for i,v in self.c.items())+self.k
class Var(Exp):
    def __init__(self,name,cat=None):
        self.name=name;self._v=None;self.idx=len(vars_);vars_.append(self)
        super().__init__({self.idx:1.})
    def value(self): return self._v
class Constraint:
    def __init__(self,e,kind): self.e=e;self.kind=kind
class Problem:
    def __init__(self,name,sense): self.cons=[]; self.objective=None;self.status=0;self.sol_status=0
    def __iadd__(self,x):
        item,name=x
        if isinstance(item,Constraint): self.cons.append((item,name))
        else:
            assert self.objective is None
            self.objective=Exp.into(item)
        return self
    def solve_scipy(self):
        n=len(vars_); c=np.zeros(n);lo=[];hi=[];mat=[]
        for i,v in self.objective.c.items(): c[i]=-v
        for con,name in self.cons:
            a=np.zeros(n)
            for i,v in con.e.c.items(): a[i]=v
            bound=-con.e.k
            mat.append(a)
            lo.append(bound if con.kind in ('==','>=') else -np.inf)
            hi.append(bound if con.kind in ('==','<=') else np.inf)
        res=milp(c=c,integrality=np.ones(n),bounds=Bounds(np.zeros(n),np.ones(n)),constraints=LinearConstraint(np.array(mat),lo,hi),options={'mip_rel_gap':0.0})
        self.status=1 if res.status==0 else -2 if res.status==2 else -1
        self.sol_status=1 if res.status==0 else 0
        if res.x is not None:
            for v,z in zip(vars_,res.x): v._v=float(z)
        return res
    def valid(self,tol):
        if any(v._v is None or abs(v._v-round(v._v))>tol or v._v < -tol or v._v>1+tol for v in vars_): return False
        return all((c.e.eval()<=tol if c.kind=='<=' else c.e.eval()>=-tol if c.kind=='>=' else abs(c.e.eval())<=tol) for c,n in self.cons)

def lpSum(terms): return sum(terms,Exp())
class Sol(dict):
    pass
sol=Sol({0:'No solution',1:'Optimal',2:'Integer Feasible'}); sol.LpSolutionOptimal=1;sol.LpSolutionIntegerFeasible=2
fake=types.ModuleType('pulp')
fake.LpVariable=Var; fake.LpProblem=Problem; fake.lpSum=lpSum
fake.LpMaximize=1;fake.LpStatus={1:'Optimal',-1:'Not Solved',-2:'Infeasible',0:'Not Solved'}
fake.LpSolution=sol;fake.LpSolutionOptimal=1;fake.LpSolutionIntegerFeasible=2;fake.value=lambda expr:Exp.into(expr).eval()
sys.modules['pulp']=fake
spec=importlib.util.spec_from_file_location('audited_model','/mnt/data/model.py')
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)

def solve_source(data):
    vars_.clear()
    m=mod.build_model(data)
    res=m.problem.solve_scipy()
    report=mod.solution_report(m)
    assert report['has_feasible_solution'] == (res.status==0)
    if res.status==0: assert abs(report['objective'] - (-res.fun+m.problem.objective.k))<1e-5
    return report, m

def exhaustive(data):
    line_options=[]
    for line in data['lines']:
        station_count=len(line['stations'])
        selections=[[(None,None)]+[(s,m) for s in range(station_count) for m in task['modes']] for task in line['tasks']]
        line_options.append(list(itertools.product(*selections)))
    best=-math.inf; best_config=None
    for config in itertools.product(*line_options):
        nh=nr=0;value=0;valid=True
        for line,choices in zip(data['lines'],config):
            tasks=line['tasks']; ix={t['id']:j for j,t in enumerate(tasks)}
            chosen={t['id']:choice for t,choice in zip(tasks,choices)}
            for i,j in line.get('precedence',[]):
                if chosen[j][0] is not None and (chosen[i][0] is None or chosen[i][0]>chosen[j][0]): valid=False; break
            if not valid: break
            if any(chosen[i][0] is None for i in line.get('required_tasks',[])): valid=False;break
            if sum(t.get('weight',0) for t,c in zip(tasks,choices) if c[0] is not None)+1e-9 < line.get('min_recovery',0):valid=False;break
            for s,cost in enumerate(line['stations']):
                selected=[(t,ch[1]) for t,ch in zip(tasks,choices) if ch[0]==s]
                time=sum(t['modes'][m]['time'] for t,m in selected)
                load=sum(t['modes'][m]['time']*t['modes'][m]['beta'] for t,m in selected)
                if time > line['cycle_time']+1e-9 or load > -math.log1p(-line['fatigue_limit'])+1e-9:valid=False;break
                h=int(any(m in ('H','J') for t,m in selected))
                r=int(any(m in ('R','J') for t,m in selected))
                nh+=h;nr+=r
                value-=int(bool(selected))*cost['fixed_cost']+h*cost['human_cost']+r*cost['robot_cost']
                value+=sum(t['value']-t['modes'][m]['cost'] for t,m in selected)
            if not valid: break
        if valid and nh<=data['human_limit'] and nr<=data['robot_limit'] and value>best:
            best=value;best_config=config
    return best,best_config

if __name__=='__main__':
    single=json.load(open('/mnt/data/single_line.json'))
    r,m=solve_source(single)
    print('Single line solve:', json.dumps(r,indent=2,ensure_ascii=False))
    b,c=exhaustive(single)
    print('Single line exhaustive:',b,'matched?',abs(r['objective']-b)<1e-6)
    rng=random.Random(314159)
    num=0; errors=[]
    for case in range(60):
        L=1 if case%3 else 2
        lines=[]
        for l in range(L):
            n=2+(case%2);ns=1+(case%3!=0)
            tasks=[]
            for i in range(n):
                modes={}
                for m in ['H','R','J']:
                    if rng.random() < .56:
                        modes[m]={'time':rng.randint(1,4),'cost':rng.randint(0,4),'beta':0 if m=='R' else round(rng.random()*.4,2)}
                if not modes:modes={'R':{'time':2,'cost':1,'beta':0}}
                tasks.append({'id':str(i+1),'value':rng.randint(-2,12),'weight':rng.randint(0,3),'modes':modes})
            edges=[['1',str(i+1)] for i in range(1,n) if rng.random()<.7]
            lines.append({'id':'L'+str(l+1),'cycle_time':rng.randint(2,7),'fatigue_limit':rng.choice([0.,.3,.5,.9]),
                'stations':[{'fixed_cost':rng.randint(0,3),'human_cost':rng.randint(0,3),'robot_cost':rng.randint(0,3)} for _ in range(ns)],
                'tasks':tasks,'precedence':edges,'required_tasks':['1'] if rng.random()<.25 else [],
                'min_recovery':rng.choice([0,1,3])})
        data={'human_limit':rng.randint(0,3),'robot_limit':rng.randint(0,2),'lines':lines}
        r,m=solve_source(data);b,conf=exhaustive(data)
        if b==-math.inf:
            if r['has_feasible_solution']: errors.append((case,'expected infeasible',r['objective']))
        elif not r['has_feasible_solution'] or abs(r['objective']-b)>1e-5:
            errors.append((case,b,r))
        num+=1
    print('Random exact comparisons:',num,'disagreements:',len(errors))
    if errors: print('ERRORS',repr(errors[:10]));raise SystemExit(1)
    print('All crosschecks passed')
