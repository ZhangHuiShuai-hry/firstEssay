"""Solver selection and conservative status normalization; no model equations.

Default remains single-thread CBC. CPLEX is loaded from its installed matching
Python API in this process only, without PATH/registry/global installation changes.
"""
from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
import importlib
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time

import pulp

CPLEX_ROOT = Path("D:/CodeProgram/IBM/cplexOp/cplex")
_dll_handles = []


def load_cplex(root=CPLEX_ROOT):
    try:
        return importlib.import_module("cplex")
    except ImportError:
        api = Path(root) / "python" / f"{sys.version_info.major}.{sys.version_info.minor}" / "x64_win64"
        if not (api / "cplex/__init__.py").is_file():
            raise RuntimeError(f"No matching CPLEX API for Python {sys.version_info[:2]} at {api}")
        if hasattr(os, "add_dll_directory"):
            _dll_handles.append(os.add_dll_directory(str(Path(root) / "bin/x64_win64")))
        sys.path.insert(0, str(api))
        return importlib.import_module("cplex")


@dataclass
class BackendConfig:
    name: str = "cbc"
    overrides: dict = field(default_factory=dict)
    threads: int = 1
    seed: int = 11
    primal_tolerance: float = 1e-8
    dual_tolerance: float = 1e-8
    mip_integrality_tolerance: float = 1e-7
    time_limit: float | None = None
    role_limits: dict = field(default_factory=dict)
    log_dir: str | None = None
    deadline: float | None = None


_config = ContextVar("solver_config", default=None)
_events = ContextVar("solver_events", default=None)


@contextmanager
def use_backend(config=None, events=None):
    config = config or BackendConfig()
    a = _config.set(config)
    b = _events.set(events if events is not None else [])
    try:
        yield config
    finally:
        _events.reset(b)
        _config.reset(a)


def objective_value(problem):
    expression = problem.objective
    if expression is None:
        return None
    total = float(expression.constant)
    for variable, coefficient in expression.items():
        if coefficient:
            value = variable.value()
            if value is None or not math.isfinite(value):
                return None
            total += coefficient * value
    return total if math.isfinite(total) else None


def _store(problem, info, start, log_path):
    info.update(wall_time=time.perf_counter() - start, log_path=log_path)
    if info["optimal"]:
        problem.assignStatus(pulp.LpStatusOptimal, pulp.LpSolutionOptimal)
    elif info["status"] == "infeasible":
        problem.assignStatus(pulp.LpStatusInfeasible, pulp.LpSolutionNoSolutionFound)
    else:
        problem.assignStatus(pulp.LpStatusNotSolved,
                             pulp.LpSolutionIntegerFeasible if info["has_incumbent"] else pulp.LpSolutionNoSolutionFound)
    problem.backend_result = info
    events = _events.get()
    if events is not None:
        events.append(dict(info))
    return problem.status


def make_solver(mip=True, msg=False, role="generic", time_limit=None, gap=0):
    config = _config.get() or BackendConfig()
    name = config.overrides.get(role, config.name)
    limit = time_limit if time_limit is not None else config.role_limits.get(role, config.time_limit)
    if config.deadline is not None:
        remaining = config.deadline - time.perf_counter()
        if remaining <= 0:
            raise TimeoutError("CG root wall-clock budget exhausted")
        limit = min(limit, remaining) if limit is not None else remaining
    # LP and exact PP must never use a positive optimality gap.
    if role in ("rmp", "pricing", "verification"):
        gap = 0
    log_dir = Path(config.log_dir) if config.log_dir else None
    events = _events.get()
    call = len(events) if events is not None else 0
    temporary = log_dir is None
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = str(log_dir / f"{call:06d}_{role}_{name}.log")
    else:
        fd, log_path = tempfile.mkstemp(suffix=".log", prefix="dlbp_")
        os.close(fd)

    if name == "cplex_py":
        cplex = load_cplex()
        api = importlib.import_module("pulp.apis.cplex_api")
        if hasattr(api.CPLEX_PY, "err"):
            api = importlib.reload(api)

        class CplexSolver(api.CPLEX_PY):
            def buildSolverModel(self, problem):
                begin = time.perf_counter()
                super().buildSolverModel(problem)
                self.translation_wall = time.perf_counter() - begin

            def callSolver(self, *args, **kwargs):
                begin = time.perf_counter()
                try:
                    return super().callSolver(*args, **kwargs)
                finally:
                    self.native_wall = time.perf_counter() - begin

            def setlogfile(self, fileobj):
                self._log_handle = fileobj
                super().setlogfile(fileobj)

            def actualSolve(self, problem, **kwargs):
                begin = time.perf_counter()
                super().actualSolve(problem, **kwargs)
                native = self.solverModel
                solution = native.solution
                code = solution.get_status()
                text = solution.get_status_string()
                incumbent = bool(solution.is_primal_feasible()) and problem.valid(1e-6)
                optimal = code in (1, 101) and incumbent
                # 102 means optimal within a tolerance; never mislabel it exact optimal.
                status = ("optimal" if optimal else "infeasible" if code in (3, 103)
                          else "time_limit" if code in (11, 107, 108)
                          else "feasible_unproven" if incumbent else "not_solved")
                value = objective_value(problem) if incumbent else None
                bound = value if optimal else None
                relative = None
                if mip:
                    try:
                        bound = float(solution.MIP.get_best_objective())
                        if abs(bound) >= 1e19:
                            bound = None
                        if incumbent:
                            relative = float(solution.MIP.get_mip_relative_gap())
                    except cplex.exceptions.CplexSolverError:
                        pass
                info = dict(backend=name, role=role, status=status, native_status=code,
                            native_status_text=text, optimal=optimal, has_incumbent=incumbent,
                            objective=value, best_bound=bound, relative_gap=relative,
                            solver_time=self.native_wall, translation_time=self.translation_wall,
                            effective_time_limit=limit, relative_gap_requested=gap,
                            options=asdict(config))
                result = _store(problem, info, begin, None if temporary else log_path)
                native.end()
                if getattr(self, "_log_handle", None) is not None:
                    self._log_handle.close()
                if temporary:
                    Path(log_path).unlink(missing_ok=True)
                return result

        solver = CplexSolver(mip=mip, msg=msg, timeLimit=limit, gapRel=gap,
                             threads=config.threads, logPath=log_path,
                             **{"mip.tolerances.absmipgap": 0.0,
                                "mip.tolerances.integrality": config.mip_integrality_tolerance,
                                "simplex.tolerances.feasibility": config.primal_tolerance,
                                "simplex.tolerances.optimality": config.dual_tolerance,
                                "randomseed": config.seed, "parallel": 1})
        return solver
    if name != "cbc":
        raise ValueError(f"Unsupported backend {name}; choose cbc or cplex_py")

    class CbcSolver(pulp.PULP_CBC_CMD):
        def actualSolve(self, problem, **kwargs):
            begin = time.perf_counter()
            super().actualSolve(problem, **kwargs)
            text = Path(log_path).read_text(encoding="utf-8", errors="replace")
            incumbent = (problem.sol_status in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible)
                         and problem.valid(1e-6))
            timed_out = "Stopped on time limit" in text or "Exiting on maximum time" in text
            optimal = (problem.status == pulp.LpStatusOptimal and problem.sol_status == pulp.LpSolutionOptimal
                       and incumbent and not timed_out and "within gap tolerance" not in text)
            status = ("optimal" if optimal else "time_limit" if timed_out
                      else "infeasible" if problem.status == pulp.LpStatusInfeasible
                      else "feasible_unproven" if incumbent else "not_solved")
            value = objective_value(problem) if incumbent else None
            match = re.search(r"Upper bound:\s*([-+0-9.eE]+)", text)
            bound = value if optimal else float(match.group(1)) if match else None
            match_time = re.search(r"Total time \(CPU seconds\):\s*([0-9.]+)", text)
            info = dict(backend=name, role=role, status=status, native_status=problem.status,
                        native_status_text=pulp.LpStatus[problem.status], optimal=optimal,
                        has_incumbent=incumbent, objective=value, best_bound=bound,
                        relative_gap=(abs(bound-value)/(abs(value)+1e-10)
                                      if bound is not None and value is not None else None),
                        solver_time=float(match_time.group(1)) if match_time else None,
                        translation_time=None, effective_time_limit=limit, relative_gap_requested=gap,
                        options=asdict(config))
            result = _store(problem, info, begin, None if temporary else log_path)
            if temporary:
                Path(log_path).unlink(missing_ok=True)
            return result

    return CbcSolver(mip=mip, msg=msg, timeLimit=limit, gapRel=gap, gapAbs=0,
                     threads=config.threads, logPath=log_path,
                     options=[f"primalTolerance {config.primal_tolerance}",
                              f"dualTolerance {config.dual_tolerance}",
                              f"integerTolerance {config.mip_integrality_tolerance}",
                              f"randomSeed {config.seed}", f"randomCbcSeed {config.seed}"])
