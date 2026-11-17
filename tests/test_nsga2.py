from app.engine.nsga2 import Individual, assign_crowding, dominates, non_dominated_sort, nsga2


def test_dominance_minimisation():
    assert dominates((1, 2), (2, 3))
    assert not dominates((1, 4), (2, 3))
    assert not dominates((1, 2), (1, 2))


def test_nondominated_sort_fronts():
    population = [
        Individual((0,), (1.0, 3.0)),
        Individual((1,), (2.0, 2.0)),
        Individual((2,), (3.0, 1.0)),
        Individual((3,), (4.0, 4.0)),
    ]
    fronts = non_dominated_sort(population)
    assert len(fronts[0]) == 3
    assert len(fronts[1]) == 1
    assign_crowding(fronts[0])
    assert sum(x.crowding == float("inf") for x in fronts[0]) >= 2


def test_nsga_is_reproducible_and_returns_non_dominated_front():
    def evaluate(genes):
        x = sum(genes)
        y = sum((i + 1) * bit for i, bit in enumerate(genes))
        return (float(x), float(10 - y)), genes
    a = nsga2(evaluate, 6, population_size=24, generations=20, seed=77)
    b = nsga2(evaluate, 6, population_size=24, generations=20, seed=77)
    assert [(x.genes, x.objectives) for x in a] == [(x.genes, x.objectives) for x in b]
    assert all(not dominates(p.objectives, q.objectives) for i, p in enumerate(a) for q in a[i + 1:])


def test_nsga_zero_gene_problem():
    result = nsga2(lambda genes: ((0.0,), "empty"), 0)
    assert result[0].payload == "empty"
