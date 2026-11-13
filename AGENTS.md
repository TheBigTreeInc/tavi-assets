# Tavi Assets — project agent instructions

Canonical key: `tavi-assets`; UUID: `d0fe2552-0ae9-4162-b8e1-68c174d14a3a` (historical ZipRunner handoff, repository verification pending). Source repository: `https://github.com/TheBigTreeInc/tavi-assets` (user-provided, live branch not verified).

## Scope and ownership
Own the data-only `.tavia` format, asset manifests, validation, portable service, SDK, LoopRD `tavi-assets` component, ingestion tooling, read-only catalog, and source-owned schemas. Tavi/Social owns the storefront, trusted app host, sessions, local installation and UI; TaviX owns packaging/host capabilities; LoopRD owns runtime and database deployment; Wallet owns Gold balances and entitlements. Asset Studio is a separate `.tavix` deliverable, not an interchangeable version of this repository.

## Safety
Never grant admin based on app ID or client flags. Staging and publication require separate explicit authorization; preserve `ecosystemAdmin` authority and audit. Do not silently upload, migrate, publish, charge Gold, grant entitlements or expose service tokens. Preserve protected paths in `project.zr`, local configuration, credentials, database state and approval gates. Do not commit/push/tag/release without approval.

## Development
Read `README.md`, `docs/workboard.adoc`, `docs/looprd-asset-registry.adoc`, `docs/asset-dependencies.adoc`, `project.zr`, `.ziprunner/` metadata and `registry/project-memory.json`. Consult `/ECOSYSTEM.md`, `/registry/INDEX.md`, `/registry/catalog.json`, and `/schematics/_defaults/` when available. Use source-owned contracts; proposals are not accepted host implementations. Run `python tools/check.py` and test the exact extracted ZIP. Report Windows, live LoopRD and operator acceptance separately. Keep README evergreen, version history in CHANGELOG, QA in docs.

## Continuation
0.1.15 is the last source version with user-confirmed LoopRD component loading, not end-to-end registry acceptance. 0.1.16 is a documentation/knowledge reconciliation candidate, not an authorized release. Asset Studio 0.1.4 is a separate unaccepted app candidate; native `.tavia` picker and backend admin path remain unproven.
