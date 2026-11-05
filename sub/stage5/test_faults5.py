"""性能运行结束后增加的安全故障回归，不改变已测算法源码。"""
import sys,unittest
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'stage1')]
from native_node_pp import LinePricing,NodeRestrictions
from branch_price5 import run
from line_cg import BackendConfig
from gap_case import instance
from verify5 import audit

class Faults(unittest.TestCase):
    def test_illegal_inherited_start_rejected_before_native_solve(self):
        d=instance();bad=dict(line='A',profit=9,human=1,robot=1,
                             stations=[dict(line='A',station=1,assignments=[['t','J']])])
        fix=NodeRestrictions().add(d,('A','t',1,'J'),0)
        events=[];session=LinePricing(BackendConfig(name='cplex_py'),events,restrictions=fix,seed_pool={'A':[bad]})
        try:
            with self.assertRaises(ValueError):session.solve(d['lines'][0],time_limit=1)
            self.assertFalse(events)
        finally:session.close()
        self.assertFalse(session.sessions)
    def test_child_timeout_preserves_incumbent_and_parent_bound(self):
        actual=LinePricing.solve
        def interrupt(session,line,**kwargs):
            if session.restrictions.fixes:raise TimeoutError('injected child deadline')
            return actual(session,line,**kwargs)
        with patch.object(LinePricing,'solve',new=interrupt):r=run(instance(),time_limit=5,pricing='warm')
        audit(instance(),r)
        self.assertEqual(r['status'],'time_limit');self.assertFalse(r['global_integer_optimal_proven'])
        self.assertTrue(r['open_nodes']);self.assertAlmostEqual(r['global_upper_bound'],6.5)
        self.assertAlmostEqual(r['global_lower_bound'],2)

if __name__=='__main__':unittest.main(verbosity=2)
