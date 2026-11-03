import unittest

from node_state import NodeRestrictions, RestrictionConflict, NumericPolicy, most_fractional
from test_dwcg import tiny


class NodeStateTests(unittest.TestCase):
    def test_restriction_validation_duplicates_conflicts_and_serialization(self):
        d = tiny(); root = NodeRestrictions(); q = ('L', 'a', 1, 'H')
        child = root.add(d, q, 1)
        self.assertTrue(child.is_child_of(root)); self.assertEqual(root.fixes, ())
        self.assertEqual(NodeRestrictions.from_records(d, child.to_records()), child)
        with self.assertRaises(ValueError): child.add(d, q, 1)
        with self.assertRaises(RestrictionConflict): child.add(d, q, 0)
        with self.assertRaises(RestrictionConflict): child.add(d, ('L','a',1,'R'), 1)
        for key in (('unknown','a',1,'H'),('L','a',2,'H'),('L','bad',1,'H'),('L','a',1,'X')):
            with self.subTest(key=key), self.assertRaises(ValueError): root.add(d,key,0)
        with self.assertRaises(ValueError): root.add(d,q,True)

    def test_deterministic_most_fractional_and_independent_siblings(self):
        d=tiny();q=('L','a',1,'H');root=NodeRestrictions()
        a=root.add(d,q,0);b=root.add(d,q,1)
        self.assertEqual(a.fixes[-1][-1],0);self.assertEqual(b.fixes[-1][-1],1)
        xs=[{'variable':['L','a',1,'R'],'value':.4},{'variable':['L','a',1,'H'],'value':.6}]
        self.assertEqual(most_fractional(xs,root,NumericPolicy())['variable'],list(q))
        self.assertIsNone(most_fractional([{'variable':list(q),'value':1-1e-9}],root,NumericPolicy()))

    def test_numerical_policy_roles_and_invalid_numbers(self):
        p=NumericPolicy();self.assertNotEqual(p.lp_primal_tolerance,p.primal_validation_tolerance)
        self.assertEqual(p.allowance(0),p.global_absolute_tolerance)
        for opts in ({'reduced_cost_epsilon':0},{'lp_primal_tolerance':float('nan')},{'branch_integrality_tolerance':.5}):
            with self.assertRaises(ValueError):NumericPolicy(**opts)


if __name__=='__main__':unittest.main()
