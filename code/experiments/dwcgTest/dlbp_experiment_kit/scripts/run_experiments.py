"""Run user's unmodified PuLP/CBC root-node CG and compact MILP on benchmark JSONs.

Use within user's local project, e.g.:
 python scripts/run_experiments.py --code-root D:/.../P1Test/code \
     --manifest instances/pilot/manifest.csv --out results/pilot --timeout 180

Needs code-root/dwcg/{solve,common,master,pricing}.py and
      code-root/milp/model.py. Will not edit them.
Each case runs in a separate process to enforce timeout and isolate solver state.
"""
from __future__ import annotations
import argparse, csv, json, math, os, subprocess, sys, time, traceback
from pathlib import Path


def _finite_or_none(x):
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) else None


def _child(code_root: Path, case_path: Path, milp_limit: float,
           max_iterations: int, verify_tiny: bool, no_recovery: bool):
    sys.path.insert(0, str(code_root / 'dwcg'))
    import solve as s
    from common import compact, cbc, require_optimal
    import pulp
    data = json.loads(case_path.read_text(encoding='utf-8-sig'))
    compact.validate_data(data)
    timing = {'rmp_build_s': 0., 'rmp_solve_s': 0., 'pricing_s': 0., 'recovery_s': 0.,
              'rmp_build_calls': 0, 'rmp_solve_calls': 0, 'pricing_calls': 0}
    # Instrument imported references, without changing model equations or source files.
    orig_build, orig_master, orig_price, orig_recover = s.build_master, s.solve_master, s.price, s.recover_integer
    def timed_build(*a, **kw):
        start = time.perf_counter()
        try: return orig_build(*a, **kw)
        finally:
            timing['rmp_build_s'] += time.perf_counter()-start
            timing['rmp_build_calls'] += 1
    def timed_master(*a, **kw):
        start = time.perf_counter()
        try: return orig_master(*a, **kw)
        finally:
            timing['rmp_solve_s'] += time.perf_counter()-start
            timing['rmp_solve_calls'] += 1
    def timed_price(*a, **kw):
        start = time.perf_counter()
        try: return orig_price(*a, **kw)
        finally:
            timing['pricing_s'] += time.perf_counter()-start
            timing['pricing_calls'] += 1
    def timed_recover(*a, **kw):
        start = time.perf_counter()
        try: return orig_recover(*a, **kw)
        finally: timing['recovery_s'] += time.perf_counter()-start
    s.build_master, s.solve_master, s.price, s.recover_integer = timed_build, timed_master, timed_price, timed_recover
    begin = time.perf_counter()
    cg, pool = s.run_cg(data, max_iterations=max_iterations, recover=not no_recovery)
    cg_time = time.perf_counter()-begin
    result = {'cg': cg, 'timing': timing, 'cg_wall_s':cg_time,
              'root_lp_wall_s':cg_time-timing['recovery_s'],
              'generated_columns':sum(len(columns) for columns in pool.values())}
    if verify_tiny:
        from verify import cross_validate
        result['verification'] = cross_validate(data, cg)
    begin = time.perf_counter()
    model = compact.build_model(data)
    milp = compact.solve(model, time_limit=milp_limit, gap=0)
    result['compact_milp'] = milp
    result['compact_milp_wall_s'] = time.perf_counter()-begin
    # Solve original compact *LP* separately: this is the appropriate relaxation
    # for studying the DW root bound, unlike comparing LP-CG directly to compact IP.
    start_lp=time.perf_counter()
    relaxed=compact.build_model(data)
    for variable in relaxed.problem.variables():
        variable.cat=pulp.LpContinuous
    relaxed.problem.solve(cbc(mip=False))
    result['compact_lp_wall_s']=time.perf_counter()-start_lp
    result['compact_lp_status']=pulp.LpStatus[relaxed.problem.status]
    if relaxed.problem.status == pulp.LpStatusOptimal:
        require_optimal(relaxed.problem)
        expr=relaxed.problem.objective
        lp_value=float(expr.constant)
        for variable, coefficient in expr.items():
            if coefficient != 0:
                if variable.value() is None:
                    raise RuntimeError('Missing nonzero compact LP objective variable')
                lp_value += coefficient*variable.value()
        result['compact_lp_objective']=float(lp_value)
        if cg.get('lp_converged') and cg['lp_objective'] > lp_value+1e-5:
            raise RuntimeError('DW root LP exceeds compact LP upper bound')
    elif relaxed.problem.status == pulp.LpStatusInfeasible:
        result['compact_lp_objective']=None
    else:
        raise RuntimeError(f'Compact LP failed: {result["compact_lp_status"]}')
    if cg.get('lp_converged') and milp.get('has_feasible_solution'):
        lp = _finite_or_none(cg.get('lp_objective'))
        ip = _finite_or_none(milp.get('objective'))
        if lp is not None and ip is not None and lp+1e-5 < ip:
            raise RuntimeError(f'Invalid LP/IP bound: CG LP={lp} < MILP incumbent={ip}')
    return result


def _safe_id(name: str) -> str:
    return ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in name)


def run_parent(args):
    root = args.code_root.resolve()
    for f in ('dwcg/solve.py', 'dwcg/common.py', 'dwcg/master.py',
              'dwcg/pricing.py', 'milp/model.py'):
        if not (root/f).is_file():
            raise FileNotFoundError(f'Missing source file {root/f}')
    manifest = args.manifest.resolve()
    rows = list(csv.DictReader(manifest.open(encoding='utf-8-sig', newline='')))
    if args.groups: rows = [row for row in rows if row['group'] in args.groups]
    if args.limit: rows = rows[:args.limit]
    out = args.out.resolve(); (out/'raw').mkdir(parents=True, exist_ok=True)
    (out/'logs').mkdir(parents=True, exist_ok=True)
    results=[]
    for index, row in enumerate(rows, 1):
        name = _safe_id(row['case_id'])
        case = Path(row['instance'])
        if not case.is_file():
            case = manifest.parent / case  # portable relative filename
        if not case.is_file():
            case = manifest.parent / (name+'.json')
        if not case.is_file():
            raise FileNotFoundError(f'Cannot locate instance for {name}')
        do_verify = args.verify_tiny and int(row['tasks_per_line']) <= 4 and int(row['lines']) <= 2
        cmd = [sys.executable, str(Path(__file__).resolve()), '--worker',
               '--code-root', str(root), '--case', str(case),
               '--milp-time-limit', str(args.milp_time_limit),
               '--max-iterations', str(args.max_iterations)]
        if args.no_recovery: cmd.append('--no-recovery')
        if do_verify: cmd.append('--verify-tiny')
        started=time.perf_counter()
        summary = dict(row); summary.update(verification_run=do_verify)
        print(f'[{index}/{len(rows)}] {name}: ', end='', flush=True)
        try:
            p = subprocess.run(cmd,capture_output=True,text=True,timeout=args.timeout,
                               env={**os.environ, 'PYTHONUNBUFFERED':'1'})
            wall=time.perf_counter()-started
            (out/'logs'/f'{name}.stderr.txt').write_text(p.stderr, encoding='utf-8')
            if p.returncode != 0:
                summary.update(run_status='error', error=p.stderr[-1200:], wall_s=wall)
            else:
                raw=json.loads(p.stdout)
                (out/'raw'/f'{name}.json').write_text(json.dumps(raw,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                cg=raw['cg']; t=raw['timing']; mip=raw['compact_milp']
                phase1=sum(1 for x in cg.get('history',[]) if x.get('phase')==1)
                phase2=sum(1 for x in cg.get('history',[]) if x.get('phase')==2)
                summary.update(run_status='completed',wall_s=wall,cg_status=cg.get('status'),
                    cg_lp_converged=cg.get('lp_converged'),cg_lp_value=cg.get('lp_objective'),
                    cg_upper_bound=cg.get('lp_upper_bound'),cg_root_time_s=raw['root_lp_wall_s'],
                    cg_total_time_s=raw['cg_wall_s'],rmp_build_s=t['rmp_build_s'],
                    rmp_solve_s=t['rmp_solve_s'],pricing_s=t['pricing_s'],
                    pricing_share_of_root=t['pricing_s']/max(1e-9,raw['root_lp_wall_s']),
                    pricing_calls=t['pricing_calls'],rmp_solve_calls=t['rmp_solve_calls'],
                    phase1_records=phase1,phase2_records=phase2,
                    generated_columns=raw['generated_columns'],
                    milp_status=mip.get('status'),milp_optimal=mip.get('optimal'),
                    milp_incumbent=mip.get('objective'),milp_time_s=raw['compact_milp_wall_s'],
                    compact_lp_status=raw.get('compact_lp_status'),
                    compact_lp_value=raw.get('compact_lp_objective'),
                    compact_lp_time_s=raw.get('compact_lp_wall_s'),
                    dw_lp_improvement=(raw.get('compact_lp_objective')-cg.get('lp_objective') if
                                      raw.get('compact_lp_objective') is not None and
                                      cg.get('lp_objective') is not None else None),
                    restricted_integer=(cg.get('integer_recovery') or {}).get('objective'),
                    validation_passed=(raw.get('verification') or {}).get('passed'))
            print(summary['run_status'], summary.get('cg_status',''), flush=True)
        except subprocess.TimeoutExpired:
            summary.update(run_status='timeout',wall_s=time.perf_counter()-started)
            print('timeout',flush=True)
        except (ValueError,KeyError) as exc:
            summary.update(run_status='error',error=str(exc),wall_s=time.perf_counter()-started)
            print('error',flush=True)
        results.append(summary)
        _write_results(out/'summary.csv',results)
    counts={k:sum(r['run_status']==k for r in results) for k in ('completed','timeout','error')}
    print('Final:',counts, 'CSV:',out/'summary.csv')


def _write_results(path, rows):
    headers=list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=headers);w.writeheader();w.writerows(rows)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    ap.add_argument('--case',type=Path,help=argparse.SUPPRESS)
    ap.add_argument('--code-root',type=Path,required=True)
    ap.add_argument('--manifest',type=Path)
    ap.add_argument('--out',type=Path)
    ap.add_argument('--timeout',type=int,default=180,help='Wall-clock limit per instance in seconds')
    ap.add_argument('--milp-time-limit',type=float,default=60)
    ap.add_argument('--max-iterations',type=int,default=200)
    ap.add_argument('--verify-tiny',action='store_true',help='Run enumerate-pool verify for n<=4 cases')
    ap.add_argument('--no-recovery',action='store_true')
    ap.add_argument('--groups',nargs='*',default=None)
    ap.add_argument('--limit',type=int)
    args=ap.parse_args()
    if args.worker:
        try:
            data=_child(args.code_root.resolve(),args.case.resolve(),
                        args.milp_time_limit,args.max_iterations,args.verify_tiny,args.no_recovery)
            print(json.dumps(data,ensure_ascii=False,allow_nan=False))
        except BaseException:
            traceback.print_exc(file=sys.stderr)
            raise SystemExit(2)
    else:
        if not args.manifest or not args.out:
            ap.error('--manifest and --out are required')
        run_parent(args)


if __name__=='__main__': main()
