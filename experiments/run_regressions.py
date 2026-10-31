"""Run all existing mathematical/certificate regressions under either backend."""
import argparse
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'code'))
from solver_backend import BackendConfig,use_backend

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--solver',choices=['cbc','cplex_py'],required=True);a=p.parse_args()
    suites=[]
    for folder in ('dwcg','milp'):
        start=str(ROOT/'code'/folder);sys.path.insert(0,start)
        suites.append(unittest.TestLoader().discover(start,pattern='test_*.py',top_level_dir=start))
    with use_backend(BackendConfig(name=a.solver)):
        result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites))
    raise SystemExit(0 if result.wasSuccessful() else 1)
