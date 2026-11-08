# Tavi Assets 0.1.9 — scoped TaviX grant source handoff

This is a ZipRunner **source candidate**, not production Tavi integration or an approved release. TA-022 repairs the reference host's flat-grant cross-pack authorization defect using TaviX 0.1.11 pack-scoped host-grants/v1 projections and a separately host-verified extension manifest/digest. TA-023 records a separate TaviX capability-grouping review. Existing Workboard task IDs and human review gates remain intact.

- Project: `tavi-assets`; canonical project ID: `d0fe2552-0ae9-4162-b8e1-68c174d14a3a`.
- Version: `0.1.9`; base version: `0.1.8`.
- Build: `python tools/check.py`; post-update check remains non-gating. ZipRunner protected `runtime/**`, `.git/**`, private state and config retained, with no automated release mechanisms.
- Source check: 91 Python tests; 12 new Node scoped grant scenarios plus existing runtime/dependency/developer/SDK examples. The exact ZIP verification report is delivered separately.
- TaviX 0.1.11 source validator/schema parity checked from supplied TaviX package. Native Windows ZipRunner, production host/entitlement, Structurizr CLI, Android/web and operator acceptance remain unverified.
- The TaviX per-pack limit of 32 explicit capabilities cannot directly expose all 90 resources of the Ink & Ember example. Source reference only exposes authorized subsets. No wildcard/prefix expansion, money, new ownership, download or cross-project code change.
- Operator: import exact candidate; collect Windows build and post-update receipts; independently verify negative access checks; approve or reject TA-022 under the original Workboard identity; review TA-023 separately.
- No Git push, tag, release or marketplace publication without explicit approval.

See `docs/tavix-grant-integration.adoc` and `docs/QA_0.1.9.adoc` for the security boundary and acceptance steps.
