$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python research\run_experiments.py --seeds 5 --instances 8 --candidates 12 --population 64 --generations 60 --output research\results\paper_benchmark
python research\plot_results.py --input research\results\paper_benchmark\synthetic_benchmark.csv --output research\results\paper_benchmark\figures
