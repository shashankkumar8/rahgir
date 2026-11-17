# Synthetic algorithm benchmark results

**Scope warning:** these results are from generated mathematical fixtures only. They are not live road routes, real POI labels, user evaluations, a field study, or evidence of safety.

Runs per algorithm: 40. Candidates per instance: 12.

| Algorithm | Mean HV (3D Monte Carlo) | Mean IGD (6D) | Mean runtime (ms) | Mean Pareto set |
|---|---:|---:|---:|---:|
| Distance-only | 0.054670 | 0.450815 | 0.053 | 1.00 |
| NSGA-II | 0.255434 | 0.126492 | 627.262 | 57.88 |
| Nearest-feasible | 0.134135 | 0.441001 | 0.061 | 1.00 |
| Weighted-greedy | 0.096785 | 0.486873 | 2.213 | 2.75 |

## Paired comparisons (positive improvement favours NSGA-II)

- hypervolume_vs_nearest: {"cluster_bootstrap_95_ci": [0.098441, 0.148631], "direction": "positive favours NSGA-II", "exact_paired_sign_flip_p_value": 0.007812, "mean_paired_improvement": 0.121299, "n_independent_instances": 8, "unit_of_resampling": "instance (seed runs averaged within instance)"}
- hypervolume_vs_weighted_greedy: {"cluster_bootstrap_95_ci": [0.135927, 0.179542], "direction": "positive favours NSGA-II", "exact_paired_sign_flip_p_value": 0.007812, "mean_paired_improvement": 0.158649, "n_independent_instances": 8, "unit_of_resampling": "instance (seed runs averaged within instance)"}
- igd_improvement_vs_nearest: {"cluster_bootstrap_95_ci": [0.287153, 0.343286], "direction": "positive favours NSGA-II", "exact_paired_sign_flip_p_value": 0.007812, "mean_paired_improvement": 0.314509, "n_independent_instances": 8, "unit_of_resampling": "instance (seed runs averaged within instance)"}
- igd_improvement_vs_weighted_greedy: {"cluster_bootstrap_95_ci": [0.330838, 0.388715], "direction": "positive favours NSGA-II", "exact_paired_sign_flip_p_value": 0.007812, "mean_paired_improvement": 0.360381, "n_independent_instances": 8, "unit_of_resampling": "instance (seed runs averaged within instance)"}
- hypervolume_vs_distance_only: {"cluster_bootstrap_95_ci": [0.17252, 0.223968], "direction": "positive favours NSGA-II", "exact_paired_sign_flip_p_value": 0.007812, "mean_paired_improvement": 0.200764, "n_independent_instances": 8, "unit_of_resampling": "instance (seed runs averaged within instance)"}
- igd_improvement_vs_distance_only: {"cluster_bootstrap_95_ci": [0.294588, 0.363566], "direction": "positive favours NSGA-II", "exact_paired_sign_flip_p_value": 0.007812, "mean_paired_improvement": 0.324324, "n_independent_instances": 8, "unit_of_resampling": "instance (seed runs averaged within instance)"}

## Interpretation constraints

- Hypervolume is a fixed-seed Monte Carlo estimate over a three-objective projection; use the same reference and sample count across algorithms.
- IGD is calculated against an exact Pareto front for each small synthetic instance and six normalised objectives.
- Paired inference averages seed runs within each instance; the independent unit is the generated instance, not an individual optimizer run.
- The weighted, nearest and distance-only baselines are intentionally simple and must be supplemented with stronger literature baselines before publication.
- Synthetic benchmark outcomes do not establish real-world route quality, POI truth, user trust, safety, or superiority over state-of-the-art TTDP methods.
- A real-world paper needs live provider snapshots, human relevance labels, route feasibility checks, and a consented participant study.
