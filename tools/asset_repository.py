"""Local author-side repository blueprint and public index tooling; no network calls."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tavi_assets.blueprint_package import create_tavib, inspect_tavib
from tavi_assets.repository_index import build_index, verify_index, write_index


def main(argv=None):
    p = argparse.ArgumentParser(description='Local Tavi Assets content-library toolkit (never publishes)')
    sub = p.add_subparsers(dest='operation', required=True)
    b = sub.add_parser('build-blueprint')
    b.add_argument('source', type=Path)
    b.add_argument('output', type=Path)
    b.add_argument('--id', required=True)
    b.add_argument('--version', required=True)
    b.add_argument('--readme', type=Path)
    b.add_argument('--preview', action='append', type=Path, default=[])
    i = sub.add_parser('inspect-blueprint')
    i.add_argument('archive', type=Path)
    for name in ('catalog-check', 'catalog-preview', 'catalog-write'):
        c = sub.add_parser(name)
        c.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = p.parse_args(argv)
    if args.operation == 'build-blueprint':
        obj = create_tavib(args.source, args.output, args.id, args.version, args.readme, args.preview)
    elif args.operation == 'inspect-blueprint':
        obj = inspect_tavib(args.archive)
    elif args.operation == 'catalog-check':
        obj = verify_index(args.root)
    elif args.operation == 'catalog-preview':
        obj = build_index(args.root)
    else:
        obj = write_index(args.root)
    print(json.dumps(obj, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
