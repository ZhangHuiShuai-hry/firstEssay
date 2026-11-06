"""Auditable Phase-II price actions; no changes to the production CG engine."""
import math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'sub'))
from validate import check_column
ALPHAS=(1.,.75,.5,.25)
def prices(current,reference,alpha):
    if alpha not in ALPHAS:raise ValueError('Unsupported action')
    if len(current)!=2 or len(reference)!=2:raise ValueError('Two resource prices required')
    if any(not math.isfinite(v) or v<0 for v in (*current,*reference)):raise ValueError('Nonnegative finite prices required')
    return [alpha*c+(1-alpha)*r for c,r in zip(current,reference)]
def exact_upper_bound(data,price,certificates):
    """Return null without complete proven maxima. Incumbents never replace upper bounds."""
    prices(price,price,1.)
    lines={l['id']:l for l in data['lines']}
    if len(certificates)!=len(lines) or {c['line'] for c in certificates}!=set(lines):raise ValueError('Incomplete or duplicate line coverage')
    vals=[]
    for c in certificates:
        if c['phase']!=2 or c['caps'] is not None or c['sigma']!=0 or [c['human_price'],c['robot_price']]!=list(price):raise ValueError('Wrong pricing domain or objective')
        if not c['optimal']:return None
        if c['solver']['native_status']!=101 or not c['column']:raise ValueError('Invalid optimal certificate')
        col=c['column'];check_column(lines[c['line']],col)
        q=col['profit']-price[0]*col['human']-price[1]*col['robot']
        if not all(math.isfinite(c['solver'][k]) for k in ('objective','best_bound')):raise ValueError('Nonfinite objective')
        if any(abs(v-q)>1e-5 for v in (c['reduced_cost'],c['solver']['objective'],c['solver']['best_bound'])):raise ValueError('Objective/bound mismatch')
        vals.append(q)
    return price[0]*data['human_limit']+price[1]*data['robot_limit']+sum(vals)
