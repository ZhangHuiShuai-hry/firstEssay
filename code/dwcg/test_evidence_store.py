import json,sqlite3,tempfile,unittest,subprocess,sys
from pathlib import Path
from evidence_store import EvidenceStore,canonical

class StoreTests(unittest.TestCase):
    def test_roundtrip_dedup_isolation(self):
        with tempfile.TemporaryDirectory() as d:
            s=EvidenceStore(Path(d)/'x.sqlite');v={'columns':[['a','H']]*50,'n':-8.,'null':None}
            s.put(v);count=s.db.execute('SELECT count(*) FROM objects').fetchone()[0];s.put(v)
            self.assertEqual(count,s.db.execute('SELECT count(*) FROM objects').fetchone()[0])
            out=s.get();self.assertEqual(canonical(v),canonical(out));out['columns'][0][0]='bad'
            self.assertEqual(s.get()['columns'][1][0],'a');s.close()
    def test_corruption_and_missing_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            s=EvidenceStore(Path(d)/'x.sqlite');h=s.put({'a':[1]})
            with s.db:s.db.execute('UPDATE objects SET payload=? WHERE hash=?',(b'bad',h))
            with self.assertRaises(Exception):s.get()
            with s.db:s.db.execute('DELETE FROM objects WHERE hash=?',(h,))
            with self.assertRaises(ValueError):s.get()
            s.close()
    def test_rollback_does_not_publish(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.sqlite';s=EvidenceStore(p);s.put({'old':True})
            with self.assertRaises(ValueError):s.put({'bad':float('nan')})
            s.close();s=EvidenceStore(p);self.assertEqual(s.get(),{'old':True});s.close()
    def test_process_crash_retains_last_committed_root(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.sqlite';s=EvidenceStore(p);s.put({'old':True});s.close()
            code="import sqlite3,os,sys;c=sqlite3.connect(sys.argv[1]);c.execute(\"INSERT INTO roots(kind,hash,version) VALUES ('result','bad',3)\");os._exit(23)"
            r=subprocess.run([sys.executable,'-c',code,str(p)]);self.assertEqual(r.returncode,23)
            s=EvidenceStore(p);self.assertEqual(s.get(),{'old':True});s.close()
