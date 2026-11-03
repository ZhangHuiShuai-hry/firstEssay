import copy,unittest
from common import make_column,empty_pool
from diagnose_pool import diagnose,render
from test_node_cg import small


class PoolDiagnosisTests(unittest.TestCase):
    def test_missing_required_task(self):
        d=small();d['lines'][0]['required_tasks']=['a']
        r=diagnose(d,empty_pool(d))
        self.assertEqual(r['original_ip']['status'],'infeasible')
        self.assertTrue(r['minimum_violation_proven']);self.assertEqual(r['total_violation'],1)
        self.assertTrue(any(e['required'] and not e['occurrences'] for e in r['coverage']))
        self.assertEqual(r['required_task_execution'][0]['count'],0)

    def test_full_coverage_but_duplicate_task(self):
        d=small();l=d['lines'][0];l['required_tasks']=['a']
        pool={('L',s):[make_column(l,s,[('a','H')])] for s in (1,2)}
        before=copy.deepcopy(pool);r=diagnose(d,pool)
        self.assertEqual(r['total_violation'],1)
        self.assertEqual(r['violations'][0]['row'],['task','L','a'])
        self.assertEqual(r['required_task_execution'][0]['count'],2)
        self.assertEqual(pool,before)

    def test_precedence_and_resource_explanations(self):
        d=small();l=d['lines'][0];l['required_tasks']=['b'];l['precedence']=[['a','b']]
        pool=empty_pool(d);pool['L',2]=[make_column(l,2,[('b','R')])]
        r=diagnose(d,pool,hard_families=['task','human','robot','recovery'])
        self.assertEqual(r['violations'][0]['row'],['precedence','L',0,2]);self.assertEqual(r['total_violation'],1)
        l['precedence']=[];d['robot_limit']=0
        r=diagnose(d,pool,hard_families=['task','precedence','human','recovery'])
        self.assertEqual(r['violations'][0]['row'],['robot']);self.assertEqual(r['total_violation'],1)

    def test_feasible_pool_zero_violation_and_recovery_deficit(self):
        d=small();pool=empty_pool(d)
        r=diagnose(d,pool);self.assertEqual(r['total_violation'],0)
        self.assertTrue(r['original_constraints_satisfied']);self.assertIn('无（每个必做任务',render(r))
        d['lines'][0]['min_recovery']=1
        r=diagnose(d,pool,hard_families=['task','precedence','human','robot'])
        self.assertEqual(r['total_violation'],1);self.assertEqual(r['violations'][0]['row'],['recovery','L'])

    def test_hard_conflict_is_not_reported_as_a_solution(self):
        d=small();l=d['lines'][0];l['required_tasks']=['a']
        r=diagnose(d,empty_pool(d),hard_families=['task'])
        self.assertEqual(r['elastic_solver']['status'],'infeasible');self.assertEqual(r['assignments'],[])
        self.assertFalse(r['minimum_violation_proven'])

if __name__=='__main__':unittest.main()
