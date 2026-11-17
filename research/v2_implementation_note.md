# Historical note: v2 superseded

The v2 workspace/chat implementation note is retained only as a historical pointer. It is not the specification for the current product and must not be used to infer v3 capabilities.

The current implementation contract is in [`../SPEC.md`](../SPEC.md). The current release boundary is in [`../docs/RELEASE_NOTES.md`](../docs/RELEASE_NOTES.md), and the reproducible test evidence is in [`../docs/TEST_REPORT.md`](../docs/TEST_REPORT.md).

Rahgir v0.3 removes trip chat from the main product. Route planning, candidate assessment, Pareto selection, full via-point validation, vehicle-cost estimation and user actions are deterministic application features. No language model is required for these workflows.
