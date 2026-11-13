# Tavi Assets

**Tavi Assets** is a reusable, data-only content management service for the Tavi ecosystem. Its purpose is to let Tavi applications share installable asset packs and user-selected customizations without each application developing its own catalog, installer, storage layer, marketplace, or purchasing mechanism.

The system separates **content** (artwork, media, typed objects and collections), **application behavior** (game rules), **presentation** (storefront), and **authority** (Tavi sessions, LoopRD entitlements and Wallet transactions).

> **Integration status:** LoopRD registry and `.tavia` are candidate source workflows, not deployed; Tavi admin-account bridging still requires authorization and operator acceptance.  This repository contains locally testable Python and JavaScript reference implementations and proposed host contracts. It does **not** yet provide production `assets.*` methods in Tavi, a published TaviX asset distribution contract, or real Gold purchasing. The SDK can be used today with the included explicit local fixture host; production access requires approved host integration.

## What the project provides

- **Asset packs:** versioned, data-only files with validated manifests, content hashes, bounded media, semantic resource capabilities, optional objects and collections.
- **Customization:** selectable resource variants and per-application preferences that override user global defaults and pack defaults.
- **Reusable content:** cards, jokers, boards, game pieces, backgrounds, clothing and furnishings can be modeled as generic typed objects and collections. Game rules are implemented by games, never downloaded as executable asset effects.
- **Discovery and composition:** an embeddable JavaScript reference service can list session-granted packs, discover typed objects across them, and resolve independent visual slots across multiple authorized packs.
- **Local lifecycle:** a Python asset manager, local registry, file integrity checks, staged updates, recovery, and an offline storefront preview.
- **Integration boundaries:** a host-owned service, a restricted consumer SDK, reviewed TaviX per-pack dependency request/grant shapes and a separate versioned *proposed* app-feature requirements declaration with per-feature fallback, and separate proposed storefront bundle/offer metadata contracts.

`rarity` is **optional game-owned metadata**. It is neither required to discover or purchase an asset nor a source of prices, entitlements, or Gold rewards.

## Project layout

| Location | Purpose |
| --- | --- |
| `contracts/` | Versioned pack, consumer request and proposed marketplace contracts |
| `sdk/` | JavaScript/TypeScript unprivileged consumer SDK (host transport injected) |
| `portable_service/` | JavaScript privileged asset service, validators, grant-bound dispatcher and reference storage adapters |
| `developer/` | Explicit local fixture host for independent game development; not production auth |
| `src/tavi_assets/` | Python asset engine, catalog/store, restricted adapter and offline preview |
| `examples/` | Original content packs, multi-deck example and sample application integrations |
| `tests/`, `tools/` | Automated checks, source-contract verification and CLI tools |
| `docs/` | Architecture, manifest, integration, QA, Workboard and developer documentation |
| `CHANGELOG.md` | Version-specific implementation notes and historical changes |

## Start building a game

Prerequisites for the JavaScript developer example: **Node.js** with ES modules and Web Crypto support. No npm install is required. From the repository root:

```sh
node examples/developer/game-assets-demo.mjs
node tests/developer_contract_smoke.mjs
```

The example requests approved content via `createTaviAssetsClient()`: it discovers installed packs, searches for typed cards, and resolves a card face and back from two different packs. The bundled fixture host explicitly installs supplied free example packs and grants capabilities only to a synthetic test session. It has **no ownership server, Wallet integration, paid unlocking or production TaviX security boundary**.

**Developer guide:** [`docs/developer-guide.adoc`](docs/developer-guide.adoc), [`docs/asset-dependencies.adoc`](docs/asset-dependencies.adoc) and [`docs/tavix-grant-integration.adoc`](docs/tavix-grant-integration.adoc) describe the API, contract shapes, stable IDs, code examples, authorization, limitations and acceptance tests. Other project developers should use this guide rather than inventing direct storage access.

## Run the standalone asset preview

Prerequisites: Python 3.10+ (stdlib only), with Node.js also required for the complete source verification command.

```sh
python tools/check.py
python tools/asset.py --root .tavi-assets preview --open
```

The preview binds to the local loopback interface and supports free example content only. It is a **developer tool**, not a production storefront or payment UI. Local `install` CLI usage operates on explicit paths and does not enforce remote entitlements; never expose that CLI to untrusted extensions.

## Architecture and ownership

- **Tavi Assets** owns verified content installation, local registry, asset discovery, customization and the storefront module.
- **Tavi** owns identity, extension sessions and grants, secure storage adapters, navigation, consent, and safe delivery of resources to applications.
- **TaviX** owns extension package/distribution contracts and proposed asset dependency declarations; it does not become an alternative wallet or asset manager.
- **LoopRD / Wallet** owns server-authoritative user entitlements, Gold balances, purchase authorization and transaction history. Gold purchases cannot consume protected free Gold and cannot be granted by local asset metadata.
- **Games and companions** own gameplay and UX, and consume semantic asset resources via a host-granted interface rather than private asset files.

Conceptual customization precedence: **application override → global user preference → pack default**. Composition combines *references and resolved resources*; the application decides layout and meaning. An asset pack does not run game rules, mint currency or install code.

The owned Structurizr model lives in [`docs/architecture/workspace.dsl`](docs/architecture/workspace.dsl); detailed integration constraints are in [`docs/integrations.adoc`](docs/integrations.adoc).

## Security and compatibility expectations

Asset packs are data-only and verified with content hashes, safe paths, allowed media and reference validation. TaviX per-pack grants are checked against a verified extension manifest and each installed pack’s requested capability/version, never flattened across packs. Collection-wide discovery awaits an explicitly approved TaviX grouping contract. Publisher trust is a separate approved distribution concern: **a SHA-256 digest proves integrity against a known expected value, not the publisher's identity**. The privileged service must remain on Tavi's trusted side; game code must receive only scoped consumer SDK requests. Pack ownership, installation and resource authorization are different states, and installation on one device is not a server entitlement.

The proposed `tavi.assets/v1` host feature requires explicit negotiation and a trusted session-bound transport. Unknown features and unsupported methods must fail closed. A game can prototype immediately against the fixture host but should **not** assume the live Tavi or TaviX runtime provides these calls yet. The Node file adapter is reference-only and not production Windows/Android storage.

For the deployment handoff to the LoopRD owner, use [`looprd/INTEGRATION.adoc`](looprd/INTEGRATION.adoc). The registry administration CLI (`tools/looprd-registry.py`) supports scoped inspection, audited publication/revocation with an exact-manifest approval receipt, and verified resource retrieval. These do not substitute for Social's missing Tavi admin delegation bridge.

## Development, verification and publication

`python tools/check.py` is the configured ZipRunner build command. Tests exercise the Python engine, JavaScript SDK and portable runtime; exact Windows, browser, Android, Structurizr CLI and operator acceptance require their own evidence. Source ZIPs include the required Workboard delta and verification plan. Build success never substitutes for operator approval.

**Do not push, tag or publish automatically.** The ZipRunner/operator approval process remains the release gate. Consult [`CHANGELOG.md`](CHANGELOG.md) and `docs/QA_*.adoc` for version-specific history, executed checks and known limitations. See [`docs/workboard.adoc`](docs/workboard.adoc) for author-side Workboard context; the operator's durable Workboard remains authoritative.

## License and contribution boundaries

The repository does not yet contain an approved top-level open-source license. Public visibility alone does not grant redistribution rights. Use original or explicitly licensed art in example packs, document dependencies and ownership, and request review before proposing distribution of third-party content or changing published contracts.


**LoopRD integration note (0.1.15):** The generated registry descriptor uses a component-local migration version `2` instead of the oversized `2026110901` value. Validate against the target LoopRD migration ledger before deployment; this change does not imply successful live loading or production publication.

## Source and knowledge continuity

See `AGENTS.md` for project-specific development boundaries, `registry/project-memory.json` for sourced durable facts, and `docs/RECONCILIATION_2026-11-13.md` for Library/registry disposition. These documents do not imply live publication or operator acceptance.
