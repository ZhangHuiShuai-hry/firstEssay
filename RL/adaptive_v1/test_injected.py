"""Test-process-only fault injection; no production constraints are patched."""
import json,unittest,zlib
from pathlib import Path
from unittest.mock import patch
from online import solve,LinePricing,ROOT
from audit import audit
HERE=Path(__file__).resolve().parent
class InterruptedCandidate(unittest.TestCase):
    def test_legal_unproven_columns_continue_to_certified_solution(self):
        data=json.loads((ROOT/'sub/stage7/evidence/validation/tiny5_original_cplex_py/instance.json').read_bytes())
        original=LinePricing.solve
        def interrupted(self,line,**kw):
            col,c=original(self,line,**kw)
            if kw.get('purpose')=='candidate' and col is not None:
                # Simulate a valid incumbent with no completed maximum-RC proof.
                c.update(optimal=False,status='time_limit');c['solver'].update(optimal=False,native_status=107,status='time_limit')
            return col,c
        with patch.object(LinePricing,'solve',interrupted):r=solve(data,seconds=20,policy_name='fixed')
        self.assertTrue(any(h.get('candidate_added') for h in r['history']))
        cs=[c for h in r['history'] for c in h.get('candidate_pricing',[])];self.assertTrue(cs);self.assertTrue(all(not c['optimal'] for c in cs))
        self.assertTrue(r['global_integer_optimal_proven']);self.assertAlmostEqual(r['lower_bound'],24.)
        replay=audit(data,r,enumerate_pricing=True);self.assertEqual(replay['status'],'PASS')
        folder=HERE/'evidence/injection';folder.mkdir(parents=True,exist_ok=False)
        (folder/'instance.json').write_text(json.dumps(data));(folder/'result.json.zlib').write_bytes(zlib.compress(json.dumps(r,allow_nan=False).encode()))
        (folder/'replay.json').write_text(json.dumps(replay,indent=2))
if __name__=='__main__':unittest.main(verbosity=2)
