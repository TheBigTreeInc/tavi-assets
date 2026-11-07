# Producer handoff — tavi-assets 0.1.4

**Project:** tavi-assets (`d0fe2552-0ae9-4162-b8e1-68c174d14a3a`)  
**Repository:** TheBigTreeInc/tavi-assets (no push performed)  
**Base:** 0.1.3  
**Candidate:** 0.1.4 source ZIP, not a released package.

**Implementation:** TA-017 adds typed card/object libraries, normalized tags and custom rarities, pack-scoped collections, inert joker modifier descriptors, strict metadata validation, proposed host requests and bounded host dispatcher, transport-injected JavaScript/TypeScript SDK, original three-deck card fixture with 16 jokers, local storefront metadata inspector, and source tests. See `docs/consumer-contract.adoc` and `docs/QA_0.1.4.adoc`.

**Reconciliation:** All 12 preexisting Workboard IDs remain in `.ziprunner-workboard-update.json`; the one new ID is TA-017. No operator review status is changed to Done. TA-010 native Windows acceptance and TA-012 Windows/operator gate remain pending. The full original Workboard was not supplied; merge the delta without overwriting user edits.

**Build:** `python tools/check.py`. No pip install required. Optional Node smoke runs if `node` is installed (otherwise skipped, not passed). `.ziprunner-post-update-tests.json` is explicitly non-gating; verify it actually executes on your Windows ZipRunner.

**Operator checks:** Import exact ZIP via ZipRunner; capture SHA and native Windows build/post-update receipts; inspect three decks and joker pool in storefront, alternate backing and persistence; review C4 with Structurizr CLI if available; verify proposed contract with Tavi and TaviX implementers. Do not infer production authorization or gameplay support from this source build.

**Approval gates:** No Git push/tag/release, wallet integration, paid inventory grant, publisher trust or production SDK calls are authorized. Operator acceptance must be recorded separately.
