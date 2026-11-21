#!/usr/bin/env python3
"""Proves that a file split moved code and changed none.

    split_check.py [--base REF] [--max-lines N] PATH...

Between `git merge-base REF HEAD` and HEAD, under PATHs, it checks that:

1. Every non-blank line removed from a file reappears among the added lines.
2. Every added line that was not removed is a `#include`, `#pragma once`, a namespace opening or
   closing, a comment line, or a class/struct/union/enum forward declaration.
3. No C or C++ file under PATHs has more than N lines (default 1000).

Whitespace-only differences are ignored. Each failure names the file, the line and the text; the
exit status is 1 when any check fails and 0 otherwise. It also prints warnings, which do not
fail: a `static` dropped or added (a linkage change), an anonymous namespace opened in new code,
and a namespace-scope object with a dynamic initializer that moved to another file.

The check is a multiset comparison of lines: it does not see statements reordered inside a
function, which a review of the diff (`git diff --color-moved`) covers.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import subprocess
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MAX_LINES = 1000
BASE_CANDIDATES = ("main", "master", "origin/main", "origin/master")
SOURCE_SUFFIXES = frozenset(
    {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".ipp", ".inl", ".tpp"}
)

NS_BEFORE_BRACE = re.compile(r"(?:^|\s)(?:inline\s+)?namespace(?:\s+[\w:]+)?\s*$")
NAMESPACE_OPEN = re.compile(r"^(?:(?:inline\s+)?namespace(?:\s+[\w:]+)?\s*\{\s*(?:\}\s*)?)+$")
ANON_NAMESPACE = re.compile(r"(?:^|\s)namespace\s*\{")
INCLUDE = re.compile(r"^#\s*include\b")
PRAGMA_ONCE = re.compile(r"^#\s*pragma\s+once\b")
FORWARD_DECL = re.compile(
    r"^(?:template\s*<[^;{}]*>\s*)?(?:class|struct|union|enum(?:\s+(?:class|struct))?)"
    r"(?:\s+\[\[[^\]]*\]\])?\s+[\w:]+(?:\s*:\s*[\w:\s]+)?\s*;$"
)
STATIC_TOKEN = re.compile(r"\bstatic\s+")
NOT_AN_OBJECT = re.compile(
    r"^(?:using|typedef|return|enum|extern|friend|static_assert|template|class|struct|union)\b"
)
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
RAW_OPEN = re.compile(r'"([^()\\\s]{0,16})\(')


def normalize(text: str) -> str:
    """Collapses whitespace so whitespace-only differences compare equal."""
    return " ".join(text.split())


@dataclass(frozen=True)
class Line:
    """One source line as seen by the scanner."""

    code: str  # comments removed, string contents blanked
    ns_only: bool  # at line start every open brace is a namespace and no parenthesis is open
    ns_close: bool  # the line only closes namespaces


NO_LINE = Line("", False, False)


def scan(text: str) -> list[Line]:
    """Classifies each line of a C++ file by its code, ignoring comments and strings."""
    lines = text.replace("\r", "").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    out: list[Line] = []
    frames: list[bool] = []  # True for a namespace brace
    parens = 0
    recent = ""  # code since the last ; { }
    in_block = False
    raw_end: str | None = None
    continued = False
    for raw in lines:
        ns_only = parens == 0 and all(frames)
        stripped = raw.strip()
        if raw_end is None and not in_block and (continued or stripped.startswith("#")):
            continued = stripped.endswith("\\")
            out.append(Line(stripped, ns_only, False))
            continue
        code: list[str] = []
        popped: list[bool] = []
        i, n = 0, len(raw)
        while i < n:
            if raw_end is not None:
                end = raw.find(raw_end, i)
                code.append('""')
                if end < 0:
                    i = n
                    break
                i = end + len(raw_end)
                raw_end = None
                continue
            if in_block:
                end = raw.find("*/", i)
                if end < 0:
                    i = n
                    break
                in_block = False
                i = end + 2
                code.append(" ")
                continue
            c = raw[i]
            if raw.startswith("//", i):
                break
            if raw.startswith("/*", i):
                in_block = True
                i += 2
                continue
            if c == '"':
                m = RAW_OPEN.match(raw, i) if i > 0 and raw[i - 1] == "R" else None
                if m:
                    raw_end = ")" + m.group(1) + '"'
                    i = m.end()
                    continue
                i = _skip_quoted(raw, i, '"')
                code.append('""')
                continue
            if c == "'" and not (i > 0 and raw[i - 1].isdigit()):
                i = _skip_quoted(raw, i, "'")
                code.append("''")
                continue
            if c == "{":
                frames.append(bool(NS_BEFORE_BRACE.search(recent)))
                recent = ""
            elif c == "}":
                popped.append(frames.pop() if frames else False)
                recent = ""
            elif c == ";":
                recent = ""
            else:
                recent += c
                if c == "(":
                    parens += 1
                elif c == ")":
                    parens = max(0, parens - 1)
            code.append(c)
            i += 1
        text_code = "".join(code).strip()
        ns_close = bool(popped) and all(popped) and set(text_code) <= {"}", " ", "\t"}
        out.append(Line(text_code, ns_only, ns_close))
    return out


def _skip_quoted(raw: str, start: int, quote: str) -> int:
    """Returns the index after the string or character literal opened at `start`."""
    i = start + 1
    while i < len(raw):
        if raw[i] == "\\":
            i += 2
        elif raw[i] == quote:
            return i + 1
        else:
            i += 1
    return len(raw)


def is_dynamic_initializer(line: Line) -> bool:
    """Whether a line looks like a namespace-scope object initialized by a call."""
    code = line.code
    if not line.ns_only or not code or NOT_AN_OBJECT.match(code) or "constexpr" in code:
        return False
    if "constinit" in code or "consteval" in code:
        return False
    depth = 0
    for i, c in enumerate(code):
        if c in "({[":
            if c == "(" and depth == 0 and "=" not in code[:i] and "{" not in code[:i]:
                return False  # a function declaration or a call before any `=`
            depth += 1
        elif c in ")}]":
            depth -= 1
        elif c == "=" and depth == 0:
            prev = code[i - 1] if i else ""
            nxt = code[i + 1] if i + 1 < len(code) else ""
            if prev in "=!<>" or nxt == "=":
                continue
            rhs = code[i + 1 :].strip()
            return "(" in rhs and not rhs.startswith("[")
    return False


@dataclass
class Entry:
    """A removed or added line."""

    path: str
    lineno: int
    text: str
    norm: str
    used: bool = False
    info: Line = NO_LINE


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class GitError(Exception):
    pass


def git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=off", "-C", str(repo), *args],
        capture_output=True,
        check=False,
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout.decode(errors="replace")


def resolve_base(repo: Path, base: str | None) -> str:
    candidates = (base,) if base else BASE_CANDIDATES
    for ref in candidates:
        if ref and git(repo, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}", check=False):
            return git(repo, "merge-base", ref, "HEAD").strip()
    wanted = base or " or ".join(BASE_CANDIDATES)
    raise GitError(f"no base commit: {wanted} does not exist (pass --base REF)")


def parse_diff(diff: str) -> tuple[list[Entry], list[Entry]]:
    """Returns the removed and added lines of a zero-context diff, with line numbers."""
    removed: list[Entry] = []
    added: list[Entry] = []
    old_path = new_path = ""
    in_hunk = False
    old_no = new_no = 0
    for raw in diff.split("\n"):
        if raw.startswith("diff --git "):
            in_hunk = False
            old_path = new_path = ""
            continue
        if not in_hunk:
            if raw.startswith("--- "):
                old_path = _header_path(raw[4:])
            elif raw.startswith("+++ "):
                new_path = _header_path(raw[4:])
            elif (m := HUNK.match(raw)) is not None:
                in_hunk = True
                old_no, new_no = int(m.group(1)), int(m.group(3))
            continue
        if (m := HUNK.match(raw)) is not None:
            old_no, new_no = int(m.group(1)), int(m.group(3))
        elif raw.startswith("-"):
            text = raw[1:].replace("\r", "")
            removed.append(Entry(old_path or new_path, old_no, text, normalize(text)))
            old_no += 1
        elif raw.startswith("+"):
            text = raw[1:].replace("\r", "")
            added.append(Entry(new_path or old_path, new_no, text, normalize(text)))
            new_no += 1
    return removed, added


def _header_path(raw: str) -> str:
    raw = raw.split("\t", maxsplit=1)[0]
    if raw == "/dev/null":
        return ""
    return raw[2:] if raw[:2] in ("a/", "b/") else raw


def read_blob(repo: Path, rev: str, path: str) -> str:
    return git(repo, "show", f"{rev}:{path}", check=False)


def is_allowed_shape(line: Line) -> bool:
    code = normalize(line.code)
    return (
        not code
        or line.ns_close
        or bool(INCLUDE.match(code))
        or bool(PRAGMA_ONCE.match(code))
        or bool(NAMESPACE_OPEN.match(code))
        or bool(FORWARD_DECL.match(code))
    )


def check_moves(repo: Path, base: str, paths: list[str], report: Report) -> None:
    diff = git(
        repo,
        "diff",
        "--no-renames",
        "--no-ext-diff",
        "--no-textconv",
        "--no-color",
        "--unified=0",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        base,
        "HEAD",
        "--",
        *paths,
    )
    removed, added = parse_diff(diff)
    old_scans: dict[str, list[Line]] = {}
    new_scans: dict[str, list[Line]] = {}

    def info(cache: dict[str, list[Line]], rev: str, entry: Entry) -> Line:
        if entry.path not in cache:
            cache[entry.path] = scan(read_blob(repo, rev, entry.path))
        lines = cache[entry.path]
        return lines[entry.lineno - 1] if 0 < entry.lineno <= len(lines) else NO_LINE

    pool: dict[str, deque[Entry]] = defaultdict(deque)
    without_static: dict[str, deque[Entry]] = defaultdict(deque)
    for r in removed:
        r.info = info(old_scans, base, r)
        if not r.norm or r.info.ns_close:
            continue
        pool[r.norm].append(r)
        if STATIC_TOKEN.search(r.norm):
            without_static[normalize(STATIC_TOKEN.sub("", r.norm, count=1))].append(r)

    def take(index: dict[str, deque[Entry]], norm: str, path: str) -> Entry | None:
        queue = index.get(norm)
        if not queue:
            return None
        while queue and queue[0].used:
            queue.popleft()
        if not queue:
            return None
        pick = next((e for e in queue if not e.used and e.path == path), queue[0])
        pick.used = True
        return pick

    unmatched: list[Entry] = []
    for a in added:
        if not a.norm:
            continue
        a.info = info(new_scans, "HEAD", a)
        if a.info.ns_close:
            continue
        source = take(pool, a.norm, a.path)
        if source is not None:
            _note_move(report, a, source)
            continue
        source = take(without_static, a.norm, a.path)
        if source is not None:
            report.warnings.append(
                f"{a.path}:{a.lineno}: warning: dropped 'static' (linkage change, "
                f"was {source.path}:{source.lineno}): {a.text.strip()}"
            )
            _note_move(report, a, source)
            continue
        if STATIC_TOKEN.search(a.norm):
            stripped = normalize(STATIC_TOKEN.sub("", a.norm, count=1))
            source = take(pool, stripped, a.path)
            if source is not None:
                report.warnings.append(
                    f"{a.path}:{a.lineno}: warning: added 'static' (linkage change, "
                    f"was {source.path}:{source.lineno}): {a.text.strip()}"
                )
                _note_move(report, a, source)
                continue
        if is_allowed_shape(a.info):
            if ANON_NAMESPACE.search(a.info.code):
                report.warnings.append(
                    f"{a.path}:{a.lineno}: warning: anonymous namespace opened in new code "
                    f"(internal linkage per translation unit): {a.text.strip()}"
                )
            continue
        unmatched.append(a)

    leftover = [r for q in pool.values() for r in q if not r.used]
    leftover.sort(key=lambda e: (e.path, e.lineno))
    _report_failures(unmatched, leftover, report)


def _note_move(report: Report, added: Entry, source: Entry) -> None:
    if source.path != added.path and is_dynamic_initializer(added.info):
        report.warnings.append(
            f"{added.path}:{added.lineno}: warning: dynamic initializer moved from "
            f"{source.path}:{source.lineno} (namespace-scope object, initialization order "
            f"between translation units): {added.text.strip()}"
        )


def _report_failures(unmatched: list[Entry], leftover: list[Entry], report: Report) -> None:
    hints: dict[int, Entry] = {}
    if unmatched and leftover and len(unmatched) * len(leftover) <= 1_000_000:
        by_norm = defaultdict(list)
        for r in leftover:
            by_norm[r.norm].append(r)
        for a in unmatched:
            close = difflib.get_close_matches(a.norm, list(by_norm), n=1, cutoff=0.6)
            if close:
                hints[id(a)] = by_norm[close[0]][0]
    for a in unmatched:
        hint = hints.get(id(a))
        tail = f" (changed from {hint.path}:{hint.lineno}: {hint.text.strip()})" if hint else ""
        report.errors.append(
            f"{a.path}:{a.lineno}: error: added line was not removed anywhere and is not an "
            f"allowed shape: {a.text.strip()}{tail}"
        )
    for r in leftover:
        report.errors.append(
            f"{r.path}:{r.lineno}: error: removed line does not reappear in any added line "
            f"(line number in the base): {r.text.strip()}"
        )


def check_sizes(repo: Path, paths: list[str], max_lines: int, report: Report) -> None:
    out = git(repo, "grep", "-c", "-I", "", "HEAD", "--", *paths, check=False)
    for row in out.splitlines():
        head, _, count = row.rpartition(":")
        path = head.removeprefix("HEAD:")
        if Path(path).suffix not in SOURCE_SUFFIXES or not count.isdigit():
            continue
        total = int(count)
        if total > max_lines:
            lines = scan_free_lines(read_blob(repo, "HEAD", path))
            text = lines[max_lines].strip() if len(lines) > max_lines else ""
            report.errors.append(
                f"{path}:{max_lines + 1}: error: file has {total} lines, the limit is "
                f"{max_lines}: {text}"
            )


def scan_free_lines(text: str) -> list[str]:
    lines = text.replace("\r", "").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def repo_paths(repo: Path, paths: list[str]) -> list[str]:
    """Converts PATHs (relative to the current directory) to repository-relative pathspecs."""
    out = []
    for p in paths:
        rel = os.path.relpath(Path(p).resolve(), repo)
        if rel == ".." or rel.startswith(".." + os.sep):
            raise GitError(f"{p} is outside the repository {repo}")
        out.append(rel)
    return out


def check(repo: Path, base: str | None, max_lines: int, paths: list[str]) -> Report:
    """Runs every check; `paths` are relative to the repository root."""
    report = Report()
    merge_base = resolve_base(repo, base)
    check_moves(repo, merge_base, paths, report)
    check_sizes(repo, paths, max_lines, report)
    report.errors.sort(key=_sort_key)
    report.warnings.sort(key=_sort_key)
    return report


def _sort_key(message: str) -> tuple[str, int, str]:
    path, _, rest = message.partition(":")
    num, _, _ = rest.partition(":")
    return (path, int(num) if num.isdigit() else 0, message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Proves a file split moved code and changed none.",
        usage="%(prog)s [--base REF] [--max-lines N] PATH...",
    )
    parser.add_argument(
        "--base", metavar="REF", help="compare against merge-base of REF and HEAD (default: main)"
    )
    parser.add_argument(
        "--max-lines",
        metavar="N",
        type=int,
        default=DEFAULT_MAX_LINES,
        help=f"longest allowed C/C++ file under PATH (default {DEFAULT_MAX_LINES})",
    )
    parser.add_argument("paths", metavar="PATH", nargs="+", help="files or directories to check")
    args = parser.parse_args(argv)
    try:
        toplevel = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
        report = check(toplevel, args.base, args.max_lines, repo_paths(toplevel, args.paths))
    except GitError as e:
        print(f"split_check: error: {e}")
        return 1
    for message in report.warnings:
        print(message)
    for message in report.errors:
        print(message)
    print(f"split_check: {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
