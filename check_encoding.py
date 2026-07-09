#!/usr/bin/env python3
"""Check project text files for UTF-8 decoding errors and likely mojibake."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


DEFAULT_EXTENSIONS = {
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".yaml",
    ".yml",
}
SKIP_DIRECTORIES = {".git", "__pycache__", ".venv", "node_modules"}
MOJIBAKE_MARKERS = {
    "\ufffd": "Unicode replacement character",
    "\u951f\u65a4\u62f7": "common replacement mojibake",
    "\u9475\u637f": "Tencent mojibake fragment",
    "\u6fa6\u5b58\u6f7d": "Toutiao mojibake fragment",
    "\u704f\u5fd5\u5b69\u6d94": "Xiaohongshu mojibake fragment",
    "\u677a\u5a08\u60c0": "operations mojibake fragment",
    "\u5a11\u581c\u20ac": "spend mojibake fragment",
    "\u93b5\u20ac\u704f": "center mojibake fragment",
    "\u6fee\u638d\u7db8": "media mojibake fragment",
}


def iter_text_files(roots: list[Path]) -> list[Path]:
    files: set[Path] = set()
    for root in roots:
        if root.is_file():
            if root.suffix.lower() in DEFAULT_EXTENSIONS:
                files.add(root)
            continue
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRECTORIES for part in path.parts):
                continue
            if path.suffix.lower() in DEFAULT_EXTENSIONS:
                files.add(path)
    return sorted(files)


def inspect_file(path: Path) -> list[str]:
    errors: list[str] = []
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        return [f"not valid UTF-8: {exc}"]
    for marker, description in MOJIBAKE_MARKERS.items():
        if marker in text:
            errors.append(f"contains {description}: {marker!r}")
    return errors


def console_safe(text: str) -> str:
    encoding = sys.stdout.encoding or "utf-8"
    return text.encode(encoding, errors="backslashreplace").decode(encoding)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate UTF-8 text files and detect common Chinese mojibake."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="Files or directories to inspect; defaults to the current directory.",
    )
    args = parser.parse_args()

    failures: list[tuple[Path, list[str]]] = []
    files = iter_text_files([Path(path) for path in args.paths])
    for path in files:
        errors = inspect_file(path)
        if errors:
            failures.append((path, errors))

    if failures:
        print("Encoding check failed:")
        for path, errors in failures:
            for error in errors:
                print(console_safe(f"  {path}: {error}"))
        return 1
    print(f"Encoding check passed: {len(files)} UTF-8 text files inspected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
