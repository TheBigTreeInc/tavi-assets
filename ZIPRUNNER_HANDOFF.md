# Tavi Assets 0.1.14 — LoopRD MemoryError migration-number repair

This is a source candidate, not a verified live LoopRD deployment. LoopRD 0.1.13 reported `load: MemoryError`; the large migration version `2026110901` is a plausible trigger. The generated descriptor now uses component-local sequential version `2` and retains `resources.*.fields`, privileges, schema and audited registry lifecycle.

- Project `tavi-assets`, canonical ID `d0fe2552-0ae9-4162-b8e1-68c174d14a3a`, version `0.1.14`, base `0.1.13`.
- Build `python tools/check.py`; no auto deployment, runtime or secret files, or production database migration.
- Validate on disposable LoopRD instance, check component migration ledger, capture actual server load and operator receipt.
- Tavi ecosystem-admin broker, Windows QA and production release remain gated.
