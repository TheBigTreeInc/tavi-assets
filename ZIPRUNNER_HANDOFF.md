# Tavi Assets 0.1.15 — LoopRD descriptor validation repair

Source-only candidate based on 0.1.14. Fixes erroneous `fields` placement: `management.resources.*.fields` is required; `resources.*.fields` is forbidden. No schema/data/authorization changes.

- Build: `python tools/check.py`.
- Verify official LoopRD validator and load response in disposable deployment; component-local migration version 2 requires ledger inspection and approval.
- Does not deploy, publish packs, alter user data, or bridge Tavi admin sessions.
- Preserve protected runtime/configuration and independent Windows/operator approval gates.
