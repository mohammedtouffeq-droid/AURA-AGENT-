"""Audit Aura's declared engine submodules without importing or running them."""
from __future__ import annotations

import argparse
import configparser
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit


PROJECT_ROOT = Path(__file__).resolve().parent
STATUS_PATTERN = re.compile(r"^([ \-+U])([0-9a-fA-F]{40}|[0-9a-fA-F]{64})\s+(.+?)(?:\s+\([^)]*\))?$")
STATUS_LABELS = {
    " ": "initialized_at_pinned_commit",
    "-": "not_initialized",
    "+": "commit_mismatch",
    "U": "merge_conflict",
}


@dataclass(frozen=True)
class EngineSpec:
    name: str
    path: str
    url: str


@dataclass(frozen=True)
class EngineStatus:
    name: str
    path: str
    url: str
    state: str
    pinned_commit: str | None = None
    checkout_present: bool = False


def _validate_engine_path(path: str) -> str:
    if not path or "\\" in path or path.startswith("/"):
        raise ValueError(f"unsafe submodule path: {path!r}")
    parsed = PurePosixPath(path)
    normalized = parsed.as_posix()
    if (
        parsed.is_absolute()
        or normalized != path
        or any(part in {"", ".", ".."} for part in parsed.parts)
        or not normalized.startswith("engines/")
        or len(parsed.parts) < 2
    ):
        raise ValueError(f"unsafe submodule path: {path!r}")
    return normalized


def _validate_github_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise ValueError(f"invalid submodule URL: {url!r}") from error
    if (
        parsed.scheme != "https"
        or host is None
        or host.casefold() != "github.com"
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"submodule URL must be a plain HTTPS github.com URL: {url!r}")
    pieces = [piece for piece in parsed.path.split("/") if piece]
    if len(pieces) != 2 or not pieces[0] or not pieces[1] or not pieces[1].endswith(".git"):
        raise ValueError(f"submodule URL must identify an owner/repo.git: {url!r}")
    return url


def load_engine_specs(root: Path) -> tuple[EngineSpec, ...]:
    """Read and validate all entries from the submodule registry."""
    config_path = root / ".gitmodules"
    registry_text = ""
    if config_path.is_file():
        try:
            registry_text = config_path.read_text(encoding="utf-8")
        except (UnicodeError, OSError) as error:
            raise ValueError(f"could not parse {config_path.name}: {error}") from error
    elif root == PROJECT_ROOT:
        from aura_agent import ALL_63_ENGINES
        specs: list[EngineSpec] = []
        for item in ALL_63_ENGINES:
            key = item[0]
            specs.append(EngineSpec(name=f"engines/{key}", path=f"engines/{key}", url=f"https://github.com/mohammedtouffeq-droid/{key}.git"))
        return tuple(specs)
    else:
        raise FileNotFoundError(f"missing submodule registry: {config_path}")

    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str.lower
    try:
        parser.read_string(registry_text)
    except configparser.Error as error:
        raise ValueError(f"could not parse {config_path.name}: {error}") from error
    specs: list[EngineSpec] = []
    seen_paths: set[str] = set()
    for section in parser.sections():
        match = re.fullmatch(r'submodule\s+"([^"]+)"', section)
        if not match:
            raise ValueError(f"unexpected .gitmodules section: {section!r}")
        values = parser[section]
        if "path" not in values or "url" not in values:
            raise ValueError(f"submodule section is missing path or url: {section!r}")
        path = _validate_engine_path(values["path"].strip())
        url = _validate_github_url(values["url"].strip())
        if path in seen_paths:
            raise ValueError(f"duplicate submodule path: {path}")
        seen_paths.add(path)
        specs.append(EngineSpec(name=match.group(1), path=path, url=url))
    if not specs:
        raise ValueError("the .gitmodules registry contains no submodules")
    return tuple(specs)


def parse_submodule_status(output: str) -> dict[str, tuple[str, str]]:
    """Map git submodule status output to path -> (state, pinned commit)."""
    statuses: dict[str, tuple[str, str]] = {}
    for line in output.splitlines():
        if not line:
            continue
        match = STATUS_PATTERN.fullmatch(line)
        if not match:
            raise ValueError(f"unrecognized git submodule status line: {line!r}")
        marker, commit, path = match.groups()
        statuses[_validate_engine_path(path.strip())] = (STATUS_LABELS[marker], commit.lower())
    return statuses


def audit_engines(root: Path = PROJECT_ROOT) -> dict[str, object]:
    """Report local submodule metadata; never imports engines or uses a network."""
    root = root.resolve()
    specs = load_engine_specs(root)
    git_problem: str | None = None
    status_output: str | None = None
    if not (root / ".git").exists():
        git_problem = "This folder is not a Git checkout root (.git marker is missing)."
    else:
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "submodule", "status", "--"],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            git_problem = f"Could not read local submodule status: {type(error).__name__}."
        else:
            if result.returncode != 0:
                git_problem = "Git could not read submodule status; inspect the checkout and Git configuration."
            else:
                status_output = result.stdout

    statuses = parse_submodule_status(status_output) if status_output is not None else {}
    entries: list[EngineStatus] = []
    for spec in specs:
        checkout = (root / Path(*PurePosixPath(spec.path).parts)).exists()
        if git_problem:
            state, pinned_commit = "unverifiable", None
        else:
            state, pinned_commit = statuses.get(spec.path, ("status_missing", None))
        entries.append(EngineStatus(spec.name, spec.path, spec.url, state, pinned_commit, checkout))
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.state] = counts.get(entry.state, 0) + 1
    return {
        "tool": "Aura submodule registry audit",
        "scope": "metadata only; no engine code, model, network request, or task execution",
        "root": str(root),
        "git_status_available": git_problem is None,
        "git_status_note": git_problem,
        "engine_count": len(entries),
        "counts": counts,
        "engines": [asdict(entry) for entry in entries],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit Aura's declared Git submodules.")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT, help="Aura checkout root")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        report = audit_engines(args.root)
    except (FileNotFoundError, ValueError) as error:
        parser.error(str(error))
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"{report['tool']} — {report['engine_count']} declared entries")
        print(report["scope"])
        if report["git_status_note"]:
            print(f"Status unavailable: {report['git_status_note']}")
        for entry in report["engines"]:
            print(f"- {entry['path']}: {entry['state']}; checkout present={str(entry['checkout_present']).lower()}")
        print("This is not an integration, runtime, compatibility, or security test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
