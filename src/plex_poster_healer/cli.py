from __future__ import annotations

import argparse
import logging
from typing import Sequence

from plex_poster_healer.config import load_settings
from plex_poster_healer.healer import PosterHealer
from plex_poster_healer.image_checks import describe_acceleration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plex-poster-healer")
    parser.add_argument("--config", default=None, help="Path to YAML config file")
    parser.add_argument("--library", default=None)
    parser.add_argument("--item-type", default=None, choices=["movie", "show", "season", "episode"])
    parser.add_argument("--title", default=None, help="Substring match on title")
    parser.add_argument("--recently-added-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO")

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("scan")
    subparsers.add_parser("heal")
    subparsers.add_parser("backup")
    subparsers.add_parser("restore")
    return parser


def _print_summary(records) -> None:
    for record in records:
        reasons = ", ".join(record.reasons) if record.reasons else "ok"
        print(
            f"[{record.status}] {record.library} :: {record.title} ({record.item_type})"
            f" | reasons={reasons}"
            f" | replacement={record.replacement_source or '-'}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    settings = load_settings(args.config)
    logging.getLogger(__name__).info("Image acceleration: %s", describe_acceleration(settings.image_backend, settings.prefer_opencl))
    healer = PosterHealer(settings)
    common_kwargs = {
        "library": args.library,
        "item_type": args.item_type,
        "title": args.title,
        "recently_added_only": args.recently_added_only,
    }

    if args.command == "scan":
        records = healer.scan(**common_kwargs)
    elif args.command == "heal":
        records = healer.heal(dry_run=args.dry_run, **common_kwargs)
    elif args.command == "backup":
        records = healer.backup(**common_kwargs)
    else:
        records = healer.restore(dry_run=args.dry_run, **common_kwargs)

    json_path, html_path = healer.report_writer.write(args.command, records)
    _print_summary(records)
    print(f"JSON report: {json_path}")
    print(f"HTML report: {html_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
