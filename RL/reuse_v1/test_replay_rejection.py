"""Mutations of actual online evidence must be rejected by offline audit."""
import json,unittest,zlib
from copy import deepcopy
from pathlib import Path
from audit_online import audit
HERE=Path(__file__).resolve().parent

class Reject(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f=HERE/'evidence/paired/lp_yes_ip_no_reuse'
        cls.data=json.loads((f/'instance.json').read_bytes());cls.result=json.loads(zlib.decompress((f/'result.json.zlib').read_bytes()))

    def test_valid_online_evidence(self):
        self.assertEqual(audit(self.data,self.result,enumerate_pricing=False)['status'],'PASS')

    def test_false_global_proof(self):
        r=deepcopy(self.result);r['global_integer_optimal_proven']=True
        with self.assertRaises(AssertionError):audit(self.data,r,enumerate_pricing=False)

    def test_future_source_and_corrupt_upper(self):
        for mutate in ('future','upper','native'):
            r=deepcopy(self.result);c=next(c for c in r['pricing_audit_calls'] if c.get('bound_certified'))
            if mutate=='future':c['reuse_proof']['sources'][0]['source']=str(c['call_index'])
            elif mutate=='upper':c['reduced_cost_upper_bound']-=100
            else:c['solver']['native_status']=101
            with self.assertRaises(AssertionError):audit(self.data,r,enumerate_pricing=False)

    def test_missing_block_coverage(self):
        r=deepcopy(self.result);h=next(h for h in r['history'] if h['complete_certified_pricing']);h['pricing'].pop()
        with self.assertRaises(AssertionError):audit(self.data,r,enumerate_pricing=False)
if __name__=='__main__':unittest.main(verbosity=2)
