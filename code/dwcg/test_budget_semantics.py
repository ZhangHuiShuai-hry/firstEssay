import sys,tempfile,unittest,json,hashlib
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments'))
from task03_1b_budget import arm

class BudgetSemantics(unittest.TestCase):
    def test_hard_stop_is_not_solver_error_or_proof(self):
        with tempfile.TemporaryDirectory() as d:
            r=arm(ROOT/'code/milp/examples/two_lines.json',Path(d)/'run','V2',.02)
            self.assertTrue(r['hard_stop']);self.assertFalse(r['final_admitted']);self.assertFalse(r['search_resume_supported'])
    def test_worker_exception_is_solver_error(self):
        with tempfile.TemporaryDirectory() as d:
            r=arm(ROOT/'code/milp/examples/two_lines.json',Path(d)/'run','bad_version',20)
            self.assertEqual(r['status'],'solver_error');self.assertEqual(r['operational_status'],'solver_error');self.assertFalse(r['final_admitted'])
    def test_missing_evidence_cannot_admit_proof(self):
        with tempfile.TemporaryDirectory() as d,patch('task03_1b_budget.subprocess.Popen') as popen:
            popen.return_value.wait.return_value=0;popen.return_value.returncode=0
            r=arm(ROOT/'code/milp/examples/two_lines.json',Path(d)/'run','V2',20)
            self.assertEqual(r['operational_status'],'missing_evidence');self.assertFalse(r['final_admitted'])
    def test_accounting_is_not_an_admission_marker(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'run';r=arm(ROOT/'code/milp/examples/two_lines.json',target,'bad_version',20)
            accounting=json.loads((target/'accounting.json').read_text());receipt=json.loads((target/'admission.json').read_text())
            self.assertFalse(accounting['final_admitted']);self.assertFalse(receipt['proof_admitted'])
            self.assertEqual(receipt['accounting_sha256'],hashlib.sha256((target/'accounting.json').read_bytes()).hexdigest())
