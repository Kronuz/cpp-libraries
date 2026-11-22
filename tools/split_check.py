#!/usr/bin/env python3
"""Proves that a file split moved code and changed none.

    split_check.py [--base REF] [--max-lines N] PATH...

Between `git merge-base REF HEAD` and HEAD, under PATHs, it checks that:

1. Every non-blank line removed from a file reappears among the added lines.
2. Every added line that was not removed is a `#include`, `#pragma once`, an include guard, a
   namespace opening or closing, a comment line, a class/struct/union/enum forward declaration,
   a namespace-scope function or `extern` declaration, or a namespace-scope `using` of a detail
   namespace.
3. Moved lines keep their order: each run of added lines that came from consecutive lines of one
   base file starts and ends at a top-level boundary of that file (outside every function, class
   and parenthesis; namespaces do not count). A run that starts or ends inside a function body,
   which is what reordering statements produces, fails; whole declarations may move freely.
4. C and C++ files under PATHs over N lines (default 1000) are reported as notes. A note never
   fails the check: whether a large file stays whole is the reader's call.

The rules are in docs/SPLITTING.md. Whitespace-only differences are ignored. Each failure names
the file, the line and the text; the exit status is 1 when check 1, 2 or 3 fails and 0 otherwise.
It also prints warnings, which do not fail: a `static` dropped or added, an `inline` added, an
added namespace-scope declaration, an anonymous namespace opened in new code (all linkage
changes), an added `using` of a detail namespace, a removed include or comment that reappears
nowhere, and a namespace-scope object with a dynamic initializer that moved to another file.
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

NS_BEFORE_BRACE = re.compile(
    r"(?:^|\s)(?:(?:inline\s+)?namespace(?:\s+[\w:]+)?|[A-Z0-9_]*NAMESPACE[A-Z0-9_]*\s*\(.*\))\s*$"
)
# A whole statement that is a macro call with no `;`, such as `ENUM_CLASS(Name, int, ...)`.
MACRO_STATEMENT = re.compile(r"^[A-Z][A-Z0-9_]*\s*\(.*\)$")
OPERATOR_NAME = re.compile(r"\boperator\s*(?:\(\s*\)|[^\s\w(]+|new|delete)")
NAMESPACE_OPEN = re.compile(r"^(?:(?:inline\s+)?namespace(?:\s+[\w:]+)?\s*\{\s*(?:\}\s*)?)+$")
ANON_NAMESPACE = re.compile(r"(?:^|\s)namespace\s*\{")
INCLUDE = re.compile(r"^#\s*include\b")
PRAGMA_ONCE = re.compile(r"^#\s*pragma\s+once\b")
# An include guard: `#ifndef`/`#define` of a guard-like name, and its `#endif`.
INCLUDE_GUARD = re.compile(r"^#\s*(?:ifndef|define)\s+\w*_(?:H|HH|HPP|HXX|INCLUDED)_*\s*$")
ENDIF = re.compile(r"^#\s*endif\b")
FORWARD_DECL = re.compile(
    r"^(?:template\s*<[^;{}]*>\s*)?(?:class|struct|union|enum(?:\s+(?:class|struct))?)"
    r"(?:\s+\[\[[^\]]*\]\])?\s+[\w:]+(?:\s*:\s*[\w:\s]+)?\s*;$"
)
STATIC_TOKEN = re.compile(r"\bstatic\s+")
INLINE_TOKEN = re.compile(r"^inline\s+")
# A namespace-scope using of a detail namespace, where SPLITTING.md puts helpers pieces share.
USING = re.compile(r"^using\s+(?:namespace\s+)?(?:[\w:]*::)?\w*detail\w*(?:::\w+)*\s*;$")
NOT_AN_OBJECT = re.compile(
    r"^(?:using|typedef|return|enum|extern|friend|static_assert|template|class|struct|union)\b"
)
NOT_A_DECLARATION = re.compile(r"^(?:using|typedef|return|enum|static_assert|class|struct|union)\b")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
RAW_OPEN = re.compile(r'"([^()\\\s]{0,16})\(')


def normalize(text: str) -> str:
    """Collapses whitespace so whitespace-only differences compare equal."""
    return " ".join(text.split())


def without_static(norm: str) -> str | None:
    """The line without its first `static` token, or None when it has none."""
    if not STATIC_TOKEN.search(norm):
        return None
    return normalize(STATIC_TOKEN.sub("", norm, count=1))


def without_inline(norm: str) -> str | None:
    """The line without its leading `inline`, or None when it has none."""
    if not INLINE_TOKEN.search(norm):
        return None
    return normalize(INLINE_TOKEN.sub("", norm, count=1))


@dataclass
class Line:
    """One source line as seen by the scanner."""

    code: str = ""  # comments removed, string contents blanked
    ns_only: bool = False  # at line start only namespaces are open, and no parenthesis
    ns_close: bool = False  # the line only closes namespaces
    decl: bool = False  # part of a namespace-scope function or extern declaration
    at_start: bool = False  # a statement begins here, outside every function and class
    at_end: bool = False  # the line completes a statement outside every function and class
    owner_start: int = 0  # line where the construct open at the line start began (0 when none)
    owner_end: int = 0  # the same at the line end


def split_lines(text: str) -> list[str]:
    lines = text.replace("\r", "").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def scan(text: str) -> list[Line]:
    """Classifies each line of a C++ file by its code, ignoring comments and strings."""
    out: list[Line] = []
    frames: list[bool] = []  # True for a namespace brace
    parens = 0
    recent = ""  # code since the last ; { }
    recent_line = 0  # line where `recent` began
    top_line = 0  # line where the outermost open non-namespace brace's statement began
    in_block = False
    raw_end: str | None = None
    continued = False

    def state() -> tuple[bool, int]:
        """(at a boundary, line of the construct left open) at the current position."""
        if frames.count(False) > 0:
            return False, top_line
        if parens > 0 or recent.strip():
            return False, recent_line
        return True, 0

    for lineno, raw in enumerate(split_lines(text), start=1):
        ns_only = parens == 0 and all(frames)
        at_start, owner_start = state()
        stripped = raw.strip()
        if raw_end is None and not in_block and (continued or stripped.startswith("#")):
            continued = stripped.endswith("\\")
            out.append(
                Line(stripped, False, False, False, at_start, at_start, owner_start, owner_start)
            )
            continue
        code: list[str] = []
        popped: list[bool] = []
        declared: list[int] = []  # first lines of declarations that end on this line
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
                is_ns = bool(NS_BEFORE_BRACE.search(recent))
                if not is_ns and frames.count(False) == 0:
                    top_line = recent_line if recent.strip() else lineno
                frames.append(is_ns)
                recent = ""
            elif c == "}":
                popped.append(frames.pop() if frames else False)
                recent = ""
            elif c == ";":
                if parens == 0 and all(frames) and _is_declaration(normalize(recent)):
                    declared.append(recent_line)
                recent = ""
            else:
                if not c.isspace() and not recent.strip():
                    recent_line = lineno
                recent += c
                if c == "(":
                    parens += 1
                elif c == ")":
                    parens = max(0, parens - 1)
            code.append(c)
            i += 1
        text_code = "".join(code).strip()
        if (
            parens == 0
            and text_code.endswith(")")
            and MACRO_STATEMENT.match(normalize(recent))
            and "NAMESPACE" not in recent.partition("(")[0]
        ):
            recent = ""
        ns_close = bool(popped) and all(popped) and set(text_code) <= {"}", " ", "\t"}
        at_end, owner_end = state()
        out.append(
            Line(text_code, ns_only, ns_close, False, at_start, at_end, owner_start, owner_end)
        )
        for first in declared:
            for k in range(max(first, 1) - 1, len(out)):
                out[k].decl = True
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


def _is_declaration(stmt: str) -> bool:
    """Whether a namespace-scope statement is a function or `extern` declaration."""
    if not stmt or NOT_A_DECLARATION.match(stmt):
        return False
    if stmt.startswith("extern "):
        return True
    head = stmt.partition("(")[0]
    return "(" in stmt and "=" not in head


def is_dynamic_initializer(line: Line) -> bool:
    """Whether a line looks like a namespace-scope object initialized by a call."""
    code = OPERATOR_NAME.sub("operator", line.code)
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


@dataclass(eq=False)
class Entry:
    """A removed or added line."""

    path: str
    lineno: int
    text: str
    norm: str
    hunk: int = 0
    used: bool = False
    info: Line = field(default_factory=Line)
    after: str = ""  # for an added line, the next non-blank added line of its hunk
    source: Entry | None = None  # for an added line, the removed line it came from


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


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


def parse_diff(diff: str) -> tuple[list[Entry], list[Entry], dict[int, tuple[int, int]]]:
    """Returns the removed and added lines of a zero-context diff, with line numbers.

    The third value maps each hunk to the base lines around its removed part: the line before
    it and the first line after it (both unchanged, so also adjacent to its added part).
    """
    removed: list[Entry] = []
    added: list[Entry] = []
    bounds: dict[int, tuple[int, int]] = {}
    old_path = new_path = ""
    in_hunk = False
    old_no = new_no = 0
    hunk = 0
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
                hunk += 1
                old_no, new_no = int(m.group(1)), int(m.group(3))
                bounds[hunk] = _hunk_bounds(m)
            continue
        if (m := HUNK.match(raw)) is not None:
            hunk += 1
            old_no, new_no = int(m.group(1)), int(m.group(3))
            bounds[hunk] = _hunk_bounds(m)
        elif raw.startswith("-"):
            text = raw[1:].replace("\r", "")
            removed.append(Entry(old_path or new_path, old_no, text, normalize(text), hunk))
            old_no += 1
        elif raw.startswith("+"):
            text = raw[1:].replace("\r", "")
            added.append(Entry(new_path or old_path, new_no, text, normalize(text), hunk))
            new_no += 1
    return removed, added, bounds


def _hunk_bounds(m: re.Match[str]) -> tuple[int, int]:
    start = int(m.group(1))
    count = 1 if m.group(2) is None else int(m.group(2))
    return (start - 1, start + count) if count else (start, start + 1)


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
        or line.decl
        or bool(INCLUDE.match(code))
        or bool(PRAGMA_ONCE.match(code))
        or bool(INCLUDE_GUARD.match(code))
        or bool(ENDIF.match(code))
        or bool(NAMESPACE_OPEN.match(code))
        or bool(FORWARD_DECL.match(code))
        or (line.ns_only and bool(USING.match(code)))
    )


class Base:
    """The files at the base commit: their lines and their scans."""

    def __init__(self, repo: Path, rev: str) -> None:
        self.repo = repo
        self.rev = rev
        self.texts: dict[str, list[str]] = {}
        self.scans: dict[str, list[Line]] = {}

    def load(self, path: str) -> None:
        if path not in self.scans:
            text = read_blob(self.repo, self.rev, path)
            self.texts[path] = split_lines(text)
            self.scans[path] = scan(text)

    def info(self, entry: Entry) -> Line:
        self.load(entry.path)
        lines = self.scans[entry.path]
        return lines[entry.lineno - 1] if 0 < entry.lineno <= len(lines) else Line()

    def next_nonblank(self, path: str, lineno: int) -> int:
        """The number of the first non-blank line after `lineno` (0 at the end of the file)."""
        self.load(path)
        texts = self.texts[path]
        for k in range(lineno, len(texts)):
            if texts[k].strip():
                return k + 1
        return 0

    def owner(self, path: str, lineno: int) -> str:
        self.load(path)
        texts = self.texts[path]
        if 0 < lineno <= len(texts):
            return f"{path}:{lineno}: {texts[lineno - 1].strip()}"
        return path


def check_moves(repo: Path, base: str, paths: list[str], report: Report) -> None:
    diff = git(
        repo,
        "diff",
        "--no-renames",
        "--no-ext-diff",
        "--no-textconv",
        "--no-color",
        "--unified=0",
        "--diff-algorithm=histogram",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        base,
        "HEAD",
        "--",
        *paths,
    )
    removed, added, bounds = parse_diff(diff)
    # Only C and C++ sources are code; a layout note or a CMake line is not a move.
    removed = [e for e in removed if Path(e.path).suffix in SOURCE_SUFFIXES]
    added = [e for e in added if Path(e.path).suffix in SOURCE_SUFFIXES]
    old = Base(repo, base)
    new_scans: dict[str, list[Line]] = {}

    def new_info(entry: Entry) -> Line:
        if entry.path not in new_scans:
            new_scans[entry.path] = scan(read_blob(repo, "HEAD", entry.path))
        lines = new_scans[entry.path]
        return lines[entry.lineno - 1] if 0 < entry.lineno <= len(lines) else Line()

    pool: dict[str, deque[Entry]] = defaultdict(deque)
    by_stripped: dict[str, deque[Entry]] = defaultdict(deque)
    by_position: dict[tuple[str, int], Entry] = {}
    for r in removed:
        r.info = old.info(r)
        if not r.norm or r.info.ns_close:
            continue
        pool[r.norm].append(r)
        by_position[r.path, r.lineno] = r
        stripped = without_static(r.norm)
        if stripped is not None:
            by_stripped[stripped].append(r)

    def follows_like(e: Entry, a: Entry) -> bool:
        """Whether the line after removed `e` is the line after added `a`."""
        nxt = by_position.get((e.path, old.next_nonblank(e.path, e.lineno)))
        return bool(a.after) and nxt is not None and nxt.norm == a.after

    def take(
        index: dict[str, deque[Entry]], norm: str, a: Entry, prev: Entry | None, stripped: bool
    ) -> Entry | None:
        """Picks the removed line `a` came from, preferring the one after `prev`'s source."""
        queue = index.get(norm)
        if not queue:
            return None
        if prev is not None and prev.source is not None:
            nxt = by_position.get(
                (prev.source.path, old.next_nonblank(prev.source.path, prev.source.lineno))
            )
            if (
                nxt is not None
                and not nxt.used
                and (without_static(nxt.norm) if stripped else nxt.norm) == norm
            ):
                nxt.used = True
                return nxt
        while queue and queue[0].used:
            queue.popleft()
        if not queue:
            return None
        live = [e for e in queue if not e.used]
        if not live:
            return None
        pick = max(live, key=lambda e: (follows_like(e, a), e.info.at_start, e.path == a.path))
        pick.used = True
        return pick

    following: Entry | None = None
    for a in reversed(added):
        if following is not None and (following.path, following.hunk) != (a.path, a.hunk):
            following = None
        a.after = following.norm if following is not None else ""
        if a.norm:
            following = a
    unmatched: list[Entry] = []
    prev: Entry | None = None
    for a in added:
        if not a.norm:
            continue
        a.info = new_info(a)
        if a.info.ns_close:
            continue
        if prev is not None and (prev.path != a.path or prev.hunk != a.hunk):
            prev = None
        source = take(pool, a.norm, a, prev, False)
        if source is None:
            source = take(by_stripped, a.norm, a, prev, True)
            if source is not None:
                report.warnings.append(
                    f"{a.path}:{a.lineno}: warning: dropped 'static' (linkage change, "
                    f"was {source.path}:{source.lineno}): {a.text.strip()}"
                )
        if source is None:
            stripped_line = without_static(a.norm)
            if stripped_line is not None:
                source = take(pool, stripped_line, a, prev, False)
                if source is not None:
                    report.warnings.append(
                        f"{a.path}:{a.lineno}: warning: added 'static' (linkage change, "
                        f"was {source.path}:{source.lineno}): {a.text.strip()}"
                    )
        if source is None:
            plain = without_inline(a.norm)
            if plain is not None:
                source = take(by_stripped, plain, a, prev, True) or take(
                    pool, plain, a, prev, False
                )
                if source is not None:
                    report.warnings.append(
                        f"{a.path}:{a.lineno}: warning: added 'inline' (linkage change, "
                        f"was {source.path}:{source.lineno}): {a.text.strip()}"
                    )
        if source is not None:
            a.source = source
            prev = a
            _note_move(report, a, source)
            continue
        if is_allowed_shape(a.info):
            if a.info.decl:
                report.warnings.append(
                    f"{a.path}:{a.lineno}: warning: namespace-scope declaration added "
                    f"(linkage change): {a.text.strip()}"
                )
            elif USING.match(normalize(a.info.code)):
                report.warnings.append(
                    f"{a.path}:{a.lineno}: warning: using added (name lookup change): "
                    f"{a.text.strip()}"
                )
            elif ANON_NAMESPACE.search(a.info.code):
                report.warnings.append(
                    f"{a.path}:{a.lineno}: warning: anonymous namespace opened in new code "
                    f"(internal linkage per translation unit): {a.text.strip()}"
                )
            continue
        unmatched.append(a)

    leftover = []
    for r in sorted(
        (r for q in pool.values() for r in q if not r.used), key=lambda e: (e.path, e.lineno)
    ):
        code = normalize(r.info.code)
        if not code or INCLUDE.match(code):
            kind = "include" if code else "comment"
            report.warnings.append(
                f"{r.path}:{r.lineno}: warning: removed {kind} does not reappear "
                f"(line number in the base): {r.text.strip()}"
            )
        else:
            leftover.append(r)
    _report_failures(unmatched, leftover, report)
    if not unmatched and not leftover:
        _check_slices(added, old, bounds, report)


def _check_slices(
    added: list[Entry], old: Base, bounds: dict[int, tuple[int, int]], report: Report
) -> None:
    """Each run of added lines from consecutive base lines must begin and end at a boundary.

    A run also continues through the unchanged lines beside its hunk, so a line edited in place
    is not a boundary.
    """
    run: list[Entry] = []

    def close() -> None:
        if not run:
            return
        first, last = run[0], run[-1]
        assert first.source is not None and last.source is not None
        before, after = bounds[first.hunk]
        in_place_start = first.source.lineno == old.next_nonblank(first.path, before)
        in_place_end = old.next_nonblank(last.path, last.source.lineno) == old.next_nonblank(
            last.path, after - 1
        )
        if not first.source.info.at_start and not (
            first.source.path == first.path and in_place_start
        ):
            _slice_error(report, old, first, "starts")
        if not last.source.info.at_end and not (last.source.path == last.path and in_place_end):
            _slice_error(report, old, last, "ends")
        run.clear()

    for a in added:
        if a.source is None:
            continue
        if run:
            last = run[-1]
            assert last.source is not None
            follows = (
                a.path == last.path
                and a.hunk == last.hunk
                and a.source.path == last.source.path
                and a.source.lineno == old.next_nonblank(last.source.path, last.source.lineno)
            )
            if not follows:
                close()
        run.append(a)
    close()


def _slice_error(report: Report, old: Base, added: Entry, edge: str) -> None:
    source = added.source
    assert source is not None
    owner = source.info.owner_start if edge == "starts" else source.info.owner_end
    where = old.owner(source.path, owner) if owner else source.path
    report.errors.append(
        f"{added.path}:{added.lineno}: error: moved lines {edge} inside a function or statement "
        f"(base {source.path}:{source.lineno}, within {where}): {added.text.strip()}"
    )


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
            report.notes.append(
                f"{path}: note: file has {total} lines (over --max-lines {max_lines})"
            )


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
    report.notes.sort(key=_sort_key)
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
        help=f"report C/C++ files under PATH over N lines as notes (default {DEFAULT_MAX_LINES})",
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
    for message in report.notes:
        print(message)
    for message in report.errors:
        print(message)
    print(
        f"split_check: {len(report.errors)} error(s), {len(report.warnings)} warning(s), "
        f"{len(report.notes)} note(s)"
    )
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
