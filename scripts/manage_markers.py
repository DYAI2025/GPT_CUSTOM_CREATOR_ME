"""CLI entry point for marker catalog management."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from enginelib.marker_catalog import MarkerCatalog


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Marker- und Schema-Manager")
    sub = parser.add_subparsers(dest="command")

    sync = sub.add_parser("sync", help="Marker einlesen und kanonische JSON erzeugen")
    sync.add_argument("sources", nargs="+", type=Path, help="Dateien oder Verzeichnisse mit Marker-Definitionen")
    sync.add_argument("--output", type=Path, default=Path("markers_canonical.json"))
    sync.add_argument("--focus", type=Path, help="Fokus-Schema (YAML/JSON)")
    sync.add_argument("--models", type=Path, help="Model-Profil Schema (YAML/JSON)")
    sync.add_argument("--spec", default="Marker Canonical", help="ld_spec Kennung")
    sync.add_argument("--version", default="1.0", help="Versionsbezeichnung für die Ausgabe")
    sync.add_argument("--watch", type=int, metavar="INTERVAL", help="Aktiviere Watch-Modus (Intervall in Sekunden)")

    return parser.parse_args(argv)


# ---------------------------------------------------------------------------- sync

def _run_sync(args: argparse.Namespace) -> None:
    def build_once() -> None:
        catalog = MarkerCatalog()
        catalog.load_markers(*args.sources)
        catalog.load_focus_schema(args.focus)
        catalog.load_model_schema(args.models)
        catalog.write(args.output, version=args.version, spec=args.spec)
        print(f"[OK] geschrieben: {args.output}")

    build_once()

    if not args.watch:
        return

    print(f"[INFO] Watch-Modus aktiv. Beobachte alle {args.watch}s auf Änderungen...")
    last_state = _snapshot_state(args.sources, args.focus, args.models)
    try:
        while True:
            time.sleep(max(1, args.watch))
            current_state = _snapshot_state(args.sources, args.focus, args.models)
            if current_state != last_state:
                try:
                    build_once()
                except Exception as exc:  # pragma: no cover - logging only
                    print(f"[ERR] Build fehlgeschlagen: {exc}")
                last_state = current_state
    except KeyboardInterrupt:
        print("[INFO] Watch beendet durch Benutzer")


def _snapshot_state(sources: Sequence[Path], focus: Optional[Path], models: Optional[Path]) -> Tuple:
    entries: List[Tuple[str, float, int]] = []
    for path in _iter_source_files(sources):
        try:
            stat = path.stat()
        except FileNotFoundError:
            continue
        entries.append((str(path), stat.st_mtime_ns, stat.st_size))
    for single in (focus, models):
        if not single:
            continue
        try:
            stat = single.stat()
        except FileNotFoundError:
            continue
        entries.append((str(single), stat.st_mtime_ns, stat.st_size))
    return tuple(sorted(entries))


def _iter_source_files(sources: Sequence[Path]) -> Iterable[Path]:
    for path in sources:
        if path.is_dir():
            for sub in path.rglob("*"):
                if sub.suffix.lower() in {".yaml", ".yml", ".json"}:
                    yield sub
        elif path.suffix.lower() in {".yaml", ".yml", ".json"}:
            yield path


# ---------------------------------------------------------------------------- entry

def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if args.command == "sync":
        _run_sync(args)
        return 0
    print("Kein Kommando angegeben. Nutze --help für Hilfe.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
