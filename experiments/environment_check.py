"""Read-only environment inventory and actual CPLEX/CBC LP/MILP smoke tests."""
import argparse
import ctypes
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
import pulp
from solver_backend import CPLEX_ROOT, BackendConfig, load_cplex, make_solver, use_backend


def environment():
    report = dict(start_utc=datetime.now(timezone.utc).isoformat(), python=sys.version,
                  executable=sys.executable, platform=platform.platform(), cpu=platform.processor(),
                  logical_cpus=os.cpu_count(), packages={}, cplex_root=str(CPLEX_ROOT), tests={})
    for package in ("pulp", "scipy", "numpy", "matplotlib", "pymupdf"):
        try:
            report["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            report["packages"][package] = None
    report["cplex_executables"] = [str(p) for p in CPLEX_ROOT.rglob("cplex.exe")]
    report["cplex_python_versions"] = [p.name for p in (CPLEX_ROOT / "python").iterdir() if p.is_dir()]
    cbc_solver=pulp.PULP_CBC_CMD(msg=False)
    cbc_banner=subprocess.check_output([cbc_solver.path,'-stop'],text=True)
    report['cbc_executable']=cbc_solver.path
    report['cbc_version']=re.search(r'Version:\s*(\S+)',cbc_banner).group(1)
    try:
        cplex = load_cplex()
        native = cplex.Cplex()
        report["cplex_version"] = native.get_version()
        native.set_results_stream(None)
        native.set_log_stream(None)
        native.set_warning_stream(None)
        native.objective.set_sense(native.objective.sense.maximize)
        native.variables.add(obj=[3.0, 2.0, -1.0], lb=[0.0]*3, names=["x", "y", "z"])
        native.linear_constraints.add(lin_expr=[[[0,1],[1.0,1.0]],[[0],[1.0]],[[1],[1.0]]],
                                      senses="LLL", rhs=[4.0,2.0,3.0])
        begin=time.perf_counter(); native.solve()
        report["direct_api_lp"] = dict(status=native.solution.get_status_string(),
            objective=native.solution.get_objective_value(), duals=native.solution.get_dual_values(),
            reduced_costs=native.solution.get_reduced_costs(), wall_time=time.perf_counter()-begin)
        assert abs(report["direct_api_lp"]["objective"]-10)<1e-7
        assert abs(report["direct_api_lp"]["reduced_costs"][2]+1)<1e-7
        native.end()
        large = cplex.Cplex(); large.set_log_stream(None); large.set_results_stream(None)
        large.variables.add(obj=[1.0]*1201, lb=[0.0]*1201, ub=[1.0]*1201)
        large.objective.set_sense(large.objective.sense.maximize); large.solve()
        report["license_test"] = {"solved_1201_variables": True,
                                  "note": "Actual solve exceeds Community Edition's 1000-variable scale; no expiry entitlement inferred."}
        large.end()
    except Exception as error:
        report["cplex_api_error"] = repr(error)
    for backend in ("cplex_py", "cbc"):
        report["tests"][backend] = []
        try:
            with use_backend(BackendConfig(name=backend, time_limit=10)):
                for mip in (False, True):
                    problem = pulp.LpProblem("smoke", pulp.LpMaximize)
                    x = pulp.LpVariable("x", lowBound=0, upBound=1 if mip else None, cat="Binary" if mip else "Continuous")
                    y = pulp.LpVariable("y", lowBound=0, upBound=1 if mip else None, cat="Binary" if mip else "Continuous")
                    z = pulp.LpVariable("z",lowBound=0)
                    problem += 3*x+2*y-z
                    problem += 2*x+2*y <= 3 if mip else x+y <= 4, "capacity"
                    if not mip: problem += x<=2, "xcap"
                    problem.solve(make_solver(mip=mip, role="smoke"))
                    item=dict(problem.backend_result)
                    item.update(mip=mip, duals=None if mip else {k:v.pi for k,v in problem.constraints.items()},
                                reduced_costs=None if mip else {v.name:v.dj for v in problem.variables()})
                    assert item["optimal"]
                    assert abs(item["objective"] - (3 if mip else 10))<1e-6
                    if not mip: assert abs(z.dj+1)<1e-6
                    report["tests"][backend].append(item)
        except Exception as error:
            report["tests"][backend].append({"error":repr(error)})
    exe = CPLEX_ROOT / "bin/x64_win64/cplex.exe"
    try:
        p=pulp.LpProblem("cmd_smoke",pulp.LpMaximize); x=pulp.LpVariable("x",0)
        p+=x; p+=x<=1,"cap"; p.solve(pulp.CPLEX_CMD(path=str(exe),mip=False,msg=False))
        report["cplex_cmd_lp"]={"status":pulp.LpStatus[p.status],"objective":x.value(),"dual":p.constraints["cap"].pi}
    except Exception as error:
        report["cplex_cmd_lp"]={"error":repr(error)}
    try:
        class Memory(ctypes.Structure):
            _fields_ = [("length",ctypes.c_ulong),("load",ctypes.c_ulong)]+[(name,ctypes.c_ulonglong) for name in
                ("total_physical","available_physical","total_pagefile","available_pagefile","total_virtual","available_virtual","extended")]
        memory=Memory();memory.length=ctypes.sizeof(Memory)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            raise OSError("GlobalMemoryStatusEx failed")
        report["hardware"] = {"physical_memory_bytes":memory.total_physical,"logical_cpus":os.cpu_count()}
    except Exception as error:
        report["hardware"] = {"error":repr(error)}
    return report


if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--out",type=Path,required=True);args=parser.parse_args()
    report=environment();args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,allow_nan=False))
