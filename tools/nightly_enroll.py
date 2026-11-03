#!/usr/bin/env python3
"""Enrolls a repository's ci.yml in the central nightly (tools/nightly_dispatch.py).

It removes the `schedule:` block, gives `workflow_dispatch:` a boolean `nightly` input, and passes
`nightly: ${{ inputs.nightly || false }}` to the shared CMake workflow. It changes nothing in a
file that already has a `nightly` input, and refuses (exit 1, file untouched) a ci.yml it does
not recognise: no `workflow_dispatch:` line, one that already has inputs, or no call of cmake.yml.

  nightly_enroll.py [--check] PATH...

PATH is a ci.yml or a repository directory. --check writes nothing and exits 1 when a file would
change. Exit status: 0 ok; 1 a file would change (--check) or was refused; 2 unusable input.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

USES = re.compile(r"^    uses: Kronuz/cpp-libraries/\.github/workflows/cmake\.yml@main\s*(?:#.*)?$")
DISPATCH = "  workflow_dispatch:"
INPUT = ["    inputs:", "      nightly: { type: boolean, default: false }"]
PASS = "      nightly: ${{ inputs.nightly || false }}"


class Refused(ValueError):
    """The file is not in the shape the edit knows."""


def enroll(text: str) -> str:
    """The ci.yml text with the schedule gone and the nightly input wired through."""
    if re.search(r"^\s+nightly:", text, re.M):
        return text
    lines = text.split("\n")
    out: list[str] = []
    skipping = False
    for line in lines:
        if skipping:
            if line.startswith("   ") or not line.strip():
                continue
            skipping = False
        if line.rstrip() == "  schedule:":
            skipping = True
            continue
        out.append(line)
    try:
        at = [line.rstrip() for line in out].index(DISPATCH)
    except ValueError:
        raise Refused("no bare `workflow_dispatch:` line") from None
    if out[at + 1].startswith("    "):
        raise Refused("workflow_dispatch already has a body")
    out[at + 1 : at + 1] = INPUT
    uses = [i for i, line in enumerate(out) if USES.match(line)]
    if len(uses) != 1:
        raise Refused(f"{len(uses)} calls of cmake.yml@main, expected 1")
    at = uses[0]
    if at + 1 < len(out) and out[at + 1].rstrip() == "    with:":
        out.insert(at + 2, PASS)
    else:
        out[at + 1 : at + 1] = ["    with:", PASS]
    return "\n".join(out)


def target(path: Path) -> Path:
    return path / ".github" / "workflows" / "ci.yml" if path.is_dir() else path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enroll ci.yml files in the central nightly.")
    parser.add_argument("paths", nargs="+", type=Path, help="a ci.yml or a repository directory")
    parser.add_argument("--check", action="store_true", help="write nothing")
    args = parser.parse_args(argv)
    status = 0
    for path in map(target, args.paths):
        if not path.is_file():
            print(f"{path}: not a file", file=sys.stderr)
            return 2
        before = path.read_text(encoding="utf-8")
        try:
            after = enroll(before)
        except Refused as why:
            print(f"{path}: refused: {why}")
            status = 1
            continue
        if after == before:
            print(f"{path}: already enrolled")
            continue
        if args.check:
            print(f"{path}: would change")
            status = 1
        else:
            path.write_text(after, encoding="utf-8")
            print(f"{path}: enrolled")
    return status


if __name__ == "__main__":
    sys.exit(main())
