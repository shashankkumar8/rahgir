# Start Rahgir locally

This package includes a working local prototype, a clearly labelled offline walkthrough, automated tests, the synthetic research benchmark, and a research-paper draft.

## 1. Run on Windows

Open PowerShell in this folder and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
Copy-Item .env.example .env
$env:PYTHONPATH = "backend"
uvicorn app.main:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000 --reload
```

Then open **http://127.0.0.1:8000**. Use the clearly labelled offline walkthrough to explore the interface without provider credentials. Synthetic routes/places are for testing interactions only—not for travel or publication.

If PowerShell blocks virtual-environment activation, use the virtual-environment Python directly:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000 --reload
```

## 2. Run the tests

```powershell
pip install -r requirements-dev.txt
$env:PYTHONPATH = "backend"
pytest -q
```

Latest recorded run: **44 passed, 0 failed, 0 skipped**. See `docs/TEST_REPORT.md` for exactly what this does and does not verify.

## 3. Configure genuine provider data

The live route workflow uses configurable Nominatim geocoding, OSRM or OpenRouteService routing, and Overpass POI discovery. Edit `.env` only after reading `docs/DATA_SOURCES.md`:

- Set `HTTP_USER_AGENT` to a real application identity and contact address before using public OpenStreetMap services.
- Respect Nominatim rate and usage requirements, Overpass shared-service limits, attribution and ODbL obligations.
- The public OSRM demo is best-effort, not a production service-level agreement.
- For sustained use, configure a contracted routing service or self-hosted provider. For ORS, set `ROUTING_PROVIDER=ors` and `ORS_API_KEY`.

A provider name shown as selected means configured, not that its live endpoint has just been tested. This project build environment could not verify external requests.

## 4. Research artifacts

- `research/paper/rahgir_paper_draft.pdf` — current paper draft.
- `research/paper/rahgir_paper_draft.tex` — editable LaTeX source.
- `research/results/paper_benchmark/` — raw outputs and summaries from synthetic algorithm experiments.
- `research/experiment_protocol.md` and `research/DATASET_CARD.md` — protocol and data boundaries.

The reported optimization results are from synthetic instances only. No live Indian route validation, road/POI field check, safety ground-truth study, or human-participant study has been completed. Do not report synthetic observations as real-world evidence.

## 5. Useful documentation

- `README.md` — full project overview and API reference.
- `docs/UX_AND_PRODUCT_DESIGN.md` — UI semantics and current feature boundaries.
- `docs/ARCHITECTURE.md` — architecture and data flow.
- `docs/DATA_SOURCES.md` — provider, licensing and attribution notes.
- `docs/TEST_REPORT.md` — current verification results and blockers.
- `docs/RELEASE_NOTES.md` — this UX/decision-support upgrade.
