# ML-HRC-DLBP-CF: Baseline Experiment Kit (v1)

> Research stage: **MILP + exact root-node column generation only**. No RL or Branch-and-Price. All input data are **synthetic**, except for `instances/single_line.json`, which is the user's previously supplied synthetic example.

## Contents

- `scripts/make_cases.py`: reproducibly generate model-compatible instances and a manifest.
- `scripts/run_experiments.py`: drive **your existing** `dwcg/solve.py` and `milp/model.py`, recording CG timings, solutions and the compact MILP baseline. Does **not** change these solver files.
- `scripts/scipy_pilot.py`, `support/audit_dlbp.py`: small independent **SciPy/HiGHS compact MILP** pilot, not a substitute for a CBC CG run.
- `instances/pilot/`: 12 experimental cases (two references + 10 factor cases).
- `instances/full/`: 32 cases for subsequent scale testing.
- `results/scipy_compact_pilot.csv`: independently executed small MILP pilot; **not** CG performance results.

## Layout of the user's existing code

Assumed at `--code-root`:

```text
P1Test/code/
├── milp/model.py
└── dwcg/
    ├── common.py
    ├── master.py
    ├── pricing.py
    ├── solve.py           # latest local version, with certificate snapshots
    └── verify.py          # latest local version
```

The original `common.py` imports `../milp/model.py`. Ensure the above layout is preserved.

## How to run on Windows with Python 3.12 / PuLP / CBC

From the extracted experiment kit root (PowerShell):

```powershell
python scripts/make_cases.py --out instances/pilot --suite pilot
python scripts/run_experiments.py `
  --code-root 'D:/Hrychang/Code/PostGraduate/test/P1Test/code' `
  --manifest instances/pilot/manifest.csv `
  --out results/pilot_cbc `
  --timeout 180 --milp-time-limit 60 --max-iterations 200 `
  --verify-tiny
```

For the complete suite **after** the pilot succeeds:

```powershell
python scripts/run_experiments.py `
  --code-root 'D:/Hrychang/Code/PostGraduate/test/P1Test/code' `
  --manifest instances/full/manifest.csv `
  --out results/full_cbc `
  --timeout 300 --milp-time-limit 120 --max-iterations 400
```

Use `--limit 3` for a smoke test, `--groups fatigue resources` for a focused experiment, and `--no-recovery` to isolate root LP CG performance. The driver uses independent child processes so a timeout does not stop the remaining batch. The `--verify-tiny` flag calls the **local project's** latest `verify.py` only for very small instances (<=4 tasks/line and <=2 lines). It is not used on larger problems because full column enumeration is exponential.

## Output

- `summary.csv`: one row per instance with statuses, root CG LP objective/upper bound, compact MILP objective, iteration counts, generated columns and timings.
- `raw/<case>.json`: original `run_cg` output and external timing instrumentation data, for plotting and traceability.
- `logs/<case>.stderr.txt`: subprocess exceptions / stderr.

Instrumentation is placed around `solve.build_master`, `solve.solve_master`, `solve.price`, and `solve.recover_integer` at runtime, without editing the original files. `pricing_s` is the total wall time spent inside the **original exact PP function**, and `pricing_share_of_root=pricing_s/root_lp_wall_s`. `rmp_build_s` and `rmp_solve_s` are separate. All timings include subprocess/solver runtime effects and depend on hardware/OS. The exact root time excludes restricted-column integer recovery; `compact_milp_wall_s` refers to the original compact MILP, not the same LP problem as CG.

## Experimental design

| Factor | Pilot | Full |
|---|---|---|
| Task count (per line) | 6, 8 | 6, 10, 16, 24 |
| Number of lines | 1, 2 | 1, 2, 3 |
| Fatigue upper bound | 0.40, 0.85 | 0.40, 0.65, 0.85 |
| Resource availability | 0.40, 0.80 | 0.40, 0.65, 1.00 |

The resource factor modifies both total human and robot caps; their dependence is specified in `make_cases.py`. All treatments within a factor use the **same underlying random task data at the same seed**. The size and line comparisons use different problem sizes (not guaranteed identical random graphs). This is exploratory synthetic benchmarking, not a statistically established industrial generalization.

The paper-relevant endpoints should include: convergence rate, CG root LP gap to compact IP incumbent (if available), number of iterations, PP calls, PP total time and PP share of CG root time, number of columns, resource usage and fatigue effects. Report infeasible and timed-out cases separately. Across multiple replicates, report median and dispersion (e.g., IQR), never claim every case solves optimally unless supported by statuses.

### Critical interpretation of speed comparisons

**CG solves the full-column root LP relaxation; compact MILP solves the integer model. These are *not the same optimization problem*.** Therefore raw `cg_root_time_s` vs `milp_time_s` cannot by itself support a claim that CG is faster than MILP at solving the same model. A fair root-LP comparison should additionally solve the compact **LP** relaxation. A globally optimal integer algorithm would require Branch-and-Price or another exact global method.

**No real CBC results have been generated within this kit.** `results/scipy_compact_pilot.csv` contains only the SciPy/HiGHS MILP feasibility/objective pilot, on the original `model.py` mathematical builder through a test adapter. Run the above commands on the user's PuLP/CBC environment for valid CG baselines.

The runner also solves the **compact LP relaxation** (same input, original integrality relaxed) and stores `compact_lp_value`, `compact_lp_time_s` and `dw_lp_improvement = compact_lp_value - cg_lp_value`. For maximization, this improvement should be nonnegative when CG converges; the larger it is, the stronger the DW root relaxation. This bound-strength comparison is different from IP optimality.
