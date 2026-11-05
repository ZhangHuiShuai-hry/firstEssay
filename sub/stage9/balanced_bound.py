import sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from economic_bound import refine
from demand_balanced import run as base_run

def run(data,*,time_limit=30,progress=None,**kwargs):
    start=time.perf_counter();base=base_run(data,time_limit=max(.001,time_limit-.25),progress=progress,**kwargs)
    r=refine(data,base);r.update(algorithm='balanced_within_round_pricing_economic_bound',certificate_version='balanced-economic-bound-1',wall_seconds=time.perf_counter()-start,
        pricing_budget_policy='remaining_time_divided_by_remaining_blocks; stop_CG_if_any_unproven')
    if progress:progress('balanced_economic_bound_refinement',r['global_lower_bound'],r['global_upper_bound'],{})
    return r
