from research.run_experiments import run


def test_synthetic_runner_pairs_algorithms_on_fixed_instances():
    rows = run(seeds=2, instances=2, n=4, population=8, generations=2)
    assert len(rows) == 2 * 2 * 4
    assert {row["algorithm"] for row in rows} == {
        "NSGA-II", "Weighted-greedy", "Nearest-feasible", "Distance-only"
    }
    for instance_id in (0, 1):
        instance_rows = [row for row in rows if row["instance_id"] == instance_id]
        assert len(instance_rows) == 8
        assert len({row["fixture_seed"] for row in instance_rows}) == 1
        assert len({row["candidate_count"] for row in instance_rows}) == 1
        assert all(row["feasibility_rate"] == 1.0 for row in instance_rows)


def test_synthetic_runner_is_seed_reproducible_except_runtime():
    first = run(seeds=1, instances=2, n=4, population=8, generations=2)
    second = run(seeds=1, instances=2, n=4, population=8, generations=2)
    stable_fields = (
        "instance_id", "seed", "fixture_seed", "algorithm", "candidate_count",
        "reference_front_size", "returned_front_size", "hypervolume_3d_mc",
        "igd_6d", "feasibility_rate", "mean_stops",
    )
    assert [[row[key] for key in stable_fields] for row in first] == [
        [row[key] for key in stable_fields] for row in second
    ]
