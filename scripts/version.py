#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATH = ROOT / "VERSION"
PYPROJECT_PATH = ROOT / "api" / "pyproject.toml"
INIT_PATH = ROOT / "api" / "src" / "transcributed" / "__init__.py"
CHART_PATH = ROOT / "charts" / "transcributed" / "Chart.yaml"
LOCK_PATH = ROOT / "api" / "uv.lock"
UI_PACKAGE_PATH = ROOT / "ui" / "package.json"
UI_LOCK_PATH = ROOT / "ui" / "package-lock.json"

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def version_from_file() -> str:
    return read_text(VERSION_PATH).strip()


def pyproject_version() -> str:
    data = tomllib.loads(read_text(PYPROJECT_PATH))
    return str(data["project"]["version"])


def regex_version(path: Path, pattern: str, label: str) -> str:
    match = re.search(pattern, read_text(path), re.MULTILINE)
    if match is None:
        raise SystemExit(f"could not find {label} in {path.relative_to(ROOT)}")
    return match.group(1)


def chart_versions() -> tuple[str, str]:
    text = read_text(CHART_PATH)

    def field(name: str) -> str:
        match = re.search(rf"^{name}:\s*(.+)$", text, re.MULTILINE)
        if match is None:
            raise SystemExit(f"could not find {name} in charts/transcributed/Chart.yaml")
        return match.group(1).strip().strip("\"'")

    return field("version"), field("appVersion")


def lock_version() -> str:
    text = read_text(LOCK_PATH)
    match = re.search(
        r'^\[\[package\]\]\nname = "transcributed"\nversion = "([^"]+)"',
        text,
        re.MULTILINE,
    )
    if match is None:
        raise SystemExit("could not find the transcributed package in api/uv.lock")
    return match.group(1)


def ui_package_version() -> str:
    return str(json.loads(read_text(UI_PACKAGE_PATH))["version"])


def ui_lock_versions() -> tuple[str, str]:
    data = json.loads(read_text(UI_LOCK_PATH))
    return str(data["version"]), str(data["packages"][""]["version"])


def collect() -> dict[str, str]:
    chart_version, chart_app_version = chart_versions()
    ui_lock_version, ui_lock_package_version = ui_lock_versions()
    return {
        "VERSION": version_from_file(),
        "api/pyproject.toml": pyproject_version(),
        "api/src/transcributed/__init__.py": regex_version(
            INIT_PATH, r'^__version__ = "([^"]+)"', "__version__"
        ),
        "charts/transcributed/Chart.yaml (version)": chart_version,
        "charts/transcributed/Chart.yaml (appVersion)": chart_app_version,
        "api/uv.lock": lock_version(),
        "ui/package.json": ui_package_version(),
        "ui/package-lock.json": ui_lock_version,
        "ui/package-lock.json (packages[''])": ui_lock_package_version,
    }


def check(tag: str | None) -> int:
    version = version_from_file()
    errors: list[str] = []

    if not VERSION_RE.match(version):
        errors.append(f"VERSION must be X.Y.Z, found {version!r}")

    for name, found in collect().items():
        if found != version:
            errors.append(f"{name}: expected {version}, found {found}")

    if tag is not None and tag != f"v{version}":
        errors.append(f"git tag: expected v{version}, found {tag}")

    if errors:
        for error in errors:
            print(f"version check failed: {error}", file=sys.stderr)
        return 1

    suffix = f" (tag {tag})" if tag else ""
    print(f"version {version} is consistent{suffix}")
    return 0


def replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = read_text(path)
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
    if count != 1:
        raise SystemExit(f"could not update {path.relative_to(ROOT)}")
    if updated != text:
        path.write_text(updated, encoding="utf-8")


def write_json_version(path: Path, new_version: str) -> None:
    text = read_text(path)
    data = json.loads(text)
    data["version"] = new_version
    packages = data.get("packages")
    if isinstance(packages, dict) and "" in packages:
        packages[""]["version"] = new_version
    updated = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if updated != text:
        path.write_text(updated, encoding="utf-8")


def bump(new_version: str) -> int:
    if not VERSION_RE.match(new_version):
        print(f"invalid version {new_version!r}; expected X.Y.Z", file=sys.stderr)
        return 1

    VERSION_PATH.write_text(f"{new_version}\n", encoding="utf-8")
    replace_once(PYPROJECT_PATH, r'^version = "[^"]*"', f'version = "{new_version}"')
    replace_once(INIT_PATH, r'^__version__ = "[^"]*"', f'__version__ = "{new_version}"')
    replace_once(CHART_PATH, r"^version: .*$", f"version: {new_version}")
    replace_once(CHART_PATH, r"^appVersion: .*$", f'appVersion: "{new_version}"')
    replace_once(
        LOCK_PATH,
        r'(^\[\[package\]\]\nname = "transcributed"\nversion = ")[^"]+(")',
        rf"\g<1>{new_version}\g<2>",
    )
    write_json_version(UI_PACKAGE_PATH, new_version)
    write_json_version(UI_LOCK_PATH, new_version)

    print(f"bumped to {new_version}")
    return check(None)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or bump the project version.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="verify all version fields match")
    check_parser.add_argument("--tag", help="also require this git tag to be v<version>")

    bump_parser = subparsers.add_parser("bump", help="update every version field")
    bump_parser.add_argument("version", help="new version in X.Y.Z form")

    args = parser.parse_args()
    if args.command == "check":
        return check(args.tag)
    return bump(args.version)


if __name__ == "__main__":
    raise SystemExit(main())
