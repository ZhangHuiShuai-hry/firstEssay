"""Reproducible synthetic benchmarks for ML-HRC-DLBP-CF.

Usage: python scripts/make_cases.py --out ./cases --suite pilot
Or:    python scripts/make_cases.py --out ./cases --suite full
Only stdlib dependencies. Instances respect existing model.py JSON schema.
"""
from __future__ import annotations
import argparse, csv, json, math, random
from pathlib import Path


def base_instance(n: int, lines: int, seed: int) -> dict:
    rng = random.Random(seed)
    out_lines = []
    for l in range(1, lines + 1):
        tasks = []
        for i in range(1, n + 1):
            htime = rng.randint(2, 4)
            rtime = max(1, htime + rng.choice([-1, 0, 1]))
            jtime = max(1, htime - rng.choice([1, 2]))
            modes = {"H": {"time": htime, "cost": rng.randint(1, 3),
                            "beta": round(rng.uniform(.055, .125), 4)}}
            if rng.random() < .70:
                modes["R"] = {"time": rtime, "cost": rng.randint(2, 5), "beta": 0.0}
            if rng.random() < .75:
                modes["J"] = {"time": jtime, "cost": rng.randint(2, 5),
                              "beta": round(rng.uniform(.035, .085), 4)}
            tasks.append({"id": str(i), "value": rng.randint(6, 14),
                          "weight": rng.randint(1, 3), "modes": modes})
        edges = set()
        # DAG: all arcs from lower to higher task ID; sparse-to-moderate density.
        for j in range(2, n + 1):
            if rng.random() < .80:
                i = rng.randint(max(1, j - 4), j - 1)
                edges.add((i, j))
            if rng.random() < .12:
                i = rng.randint(1, j - 1)
                edges.add((i, j))
        required = [str(i) for i in range(1, max(2, n // 5 + 1))]
        k = max(2, math.ceil(n / 2.2))
        station_cost = {"fixed_cost": 2, "human_cost": 1, "robot_cost": 3}
        out_lines.append({"id": f"L{l}", "cycle_time": 7,
                          "fatigue_limit": .65,
                          "stations": [dict(station_cost) for _ in range(k)],
                          "tasks": tasks,
                          "precedence": [[str(i), str(j)] for i, j in sorted(edges)],
                          "required_tasks": required,
                          "min_recovery": sum(tasks[int(i) - 1]["weight"] for i in required)})
    total_stations = sum(len(line["stations"]) for line in out_lines)
    return {"name": f"synthetic_n{n}_L{lines}_seed{seed}",
            "human_limit": total_stations, "robot_limit": total_stations,
            "lines": out_lines}


def cases_for_suite(suite):
    # Case identity and factorization are recorded in manifest; no hidden randomness.
    yield "reference", "reference_single", 0, None, None
    yield "reference", "reference_double", 0, None, None
    if suite == "pilot":
        for n in (6, 8):
            for seed in (11, 12):
                yield "size", f"size_n{n}_seed{seed}", seed, (n, 1), {}
        for lines in (1, 2):
            yield "lines", f"lines_L{lines}_seed21", 21, (6, lines), {}
        for fatigue in (.40, .85):
            yield "fatigue", f"fatigue_{fatigue:.2f}_seed31", 31, (6, 2), {"fatigue": fatigue}
        for ratio in (.40, .80):
            yield "resources", f"resource_{ratio:.2f}_seed41", 41, (6, 2), {"ratio": ratio}
    else:
        for n in (6, 10, 16, 24):
            for seed in (11, 12, 13):
                yield "size", f"size_n{n}_seed{seed}", seed, (n, 1), {}
        for lines in (1, 2, 3):
            for seed in (21, 22):
                yield "lines", f"lines_L{lines}_seed{seed}", seed, (8, lines), {}
        for fatigue in (.40, .65, .85):
            for seed in (31, 32):
                yield "fatigue", f"fatigue_{fatigue:.2f}_seed{seed}", seed, (8, 2), {"fatigue": fatigue}
        for ratio in (.40, .65, 1.00):
            for seed in (41, 42):
                yield "resources", f"resource_{ratio:.2f}_seed{seed}", seed, (8, 2), {"ratio": ratio}


def write_suite(destination: Path, suite: str, reference: Path):
    destination.mkdir(parents=True, exist_ok=True)
    sample = json.loads(reference.read_text(encoding="utf-8-sig"))
    rows = []
    for group, case, seed, shape, modifications in cases_for_suite(suite):
        if group == "reference":
            import copy
            data = copy.deepcopy(sample)
            if case == "reference_double":
                second = copy.deepcopy(data["lines"][0]); second["id"] = "L2"
                data["lines"].append(second)
                data["human_limit"] *= 2; data["robot_limit"] *= 2
        else:
            n, lines = shape
            data = base_instance(n, lines, seed)
            if "fatigue" in modifications:
                for line in data["lines"]:
                    line["fatigue_limit"] = modifications["fatigue"]
            if "ratio" in modifications:
                total = sum(len(line["stations"]) for line in data["lines"])
                data["human_limit"] = max(0, math.ceil(total * modifications["ratio"]))
                data["robot_limit"] = max(0, math.ceil(total * modifications["ratio"] * .6))
        filename = destination / f"{case}.json"
        filename.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        rows.append(dict(case_id=case, group=group, seed=seed, instance=filename.name,
                         lines=len(data["lines"]), tasks=sum(len(l["tasks"]) for l in data["lines"]),
                         tasks_per_line=max(len(l["tasks"]) for l in data["lines"]),
                         stations=sum(len(l["stations"]) for l in data["lines"]),
                         edges=sum(len(l.get("precedence", [])) for l in data["lines"]),
                         fatigue_limits="/".join(str(l["fatigue_limit"]) for l in data["lines"]),
                         human_limit=data["human_limit"], robot_limit=data["robot_limit"]))
    path = destination / "manifest.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(f"Generated {len(rows)} {suite} cases: {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--suite", choices=("pilot", "full"), default="pilot")
    ap.add_argument("--reference", type=Path, default=Path(__file__).resolve().parents[1] / "instances" / "single_line.json")
    args = ap.parse_args()
    write_suite(args.out, args.suite, args.reference)
