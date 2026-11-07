# Tavi Assets 0.1.3 — crash-recovery and post-update QA + offline storefront

This repository contains the **data-only** asset lifecycle engine, a curated sample catalog, a **local developer storefront**, and a proposed restricted host adapter. It does not implement Tavi, TaviX extension loading, LoopRD authentication, production downloads or Wallet purchases.

## Verify the extracted source

Run in the extracted ZIP's project root (Python 3.10+; no pip install needed):

```text
python tools/check.py
```

The check validates the mandatory ZipRunner Workboard update, cross-references the source verification plan and identity, then runs the complete test suite and verifies both sample pack manifests and the example catalog. On Windows, the same command works from PowerShell or CMD.

## Open the storefront preview

```text
python tools/asset.py --root .tavi-assets preview --open
```

If the browser doesn't open, visit `http://127.0.0.1:8765/`. `Ctrl+C` stops the development server. No network calls to external servers are made. **Only this local development UI is served; do not expose it on a public interface.** The preview binds to loopback and uses a token for state-changing requests.

Install the latest free playing-card pack, choose Blue or Green backs, restart the CLI and confirm the choice persists. For an update demonstration, install the older version before opening the preview:

```text
python tools/asset.py --root .tavi-assets install examples/cards-v1
python tools/asset.py --root .tavi-assets preview --open
```

The storefront will then display an update to 0.1.2. Removal clears installed cache bytes but retains customization settings for a future reinstallation. The developer CLI installs *explicit local paths* and bypasses storefront entitlement checks by design; it MUST NOT be exposed to extensions or used as a production install endpoint.

## Recover an interrupted local install (disposable cache only)

```text
python tools/asset.py --root .tavi-assets doctor
```

The asset manager performs a bounded cleanup on initialization while holding its writer lock. `doctor` reports counts of discarded exact-name scratch stages and registry temp files, and finalized but **unregistered** releases still on disk. These inactive releases do not become installed or entitled. A corrupt registry or unsafe cache symlink rejects recovery; it never attempts to infer user ownership. For native Windows acceptance, simulate a stage interruption in a **disposable** cache and retain the exact build/QA log.

`.ziprunner-post-update-tests.json` supplies an explicitly non-gating `python tools/check.py` post-update check. Its presence is **not** evidence that the Windows ZipRunner consumer executed it or supports all proposed spec features.

## Design and responsibilities

- **Tavi Assets:** data-only packs, catalog integration, local lifecycle and preferences, read-only host resolution and preview UI.
- **Tavi:** trusted host session, navigation, authorization, extension-to-host bridge and core settings.
- **LoopRD and Wallet:** server-authoritative ownership, price, transaction and protected-gold decisions.
- **TaviX:** extension/package distribution tooling; its verified existing `.tavix` format is not itself this asset-pack contract.

A host-side `HostAssetService` grants pack/capability pairs to **trusted session identities**. It does not provide a production TaviX wire method, and it must never trust an extension-supplied caller ID. Paid catalog items always fail entitlement checks in the default adapter. Purchases are unavailable.

Further information: `docs/architecture.adoc`, `docs/manifest.adoc`, `docs/integrations.adoc`, `docs/workboard.adoc`, and `architecture/workspace.dsl`.

## Release gate

This source is intended for ZipRunner acceptance. Nothing may push, tag, publish or modify active local credentials, databases or runtime settings. `project.zr` follows the observed TaviX ZipRunner descriptor pattern, but native import behavior still needs verification.

## ZipRunner QA and release boundaries (0.1.3)

ZipRunner reported **`build_passed_operator_unverified`** for the exact 0.1.2 source ZIP, but no post-update plan, operator decision or push was observed. The 0.1.3 candidate adds the post-update descriptor and a bounded TA-010 recovery implementation. This is a producer claim awaiting independent Windows validation, **not** a Windows acceptance result. The local Workboard's original `define-next-pass` and `TA-016` remained Review in the 0.1.2 QA index and remain operator-owned; no Done status or release authorization is inferred. See `docs/QA_0.1.3.adoc` and `ziprunner-verification-plan.json`.

Canonical project ID: `d0fe2552-0ae9-4162-b8e1-68c174d14a3a`. No Git push/tag/Pages/release is authorized or implied.
