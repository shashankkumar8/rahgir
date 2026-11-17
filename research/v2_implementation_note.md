# Rahgir v2 implementation note

**Software release:** 0.2.0  
**Date:** 17 November 2026

This note accompanies the implementation release and is not an updated or replacement research paper.

## Motivation

The supplied team recordings show a landing-to-trip form, interest selection, map-and-itinerary results, stop information, a navigation-like workspace, saved trips, journal notes and a trip conversation surface. The supplied six-page team paper describes a five-stage route-aware discovery and grounded narration pipeline, and explicitly identifies limitations around straight-line detour estimation, independent per-stop budgets, temporary storage, authentication, and unvalidated generated explanations.

## Implemented extension

Rahgir v2 adds an application workspace around the existing route optimizer, including a saved trip index and per-trip journal in browser storage, source-linked POI article context and thumbnails when an explicit OSM Wikipedia tag exists, trip-specific question answering, and live-route-only Google Maps deep links. The question-answer endpoint defaults to deterministic local rules using the stored trip record. An optional OpenRouter client may phrase answers from supplied trip evidence, but neither route planning nor ranking calls the LLM.

The previous route engine remains in place: road-network route and matrix calls, candidate filtering, hard itinerary constraints, seeded multi-objective optimization and source/uncertainty handling. The v2 interface does not use the team's fixed-speed straight-line detour formula as a substitute for the route matrix implementation.

## Safety and grounding decisions

- Trip evidence passed to the optional model is included as untrusted user data, not as system instructions. The system message explicitly treats retrieved JSON and user turns as untrusted and prohibits making up absent route, safety, weather, operating-hours or POI details.
- Local deterministic responses are used if the model key is absent or the provider fails.
- Linked thumbnails are accepted only from `upload.wikimedia.org`; Wikipedia summaries are fetched only for explicit English-language `wikipedia` tags on OSM features.
- Saved trip indices and journal notes remain browser-local; they are not presented as authenticated accounts or cloud sync.
- No road-safety, weather, traffic or emergency data feed has been added. Missing evidence remains missing.

## Evidence and limitations

The v2 verification suite covers backend functional behaviour and a route-intercepted Chromium interaction flow. OpenRouter calls and live external map/provider responses were not validated without user-supplied credentials and live provider access. The current Render preview still uses ephemeral SQLite under `/tmp`; live geocoding remains disabled until a real public-provider contact string is configured. There has been no field validation, human-participant study or controlled comparison against commercial services. No new recommendation-quality or safety outcome claims are supported by this software update.

## Paper update policy

The supplied team paper is retained unchanged. A revised manuscript should only be prepared after the team agrees on authorship and contribution statements and after the methods, software version, experiments and evidence tables are updated consistently. This note should not be cited as proof of effectiveness.
