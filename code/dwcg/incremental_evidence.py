"""Append-only column IDs and immutable prefix views; expand only for legacy replay."""
from dataclasses import fields,is_dataclass

class ColumnLedger:
    def __init__(self):self.columns={}
    def capture(self,pool):
        counts=[]
        for key,columns in sorted(pool.items()):
            old=self.columns.setdefault(key,[])
            if len(columns)<len(old):raise ValueError('Column pool shrank')
            if any(c.assignments!=old[i] for i,c in enumerate(columns[:len(old)])):
                raise ValueError('Column prefix changed')
            for column in columns[len(old):]:old.append(column.assignments)
            counts.append((key,len(columns)))
        return PoolView(self,tuple(counts))

class PoolView:
    def __init__(self,ledger,counts):self.ledger=ledger;self.counts=counts
    def __deepcopy__(self,memo):return self
    def materialize(self):
        return [dict(line=l,station=s,patterns=[[list(a) for a in c] for c in self.ledger.columns[l,s][:n]]) for (l,s),n in self.counts]

class PrimalView:
    def __init__(self,pool,variables):
        self.pool=pool;self.coordinates=tuple(variables);self.weights=tuple(v.value() for v in variables.values())
    def __deepcopy__(self,memo):return self
    def __iter__(self):
        for (l,s,p),weight in zip(self.coordinates,self.weights):
            yield dict(line=l,station=s,column=p,assignments=list(self.pool.ledger.columns[l,s][p]),weight=weight)
    def materialize(self):return list(self)

def certificate_fields(certificate):
    return {f.name:getattr(certificate,f.name) for f in fields(certificate)}

def materialize(value):
    if isinstance(value,(PoolView,PrimalView)):return value.materialize()
    if isinstance(value,dict):return {k:materialize(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [materialize(v) for v in value]
    return value
