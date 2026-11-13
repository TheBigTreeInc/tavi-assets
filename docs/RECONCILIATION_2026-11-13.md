# Reconciliation — 2026-11-13

## Identity and evidence
- Key: `tavi-assets`; canonical ID historical handoff `d0fe2552-0ae9-4162-b8e1-68c174d14a3a` (live source not verified).
- User-provided repo: https://github.com/TheBigTreeInc/tavi-assets; branch/HEAD unavailable from connected repository search.
- Source baseline: `tavi-assets-0.1.15-ziprunner.zip`, SHA256 `84bcdf6dcabe39c9298a28b19b1adf09ce0ac8e8748cd92e7b4fa1ebe6313f86`. Operator reported LoopRD component loads.
- Reconciliation source candidate: 0.1.16, docs and metadata only; unaccepted.
- Separate deliverable: Asset Studio `.tavix` 0.1.4 candidate; not merged into Assets engine.
- Library `/tavi-assets/` initially returned no children, but a subsequent provider listing enumerated over 90 root files, including older engine ZIPs, separate Studio/TaviX/Social sources, QA logs and screenshots; shared `/registry/catalog.json` is a proposed catalog containing only ZipRunner and ZipRunner Spec. No authorized shared catalog edits.
- Global `/ECOSYSTEM.md` and `/schematics/_defaults/` were discoverable; no project-specific `/schematics/tavi-assets/` or `/registry/projects/tavi-assets/` was found.

## Deliverable families and disposition
- Engine/LoopRD source: retain verified source baseline 0.1.15; 0.1.16 candidate pending QA and operator acceptance.
- Asset Studio: 0.1.4 installable app and separate ZipRunner source, still unaccepted; keep distinct.
- `.tavia` smoke pack: `org.tavi.assets.registry-smoke` v0.1.0, test input; not a release of engine.
- Contract schemas: source-owned `contracts/` remain canonical; project Library mirror proposed only.
- QA evidence: retain unique version-specific results; older ZIPs may be archived after hash and completeness review.

## Protected / blocked
- No permanent deletions, live migration, Git push, tag or release.
- No Library moves because project-local files were not enumerated; no Project detach action was available.
- Live repo HEAD, accepted release, migration ledger, Windows QA and host file-import acceptance unverified.
- Shared catalog and schematics publication require steward approval.

## Follow-up inventory correction
The second provider inventory returned the project-local historical files. These remain in the root pending exact-byte checks and move verification. No older software was deleted or archived.
