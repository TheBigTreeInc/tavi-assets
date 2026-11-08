# Tavi Assets 0.1.6 — ZipRunner build repair handoff

Project: `tavi-assets`  
Canonical ID: `d0fe2552-0ae9-4162-b8e1-68c174d14a3a`  
Version: `0.1.6`  
Last stable base: `0.1.4` (failed 0.1.5 overlay remains unaccepted)  
Update ID: `TAVI-ASSETS-20261108-0116-PROTECTED-OVERLAY-REPAIR`

## Corrected — TA-019 / retains TA-018

The 0.1.5 package accidentally placed the *source* portable service in `runtime/` while ZipRunner's `runtime/**` protected path excluded it from the Windows source overlay. 0.1.5 failed its source evidence check. In 0.1.6 the code, types and related source move to `portable_service/`. Existing protected config/state is deliberately left protected. Tests simulate filtering during import and prevent repeating the mistake.

## Verify

`python tools/check.py` runs Python suite, metadata/pack validations and Node runtime/SDK demos. `tests/test_overlay_protected_paths.py` checks a Windows-like filtered source overlay and missing evidence negative cases. Inspect `docs/QA_0.1.6.adoc` for operator checks.

No native Windows build, actual Tavi host integration, operator approval or Git publication is claimed until separately evidenced. No active config, runtime/private state or generated output is contained in this source ZIP.
