#!/usr/bin/env python3
"""Proves that a file split moved code and changed none.

    split_check.py [--base REF] [--max-lines N] [--members] PATH...

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

With --members it first proves member function definitions moved out of a class body (each body
unchanged but for one indentation change, its declaration left in the class without its noinline
attribute, the head changed only as docs/SPLITTING.md lists) and runs the checks above on the
rest of the diff.
"""

from __future__ import annotations

import argparse
import bisect
import difflib
import os
import re
import subprocess
import sys
from collections import defaultdict, deque
from collections.abc import Callable
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
NOINLINE_ATTRIBUTE = (
    r"\[\[\s*(?:gnu|clang|msvc)\s*::\s*(?:__)?noinline(?:__)?\s*\]\]"
    r"|__attribute__\s*\(\(\s*(?:__)?noinline(?:__)?\s*\)\)|__declspec\s*\(\s*noinline\s*\)"
)
OBJECT_DEFINE = re.compile(r"^[ \t]*#[ \t]*define[ \t]+(\w+)(?![\w(])(.*)$", re.M)
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
            if c == "'" and not _digit_separator(raw, i):
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
    moved: dict[str, int] = field(default_factory=dict)  # --members: class -> definitions


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


def check_moves(
    repo: Path, base: str, paths: list[str], report: Report, members: bool = False
) -> None:
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
    if members:
        gone, came = check_members(repo, base, removed, added, report)
        removed = [e for e in removed if (e.path, e.lineno) not in gone]
        added = [e for e in added if (e.path, e.lineno) not in came]
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
    _anchor_runs(added, pool, by_position, old, new_info)
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
        if a.source is not None:
            prev = a
            _note_move(report, a, a.source)
            continue
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


def _anchor_runs(
    added: list[Entry],
    pool: dict[str, deque[Entry]],
    by_position: dict[tuple[str, int], Entry],
    old: Base,
    new_info: Callable[[Entry], Line],
) -> None:
    """Matches the runs around anchors before the line-by-line pass guesses.

    An anchor is a line whose text is removed once and added once. From each anchor the run
    extends over the neighboring non-blank lines while the added and the removed line read the
    same, so a common line (`}`, `inline bool`, a license's `/*`) takes the source of the run it
    sits in instead of the first equal line the pass meets.
    """
    lines = [a for a in added if a.norm]
    counts: dict[str, int] = defaultdict(int)
    for a in lines:
        counts[a.norm] += 1
    index = {id(a): k for k, a in enumerate(lines)}

    def removed_prev(r: Entry) -> Entry | None:
        old.load(r.path)
        texts = old.texts[r.path]
        for k in range(r.lineno - 2, -1, -1):
            if texts[k].strip():
                return by_position.get((r.path, k + 1))
        return None

    def removed_next(r: Entry) -> Entry | None:
        return by_position.get((r.path, old.next_nonblank(r.path, r.lineno)))

    def pin(a: Entry, r: Entry) -> None:
        a.info = new_info(a)
        a.source = r
        r.used = True

    def extend(k: int, r: Entry, step: int) -> None:
        a = lines[k]
        while True:
            k += step
            if not 0 <= k < len(lines):
                return
            nxt = lines[k]
            if nxt.path != a.path or nxt.hunk != a.hunk or nxt.source is not None:
                return
            near = removed_prev(r) if step < 0 else removed_next(r)
            if near is None or near.used or near.norm != nxt.norm:
                return
            pin(nxt, near)
            r = near

    for a in lines:
        queue = pool.get(a.norm)
        if a.source is not None or counts[a.norm] != 1 or not queue or len(queue) != 1:
            continue
        r = queue[0]
        if r.used:
            continue
        pin(a, r)
        extend(index[id(a)], r, -1)
        extend(index[id(a)], r, 1)


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


# --- --members: member function definitions moved out of a class body -------------------------

TOKEN = re.compile(
    r"\s+|(?P<t>[A-Za-z_]\w*|\.?\d(?:[\w.']|[eEpP][+-])*|\"[^\"\n]*\"|'[^'\n]*'"
    r"|::|->|\.\.\.|&&|\|\||==|!=|\+\+|--|\S)"
)
IDENT = re.compile(r"[A-Za-z_]\w*$")
LABEL = re.compile(r"([A-Za-z_]\w*)\s*:(?!:)")
ACCESS = frozenset({"public", "private", "protected"})
# Specifiers only the declaration in the class keeps; `inline` is optional on the definition.
CLASS_ONLY = frozenset({"static", "virtual", "explicit", "inline", "friend"})
VIRT_SPECIFIERS = frozenset({"override", "final"})
# Words followed by `(` that do not name a function.
NOT_A_NAME = frozenset(
    {
        "decltype",
        "noexcept",
        "alignas",
        "alignof",
        "sizeof",
        "__attribute__",
        "__declspec",
        "requires",
        "throw",
        "typeof",
        "__typeof__",
        "static_assert",
        "template",
        "operator",
        "return",
    }
)
HEADER_SUFFIXES = frozenset({".h", ".hh", ".hpp", ".hxx", ".ipp", ".inl", ".tpp"})
OPERATOR_TOKEN = re.compile(r"\boperator\s*(?:\(\s*\)|\[\s*\]|[^\s\w(]+)")
EXTERN_C = re.compile(r'extern\s*"[^"]*"\s*$')
TEMPLATE_OPEN = re.compile(r"\s*template\s*<")
MEM_INIT_NAME = re.compile(r"\s*(?:::)?[A-Za-z_]\w*(?:\s*::\s*(?:template\s+)?[A-Za-z_]\w*)*\s*")
MORE_NAME = re.compile(r"(?:\s*::\s*[A-Za-z_]\w*)*\s*")
PACK = re.compile(r"\s*(?:\.\.\.)?\s*")


class Source:
    """A file's text, its code (comments, literals and preprocessor lines blanked) and lines."""

    def __init__(self, text: str) -> None:
        self.text = text.replace("\r", "")
        self.starts = [0]
        self.starts.extend(i + 1 for i, c in enumerate(self.text) if c == "\n")
        self.code, self.raw, self.pp = _mask(self.text)

    def line(self, offset: int) -> int:
        """The 1-based line holding `offset`."""
        return bisect.bisect_right(self.starts, offset)

    def text_of(self, lineno: int) -> str:
        end = self.starts[lineno] - 1 if lineno < len(self.starts) else len(self.text)
        return self.text[self.starts[lineno - 1] : end]

    def code_of(self, lineno: int) -> str:
        end = self.starts[lineno] - 1 if lineno < len(self.starts) else len(self.code)
        return self.code[self.starts[lineno - 1] : end]


def _mask(text: str) -> tuple[str, set[int], set[int]]:
    """Blanks comments, literal contents and preprocessor lines, keeping offsets and newlines.

    Also returns the lines that begin inside a raw string literal and the preprocessor lines.
    """
    out = list(text)
    raw: set[int] = set()
    pp: set[int] = set()
    n = len(text)
    lineno = 1
    bol = True
    i = 0

    def blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = text[i]
        if c == "\n":
            lineno += 1
            bol = True
            i += 1
            continue
        if c in " \t\f\v":
            i += 1
            continue
        if bol and c == "#":
            seg = i
            while True:
                pp.add(lineno)
                e = text.find("\n", seg)
                e = n if e < 0 else e
                blank(seg, e)
                if e < n and text[seg:e].rstrip().endswith("\\"):
                    lineno += 1
                    seg = e + 1
                    continue
                break
            i = e
            continue
        bol = False
        if text.startswith("//", i):
            e = text.find("\n", i)
            e = n if e < 0 else e
            blank(i, e)
            i = e
        elif text.startswith("/*", i):
            e = text.find("*/", i + 2)
            e = n if e < 0 else e + 2
            lineno += text.count("\n", i, e)
            blank(i, e)
            i = e
        elif c == '"' and i > 0 and text[i - 1] == "R" and (m := RAW_OPEN.match(text, i)):
            close = ")" + m.group(1) + '"'
            e = text.find(close, m.end())
            e = n - 1 if e < 0 else e + len(close) - 1
            for k in range(i + 1, e):
                if text[k] == "\n":
                    lineno += 1
                    raw.add(lineno)
            blank(i + 1, e)
            i = e + 1
        elif c in "\"'":
            if c == "'" and _digit_separator(text, i):
                i += 1
                continue
            j = i + 1
            while j < n and text[j] not in (c, "\n"):
                j += 2 if text[j] == "\\" else 1
            blank(i + 1, min(j, n))
            i = j + 1
        else:
            i += 1
    return "".join(out), raw, pp


def _digit_separator(text: str, i: int) -> bool:
    k = i - 1
    while k >= 0 and (text[k].isalnum() or text[k] in "_'."):
        k -= 1
    return k + 1 < i and text[k + 1].isdigit()


@dataclass(eq=False)
class Item:
    """One declaration of a scope, found in masked code."""

    kind: str  # func, decl, class, namespace, label, other
    start: int
    end: int
    body: int = -1  # the opening brace of a function body, class or namespace
    close: int = -1  # its closing brace
    init: int = -1  # a constructor's initializer `:`
    children: list[Item] = field(default_factory=list)


def _items(code: str, lo: int, hi: int, in_class: bool) -> list[Item]:
    items: list[Item] = []
    i = lo
    while i < hi:
        if code[i].isspace() or code[i] == ";":
            i += 1
            continue
        m = LABEL.match(code, i, hi)
        if in_class and m and (m.group(1) in ACCESS or m.group(1).isupper()):
            items.append(Item("label", i, m.end()))
            i = m.end()
            continue
        item = _item(code, i, hi)
        if item.kind in ("class", "namespace"):
            item.children = _items(code, item.body + 1, item.close, item.kind == "class")
        items.append(item)
        i = max(item.end, i + 1)
    return items


def _item(code: str, start: int, hi: int) -> Item:
    depth = 0
    called = False  # a parenthesis closed at depth 0
    j = start
    while j < hi:
        c = code[j]
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
            called = called or (depth == 0 and c == ")")
        elif depth == 0:
            if c == ";":
                return Item("decl", start, j + 1)
            if c == "{":
                kind = _head_kind(code[start:j])
                close = _match(code, j, hi)
                if kind in ("enum", "init"):
                    j = close + 1
                    continue
                if kind == "class":
                    return Item("class", start, _after_declarators(code, close + 1, hi), j, close)
                return Item(kind, start, close + 1, j, close)
            if (
                c == ":"
                and called
                and code[j + 1 : j + 2] != ":"
                and code[j - 1] != ":"
                and _head_kind(code[start:j]) == "func"
            ):
                body = _skip_initializers(code, j + 1, hi)
                if body >= 0:
                    close = _match(code, body, hi)
                    return Item("func", start, close + 1, body, close, j)
        j += 1
    return Item("other", start, hi)


def _match(code: str, i: int, hi: int) -> int:
    """The offset of the bracket closing the one at `i` (masked code), or hi - 1."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    open_, close = code[i], pairs[code[i]]
    depth = 0
    for j in range(i, hi):
        if code[j] == open_:
            depth += 1
        elif code[j] == close:
            depth -= 1
            if depth == 0:
                return j
    return hi - 1


def _match_angle(text: str, i: int) -> int:
    """The offset of the `>` closing the `<` at `i`, ignoring brackets inside parentheses."""
    depth = paren = 0
    for j in range(i, len(text)):
        c = text[j]
        if c in "([{":
            paren += 1
        elif c in ")]}":
            paren -= 1
        elif paren == 0 and c == "<":
            depth += 1
        elif paren == 0 and c == ">":
            depth -= 1
            if depth == 0:
                return j
    return len(text) - 1


def _skip_templates(text: str, i: int) -> int:
    while (m := TEMPLATE_OPEN.match(text, i)) is not None:
        i = _match_angle(text, m.end() - 1) + 1
    return i


def _after_declarators(code: str, k: int, hi: int) -> int:
    """The offset after the `;` that ends a class definition's declarators."""
    j = k
    while j < hi:
        c = code[j]
        if c in "([{":
            j = _match(code, j, hi)
        elif c == ";":
            return j + 1
        elif not c.isspace() and not (c.isalnum() or c in "_*&,=:<>."):
            return k
        j += 1
    return k


def _head_kind(head: str) -> str:
    """What a declaration whose head is followed by `{` opens."""
    h = head[_skip_templates(head, 0) :].strip()
    while h.startswith("[["):
        h = h[h.find("]]") + 2 :].lstrip()
    if NS_BEFORE_BRACE.search(h) or EXTERN_C.match(h):
        return "namespace"
    if re.match(r"(?:class|struct|union)\b", h):
        paren = h.find("(")
        if paren < 0 or re.search(
            r"(?:\balignas|__attribute__|__declspec|\b[A-Z][A-Z0-9_]*)\s*$", h[:paren]
        ):
            return "class"
    if re.match(r"enum\b", h):
        return "enum"
    return "func" if _is_function_head(h) else "init"


def _is_function_head(head: str) -> bool:
    """Whether a head has a parameter list outside template arguments and no initializer `=`."""
    h = OPERATOR_TOKEN.sub("operator@", head)
    depth = angle = 0
    called = False
    for k, c in enumerate(h):
        if c in "([{":
            called = called or (c == "(" and depth == 0 and angle == 0)
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif depth == 0 and c == "<" and re.search(r"[\w>]\s*$", h[:k]):
            angle += 1
        elif depth == 0 and c == ">" and angle:
            angle -= 1
        elif c == "=" and depth == 0 and angle == 0:
            if (k and h[k - 1] in "=!<>") or h[k + 1 : k + 2] == "=":
                continue
            return False
    return called


def _skip_initializers(code: str, k: int, hi: int) -> int:
    """The offset of the body's `{` after a constructor's member initializers, or -1."""
    while True:
        m = MEM_INIT_NAME.match(code, k, hi)
        if not m:
            return -1
        k = m.end()
        if code[k : k + 1] == "<":
            k = _match_angle(code, k) + 1
            k = _end(MORE_NAME, code, k)
        if k >= hi or code[k] not in "({":
            return -1
        k = _match(code, k, hi) + 1
        k = _end(PACK, code, k)
        if code[k : k + 1] == ",":
            k += 1
            continue
        return k if code[k : k + 1] == "{" else -1


def _end(pattern: re.Pattern[str], text: str, k: int) -> int:
    """The end of `pattern`'s match at `k` (the pattern matches the empty string)."""
    m = pattern.match(text, k)
    return m.end() if m else k


def _tokens(src: Source, lo: int, hi: int) -> list[str]:
    out: list[str] = []
    for m in TOKEN.finditer(src.code, lo, hi):
        if m.group("t") is not None:
            s, e = m.span("t")
            out.append(src.text[s:e] if src.code[s] in "\"'" else src.code[s:e])
    return out


def _is_ident(tok: str) -> bool:
    return bool(IDENT.match(tok))


def _close_tok(toks: list[str], i: int, hi: int) -> int:
    """The index of the token closing the bracket at `i` (angles count only outside parens)."""
    pairs = {"(": ")", "[": "]", "{": "}", "<": ">"}
    stack: list[str] = []
    for k in range(i, hi):
        t = toks[k]
        if t in "([{" or (t == "<" and (not stack or stack[-1] == "<")):
            stack.append(t)
        elif stack and t == pairs[stack[-1]]:
            stack.pop()
            if not stack:
                return k
        elif t in ")]}" and stack and stack[-1] == "<":
            return k  # an unbalanced `<` was a comparison
    return hi - 1


def _open_angle(toks: list[str], lo: int, i: int) -> int:
    """The index of the `<` that the `>` at `i` closes, or lo."""
    depth = paren = 0
    for k in range(i, lo - 1, -1):
        t = toks[k]
        if t in ")]}":
            paren += 1
        elif t in "([{":
            paren -= 1
        elif paren == 0 and t == ">":
            depth += 1
        elif paren == 0 and t == "<":
            depth -= 1
            if depth == 0:
                return k
    return lo


def _split_top(toks: list[str]) -> list[list[str]]:
    """Splits a token list at commas outside brackets."""
    parts: list[list[str]] = [[]]
    stack: list[str] = []
    for k, t in enumerate(toks):
        if t in "([{" or (t == "<" and k and (_is_ident(toks[k - 1]) or toks[k - 1] == ">")):
            stack.append(t)
        elif t in ")]}>" and stack:
            stack.pop()
        elif t == "," and not stack:
            parts.append([])
            continue
        parts[-1].append(t)
    return [] if parts == [[]] else parts


def _strip_default(param: list[str]) -> list[str]:
    depth = 0
    for k, t in enumerate(param):
        if t in "([{" or (t == "<" and k and _is_ident(param[k - 1])):
            depth += 1
        elif t in ")]}>" and depth:
            depth -= 1
        elif t == "=" and depth == 0:
            return param[:k]
    return param


@dataclass
class Sig:
    """A function head in tokens: `headers prefix qual name(params) tail init`."""

    headers: list[list[str]]  # each template header's parameter list
    prefix: list[str]  # specifiers and the leading return type
    qual: list[str]  # the class qualifier before the name
    name: str
    params: list[list[str]]
    tail: list[str]  # qualifiers, noexcept, trailing return, requires
    init: list[str]  # a constructor's member initializers


def _signature(src: Source, item: Item) -> Sig | None:
    stop = item.init if item.init >= 0 else item.body
    toks = _tokens(src, item.start, stop)
    init = _tokens(src, item.init + 1, item.body) if item.init >= 0 else []
    k = 0
    headers: list[list[str]] = []
    while k + 1 < len(toks) and toks[k] == "template" and toks[k + 1] == "<":
        e = _close_tok(toks, k + 1, len(toks))
        headers.append(toks[k + 2 : e])
        k = e + 1
    found = _declarator(toks, k, len(toks))
    if found is None:
        return None
    q, n, p, c = found
    return Sig(
        headers,
        toks[k:q],
        toks[q:n],
        _name(toks[n:p]),
        _split_top(toks[p + 1 : c]),
        toks[c + 1 :],
        init,
    )


def _name(toks: list[str]) -> str:
    """A declarator name as written without spaces around punctuation: `~C`, `operator()`."""
    return re.sub(r"(?<=\W) | (?=\W)", "", " ".join(toks))


def _declarator(toks: list[str], lo: int, hi: int) -> tuple[int, int, int, int] | None:
    """(qualifier start, name start, parameters `(`, parameters `)`) of a function head."""
    stack: list[str] = []
    found: list[tuple[int, int]] = []
    k = lo
    while k < hi:
        t = toks[k]
        if not stack and t == "operator":
            j = k + 1
            if toks[j : j + 2] in (["(", ")"], ["[", "]"]):
                j += 2
            while j < hi and toks[j] != "(":
                j += 1
            if j >= hi:
                return None
            return (_qualifier_start(toks, lo, k), k, j, _close_tok(toks, j, hi))
        if t == "(" and not stack:
            prev = toks[k - 1] if k > lo else ""
            if prev not in NOT_A_NAME and k + 1 < hi and toks[k + 1] in ("*", "&", "&&", "^"):
                inner = _declarator(toks, k + 2, _close_tok(toks, k, hi))
                if inner is not None:
                    return inner
            elif k > lo and _is_ident(toks[k - 1]) and toks[k - 1] not in NOT_A_NAME:
                n = k - 1 if k - 1 == lo or toks[k - 2] != "~" else k - 2
                found.append((n, k))
        if t in "([{":
            stack.append(t)
        elif t in ")]}":
            if stack:
                stack.pop()
        elif t == "<" and k > lo and _is_ident(toks[k - 1]) and (not stack or stack[-1] == "<"):
            stack.append(t)
        elif t == ">" and stack and stack[-1] == "<":
            stack.pop()
        k += 1
    if not found:
        return None
    n, p = next((f for f in found if not toks[f[1] - 1].isupper()), found[0])
    return (_qualifier_start(toks, lo, n), n, p, _close_tok(toks, p, hi))


def _qualifier_start(toks: list[str], lo: int, n: int) -> int:
    q = n
    while q - 2 >= lo and toks[q - 1] == "::":
        p = q - 2
        if toks[p] == ">":
            p = _open_angle(toks, lo, p) - 1
        if p >= lo and _is_ident(toks[p]):
            q = p
        else:
            break
    if q - 1 >= lo and toks[q - 1] == "::":
        q -= 1
    return q


def _components(qual: list[str]) -> list[tuple[str, list[str] | None]]:
    """`a::b<T>::` as [("a", None), ("b", ["T"])]."""
    out: list[tuple[str, list[str] | None]] = []
    k = 1 if qual[:1] == ["::"] else 0
    while k < len(qual):
        name = qual[k]
        k += 1
        args: list[str] | None = None
        if k < len(qual) and qual[k] == "<":
            e = _close_tok(qual, k, len(qual))
            args = qual[k + 1 : e]
            k = e + 1
        out.append((name, args))
        k += 1  # the `::`
    return out


def _param_names(header: list[str]) -> list[str] | None:
    """The argument list naming a template header's parameters (`T, Ts...`), or None."""
    out: list[str] = []
    for param in _split_top(header):
        decl = _strip_default(param)
        names = [t for t in decl if _is_ident(t)]
        if len(names) < 2 and not (names and decl[0] not in ("class", "typename")):
            return None
        if out:
            out.append(",")
        out.append(names[-1])
        if "..." in decl:
            out.append("...")
    return out


@dataclass(eq=False)
class Cls:
    """A class definition: its scope, its own template header and its members."""

    path: str
    src: Source
    key: tuple[str, ...]  # namespaces and class names
    names: tuple[str, ...]  # class names, outermost first
    item: Item
    header: list[str] | None  # the class's template parameter list
    outer: Cls | None
    members: list[Member] = field(default_factory=list)
    inner: list[Cls] = field(default_factory=list)
    decls: set[str] = field(default_factory=set)  # normalized member declarations
    types: set[str] = field(default_factory=set)  # member types and static data

    def chain(self) -> list[Cls]:
        out: list[Cls] = []
        c: Cls | None = self
        while c is not None:
            out.append(c)
            c = c.outer
        return out[::-1]

    def root(self) -> Cls:
        return self.chain()[0]

    def qualifier(self) -> list[str] | None:
        """`a<T>::b::` for this class, or None when a template parameter has no name."""
        out: list[str] = []
        for c in self.chain():
            out.append(c.names[-1])
            if c.header is not None:
                args = _param_names(c.header)
                if args is None:
                    return None
                out += ["<", *args, ">"]
            out.append("::")
        return out

    def scope_types(self) -> set[str]:
        return set().union(*(c.types for c in self.chain()))

    def all_members(self) -> list[Member]:
        out = list(self.members)
        for c in self.inner:
            out += c.all_members()
        return out


@dataclass(eq=False)
class Member:
    """A function defined in a class body at the base, or out of the class at HEAD."""

    path: str
    src: Source
    item: Item
    sig: Sig
    cls: Cls | None
    ns: tuple[str, ...] = ()
    line: int = 0

    def label(self) -> str:
        assert self.cls is not None
        return "::".join((*self.cls.names, self.sig.name))


@dataclass
class Parsed:
    path: str
    src: Source
    classes: list[Cls] = field(default_factory=list)
    defs: list[Member] = field(default_factory=list)  # out-of-class definitions


def _parse(path: str, src: Source) -> Parsed:
    out = Parsed(path, src)
    _walk(path, src, _items(src.code, 0, len(src.code), False), (), None, out=out)
    return out


def _class_head(src: Source, item: Item) -> tuple[list[str] | None, str]:
    toks = _tokens(src, item.start, item.body)
    header: list[str] | None = None
    k = 0
    while k + 1 < len(toks) and toks[k] == "template" and toks[k + 1] == "<":
        e = _close_tok(toks, k + 1, len(toks))
        header = toks[k + 2 : e]
        k = e + 1
    body = toks[k:]
    depth = 0
    for j, t in enumerate(body):
        if t in "(<[":
            depth += 1
        elif t in ")>]":
            depth -= 1
        elif t == ":" and depth == 0:
            body = body[:j]
            break
    while body and body[-1] == "final":
        body.pop()
    if body and body[-1] == ">":
        body = body[: _open_angle(body, 0, len(body) - 1)]
    name = body[-1] if len(body) > 1 and _is_ident(body[-1]) else ""
    return header, name


def _walk(
    path: str,
    src: Source,
    items: list[Item],
    ns: tuple[str, ...],
    cls: Cls | None,
    *,
    out: Parsed,
) -> None:
    for item in items:
        if item.kind == "namespace":
            toks = _tokens(src, item.start, item.body)
            name = "".join(
                t for t in toks if t not in ("inline", "namespace", "extern") and t[0] != '"'
            )
            _walk(path, src, item.children, (*ns, name) if name else ns, None, out=out)
        elif item.kind == "class":
            header, name = _class_head(src, item)
            names = (*cls.names, name) if cls else (name,)
            inner = Cls(path, src, (*ns, *names), names, item, header, cls)
            if cls is not None:
                cls.inner.append(inner)
                if name:
                    cls.types.add(name)
            out.classes.append(inner)
            _walk(path, src, item.children, ns, inner, out=out)
        elif item.kind == "func":
            sig = _signature(src, item)
            if sig is None:
                continue
            if cls is not None and "friend" not in sig.prefix:
                cls.members.append(Member(path, src, item, sig, cls, ns, src.line(item.start)))
            elif cls is None and sig.qual:
                out.defs.append(Member(path, src, item, sig, None, ns, src.line(item.start)))
        elif item.kind == "decl" and cls is not None:
            cls.decls.add(normalize(src.text[item.start : item.end]))
            toks = _tokens(src, item.start, item.end)
            cls.types.update(_declared_types(toks))


def _declared_types(toks: list[str]) -> set[str]:
    """Names of types and static data a member declaration declares."""
    if not toks:
        return set()
    k = 0
    while k + 1 < len(toks) and toks[k] == "template" and toks[k + 1] == "<":
        k = _close_tok(toks, k + 1, len(toks)) + 1
    head = toks[k:]
    if head[:1] == ["using"] and len(head) > 2 and head[2] == "=":
        return {head[1]}
    if head[:1] in (["enum"], ["class"], ["struct"], ["union"]):
        names = [t for t in head[1:4] if _is_ident(t) and t not in ("class", "struct")]
        return set(names[:1])
    if head[:1] == ["typedef"] or (head[:1] == ["static"] and "(" not in head):
        stop = next((j for j, t in enumerate(head) if t in ("=", "{", ";", "[")), len(head))
        names = [t for t in head[:stop] if _is_ident(t)]
        return set(names[-1:])
    return set()


def _decl_text(m: Member) -> tuple[str, str]:
    """The declaration a moved definition leaves in the class: its head and a `;`, and the
    comment after it."""
    stop = m.item.init if m.item.init >= 0 else m.item.body
    code = m.src.code
    k = stop - 1
    while k > m.item.start and code[k].isspace():
        k -= 1
    return m.src.text[m.item.start : k + 1] + ";", m.src.text[k + 1 : stop].rstrip()


def _unqualify(toks: list[str], cls: Cls) -> list[str]:
    """Drops qualifiers naming the class or its enclosing classes, and `C<T>` becomes `C`."""
    chain = cls.chain()
    pieces: list[list[str]] = []
    for c in chain:
        piece = [c.names[-1]]
        if c.header is not None:
            args = _param_names(c.header)
            if args is not None:
                piece += ["<", *args, ">"]
        pieces.append(piece)
    out: list[str] = []
    k = 0
    while k < len(toks):
        if k == 0 or toks[k - 1] != "::":
            j = k
            for piece in pieces:
                if toks[j : j + len(piece)] == piece and toks[
                    j + len(piece) : j + len(piece) + 1
                ] == ["::"]:
                    j += len(piece) + 1
                else:
                    break
            if j > k:
                if out and out[-1] == "typename":
                    out.pop()
                k = j
                continue
            hit = next((p for p in pieces if len(p) > 1 and toks[k : k + len(p)] == p), None)
            if hit is not None:
                out.append(hit[0])
                k += len(hit)
                continue
        out.append(toks[k])
        k += 1
    return out


def _split_trailing(tail: list[str]) -> tuple[list[str], list[str]] | None:
    """(tail without its trailing return type, the return type), or None without one."""
    depth = 0
    for k, t in enumerate(tail):
        if t in "([{":
            depth += 1
        elif t in ")]}":
            depth -= 1
        elif t == "->" and depth == 0:
            end = next((j for j in range(k + 1, len(tail)) if tail[j] == "requires"), len(tail))
            return tail[:k] + tail[end:], tail[k + 1 : end]
    return None


def _base_form(m: Member) -> tuple[object, ...]:
    """The out-of-class definition a base member's head becomes, in canonical tokens."""
    assert m.cls is not None
    headers = [_strip_header(c.header) for c in m.cls.chain() if c.header is not None] + [
        _strip_header(h) for h in m.sig.headers
    ]
    prefix = _unqualify([t for t in m.sig.prefix if t not in CLASS_ONLY], m.cls)
    tail = [t for t in m.sig.tail if t not in VIRT_SPECIFIERS]
    params = [_strip_default(p) for p in m.sig.params]
    return _form(headers, prefix, m.sig.name, params=params, tail=tail, init=m.sig.init)


def _strip_header(header: list[str]) -> list[str]:
    out: list[str] = []
    for param in _split_top(header):
        if out:
            out.append(",")
        out += _strip_default(param)
    return out


def _form(
    headers: list[list[str]],
    prefix: list[str],
    name: str,
    *,
    params: list[list[str]],
    tail: list[str],
    init: list[str],
) -> tuple[object, ...]:
    return (
        tuple(" ".join(h) for h in headers),
        " ".join(prefix),
        name,
        tuple(" ".join(p) for p in params),
        " ".join(tail),
        " ".join(init),
    )


def _show(form: tuple[object, ...]) -> str:
    headers, prefix, name, params, tail, init = form
    assert isinstance(headers, tuple) and isinstance(params, tuple)
    text = "".join(f"template <{h}> " for h in headers)
    text += f"{prefix} {name}({', '.join(str(p) for p in params)}) {tail}"
    return normalize(text + (f" : {init}" if init else ""))


def _owner(d: Member, classes: dict[tuple[str, ...], Cls]) -> Cls | None:
    names = tuple(n for n, _ in _components(d.sig.qual))
    for k in range(len(d.ns), -1, -1):
        c = classes.get((*d.ns[:k], *names))
        if c is not None:
            return c
    return None


def _body_lines(m: Member) -> list[tuple[int, str]]:
    """The body from its `{` to its `}`, as (line number, text) pairs."""
    text = m.src.text[m.item.body : m.item.close + 1]
    first = m.src.line(m.item.body)
    return [(first + k, t.rstrip()) for k, t in enumerate(text.split("\n"))]


def _compare_bodies(b: Member, h: Member) -> tuple[int, str, int, str] | None:
    """The first line pair that differs beyond one uniform change of leading indentation."""
    bl, hl = _body_lines(b), _body_lines(h)
    delta: tuple[str, str] | None = None
    for k in range(max(len(bl), len(hl))):
        if k >= len(bl) or k >= len(hl):
            at = min(k, len(hl) - 1)
            bk = min(k, len(bl) - 1)
            return hl[at][0], hl[at][1], bl[bk][0], bl[bk][1]
        (bn, bt), (hn, ht) = bl[k], hl[k]
        if k == 0 or bn in b.src.raw or bt.startswith("#"):
            same = bt == ht
        elif not bt.strip() and not ht.strip():
            continue
        else:
            bi = bt[: len(bt) - len(bt.lstrip())]
            hi = ht[: len(ht) - len(ht.lstrip())]
            if bt[len(bi) :] != ht[len(hi) :]:
                same = False
            else:
                d = ("-", bi[: len(bi) - len(hi)]) if bi.endswith(hi) else None
                if d is None and hi.endswith(bi):
                    d = ("+", hi[: len(hi) - len(bi)])
                if delta is None:
                    delta = d
                same = d is not None and d == delta
        if not same:
            return hn, ht, bn, bt
    return None


def check_members(
    repo: Path, base: str, removed: list[Entry], added: list[Entry], report: Report
) -> tuple[set[tuple[str, int]], set[tuple[str, int]]]:
    """Proves the member function definitions that left a class body.

    Returns the base lines and the HEAD lines it accounts for: each restructured class whole,
    and each moved definition with the preprocessor lines that moved beside it.
    """
    gone: set[tuple[str, int]] = set()
    came: set[tuple[str, int]] = set()
    added_at = {(e.path, e.lineno) for e in added}
    old_src = {p: Source(read_blob(repo, base, p)) for p in sorted({e.path for e in removed})}
    new_src = {p: Source(read_blob(repo, "HEAD", p)) for p in sorted({e.path for e in added})}
    old = [_parse(p, src) for p, src in old_src.items()]
    new = [_parse(p, src) for p, src in new_src.items()]
    noinline = _noinline_pattern([*old_src.values(), *new_src.values()])
    base_classes = {c.key: c for p in old for c in p.classes}
    head_classes: dict[tuple[str, ...], list[Cls]] = defaultdict(list)
    for p in new:
        for c in p.classes:
            head_classes[c.key].append(c)

    # Out-of-class definitions new at HEAD, by owner and canonical head.
    pending: dict[tuple[object, ...], list[Member]] = defaultdict(list)
    by_name: dict[tuple[tuple[str, ...], str], list[Member]] = defaultdict(list)
    for p in new:
        for d in p.defs:
            owner = _owner(d, base_classes)
            if owner is None or (d.path, d.src.line(d.item.body)) not in added_at:
                continue
            d.cls = owner
            by_name[owner.key, d.sig.name].append(d)
            for form in _head_forms(d, owner):
                pending[(owner.key, form)].append(d)

    members = [m for c in base_classes.values() for m in c.members]
    moved: dict[int, Member] = {}  # id(base member) -> its definition at HEAD
    used: set[int] = set()
    roots: dict[int, Cls] = {}
    for m in members:
        assert m.cls is not None
        d = next(
            (d for d in pending.get((m.cls.key, _base_form(m)), []) if id(d) not in used), None
        )
        if d is not None:
            moved[id(m)] = d
            used.add(id(d))
            roots[id(m.cls.root())] = m.cls.root()
    for m in members:
        assert m.cls is not None
        if id(m) in moved:
            continue
        decl = _decl_text(m)[0]
        forms = {normalize(decl), normalize(re.sub(noinline, " ", decl))}
        if not any(forms & h.decls for h in head_classes.get(m.cls.key, [])):
            continue  # still defined in the class, or the class check reports it
        roots[id(m.cls.root())] = m.cls.root()
        where = f"{m.path}:{m.line}"
        rival = next(
            (d for d in by_name.get((m.cls.key, m.sig.name), []) if id(d) not in used), None
        )
        if rival is None:
            report.errors.append(
                f"{where}: error: member {m.label()}: its body left the class but no "
                f"out-of-class definition matches it (line number in the base): "
                f"{m.src.text_of(m.line).strip()}"
            )
            continue
        used.add(id(rival))
        moved[id(m)] = rival
        report.errors.append(
            f"{rival.path}:{rival.line}: error: member {m.label()} (base {where}): the "
            f"definition's head is not the declaration's: {_show(_head_forms(rival, m.cls)[0])} "
            f"(expected {_show(_base_form(m))})"
        )
    for m in members:
        d = moved.get(id(m))
        if d is not None:
            assert m.cls is not None
            root = "::".join(m.cls.root().key)
            report.moved[root] = report.moved.get(root, 0) + 1
            _check_definition(m, d, report)
            came.update((d.path, n) for n in range(d.line, d.src.line(d.item.close) + 1))
    for root in roots.values():
        leaving = _check_class(
            root, moved, head_classes, noinline, report=report, gone=gone, came=came
        )
        _check_moved_preprocessor(root, leaving, moved, new, report=report, came=came)
    return gone, came


def _head_forms(d: Member, cls: Cls) -> list[tuple[object, ...]]:
    """The canonical heads a definition at HEAD reads as: as written, and with a trailing
    return type moved to the front."""
    prefix = [t for t in d.sig.prefix if t != "inline"]
    sig = d.sig
    forms = [
        _form(
            sig.headers,
            _unqualify(prefix, cls),
            sig.name,
            params=sig.params,
            tail=sig.tail,
            init=sig.init,
        )
    ]
    trailing = _split_trailing(sig.tail)
    if trailing is not None and prefix[-1:] == ["auto"]:
        tail, ret = trailing
        lead = _unqualify(prefix[:-1] + ret, cls)
        forms.append(
            _form(sig.headers, lead, sig.name, params=sig.params, tail=tail, init=sig.init)
        )
    return forms


def _check_definition(m: Member, d: Member, report: Report) -> None:
    assert m.cls is not None
    where = f"{m.path}:{m.line}"
    label = m.label()
    expected = m.cls.qualifier()
    if expected is not None and d.sig.qual[-len(expected) :] != expected:
        report.errors.append(
            f"{d.path}:{d.line}: error: member {label} (base {where}): the qualifier is "
            f"{''.join(d.sig.qual)} (expected {''.join(expected)})"
        )
    diff = _compare_bodies(m, d)
    if diff is not None:
        hn, ht, bn, bt = diff
        report.errors.append(
            f"{d.path}:{hn}: error: member {label} (base {where}): the body changed: "
            f"{ht.strip()} (base {m.path}:{bn}: {bt.strip()})"
        )
    header = Path(d.path).suffix in HEADER_SUFFIXES
    templated = bool(d.sig.headers)
    if header and not templated and not set(d.sig.prefix) & {"inline", "constexpr", "consteval"}:
        report.errors.append(
            f"{d.path}:{d.line}: error: member {label} (base {where}): a non-template "
            f"definition out of the class in a header needs 'inline' (one definition rule)"
        )
    if not header:
        report.warnings.append(
            f"{d.path}:{d.line}: warning: member {label} (base {where}) moved to a source "
            f"file (linkage change: no longer inline)"
        )
    types = m.cls.scope_types()
    templates = {c.names[-1] for c in m.cls.chain() if c.header is not None}
    prefix = d.sig.prefix
    for k, t in enumerate(prefix):
        if k and prefix[k - 1] in ("::", ".", "->"):
            continue
        if t in types or (t in templates and prefix[k + 1 : k + 2] != ["<"]):
            report.errors.append(
                f"{d.path}:{d.line}: error: member {label} (base {where}): the return type "
                f"names the class's '{t}' unqualified, which out of the class resolves at "
                f"namespace scope; qualify it or use a trailing return type"
            )
            break


@dataclass
class ClassLine:
    """A non-blank line the class at HEAD must hold."""

    text: str  # normalized
    line: int  # in the base
    member: Member | None  # the member the line belongs to
    decl: bool  # the declaration a moved definition left


def _line_range(src: Source, item: Item) -> range:
    return range(src.line(item.start), src.line(item.end - 1) + 1)


def _noinline_pattern(sources: list[Source]) -> str:
    """A noinline attribute, or an object-like macro defined in `sources` whose every non-empty
    definition is one."""
    verdict: dict[str, bool] = {}
    for src in sources:
        for d in OBJECT_DEFINE.finditer(src.text):
            body = re.sub(r"\s*(?://.*|/\*.*?\*/\s*)$", "", d.group(2)).strip()
            if body:
                ok = re.fullmatch(NOINLINE_ATTRIBUTE, body) is not None
                verdict[d.group(1)] = verdict.get(d.group(1), True) and ok
    names = sorted(n for n, ok in verdict.items() if ok)
    return "|".join([NOINLINE_ATTRIBUTE, *(rf"\b{re.escape(n)}\b" for n in names)])


def _expected_class(root: Cls, moved: dict[int, Member], noinline: str) -> list[ClassLine]:
    """The base class's lines with each moved definition replaced by its declaration, which
    leaves a noinline attribute to the definition."""
    src = root.src
    every = sorted(root.all_members(), key=lambda m: m.item.start)
    lines = _line_range(src, root.item)
    lo = src.starts[lines[0] - 1]
    hi = src.starts[lines[-1]] - 1 if lines[-1] < len(src.starts) else len(src.text)
    chunks: list[tuple[str, int, Member | None]] = []
    pos = lo
    for m in every:
        if id(m) in moved:
            chunks.append((src.text[pos : m.item.start], pos, None))
            chunks.append((re.sub(noinline, " ", "".join(_decl_text(m))), m.item.start, m))
            pos = m.item.end
    chunks.append((src.text[pos:hi], pos, None))
    starts = [m.item.start for m in every]

    def owner_at(offset: int) -> Member | None:
        k = bisect.bisect_right(starts, offset) - 1  # members never nest
        return every[k] if k >= 0 and offset < every[k].item.end else None

    out: list[ClassLine] = []
    current = ClassLine("", lines[0], None, False)
    for chunk, at, decl_of in chunks:
        offset = at
        for k, piece in enumerate(chunk.split("\n")):
            if k:
                out.append(current)
                line = decl_of.line + k if decl_of else src.line(offset)
                current = ClassLine("", line, None, False)
            if piece.strip():
                current.member = current.member or decl_of or owner_at(offset)
                current.decl = current.decl or decl_of is not None
            current.text += piece
            offset += len(piece) + 1
    out.append(current)
    for e in out:
        e.text = normalize(e.text)
    return [e for e in out if e.text]


def _check_class(
    root: Cls,
    moved: dict[int, Member],
    head_classes: dict[tuple[str, ...], list[Cls]],
    noinline: str,
    *,
    report: Report,
    gone: set[tuple[str, int]],
    came: set[tuple[str, int]],
) -> list[ClassLine]:
    """The class at HEAD must read as the base's with each moved definition replaced by its
    declaration. Returns the class-level preprocessor lines that left it."""
    label = "::".join(root.names)
    where = f"{root.path}:{root.src.line(root.item.start)}"
    gone.update((root.path, n) for n in _line_range(root.src, root.item))
    heads = head_classes.get(root.key, [])
    if not heads:
        report.errors.append(f"{where}: error: class {label}: not found at HEAD")
        return []
    head = next((h for h in heads if h.path == root.path), heads[0])
    came.update((head.path, n) for n in _line_range(head.src, head.item))
    expected = _expected_class(root, moved, noinline)
    actual = [
        (normalize(head.src.text_of(n)), n)
        for n in _line_range(head.src, head.item)
        if head.src.text_of(n).strip()
    ]
    leaving: list[ClassLine] = []
    matcher = difflib.SequenceMatcher(
        None, [e.text for e in expected], [a[0] for a in actual], autojunk=False
    )
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "equal":
            continue
        if op == "delete" and all(not e.decl and e.line in root.src.pp for e in expected[i1:i2]):
            leaving.extend(expected[i1:i2])
            continue
        exp = expected[min(i1, len(expected) - 1)]
        member = next((e.member for e in expected[i1:i2] if e.member is not None), exp.member)
        about = (
            f"member {member.label()} (base {member.path}:{member.line})"
            if member is not None
            else f"class {label} (base {where})"
        )
        if j1 < j2:
            text, n = actual[j1]
            what = "the declaration left in the class differs" if exp.decl else "the class changed"
            if exp.decl and normalize(re.sub(noinline, " ", text)) == exp.text != text:
                what = (
                    "the declaration keeps a noinline attribute, which moves to the definition "
                    "(GCC rejects an inline definition after a noinline declaration)"
                )
            tail = f" (expected base {root.path}:{exp.line}: {exp.text})" if i1 < i2 else ""
            report.errors.append(f"{head.path}:{n}: error: {about}: {what}: {text}{tail}")
        else:
            report.errors.append(
                f"{root.path}:{exp.line}: error: {about}: a line left the class and does not "
                f"leave with a moved definition (line number in the base): {exp.text}"
            )
    return leaving


Gap = tuple[int, int]  # ids of the moved members before and after (0 when none is adjacent)


def _gaps(events: list[tuple[str, int]]) -> dict[Gap, list[int]]:
    """Groups preprocessor events ("P", index) by the moved definitions ("D", id) beside them;
    any other code ("O") between breaks the adjacency."""
    out: dict[Gap, list[int]] = defaultdict(list)
    for k, (kind, value) in enumerate(events):
        if kind != "P":
            continue
        before = next((e for e in reversed(events[:k]) if e[0] != "P"), ("O", 0))
        after = next((e for e in events[k + 1 :] if e[0] != "P"), ("O", 0))
        key = (before[1] if before[0] == "D" else 0, after[1] if after[0] == "D" else 0)
        out[key].append(value)
    return out


def _events(
    src: Source, lines: range, span: dict[int, Member], moving: dict[int, int]
) -> list[tuple[str, int]]:
    """The lines as events: a moved definition, a moving preprocessor line, or other code."""
    events: list[tuple[str, int]] = []
    for n in lines:
        if n in span:
            event = ("D", id(span[n]))
            if not events or events[-1] != event:
                events.append(event)
        elif n in moving:
            events.append(("P", moving[n]))
        elif src.code_of(n).strip() or n in src.pp:
            events.append(("O", 0))
    return events


def _check_moved_preprocessor(
    root: Cls,
    leaving: list[ClassLine],
    moved: dict[int, Member],
    new: list[Parsed],
    *,
    report: Report,
    came: set[tuple[str, int]],
) -> None:
    """A class-level preprocessor line may leave the class only to sit beside the same moved
    definitions, in the same order: a `#define` and `#undef` pair around a member's body."""
    if not leaving:
        return
    src = root.src
    span: dict[int, Member] = {}
    for m in root.all_members():
        if id(m) in moved:
            span.update(dict.fromkeys(range(m.line, src.line(m.item.close) + 1), m))
    base_lines = {e.line: k for k, e in enumerate(leaving)}
    base_gaps = _gaps(_events(src, _line_range(src, root.item), span, base_lines))

    texts = {e.text for e in leaving}
    owner = {id(d): m for m in root.all_members() if (d := moved.get(id(m))) is not None}
    found: list[tuple[str, str, int]] = []  # text, path, line at HEAD
    head_gaps: dict[Gap, list[int]] = {}
    for p in new:
        dspan: dict[int, Member] = {}
        for d in p.defs:
            m = owner.get(id(d))
            if m is not None:
                dspan.update(dict.fromkeys(range(d.line, p.src.line(d.item.close) + 1), m))
        if not dspan:
            continue
        moving: dict[int, int] = {}
        for n in range(1, len(p.src.starts) + 1):
            text = normalize(p.src.text_of(n))
            if n in p.src.pp and n not in dspan and text in texts and (p.path, n) not in came:
                moving[n] = len(found)
                found.append((text, p.path, n))
        head_gaps.update(_gaps(_events(p.src, range(1, len(p.src.starts) + 1), dspan, moving)))
    label = "::".join(root.names)
    for key, group in base_gaps.items():
        there = head_gaps.get(key, [])
        if key != (0, 0) and [found[k][0] for k in there] == [leaving[k].text for k in group]:
            came.update((found[k][1], found[k][2]) for k in there)
            continue
        for k in group:
            report.errors.append(
                f"{root.path}:{leaving[k].line}: error: class {label}: a preprocessor line "
                f"left the class but does not sit beside the same moved definitions at HEAD "
                f"(line number in the base): {leaving[k].text}"
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


def check(
    repo: Path, base: str | None, max_lines: int, paths: list[str], members: bool = False
) -> Report:
    """Runs every check; `paths` are relative to the repository root."""
    report = Report()
    merge_base = resolve_base(repo, base)
    check_moves(repo, merge_base, paths, report, members)
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
        usage="%(prog)s [--base REF] [--max-lines N] [--members] PATH...",
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
    parser.add_argument(
        "--members",
        action="store_true",
        help="also prove member function definitions moved out of a class body",
    )
    parser.add_argument("paths", metavar="PATH", nargs="+", help="files or directories to check")
    args = parser.parse_args(argv)
    try:
        toplevel = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
        report = check(
            toplevel, args.base, args.max_lines, repo_paths(toplevel, args.paths), args.members
        )
    except GitError as e:
        print(f"split_check: error: {e}")
        return 1
    for message in report.warnings:
        print(message)
    for message in report.notes:
        print(message)
    for message in report.errors:
        print(message)
    for cls, count in sorted(report.moved.items()):
        print(f"split_check: {cls}: {count} member definition(s) moved out of the class")
    print(
        f"split_check: {len(report.errors)} error(s), {len(report.warnings)} warning(s), "
        f"{len(report.notes)} note(s)"
    )
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
