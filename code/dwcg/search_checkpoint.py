"""Explicitly prevent a safe LB summary being used as a full search restart."""
def resume_search(*args,**kwargs):
    raise NotImplementedError('Full DFS checkpoint validation/restart is NOT IMPLEMENTED; safe_initial_frontier is only a conservative bound summary')
