# Tavi Assets 0.1.6 — portable service and protected-path build repair

This is a **standalone source implementation**, delivered through ZipRunner first. It has a local asset engine, versioned data-only manifests, a curated offline storefront, a restricted Python host-test adapter, and a **proposed** JS/TypeScript consumer SDK. It does not provide production Tavi host methods, LoopRD ownership, Wallet purchases, automatic remote downloads, or live TaviX extension distribution.

## Verify the source

On Python 3.10+ (no pip installation required), run from the extracted root:

```sh
python tools/check.py
```

The same command is configured as the project's ZipRunner build command and post-update check. The contract verifier checks package/project identity, original Workboard IDs, verification plan references, and source C4 DSL presence. It validates the example packs and runs the complete Python suite; the Node SDK mock smoke executes only if `node` is available (otherwise skipped, **not passed**). Native Windows and real Tavi extension integration require separate acceptance.

## Open the local storefront

```sh
python tools/asset.py --root .tavi-assets preview --open
```

Preview is loopback-only and development-purpose; never expose it publicly. The catalog includes a classic deck (v0.1.1 and v0.1.2) and the new **Ink & Ember Card Library** (v0.1.0). All sample content is free with **original artwork** and no external network calls. Choose the new card library and expand **Inspect contents** to filter by object type or rarity, view three deck collections and 16 jokers, and preview art. Install it and change its card-back variant (`ochre` / `indigo`) to test persistent customization.

Use `python tools/asset.py --root .tavi-assets doctor` to inspect bounded recovery of abandoned scratch entries. Local developer CLI `install` deliberately operates on an explicit path and **does not enforce remote entitlements**; never expose that command to untrusted applications.

## Integration contract for other projects

- **Authoritative source-level asset pack**: `contracts/tavi-assets-pack-v1.schema.json` and `docs/consumer-contract.adoc` describe `tavi.assets.pack/v1` optional `objects`, `collections`, `taxonomy`, `tags`, `rarity`, `attributes`, `rulesRef`, and resource capability references. `core.validate()` enforces cross references and digest/security checks not expressible by the JSON Schema alone.
- **Proposed host consumer contract**: `contracts/tavi-assets-consumer-v1.json` describes `tavi.assets/v1` and proposed `assets.describe`, `assets.objects.*`, `assets.collections.*`, `assets.preferences.*` and `assets.resolve` methods, which are **NOT yet implemented in Tavi**.
- **Reference SDK**: `sdk/client.mjs` / `sdk/index.d.ts` with feature negotiation and a host-supplied request transport. `sdk/README.adoc` and `examples/consumer-sdk-demo.mjs` explain usage. This is **not** an installed or published TaviX SDK package.
- **Game boundary**: packs describe objects and optional opaque `rulesRef` identifiers. Games own rule execution, card effects and legal deck building. Packs can declare an unlimited variety of designs within bounded validation limits, but **cannot execute scripts or change gameplay without an approved game implementation**.
- **Example metadata**: `examples/storybook-decks/` contains three independent deck collections with 52 playing, 12 arcana and 9 astral cards, plus a collection of 16 custom joker objects. 91 small static SVG illustrations; all art and identities are newly authored, not copies of existing games.

## Release and QA

`project.zr` preserves local config/runtime paths and executes `python tools/check.py` without pushing or releasing. `.ziprunner-workboard-update.json` carries source-reported implementation evidence against **TA-018 and TA-019**, with TA-017 still awaiting operator review and preserves all prior operator/QA ticket IDs. `ziprunner-verification-plan.json`, `.ziprunner-post-update-tests.json` and `docs/QA_0.1.4.adoc` define unexecuted Windows/manual acceptance. No source-push, commit, Actions result or operator-approved release is claimed.

**Next priority:** Verify the 0.1.4 exact ZIP in native Windows ZipRunner, review the proposed contract and actual game support, then negotiate the real Tavi host and TaviX distribution boundaries under existing tickets TA-007/TA-008. Ownership and purchases remain TA-009.

## 0.1.5 — portable service groundwork (source-only)

* `portable_service/service.mjs`, `portable_service/validation.mjs` — no-Python JS asset service with trusted installation policy, signed-off source expectation, strict media/hashes, scoped read-only host dispatch, and global/app-specific preference resolution.
* `portable_service/storage.mjs`, `portable_service/node-file-storage.mjs` — pluggable atomic storage interface; memory and bounded Node **reference** adapters; no production Windows/Android adapter.
* `portable_service/index.d.ts`, `portable_service/README.adoc` — typed host-side SDK and integration responsibilities.
* `contracts/tavi-assets-portable-runtime-v1.json` and `contracts/tavix-asset-dependencies-proposal-v1.json` — machine-readable integration proposal and unresolved TaviX dependencies.
* `tests/runtime_portable_smoke.mjs` — exercises actual data-only three-deck fixture through the consumer SDK and trusted host dispatcher.

The original Python storefront and asset engine are retained. No Tavi 0.3.139 host code was changed. Production TaviX `.tavix` does **not** yet define the proposed asset dependency contract. Run `python tools/check.py` for the source test suite; imported local startup and release remain operator-controlled.

## 0.1.6 — Windows ZipRunner protected-path repair (source-only)

The 0.1.5 Windows build failed because the new JS service was placed in `runtime/`, which is intentionally protected by the existing `project.zr` `runtime/**` overlay exclusion. This repair relocates source modules to `portable_service/` and rewrites imports, documentation, evidence references and C4 model paths. It deliberately **does not remove `runtime/**` from `protected_paths`**: user runtime state must remain untouched. The `tests/test_overlay_protected_paths.py` regression emulates the filter and verifies the resulting source contract. Existing portable service capabilities are preserved. Windows acceptance and Tavi host integration remain pending. See `docs/QA_0.1.6.adoc`.
