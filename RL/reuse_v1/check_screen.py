"""Independent cached-certificate checker; no imports from the production cache."""
import hashlib,json,math
def check(line,c,calls):
    q=c['reuse_proof'];domain=hashlib.sha256(json.dumps(line,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    assert q['domain']==domain and q['padding']==1e-8 and c['phase']==2 and c['caps'] is None
    assert not c['optimal'] and c['column'] is None and c['solver']['native_status'] is None
    price=[c['human_price'],c['robot_price']];assert q['price']==price and all(math.isfinite(v) and v>=0 for v in price)
    assert q['sources'];values=[]
    for s in q['sources']:
        i=int(s['source']);assert 0<=i<c['call_index'];old=calls[i]
        assert old['call_index']==i and old['line']==line['id'] and old['optimal'] and old['phase']==2 and old['caps'] is None
        assert old['solver']['backend']=='cplex_py' and old['solver']['native_status']==101 and not old.get('restrictions')
        col=old['column'];v=col['profit']-old['human_price']*col['human']-old['robot_price']*col['robot']
        assert s['domain']==domain and abs(v-s['q'])<1e-8 and s['human']==old['human_price'] and s['robot']==old['robot_price']
        for val in (old['reduced_cost'],old['solver']['objective'],old['solver']['best_bound']):assert abs(val+old['sigma']-v)<1e-5
    cells=[]
    for h in range(len(line['stations'])+1):
        for r in range(len(line['stations'])+1):
            vals=[s['q']+s['human']*h+s['robot']*r+1e-8 for s in q['sources']];idx=min(range(len(vals)),key=vals.__getitem__)
            cells.append(dict(human=h,robot=r,upper=vals[idx]-price[0]*h-price[1]*r,source_index=idx))
    assert cells==q['cells'] and max(x['upper'] for x in cells)==q['upper']
    assert abs(q['upper']-c['sigma']-c['reduced_cost_upper_bound'])<1e-9 and c['reduced_cost_upper_bound']<=1e-7
