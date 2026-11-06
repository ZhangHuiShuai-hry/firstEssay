import json,unittest,zlib
from copy import deepcopy
from pathlib import Path
from audit import audit
from check_candidates import check
HERE=Path(__file__).resolve().parent
class Safety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        f=HERE/'evidence/small/tiny5_original_fixed';cls.data=json.loads((f/'instance.json').read_bytes());cls.r=json.loads(zlib.decompress((f/'result.json.zlib').read_bytes()))
    def test_all_small_full_oracles(self):
        rows=json.loads((HERE/'evidence/small/summary.json').read_bytes());self.assertEqual(len(rows),16)
        for row in rows:
            f=HERE/'evidence/small'/f"{row['case']}_{row['policy_name']}";v=json.loads((f/'replay.json').read_bytes())
            self.assertEqual(v['status'],'PASS');self.assertEqual(v['scope'],'complete_independent_enumeration')
    def test_unproven_candidate_is_allowed_as_candidate(self):
        r=deepcopy(self.r)
        for h in r['history']:
            for c in h.get('candidate_pricing',[]):
                c['optimal']=False;c['status']='time_limit';c['solver']['optimal']=False;c['solver']['native_status']=107
                r['pricing_audit_calls'][c['call_index']]=c
        check(self.data,r)  # Does not authorize any bound from these columns.
    def test_reject_future_reference_and_wrong_raw_rc(self):
        for field in ('future','rc','price'):
            r=deepcopy(self.r);h=next(h for h in r['history'] if h.get('candidate_added'))
            if field=='future':h['candidate_action']['reference_history_index']=999
            elif field=='rc':h['candidate_added'][0]['raw_reduced_cost']+=1
            else:h['candidate_action']['price'][0]+=1
            with self.assertRaises(AssertionError):audit(self.data,r,enumerate_pricing=False)
    def test_reject_candidate_as_exact_round(self):
        r=deepcopy(self.r);h=next(h for h in r['history'] if h.get('candidate_only'));h['complete_certified_pricing']=True;h['repaired_upper_bound']=0
        with self.assertRaises(AssertionError):audit(self.data,r,enumerate_pricing=False)
    def test_reject_missing_fallback_and_missing_block(self):
        r=deepcopy(self.r);h=next(h for h in r['history'] if h.get('candidate_action') and not h.get('candidate_added'));h['pricing']=[]
        with self.assertRaises(AssertionError):audit(self.data,r,enumerate_pricing=False)
        r=deepcopy(self.r);h=next(h for h in r['history'] if h['complete_certified_pricing']);h['pricing'].pop()
        with self.assertRaises(AssertionError):audit(self.data,r,enumerate_pricing=False)
if __name__=='__main__':unittest.main(verbosity=2)
