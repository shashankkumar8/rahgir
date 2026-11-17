"""Plot synthetic benchmark results using instance-level aggregates.

The independent unit is the generated instance. Repeated optimizer seeds are
first averaged within each instance to avoid pseudoreplication in figures.
"""
from __future__ import annotations
import argparse
import csv
from collections import defaultdict
from pathlib import Path
import statistics

import matplotlib.pyplot as plt


def load_instance_means(csv_path: Path):
    grouped = defaultdict(lambda: defaultdict(list))
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            grouped[row["algorithm"]][int(row["instance_id"])].append(row)
    output = {}
    for algorithm, instances in grouped.items():
        output[algorithm] = {}
        for instance_id, rows in instances.items():
            output[algorithm][instance_id] = {
                metric: statistics.mean(float(row[metric]) for row in rows)
                for metric in ("hypervolume_3d_mc", "igd_6d", "runtime_ms")
            }
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path(__file__).parent / "results" / "paper_benchmark" / "synthetic_benchmark.csv")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "results" / "paper_benchmark" / "figures")
    args = parser.parse_args()
    if not args.input.exists():
        parser.error(f"input file does not exist: {args.input}")
    results = load_instance_means(args.input)
    algorithms = [name for name in ("Distance-only", "Nearest-feasible", "Weighted-greedy", "NSGA-II") if name in results]
    args.output.mkdir(parents=True, exist_ok=True)
    plots = [
        ("hypervolume_3d_mc", "3D Monte Carlo hypervolume (higher is better)", "hypervolume_by_instance.png"),
        ("igd_6d", "6D inverted generational distance (lower is better)", "igd_by_instance.png"),
        ("runtime_ms", "Optimizer runtime per run (ms; lower is faster)", "runtime_by_instance.png"),
    ]
    for metric, ylabel, filename in plots:
        values = [[results[algorithm][instance_id][metric] for instance_id in sorted(results[algorithm])] for algorithm in algorithms]
        fig, ax = plt.subplots(figsize=(8.6, 4.8))
        ax.boxplot(values, tick_labels=algorithms, showmeans=True)
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Algorithm")
        ax.grid(axis="y", alpha=0.25)
        ax.tick_params(axis="x", rotation=12)
        fig.tight_layout()
        fig.savefig(args.output / filename, dpi=220)
        plt.close(fig)
    print(f"Wrote {len(plots)} figures to {args.output}; each box contains {len(next(iter(results.values())))} instance-level observations (seed runs averaged within instance).")


if __name__ == "__main__":
    main()
