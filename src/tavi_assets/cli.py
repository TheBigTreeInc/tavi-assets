import argparse
import json
from pathlib import Path

from .core import AssetManager, validate


def main():
    p = argparse.ArgumentParser(description="Tavi Assets local development CLI")
    p.add_argument("--root", default=".tavi-assets", help="local device cache, never commit")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "install"):
        sub.add_parser(name).add_argument("path")
    sub.add_parser("list")
    sub.add_parser("doctor", help="recover interrupted local scratch stages under lock")
    preview = sub.add_parser("preview", help="loopback-only storefront (no real purchases)")
    preview.add_argument("--examples", default=str(Path(__file__).resolve().parents[2] / "examples"))
    preview.add_argument("--port", type=int, default=8765)
    preview.add_argument("--open", action="store_true")
    args = p.parse_args()
    if args.cmd == "validate":
        print(json.dumps(validate(args.path), indent=2))
    elif args.cmd == "install":
        print(json.dumps(AssetManager(args.root).install(args.path), indent=2))
    elif args.cmd == "list":
        print(json.dumps(AssetManager(args.root)._load(), indent=2))
    elif args.cmd == "doctor":
        # Initializing AssetManager performs crash-safe bounded recovery.
        print(json.dumps(AssetManager(args.root).recovery, indent=2))
    else:
        from .catalog import Catalog, StoreService
        from .preview import run_preview
        run_preview(StoreService(AssetManager(args.root), Catalog(args.examples)), args.port, args.open)


if __name__ == "__main__":
    main()
