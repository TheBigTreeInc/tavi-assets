# Tavi Assets 0.1.11 — Windows ZipRunner dependency repair

Corrects the observed Windows `ModuleNotFoundError: No module named sqlalchemy` when importing the new LoopRD registry integration tests. The source test harness runs the exact LoopRD SQL against stdlib SQLite when SQLAlchemy is unavailable, while actual LoopRD uses SQLAlchemy unchanged. No production DB or authorization changes.

Version 0.1.11, base 0.1.10 (failed Windows build), latest accepted baseline 0.1.9. Operator approval and real Windows build remain required. Protected configuration/runtime and publishing gates preserved. No push, tag, release, credentials or automatic online upload.
