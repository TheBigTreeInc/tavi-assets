## 0.1.14 — LoopRD load MemoryError mitigation (candidate)

- Replace initial `tavi-assets` migration version `2026110901` with sequential version `2` in the canonical LoopRD generator and descriptor; preserve both management resource fields.
- Regression check exact version and bounded sequential number; document that the reported server `MemoryError` needs live validation, and that the component migration ledger must be checked before DB changes.
- No actual LoopRD schema execution or deployment, no new administrative authority, no asset publication or Git push.

## 0.1.13 — LoopRD specification validation repair

- Add explicit `fields` to both operator resources in the generated LoopRD descriptor.
- Use migration namespace version 2026110901 rather than reserved/too-low 1; review against target LoopRD migration history before deployment.
- Cover both invariants in a source regression test; keep authorization and publication gates unchanged.
- No production deployment, schema execution or account bridge.

## 0.1.13 — LoopRD integration/operator tooling candidate

- Extended the versioned LoopRD registry descriptor with scoped operator audit inspection and preserved immutable pack/data-only validation.
- Added a no-dependency operator CLI for staging inspection, audit views, exact-manifest receipt-gated publish/revoke, and SHA-256-verified chunk downloads.
- Added isolated negative tests for URL/token handling, write approvals, audit access, digest and download integrity.
- Added LoopRD deployment handoff documenting separate schema ownership, Social admin broker requirement and disposable-instance acceptance gates. No live endpoint, database or publication was changed.

## 0.1.11 — Windows ZipRunner source test dependency repair

- Fixed the `ModuleNotFoundError: No module named sqlalchemy` in `tests/test_tavia_looprd.py` on stock Windows Python.
- Test harness now runs real LoopRD SQL statements against stdlib SQLite when SQLAlchemy is not installed; full SQLAlchemy path remains unchanged when it is available.
- Production LoopRD handler, DAPI source, schemas and permissions are unchanged. No auto-deploy or live ingestion added.
- Existing release/approval gates remain open.

## 0.1.10 — developer TAVIA and LoopRD registry candidate

- Added data-only `.tavia` builder/validator and staged LoopRD database BLOB ingestion implementation.
- Added generated LoopRD service descriptor, audited publish/revoke transitions, management metadata views and offline tests.
- Kept live admin-account integration and LoopRD deployment gated; Tavi ecosystem admin approval requires authoritative verified-session bridge.
- No registry publication, GitHub push, production migration or wallet transaction performed.

# Changelog

Implementation history for source candidates. This document is not a record of release approval or production deployment; exact build receipts and operator decisions are tracked by ZipRunner.

## 0.1.9 — TaviX scoped-grant compatibility repair (source candidate)

- Replaced unsafe flat pack/capability union grants in the reference host with TaviX 0.1.11 per-pack grant projections bound to a separately verified installed extension manifest identity/version/digest. Rejects forged requests, legacy flat grants, revoked scopes, stale pack versions, unrequested capabilities and unauthorized customization.
- Filtered object and collection metadata before totals/pagination and checked each cross-pack composition slot independently; reference dependency status can derive required/optional entries from verified TaviX declarations.
- Added an explicit TaviX fixture and 12 negative/positive regression scenarios, the updated developer fixture host, typed adapter contract and C4/source Workboard updates.
- Recorded the TaviX 32-explicit-capability-per-pack limitation against the 90-resource Ink & Ember sample as TA-023. No implicit wildcard or prefix permission granted. Windows, Tavi-host, LoopRD/Wallet, operator and publication gates remain open.

## 0.1.8 — Proposed application dependency resolution

- Added `tavi.assets.requirements/v1` schema and proposal examples for game-specific required and optional content, version ranges and bundled fallbacks.
- Added a host-only deterministic, grant-scoped dependency readiness resolver, separate `tavi.assets.dependencies/v1` feature negotiation, and a synthetic reference-host test path.
- Added negative tests for spoofing, ungranted content, stale versions and invalid declarations; documented Atrium/Klondike/Social/TaviX handoffs without modifying those projects.

## 0.1.7 — Developer contract stabilization (source candidate)

- Introduced host-granted cross-pack discovery (`assets.packs.list`, `assets.objects.discover`) and read-only multi-slot resolution (`assets.composition.resolve`) in the portable JavaScript reference service and consumer SDK.
- Added independently runnable game developer fixture host, multi-pack game demo and security regression tests.
- Kept rarity optional and game-specific; absent rarity no longer implicitly becomes `common` in Python/JS metadata queries.
- Added proposed customization-bundle and store-offer JSON Schemas. Store offer display metadata is not a payment authorization; actual variant-level ownership still requires future server and host integration.
- Reworked root README into an evergreen entry point with correct status boundaries, developer quickstarts and ownership model. Moved implementation history here.
- Added contract-source verification, Workboard/verification-plan updates and Level 3 C4 changes. Windows, actual Tavi, Android and operator acceptance remain pending.

## 0.1.6 — ZipRunner protected-path repair

- Relocated portable JavaScript service from `runtime/` to `portable_service/`, preserving protected runtime data. Added regression coverage for protected-path source overlays.
- Corrected evidence paths after the Windows 0.1.5 build failed when protected service files were not copied.

## 0.1.5 — Embeddable JavaScript reference service

- Added privileged host-side service, SHA-256/media validation, reference storage adapters, scoped preferences and restricted host-session adapter.
- Added Node tests and a three-deck demonstration. The service was not yet production Tavi integration.

## 0.1.4 — Typed content and consumer SDK

- Added object/collection manifests, optional rarity and tags, descriptive modifiers, three example decks and 16 sample jokers.
- Introduced proposed `tavi.assets/v1` consumer contract, SDK, host request schema and limited preview metadata inspection.

## 0.1.3 — Recovery and post-update checks

- Added bounded staging recovery, safe OS-lock cleanup, recovery tests, CLI doctor and a proposed ZipRunner post-update command.

## 0.1.2 — Source interchange and architecture

- Added required root ZipRunner Workboard update, verification plan, source-contract checks and component-level C4 model expansion.

## 0.1.1 — Offline preview

- Added loopback storefront preview, free curated sample catalog and restricted local management/host test interfaces.

## 0.1.0 — Initial vertical slice

- Added data-only pack manifest, validator, local installation/registry, preferences, example playing-card pack and initial tests.

