"""List or explicitly initialize Aura's Git submodules; never run their code."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from aura_agent import PROJECT_ROOT, load_engine_specs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List Aura submodules or initialize selected ones.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="Aura checkout root")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--list", action="store_true", help="list modules (default)")
    action.add_argument("--init", nargs="+", metavar="NAME_OR_PATH", help="initialize selected modules")
    action.add_argument("--all", action="store_true", help="download all registered upstream source")
    parser.add_argument("--timeout", type=int, default=900, help="Git operation timeout in seconds")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        specs = load_engine_specs(root)
    except (FileNotFoundError, ValueError) as error:
        parser.error(str(error))
    if args.timeout < 1:
        parser.error("--timeout must be positive")

    if not args.init and not args.all:
        print(f"Aura submodule registry: {len(specs)} configured entries")
        print("Default mode lists metadata only; it does not download or run upstream code.")
        for spec in specs:
            print(f"- {spec.name}: {spec.path} <- {spec.url}")
        print("Use --init NAME_OR_PATH for selected source, or --all only if intended.")
        return 0

    if not (root / ".git").exists():
        parser.error(f"{root} is not a Git checkout root; refusing to initialize submodules")
    by_name = {spec.name: spec for spec in specs}
    by_path = {spec.path: spec for spec in specs}
    if args.all:
        selected = list(specs)
    else:
        selected = []
        seen: set[str] = set()
        for requested in args.init:
            spec = by_name.get(requested) or by_path.get(requested)
            if spec is None:
                parser.error(f"unknown module {requested!r}; use --list to see valid names and paths")
            if spec.path not in seen:
                selected.append(spec)
                seen.add(spec.path)

    paths = [spec.path for spec in selected]
    print(f"Initializing {len(paths)} selected submodule(s) at parent-pinned commits.")
    print("This downloads upstream source; Aura does not execute that code.")
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "submodule", "update", "--init", "--depth", "1", "--", *paths],
            check=False, capture_output=True, text=True, timeout=args.timeout, shell=False,
        )
    except subprocess.TimeoutExpired:
        print(f"Git submodule update exceeded {args.timeout} seconds.")
        return 1
    except OSError as error:
        print(f"Could not start Git: {type(error).__name__}.")
        return 1
    if result.stdout:
        print(result.stdout.rstrip())
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.rstrip())
        print("Submodule update failed; inspect Git output before retrying.")
        return result.returncode or 1
    print("Selected checkouts completed. This does not verify compatibility or safety.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

