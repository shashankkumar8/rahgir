#!/usr/bin/env python3
"""Reproducible synthetic benchmark for Rahgir's route-corridor selection engine.

These experiments test the optimisation code on generated instances only. They are
NOT real-world route validation, a user study, cultural truth labels, or field data.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.engine.nsga2 import dominates, nsga2  # noqa: E402

CATEGORIES = ["heritage", "food", "nature", "craft", "viewpoint", "history", "market"]


def generate_instance(seed: int, n: int = 12) -> dict:
    rng = random.Random(seed)
    pois = []
    for i in range(n):
        pois.append({
            "id": i,
            "category": rng.choice(CATEGORIES),
            "preference": rng.uniform(0.15, 1.0),
            "cultural": rng.uniform(0.2, 1.0),
            "metadata": rng.uniform(0.2, 1.0),
            "detour_min": rng.uniform(3, 27),
            "detour_km": rng.uniform(1.5, 22),
            "progress": (i + rng.random() * .2) / n,
        })
    return {"pois": pois, "budget_min": 90.0, "budget_km": 100.0, "max_stops": 5, "base_min": 260.0, "max_journey_min": 560.0}


def objective(instance: dict, genes: tuple[int, ...]) -> tuple[tuple[float, ...], dict]:
    pois = instance["pois"]
    selected = [p for p, bit in zip(pois, genes) if bit]
    if len(selected) > instance["max_stops"]:
        return (1e6,) * 6, {"feasible": False, "stops": 0}
    selected.sort(key=lambda p: p["progress"])
    # A small interaction cost represents junction/sequence effects in a synthetic fixture.
    drive_min = sum(p["detour_min"] for p in selected) + max(0, len(selected) - 1) * 1.8
    drive_km = sum(p["detour_km"] for p in selected) + max(0, len(selected) - 1) * 1.2
    total_min = instance["base_min"] + drive_min + len(selected) * 25
    if drive_min > instance["budget_min"] or drive_km > instance["budget_km"] or total_min > instance["max_journey_min"]:
        return (1e6,) * 6, {"feasible": False, "stops": len(selected)}
    if not selected:
        value = diversity = novelty = metadata = 0.0
    else:
        value = sum(p["cultural"] * p["preference"] for p in selected) / instance["max_stops"]
        diversity = len({p["category"] for p in selected}) / instance["max_stops"]
        freq = {c: sum(1 for p in pois if p["category"] == c) for c in CATEGORIES}
        novelty = sum(1 / math.sqrt(freq[p["category"]]) for p in selected) / len(selected)
        novelty /= max((1 / math.sqrt(max(1, v)) for v in freq.values()), default=1)
        metadata = sum(p["metadata"] for p in selected) / len(selected)
    objectives = (-value, -diversity, -novelty, drive_min / instance["budget_min"], drive_km / instance["budget_km"], -metadata)
    return objectives, {"feasible": True, "stops": len(selected), "drive_min": drive_min, "value": value, "diversity": diversity}


def nondominated(items):
    out = []
    for i, item in enumerate(items):
        obj = item[0]
        if not any(j != i and dominates(other[0], obj) for j, other in enumerate(items)):
            out.append(item)
    # Deduplicate by objective vector.
    unique = {}
    for item in out:
        unique[tuple(round(x, 10) for x in item[0])] = item
    return list(unique.values())


def exhaustive_front(instance):
    n = len(instance["pois"])
    solutions = []
    for mask in range(1 << n):
        genes = tuple((mask >> i) & 1 for i in range(n))
        obj, payload = objective(instance, genes)
        if payload["feasible"]:
            solutions.append((obj, payload, genes))
    return nondominated([(x[0], (x[1], x[2])) for x in solutions])


def weighted_greedy(instance, weights):
    selected = [0] * len(instance["pois"])
    current_obj, current = objective(instance, tuple(selected))
    remaining = set(range(len(selected)))
    while remaining:
        choices = []
        for idx in remaining:
            candidate = selected.copy(); candidate[idx] = 1
            obj, payload = objective(instance, tuple(candidate))
            if not payload["feasible"]:
                continue
            utility = weights[0] * (-obj[0]) + weights[1] * (-obj[1]) + weights[2] * (-obj[2]) + weights[3] * (-obj[5])
            incremental_cost = max(1.0, obj[3] - current_obj[3])
            choices.append((utility / incremental_cost, idx, obj, payload))
        if not choices:
            break
        _, idx, current_obj, current = max(choices, key=lambda x: (x[0], -x[1]))
        selected[idx] = 1
        remaining.remove(idx)
    return current_obj, current, tuple(selected)


def nearest_feasible(instance):
    order = sorted(range(len(instance["pois"])), key=lambda i: (instance["pois"][i]["detour_min"], i))
    selected = [0] * len(order)
    best_obj, best_payload = objective(instance, tuple(selected))
    for idx in order:
        trial = selected.copy(); trial[idx] = 1
        obj, payload = objective(instance, tuple(trial))
        if payload["feasible"]:
            selected, best_obj, best_payload = trial, obj, payload
    return best_obj, best_payload, tuple(selected)


def distance_only(instance):
    """Greedy feasibility baseline that prioritises additional distance only."""
    order = sorted(range(len(instance["pois"])), key=lambda i: (instance["pois"][i]["detour_km"], i))
    selected = [0] * len(order)
    best_obj, best_payload = objective(instance, tuple(selected))
    for idx in order:
        trial = selected.copy(); trial[idx] = 1
        obj, payload = objective(instance, tuple(trial))
        if payload["feasible"]:
            selected, best_obj, best_payload = trial, obj, payload
    return best_obj, best_payload, tuple(selected)


def normalise_for_igd(obj: tuple[float, ...], instance: dict) -> tuple[float, ...]:
    return (
        max(0.0, min(1.0, 1.0 + obj[0])),
        max(0.0, min(1.0, 1.0 + obj[1])),
        max(0.0, min(1.0, 1.0 + obj[2])),
        max(0.0, min(1.0, obj[3])),
        max(0.0, min(1.0, obj[4])),
        max(0.0, min(1.0, 1.0 + obj[5])),
    )


def igd(approx, reference, instance):
    if not approx or not reference:
        return 1.0
    a = [normalise_for_igd(x[0], instance) for x in approx]
    r = [normalise_for_igd(x[0], instance) for x in reference]
    return sum(min(math.dist(p, q) for q in a) for p in r) / len(r)


def hypervolume_3d_mc(front, seed=12345, samples=25000):
    """Monte-Carlo HV for (1-relevance, 1-diversity, normalised detour), ref=(1,1,1)."""
    points = []
    for obj, _ in front:
        points.append((max(0, min(1, 1 + obj[0])), max(0, min(1, 1 + obj[1])), max(0, min(1, obj[3]))))
    if not points:
        return 0.0
    rng = random.Random(seed)
    dominated = 0
    for _ in range(samples):
        x, y, z = rng.random(), rng.random(), rng.random()
        if any(px <= x and py <= y and pz <= z for px, py, pz in points):
            dominated += 1
    return dominated / samples


def run(seeds: int, instances: int, n: int, population: int, generations: int) -> list[dict]:
    rows = []
    for instance_id in range(instances):
        # One fixed generated problem per instance; optimizer seeds vary inside
        # the same instance. Exact reference front is computed once per instance.
        fixture_seed = 100_000 + instance_id * 1009
        problem = generate_instance(fixture_seed, n)
        reference = exhaustive_front(problem)
        evaluator = lambda genes: objective(problem, genes)
        for seed in range(seeds):
            start = time.perf_counter()
            nsga = nsga2(evaluator, n, population_size=population, generations=generations, seed=seed + 99)
            nsga_elapsed = (time.perf_counter() - start) * 1000
            nsga_front = nondominated([(x.objectives, x.payload) for x in nsga if x.payload and x.payload["feasible"]])

            start = time.perf_counter()
            greedy_set = []
            for weights in [(1, .4, .3, .2), (.4, 1, .3, .2), (.4, .3, 1, .2), (.5, .5, .5, .5), (1, 1, .2, .8)]:
                greedy_set.append(weighted_greedy(problem, weights))
            greedy_front = nondominated([(x[0], x[1]) for x in greedy_set if x[1]["feasible"]])
            greedy_elapsed = (time.perf_counter() - start) * 1000

            start = time.perf_counter()
            nearest = nearest_feasible(problem)
            nearest_elapsed = (time.perf_counter() - start) * 1000

            start = time.perf_counter()
            distance_solution = distance_only(problem)
            distance_elapsed = (time.perf_counter() - start) * 1000

            nearest_front = [(nearest[0], nearest[1])]
            distance_front = [(distance_solution[0], distance_solution[1])]
            for name, front, elapsed in [
                ("NSGA-II", nsga_front, nsga_elapsed),
                ("Weighted-greedy", greedy_front, greedy_elapsed),
                ("Nearest-feasible", nearest_front, nearest_elapsed),
                ("Distance-only", distance_front, distance_elapsed),
            ]:
                rows.append({
                    "instance_id": instance_id,
                    "seed": seed,
                    "fixture_seed": fixture_seed,
                    "algorithm": name,
                    "candidate_count": n,
                    "reference_front_size": len(reference),
                    "returned_front_size": len(front),
                    "hypervolume_3d_mc": round(hypervolume_3d_mc(front, seed=fixture_seed), 6),
                    "igd_6d": round(igd(front, reference, problem), 6),
                    "runtime_ms": round(elapsed, 3),
                    "feasibility_rate": 1.0 if front else 0.0,
                    "mean_stops": round(statistics.mean([x[1].get("stops", 0) for x in front]), 3) if front else 0.0,
                })
    return rows


def paired_comparison(rows: list[dict], metric: str, baseline: str, *, higher_is_better: bool) -> dict:
    """Cluster-bootstrap instance means and exact sign-flip inference."""
    by_instance: dict[int, dict[str, list[float]]] = {}
    for row in rows:
        by_instance.setdefault(int(row["instance_id"]), {}).setdefault(row["algorithm"], []).append(float(row[metric]))
    differences = []
    for instance_id in sorted(by_instance):
        group = by_instance[instance_id]
        if "NSGA-II" not in group or baseline not in group:
            continue
        raw = statistics.mean(group["NSGA-II"]) - statistics.mean(group[baseline])
        differences.append(raw if higher_is_better else -raw)
    if not differences:
        return {"n_independent_instances": 0, "interpretation": "not enough paired instances"}
    observed = statistics.mean(differences)
    rng = random.Random(99173 + len(differences))
    bootstrap = []
    for _ in range(10000):
        bootstrap.append(statistics.mean(differences[rng.randrange(len(differences))] for _ in differences))
    bootstrap.sort()
    low = bootstrap[int(0.025 * (len(bootstrap) - 1))]
    high = bootstrap[int(0.975 * (len(bootstrap) - 1))]
    n = len(differences)
    p_value = None
    if n <= 16:
        extreme = 0
        total = 1 << n
        threshold = abs(observed) - 1e-12
        for mask in range(total):
            signed = [value if (mask >> i) & 1 else -value for i, value in enumerate(differences)]
            if abs(statistics.mean(signed)) >= threshold:
                extreme += 1
        p_value = extreme / total
    return {
        "n_independent_instances": n,
        "mean_paired_improvement": round(observed, 6),
        "cluster_bootstrap_95_ci": [round(low, 6), round(high, 6)],
        "exact_paired_sign_flip_p_value": round(p_value, 6) if p_value is not None else None,
        "direction": "positive favours NSGA-II",
        "unit_of_resampling": "instance (seed runs averaged within instance)",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--instances", type=int, default=10)
    parser.add_argument("--candidates", type=int, default=12)
    parser.add_argument("--population", type=int, default=64)
    parser.add_argument("--generations", type=int, default=60)
    parser.add_argument("--output", type=Path, default=ROOT / "research" / "results")
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("--seeds must be at least 1")
    if args.instances < 2:
        parser.error("--instances must be at least 2 for paired instance-level comparisons")
    if not 4 <= args.candidates <= 12:
        parser.error("--candidates must be between 4 and 12 (the exact reference-front enumerator is exponential)")
    if args.population < 4:
        parser.error("--population must be at least 4")
    if args.generations < 0:
        parser.error("--generations must be non-negative")
    args.output.mkdir(parents=True, exist_ok=True)
    rows = run(args.seeds, args.instances, args.candidates, args.population, args.generations)
    csv_path = args.output / "synthetic_benchmark.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)
    summary = {}
    for algorithm in sorted({r["algorithm"] for r in rows}):
        subset = [r for r in rows if r["algorithm"] == algorithm]
        summary[algorithm] = {
            "runs": len(subset),
            "mean_hypervolume_3d_mc": round(statistics.mean(x["hypervolume_3d_mc"] for x in subset), 6),
            "mean_igd_6d": round(statistics.mean(x["igd_6d"] for x in subset), 6),
            "mean_runtime_ms": round(statistics.mean(x["runtime_ms"] for x in subset), 3),
            "mean_front_size": round(statistics.mean(x["returned_front_size"] for x in subset), 3),
        }
    payload = {
        "experiment_type": "synthetic algorithm benchmark only",
        "warning": "Not road validation, not POI ground truth, not a user study, not a safety study, and not a claim of real-world effectiveness.",
        "parameters": {"seeds": args.seeds, "instances": args.instances, "candidates": args.candidates, "population": args.population, "generations": args.generations},
        "results": summary,
        "paired_comparisons": {
            "hypervolume_vs_nearest": paired_comparison(rows, "hypervolume_3d_mc", "Nearest-feasible", higher_is_better=True),
            "hypervolume_vs_weighted_greedy": paired_comparison(rows, "hypervolume_3d_mc", "Weighted-greedy", higher_is_better=True),
            "igd_improvement_vs_nearest": paired_comparison(rows, "igd_6d", "Nearest-feasible", higher_is_better=False),
            "igd_improvement_vs_weighted_greedy": paired_comparison(rows, "igd_6d", "Weighted-greedy", higher_is_better=False),
            "hypervolume_vs_distance_only": paired_comparison(rows, "hypervolume_3d_mc", "Distance-only", higher_is_better=True),
            "igd_improvement_vs_distance_only": paired_comparison(rows, "igd_6d", "Distance-only", higher_is_better=False),
        },
    }
    (args.output / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    lines = ["# Synthetic algorithm benchmark results", "", "**Scope warning:** these results are from generated mathematical fixtures only. They are not live road routes, real POI labels, user evaluations, a field study, or evidence of safety.", "", f"Runs per algorithm: {args.seeds * args.instances}. Candidates per instance: {args.candidates}.", "", "| Algorithm | Mean HV (3D Monte Carlo) | Mean IGD (6D) | Mean runtime (ms) | Mean Pareto set |", "|---|---:|---:|---:|---:|"]
    for name, value in summary.items():
        lines.append(f"| {name} | {value['mean_hypervolume_3d_mc']:.6f} | {value['mean_igd_6d']:.6f} | {value['mean_runtime_ms']:.3f} | {value['mean_front_size']:.2f} |")
    lines += ["", "## Paired comparisons (positive improvement favours NSGA-II)", ""]
    for name, comparison in payload["paired_comparisons"].items():
        lines.append(f"- {name}: {json.dumps(comparison, sort_keys=True)}")
    lines += ["", "## Interpretation constraints", "", "- Hypervolume is a fixed-seed Monte Carlo estimate over a three-objective projection; use the same reference and sample count across algorithms.", "- IGD is calculated against an exact Pareto front for each small synthetic instance and six normalised objectives.", "- Paired inference averages seed runs within each instance; the independent unit is the generated instance, not an individual optimizer run.", "- The weighted, nearest and distance-only baselines are intentionally simple and must be supplemented with stronger literature baselines before publication.", "- Synthetic benchmark outcomes do not establish real-world route quality, POI truth, user trust, safety, or superiority over state-of-the-art TTDP methods.", "- A real-world paper needs live provider snapshots, human relevance labels, route feasibility checks, and a consented participant study."]
    (args.output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
