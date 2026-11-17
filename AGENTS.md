# Engineering rules for Rahgir

These rules are mandatory for every change in this repository.

## Product and scope

- Read `SPEC.md` before changing product behaviour. It is the acceptance contract.
- Rahgir is a route-feasibility and traveller decision tool, not a chatbot, LLM wrapper, generic dashboard or CRUD demo.
- Do not add LLMs to geocoding, routing, stop selection, constraints, ranking, map actions or verification.
- Prefer a complete, specific traveller workflow over a broad feature list. Keep the main route journey obvious.

## Truth and evidence

- No fake live data, invented POIs, fabricated photos, guessed opening hours, guessed vehicle efficiency or guessed prices.
- Synthetic fixtures must be isolated behind an explicit user action and clearly labelled in every relevant view/export.
- A provider failure is a visible structured failure; never silently substitute synthetic data.
- Preserve provider/source attribution, retrieval times and evidence caveats. Do not call metadata completeness factual confidence.
- Never infer safety from no reports, and never claim live traffic, weather, charger availability or medical capacity without an authoritative feed.
- Do not claim a feature or external integration is verified unless its actual path has been tested.

## Implementation discipline

- Work in small vertical slices. Keep modules single-purpose and aim for fewer than 250 lines per module; keep entrypoints thin.
- Avoid monolithic scripts, hidden cross-module globals and duplicate exports.
- Every visible interactive control must have a real action, validation, disabled/loading state and recoverable error state.
- Avoid TODOs, placeholder buttons, no-op event handlers, fake progress timers and mock data in production paths.
- Use typed/validated request and response contracts. Validate coordinates, provider payload dimensions, sequence constraints and external URLs at boundaries.
- Do not add a dependency unless the capability requires it and the value is documented.
- Keep secrets out of source control. Document the exact environment variable and where to configure it.

## Required verification before each release

- Run the complete backend test suite, not only the edited test.
- Run syntax/compile checks for every touched language.
- Run the Chromium browser flow against the real built HTML and separate static modules.
- Check console errors, uncaught page errors, network/API status and one narrow mobile viewport.
- Test success, empty, validation failure and provider failure states for each changed workflow.
- Inspect screenshots and compare them to the intended product, not just a DOM assertion.
- Document what was tested and what could not be tested (especially external provider reachability and field validation).
- Never turn synthetic benchmark results into claims about actual Indian road performance.

## Release discipline

- Commit a complete vertical slice; do not force-push over user work.
- Keep `README.md`, `SPEC.md`, environment examples, deployment notes and test report aligned with the current implementation.
- Do not leave references to removed features in navigation, CSS, docs or API claims.
