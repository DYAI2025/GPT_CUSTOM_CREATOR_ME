"""Command line interface for marker manager."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .service import MarkerManagerService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Marker manager toolkit")
    parser.add_argument("-c", "--config", required=True, help="Path to marker_manager_config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sync", help="Build canonical markers JSON")
    sub.add_parser("validate", help="Validate YAML markers without writing")
    sub.add_parser("watch", help="Watch YAML directory for changes")
    sub.add_parser("gui", help="Run the management GUI")
    return parser


def _load_service(args: argparse.Namespace) -> MarkerManagerService:
    return MarkerManagerService(Path(args.config))


def cmd_sync(args: argparse.Namespace) -> int:
    service = _load_service(args)
    result = service.sync()
    print(json.dumps(result.summary(), indent=2))
    return 0 if result.ok else 1


def cmd_validate(args: argparse.Namespace) -> int:
    service = _load_service(args)
    result = service.validate()
    print(json.dumps(result.summary(), indent=2))
    return 0 if result.ok else 1


def cmd_watch(args: argparse.Namespace) -> int:
    service = _load_service(args)
    service.start_watcher()
    print("Watching for changes. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        service.stop_watcher()
        print("Watcher stopped")
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    from .gui import create_app

    service = _load_service(args)
    app = create_app(service)
    app.run(host="0.0.0.0", port=5173, debug=False)
    return 0


COMMAND_HANDLERS = {
    "sync": cmd_sync,
    "validate": cmd_validate,
    "watch": cmd_watch,
    "gui": cmd_gui,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = COMMAND_HANDLERS[args.command]
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
