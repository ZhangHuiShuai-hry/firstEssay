import json,unittest,zlib
from copy import deepcopy
from pathlib import Path
from verify_bundle import native_contract
class Contract(unittest.TestCase):
    def test_reject_false_exact_native_status_and_bound(self):
        path=Path(__file__).resolve().parent/'evidence/small/tiny5_original_fixed/result.json.zlib';r=json.loads(zlib.decompress(path.read_bytes()))
        native_contract(r)
        for key,value in [('native_status',107),('best_bound',1e8),('optimal',False)]:
            bad=deepcopy(r);c=next(c for c in bad['pricing_audit_calls'] if c['optimal']);c['solver'][key]=value
            with self.assertRaises(AssertionError):native_contract(bad)
if __name__=='__main__':unittest.main(verbosity=2)
