"""Per-node native PP; no native object is shared across nodes."""
import time
from dataclasses import asdict
from persistent_pricing import PersistentPricing
from node_state import PricingCertificate,NodePricingResult
from node_pricing import fixed_records,validate_column
from common import reduced_cost


class NodePersistentPricing(PersistentPricing):
    def __init__(self,line,station,restrictions,policy,config,log_path=None):
        super().__init__(line,station,config,log_path)
        self.restrictions=restrictions;self.policy=policy
        for key,b in restrictions.block_fixes(line['id'],station).items():
            j=self.z[key]
            self.native.variables.set_lower_bounds(j,float(b))
            self.native.variables.set_upper_bounds(j,float(b))

    def run(self,duals,phase,deadline,feasibility=False):
        tick=time.perf_counter()
        cert=PricingCertificate(self.line['id'],self.station,phase,'local_feasibility' if feasibility else 'pricing')
        cert.fixed_variables=fixed_records(self.restrictions,self.line['id'],self.station)
        if feasibility:
            from master import build_master
            from common import empty_pool
            data={'lines':[self.line],'human_limit':0,'robot_limit':0}
            duals={k:0. for k in build_master(data,empty_pool(data)).rows}
        try:
            col,rc=super().solve(duals,1 if feasibility else phase,deadline)
            validate_column(self.line,self.station,col,self.restrictions,self.policy)
            if not feasibility and abs(rc-reduced_cost(self.line,self.station,col,duals,phase))>self.policy.bound_consistency_tolerance:
                raise RuntimeError('Native PP RC mismatch')
            rec=self.records[-1]
            info=dict(rec,backend='node_persistent_cplex',status='optimal',optimal=True,has_incumbent=True)
            cert.status='optimal';cert.optimal=True;cert.has_incumbent=True
            cert.objective=rc;cert.incumbent=rc;cert.best_bound=rec['best_bound'];cert.reduced_cost=None if feasibility else rc
            cert.assignments=list(col.assignments);cert.solver_result=info
            return NodePricingResult(cert,col)
        except Exception as error:
            rec=self.records[-1] if self.records else {}
            code=rec.get('native_status')
            cert.status='infeasible' if code==103 else 'time_limit' if isinstance(error,TimeoutError) else 'solver_error'
            cert.error=repr(error);cert.best_bound=rec.get('best_bound')
            cert.solver_result=dict(rec,status=cert.status,optimal=False,backend='node_persistent_cplex')
            return NodePricingResult(cert)
        finally:cert.solve_seconds=time.perf_counter()-tick
