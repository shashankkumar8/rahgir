from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass
class Individual(Generic[T]):
    genes: tuple[int, ...]
    objectives: tuple[float, ...]
    payload: T | None = None
    rank: int = 0
    crowding: float = 0.0


def dominates(a: tuple[float, ...], b: tuple[float, ...], eps: float = 1e-12) -> bool:
    """Minimization dominance: no worse in all objectives and strictly better in one."""
    if len(a) != len(b):
        raise ValueError("Objective vectors must have equal dimensions")
    return all(x <= y + eps for x, y in zip(a, b)) and any(x < y - eps for x, y in zip(a, b))


def non_dominated_sort(population: list[Individual]) -> list[list[Individual]]:
    dominates_set: dict[int, list[int]] = {i: [] for i in range(len(population))}
    dominated_count = [0] * len(population)
    fronts_idx: list[list[int]] = [[]]
    for i, p in enumerate(population):
        for j in range(i + 1, len(population)):
            q = population[j]
            if dominates(p.objectives, q.objectives):
                dominates_set[i].append(j)
                dominated_count[j] += 1
            elif dominates(q.objectives, p.objectives):
                dominates_set[j].append(i)
                dominated_count[i] += 1
    for i, count in enumerate(dominated_count):
        if count == 0:
            population[i].rank = 0
            fronts_idx[0].append(i)
    current = 0
    while current < len(fronts_idx) and fronts_idx[current]:
        next_front: list[int] = []
        for i in fronts_idx[current]:
            for j in dominates_set[i]:
                dominated_count[j] -= 1
                if dominated_count[j] == 0:
                    population[j].rank = current + 1
                    next_front.append(j)
        if next_front:
            fronts_idx.append(next_front)
        current += 1
    return [[population[i] for i in front] for front in fronts_idx if front]


def assign_crowding(front: list[Individual]) -> None:
    if not front:
        return
    for item in front:
        item.crowding = 0.0
    dimensions = len(front[0].objectives)
    if len(front) <= 2:
        for item in front:
            item.crowding = float("inf")
        return
    for dim in range(dimensions):
        ordered = sorted(front, key=lambda x: x.objectives[dim])
        ordered[0].crowding = ordered[-1].crowding = float("inf")
        low, high = ordered[0].objectives[dim], ordered[-1].objectives[dim]
        if high - low <= 1e-12:
            continue
        for i in range(1, len(ordered) - 1):
            if ordered[i].crowding != float("inf"):
                ordered[i].crowding += (ordered[i + 1].objectives[dim] - ordered[i - 1].objectives[dim]) / (high - low)


def _tournament(population: list[Individual], rng: random.Random) -> Individual:
    a, b = rng.sample(population, 2)
    return a if (a.rank, -a.crowding) <= (b.rank, -b.crowding) else b


def nsga2(
    evaluate: Callable[[tuple[int, ...]], tuple[tuple[float, ...], T | None]],
    n_genes: int,
    population_size: int = 64,
    generations: int = 60,
    seed: int = 42,
    mutation_probability: float | None = None,
) -> list[Individual[T]]:
    """Binary NSGA-II with elitist environmental selection and deterministic seeding."""
    if n_genes < 0:
        raise ValueError("n_genes cannot be negative")
    if n_genes == 0:
        objectives, payload = evaluate(())
        return [Individual((), objectives, payload)]
    if population_size < 4 or generations < 0:
        raise ValueError("population_size must be >=4 and generations >=0")
    rng = random.Random(seed)
    mutation_probability = mutation_probability if mutation_probability is not None else 1.0 / n_genes
    cache: dict[tuple[int, ...], Individual[T]] = {}

    def make(genes: tuple[int, ...]) -> Individual[T]:
        if genes not in cache:
            objectives, payload = evaluate(genes)
            cache[genes] = Individual(genes, tuple(float(x) for x in objectives), payload)
        return Individual(genes, cache[genes].objectives, cache[genes].payload)

    initial: list[Individual[T]] = [make(tuple(0 for _ in range(n_genes))), make(tuple(1 for _ in range(n_genes)))]
    while len(initial) < population_size:
        initial.append(make(tuple(rng.randint(0, 1) for _ in range(n_genes))))
    population = initial

    for _ in range(generations):
        fronts = non_dominated_sort(population)
        for front in fronts:
            assign_crowding(front)
        offspring: list[Individual[T]] = []
        while len(offspring) < population_size:
            p1, p2 = _tournament(population, rng), _tournament(population, rng)
            child1, child2 = [], []
            for a, b in zip(p1.genes, p2.genes):
                if rng.random() < 0.5:
                    child1.append(a); child2.append(b)
                else:
                    child1.append(b); child2.append(a)
            for child in (child1, child2):
                for i in range(n_genes):
                    if rng.random() < mutation_probability:
                        child[i] = 1 - child[i]
                offspring.append(make(tuple(child)))
                if len(offspring) >= population_size:
                    break
        combined = population + offspring
        next_population: list[Individual[T]] = []
        for front in non_dominated_sort(combined):
            assign_crowding(front)
            if len(next_population) + len(front) <= population_size:
                next_population.extend(front)
            else:
                next_population.extend(sorted(front, key=lambda x: x.crowding, reverse=True)[: population_size - len(next_population)])
                break
        population = next_population

    first_front = non_dominated_sort(population)[0]
    assign_crowding(first_front)
    # Stable ordering for deterministic serialisation and tests.
    return sorted(first_front, key=lambda x: (x.objectives, x.genes))
