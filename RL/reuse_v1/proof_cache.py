"""Root whole-line Phase-II proof reuse. No truncated-bound contract enabled."""
import hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'sub'))
from validate import check_column

def digest(line):
    return hashlib.sha256(json.dumps(line,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

class ProofCache:
    def __init__(self,line,padding=1e-8):
        if not math.isfinite(padding) or padding<0:raise ValueError('Invalid bound padding')
        self.line=line;self.domain=digest(line);self.sources=[];self.padding=padding

    def add(self,line,cert,source):
        if digest(line)!=self.domain:raise ValueError('Domain mismatch')
        if cert['line']!=line['id'] or cert['phase']!=2 or cert.get('caps') is not None or cert.get('restrictions'):raise ValueError('Restricted/wrong pricing domain')
        if not cert['optimal']:return False
        s=cert['solver'];col=cert['column']
        if s.get('backend')!='cplex_py' or s['native_status']!=101 or not col:raise ValueError('Not a native exact certificate')
        check_column(line,col)
        h,r=cert['human_price'],cert['robot_price'];sigma=cert['sigma']
        if any(not math.isfinite(v) for v in (h,r,sigma)) or min(h,r)<0:raise ValueError('Invalid price')
        q=col['profit']-h*col['human']-r*col['robot']
        for v in (cert['reduced_cost'],s['objective'],s['best_bound']):
            if v is None or not math.isfinite(v) or abs(v+sigma-q)>1e-5:raise ValueError('Certificate objective mismatch')
        self.sources.append(dict(source=source,q=q,human=h,robot=r,domain=self.domain))
        return True

    def query(self,line,price,columns=()):
        if digest(line)!=self.domain:raise ValueError('Domain mismatch')
        if len(price)!=2 or any(not math.isfinite(v) or v<0 for v in price):raise ValueError('Invalid query price')
        # All count pairs are retained, including physically impossible pairs.
        # This over-approximation cannot make the maximization bound smaller.
        upper=None;cells=[];k=len(line['stations'])
        if self.sources:
            for h in range(k+1):
                for r in range(k+1):
                    values=[s['q']+s['human']*h+s['robot']*r+self.padding for s in self.sources]
                    i=min(range(len(values)),key=values.__getitem__)
                    v=values[i]-price[0]*h-price[1]*r
                    cells.append(dict(human=h,robot=r,upper=v,source_index=i))
            upper=max(c['upper'] for c in cells)
        lower=None
        for c in columns:
            check_column(line,c)
            v=c['profit']-price[0]*c['human']-price[1]*c['robot']
            lower=v if lower is None else max(lower,v)
        if lower is not None and upper is not None and upper<lower-1e-5:raise ValueError('Cached bound contradicts witness')
        return dict(domain=self.domain,price=list(price),upper=upper,lower=lower,
                    sources=list(self.sources),cells=cells,padding=self.padding)
