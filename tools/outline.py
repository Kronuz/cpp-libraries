#!/usr/bin/env python3
"""Moves a class's member function definitions out of its body, one header per map group.

    outline.py list HEADER [MAP]
    outline.py apply HEADER MAP [--inline]

`list` prints each member function defined in the class body (nested classes included) with
its lines and, given a MAP, the header it goes to (`?` when it stays). `apply` rewrites HEADER:
each mapped definition leaves the class, which keeps its declaration (the head and a `;`, with
its comments and default arguments), and becomes an out-of-class definition in its header. The
body is unchanged except one tab-or-space prefix less on every line after the first: column-0
preprocessor lines and lines inside raw strings stay as they are. The definition:

- drops `static`, `virtual`, `explicit`, `friend`, `override`, `final` and default arguments;
- keeps a noinline attribute, which leaves the declaration (GCC rejects `inline` after it): a
  `[[gnu::noinline]]`, `__attribute__((noinline))`, `__declspec(noinline)`, or an object-like
  macro HEADER defines as one; noinline inside a longer attribute list is refused;
- gains each enclosing class template's header, the member's own header without default
  arguments, the class qualifier (`C<T>::`, `C::Nested::`), and `inline` with `--inline` (for a
  non-template class);
- takes a trailing return type when its return type names a member type or static member
  (`auto C<T>::f() -> T`), or for a function returning a function pointer, qualifies those names.

MAP is the committed record of the move:

    # comment
    class: basic_index                       the class (default: the file's largest)
    umbrella-include: "strata/core/index.hh" what each piece includes (default: a relative path)
    piece-include: "strata/core/{}"          how HEADER includes each piece (default: relative)
    includes-after: #undef UINTEGER_T_PRIVATE where the piece includes go (default: the end,
                                             before a closing include-guard #endif)
    includes-comment: // One header per mechanism.  a line before the piece includes
    keep-one-line: yes                       definitions on one line stay unless named @LINE
    index_open.hh: what the piece holds      a piece, its first line's comment, then its keys
        create open ~basic_index operator= find@120 container::reserve 488-606 #4551-4557

A key is a member name (every overload; `Nested::name` for a nested class's), `name@LINE` (the
one spanning LINE), `FIRST-LAST` (every member starting in those lines), or `#LINE` and
`#FIRST-LAST` (class-level preprocessor lines, which move beside the definitions around them,
such as a `#define` and `#undef` pair). Each key must match something, and nothing twice.
Members no key names stay in the class. `split_check.py --members` proves the result; this
tool shares no code with it, so that proof is a second reading. Python 3.9 or newer.
"""

from __future__ import annotations

import bisect
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ACCESS_WORDS = ("public", "private", "protected")
DROPPED = ("static", "virtual", "explicit", "friend")
NOT_NAMES = frozenset(
    [
        "decltype",
        "noexcept",
        "alignas",
        "alignof",
        "sizeof",
        "__attribute__",
        "__declspec",
        "requires",
        "throw",
        "static_assert",
        "template",
        "operator",
        "return",
    ]
)
SPECIFIER = re.compile(
    r"\s*(?:\[\[.*?\]\]|alignas\s*\([^()]*\)|__attribute__\s*\(\([^()]*\)\)|"
    r"__declspec\s*\([^()]*\)|inline|static|constexpr|consteval|virtual|"
    r"explicit|friend|[A-Z][A-Z0-9_]+(?!\s*::))(?!\w)\s*"
)


def blank(text: str) -> tuple[str, set[int]]:
    """Comments, literal contents and preprocessor lines as spaces, offsets kept; and the
    0-based lines that begin inside a raw string."""
    chars = list(text)
    raw: set[int] = set()
    i, n = 0, len(text)
    line_start = True
    line = 0

    def wipe(a: int, b: int) -> None:
        for k in range(a, b):
            if chars[k] != "\n":
                chars[k] = " "

    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            line_start = True
            i += 1
        elif c in " \t":
            i += 1
        elif line_start and c == "#":
            j = i
            while True:
                e = text.find("\n", j)
                e = n if e < 0 else e
                if e < n and text[j:e].rstrip().endswith("\\"):
                    j = e + 1
                    line += 1
                    continue
                break
            wipe(i, e)
            i = e
        elif text.startswith("//", i):
            e = text.find("\n", i)
            e = n if e < 0 else e
            wipe(i, e)
            i = e
            line_start = False
        elif text.startswith("/*", i):
            e = text.find("*/", i + 2)
            e = n if e < 0 else e + 2
            line += text.count("\n", i, e)
            wipe(i, e)
            i = e
            line_start = False
        elif c == '"' and text[i - 1 : i] == "R":
            m = re.compile(r'"([^()\\\s]{0,16})\(').match(text, i)
            end = text.find(")" + (m.group(1) if m else "") + '"', i + 1)
            end = n - 1 if end < 0 else end + len(m.group(1) if m else "") + 1
            for k in range(i, end):
                if text[k] == "\n":
                    raw.add(text.count("\n", 0, k) + 1)
            line += text.count("\n", i, end)
            wipe(i + 1, end)
            i = end + 1
            line_start = False
        elif c == '"' or (c == "'" and not re.search(r"\b\d[\w']*$", text[max(0, i - 40) : i])):
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            wipe(i + 1, min(j, n))
            i = j + 1
            line_start = False
        else:
            i += 1
            line_start = False
    return "".join(chars), raw


def closing(code: str, i: int) -> int:
    """The index of the bracket that closes code[i]."""
    pair = {"(": ")", "[": "]", "{": "}", "<": ">"}[code[i]]
    depth = 0
    paren = 0
    for j in range(i, len(code)):
        ch = code[j]
        if code[i] == "<":
            if ch in "([{":
                paren += 1
            elif ch in ")]}":
                paren -= 1
            elif paren == 0 and ch == "<":
                depth += 1
            elif paren == 0 and ch == ">":
                depth -= 1
                if depth == 0:
                    return j
            continue
        if ch == code[i]:
            depth += 1
        elif ch == pair:
            depth -= 1
            if depth == 0:
                return j
    raise SystemExit(f"outline: unbalanced {code[i]!r} at offset {i}")


def after_templates(code: str, i: int) -> int:
    while True:
        m = re.compile(r"\s*template\s*<").match(code, i)
        if not m:
            return i
        i = closing(code, m.end() - 1) + 1


CLASS_HEAD = re.compile(r"\b(?:class|struct)\s+(?:\[\[.*?\]\]\s*)?(\w+)[^;{}()]*$")


def without_template_headers(head: str) -> str:
    """`head` with each `template <...>` replaced by spaces, offsets kept."""
    out: list[str] = []
    pos = 0
    for m in re.finditer(r"\btemplate\s*<", head):
        if m.start() < pos:
            continue
        gt = closing(head, m.end() - 1)
        out += [head[pos : m.start()], " " * (gt + 1 - m.start())]
        pos = gt + 1
    out.append(head[pos:])
    return "".join(out)


def is_function(head: str) -> bool:
    """A parameter list outside template arguments and no top-level `=`."""
    h = re.sub(r"\boperator\s*(?:\(\s*\)|\[\s*\]|[^\s\w(]+)", "operator_", head)
    paren = angle = 0
    params = False
    for k, ch in enumerate(h):
        if ch in "([{":
            params = params or (ch == "(" and paren == 0 and angle == 0)
            paren += 1
        elif ch in ")]}":
            paren -= 1
        elif paren == 0 and ch == "<" and re.search(r"[\w>]\s*$", h[:k]):
            angle += 1
        elif paren == 0 and ch == ">" and angle:
            angle -= 1
        elif paren == 0 and angle == 0 and ch == "=":
            if h[k - 1 : k] not in ("=", "!", "<", ">") and h[k + 1 : k + 2] != "=":
                return False
    return params


@dataclass
class Unit:
    kind: str  # func, type, decl, label
    start: int
    end: int
    body: int = -1
    close: int = -1
    init: int = -1
    name: str = ""
    inner: list[Unit] = field(default_factory=list)


def skip(pattern: str, text: str, k: int) -> int:
    """The end of the match of `pattern` (which matches the empty string) at k."""
    m = re.compile(pattern).match(text, k)
    return m.end() if m else k


def initializers_end(code: str, k: int) -> int:
    """The body's `{` after a constructor's member initializers starting at k, or -1."""
    name = re.compile(r"\s*(?:::)?\w+(?:\s*::\s*\w+)*\s*")
    while True:
        m = name.match(code, k)
        if not m:
            return -1
        k = m.end()
        if code[k : k + 1] == "<":
            k = closing(code, k) + 1
            k = skip(r"(?:\s*::\s*\w+)*\s*", code, k)
        if code[k : k + 1] not in ("(", "{"):
            return -1
        k = closing(code, k) + 1
        k = skip(r"\s*(?:\.\.\.)?\s*", code, k)
        if code[k : k + 1] == ",":
            k += 1
            continue
        return k if code[k : k + 1] == "{" else -1


def units(code: str, lo: int, hi: int) -> list[Unit]:
    """The members of a class body code[lo:hi]."""
    out: list[Unit] = []
    i = lo
    label = re.compile(r"(\w+)\s*:(?!:)")
    while i < hi:
        if code[i].isspace() or code[i] == ";":
            i += 1
            continue
        m = label.match(code, i)
        if m and (m.group(1) in ACCESS_WORDS or m.group(1).isupper()):
            out.append(Unit("label", i, m.end()))
            i = m.end()
            continue
        out.append(unit(code, i, hi))
        i = out[-1].end
    return out


def unit(code: str, start: int, hi: int) -> Unit:
    paren = 0
    closed = False
    j = start
    while j < hi:
        ch = code[j]
        if ch in "([":
            paren += 1
        elif ch in ")]":
            paren -= 1
            closed = closed or (paren == 0 and ch == ")")
        elif paren == 0 and ch == ";":
            return Unit("decl", start, j + 1)
        elif paren == 0 and ch == "{":
            head = code[after_templates(code, start) : j].strip()
            end = closing(code, j)
            bare = re.sub(r"\b(?:alignas|__attribute__)\s*\(+[^()]*\)+", "", head)
            if re.match(r"(?:class|struct|union)\b", head) and "(" not in bare:
                semi = code.index(";", end)
                name = re.findall(r"\w+", re.sub(r"\s*:[^:].*$|\bfinal\b", "", bare, flags=re.S))
                u = Unit("type", start, semi + 1, j, end, name=name[-1] if len(name) > 1 else "")
                u.inner = units(code, j + 1, end)
                return u
            if not re.match(r"enum\b", head) and is_function(head):
                return Unit("func", start, end + 1, j, end)
            j = end  # an enum or a brace initializer
        elif (
            paren == 0
            and ch == ":"
            and closed
            and code[j + 1 : j + 2] != ":"
            and code[j - 1] != ":"
            and is_function(code[after_templates(code, start) : j])
        ):
            body = initializers_end(code, j + 1)
            if body >= 0:
                return Unit("func", start, closing(code, body) + 1, body, closing(code, body), j)
        j += 1
    raise SystemExit(f"outline: a member at offset {start} does not end")


def declarator(code: str, lo: int, hi: int) -> tuple[int, int] | None:
    """(name start, parameter list `(`) of the function head code[lo:hi]."""
    paren = angle = 0
    first: tuple[int, int] | None = None
    caps: tuple[int, int] | None = None
    k = lo
    while k < hi:
        ch = code[k]
        if paren == 0 and angle == 0 and re.compile(r"\boperator\b").match(code, k):
            j = k + len("operator")
            m = re.compile(r"\s*(?:\(\s*\)|\[\s*\])").match(code, j)
            j = code.index("(", m.end() if m else j)
            return k, j
        if ch == "(" and paren == 0 and angle == 0:
            before = re.search(r"(~\s*)?([A-Za-z_]\w*)\s*$", code[lo:k])
            if re.match(r"\(\s*(?:\*|&)", code[k:]) and not (
                before and before.group(2) in NOT_NAMES
            ):
                found = declarator(code, k + 1, closing(code, k))
                if found:
                    return found
            elif before and before.group(2) not in NOT_NAMES:
                spot = (lo + before.start(), k)
                if before.group(2).isupper():
                    caps = caps or spot
                elif first is None:
                    first = spot
                    break
        if ch in "([{":
            paren += 1
        elif ch in ")]}":
            paren -= 1
        elif paren == 0 and ch == "<" and re.search(r"\w\s*$", code[lo:k]):
            angle += 1
        elif paren == 0 and ch == ">" and angle:
            angle -= 1
        k += 1
    return first or caps


def split_commas(code: str, lo: int, hi: int) -> list[tuple[int, int]]:
    """The top-level comma-separated pieces of code[lo:hi]."""
    pieces: list[tuple[int, int]] = []
    depth = 0
    start = lo
    for k in range(lo, hi):
        ch = code[k]
        if ch in "([{" or (ch == "<" and re.search(r"\w\s*$", code[start:k])):
            depth += 1
        elif ch in ")]}>" and depth:
            depth -= 1
        elif ch == "," and depth == 0:
            pieces.append((start, k))
            start = k + 1
    if code[start:hi].strip():
        pieces.append((start, hi))
    return pieces


def without_defaults(text: str, code: str, lo: int, hi: int) -> str:
    """text[lo:hi] (a parameter list) with each top-level `= default` cut."""
    out: list[str] = []
    pos = lo
    for a, b in split_commas(code, lo, hi):
        depth = 0
        for k in range(a, b):
            ch = code[k]
            if ch in "([{" or (ch == "<" and re.search(r"\w\s*$", code[a:k])):
                depth += 1
            elif ch in ")]}>" and depth:
                depth -= 1
            elif ch == "=" and depth == 0 and code[k + 1 : k + 2] != "=":
                cut = k
                while cut > a and text[cut - 1] in " \t":
                    cut -= 1
                tail = b
                while tail > k and text[tail - 1] in " \t\n":
                    tail -= 1
                out.append(text[pos:cut])
                pos = tail
                break
    out.append(text[pos:hi])
    return "".join(out)


@dataclass
class Scope:
    """A class on the path to a member: its name, template header and member types."""

    name: str
    header: str | None  # the template parameter list, default arguments cut
    args: str  # `<T, Ts...>` or ""
    types: set[str]


@dataclass
class Member:
    unit: Unit
    scopes: list[Scope]
    name: str
    first: int  # 1-based lines
    last: int
    decl: str = ""
    defn: str = ""

    def qualified(self) -> str:
        return "::".join([s.name for s in self.scopes[1:]] + [self.name])


def is_noinline(spec: str) -> bool:
    """`[[gnu::noinline]]`, `__attribute__((noinline))` or `__declspec(noinline)`, alone."""
    words = re.findall(r"\w+", spec)
    if len(words) != 2 or words[1].strip("_") != "noinline":
        return False
    if spec.startswith("[["):
        return words[0] in ("gnu", "clang", "msvc") and "::" in spec
    return words[0] in ("__attribute__", "__declspec")


def noinline_macros(text: str) -> set[str]:
    """Object-like macros whose every non-empty `#define` is a noinline attribute."""
    good: set[str] = set()
    bad: set[str] = set()
    for line in text.split("\n"):
        d = re.match(r"\s*#\s*define\s+(\w+)(?![\w(])(.*)", line)
        if not d:
            continue
        body = d.group(2).split("//")[0].strip()
        if body:
            (good if is_noinline(body) else bad).add(d.group(1))
    return good - bad


def template_args(params: str) -> str:
    """`<T, Ts...>` for the parameter list `class T, class... Ts`."""
    names = []
    for piece in re.split(r",(?![^<(]*[>)])", params):
        words = re.findall(r"[A-Za-z_]\w*|\.\.\.", piece.split("=")[0])
        pack = "..." in words
        words = [w for w in words if w != "..."]
        names.append(words[-1] + ("..." if pack else ""))
    return "<" + ", ".join(names) + ">"


def member_types(text: str, code: str, body: list[Unit]) -> set[str]:
    """Names a member's leading return type cannot use unqualified out of the class."""
    out: set[str] = set()
    for u in body:
        head = code[after_templates(code, u.start) : u.end]
        if u.kind == "type" and u.name:
            out.add(u.name)
        elif u.kind == "decl":
            m = re.match(r"\s*using\s+(\w+)\s*=", head) or re.match(
                r"\s*enum(?:\s+class|\s+struct)?\s+(\w+)", head
            )
            if m:
                out.add(m.group(1))
                continue
            m = re.match(r"\s*(?:typedef|static)\b([^=({\[;]*?)(\w+)\s*(?:[=;{\[]|$)", head)
            if m and "(" not in head.split("=")[0]:
                out.add(m.group(2))
    return out


class Outline:
    def __init__(self, path: Path, cls: str | None) -> None:
        self.path = path
        self.text = path.read_text()
        self.lines = self.text.split("\n")
        self.starts = [0]
        for ln in self.lines[:-1]:
            self.starts.append(self.starts[-1] + len(ln) + 1)
        self.code, self.raw = blank(self.text)
        self.noinline = noinline_macros(self.text)
        self.cls, self.namespaces, self.head, self.open = self.find_class(cls)
        close = closing(self.code, self.open)
        header = re.match(r"\s*template\s*<", self.code[self.head : self.open])
        top = Scope(self.cls, None, "", set())
        if header:
            lt = self.head + header.end() - 1
            params = self.cut_defaults(lt + 1, closing(self.code, lt))
            top = Scope(self.cls, params, template_args(params), {self.cls})  # needs <T>
        self.members: list[Member] = []
        self.pp: list[int] = []  # 1-based class-level preprocessor lines
        self.collect(units(self.code, self.open + 1, close), [top])
        lines = range(self.line(self.open), self.line(close) + 1)
        spans = {n for m in self.members for n in range(m.first, m.last + 1)}
        self.pp = [
            n for n in lines if self.line_text(n).lstrip().startswith("#") and n not in spans
        ]

    def line(self, offset: int) -> int:
        return bisect.bisect_right(self.starts, offset)

    def line_text(self, n: int) -> str:
        return self.lines[n - 1]

    def find_class(self, wanted: str | None) -> tuple[str, list[str], int, int]:
        """(name, enclosing namespaces, head offset, `{` offset) of the class."""
        found: list[tuple[int, str, list[str], int, int]] = []
        stack: list[str | None] = []
        stmt = 0
        for k, ch in enumerate(self.code):
            if ch == "{":
                head = self.code[stmt:k]
                ns = re.search(r"\bnamespace\s*([\w:]*)\s*$", head)
                if ns is not None:
                    stack.append(ns.group(1))
                elif re.search(r'\bextern\s*"\s*"\s*$', head):
                    stack.append("")
                else:
                    cls = None
                    if all(s is not None for s in stack):
                        # Template headers blanked, so a `class T` parameter is not the class.
                        own = without_template_headers(head)
                        cls = CLASS_HEAD.search(own)
                    if cls:
                        name = cls.group(1)
                        start = stmt + len(head) - len(head.lstrip())
                        size = closing(self.code, k) - k
                        names = [s for s in stack if s is not None and s]
                        found.append((size, name, names, start, k))
                    stack.append(None)
                stmt = k + 1
            elif ch == "}":
                if stack:
                    stack.pop()
                stmt = k + 1
            elif ch == ";":
                stmt = k + 1
        hits = [f for f in found if wanted is None or f[1] == wanted]
        if not hits:
            raise SystemExit(f"outline: no class {wanted or ''} in {self.path}")
        _, name, names, start, brace = max(hits)
        return name, names, start, brace

    def cut_defaults(self, lo: int, hi: int) -> str:
        return " ".join(without_defaults(self.text, self.code, lo, hi).split())

    def collect(self, body: list[Unit], scopes: list[Scope]) -> None:
        scopes[-1].types |= member_types(self.text, self.code, body)
        for u in body:
            if u.kind == "type" and u.name:
                inner = Scope(u.name, None, "", set())
                header = re.match(r"\s*template\s*<", self.code[u.start : u.body])
                if header:
                    lt = u.start + header.end() - 1
                    params = self.cut_defaults(lt + 1, closing(self.code, lt))
                    inner = Scope(u.name, params, template_args(params), set())
                self.collect(u.inner, [*scopes, inner])
            elif u.kind == "func":
                stop = u.init if u.init >= 0 else u.body
                spot = declarator(self.code, after_templates(self.code, u.start), stop)
                if spot is None:
                    continue
                prefix = self.code[u.start : spot[0]]
                if re.search(r"\bfriend\b", prefix):
                    continue  # a friend defined in the class stays there
                name = " ".join(self.code[spot[0] : spot[1]].split()).replace("~ ", "~")
                name = re.sub(r"operator\s+(?=\W)", "operator", name)
                m = Member(u, scopes, name, self.line(u.start), self.line(u.close))
                self.members.append(m)

    def build(self, m: Member, add_inline: bool) -> None:
        text, code, u = self.text, self.code, m.unit
        stop = u.init if u.init >= 0 else u.body
        k = stop - 1
        while code[k].isspace():
            k -= 1
        own = after_templates(code, u.start)
        # A noinline attribute moves to the definition: GCC rejects `inline` after it.
        decl = text[u.start : k + 1]
        at = own + len(text[own:stop]) - len(text[own:stop].lstrip())
        cuts: list[tuple[int, int]] = []
        while (sm := SPECIFIER.match(text, at)) and sm.end() > at:
            word = text[at : sm.end()].strip()
            begin = at + text[at : sm.end()].index(word)
            if word in self.noinline or is_noinline(word):
                cuts.append((begin - u.start, sm.end() - u.start))
            elif word.startswith("[[") and "noinline" in re.findall(r"\w+", word.replace("__", "")):
                raise SystemExit(
                    f"outline: {m.qualified()}: noinline shares an attribute list; "
                    f"write it as its own [[gnu::noinline]]"
                )
            at = sm.end()
        for a, b in reversed(cuts):
            decl = decl[:a] + decl[b:]
        m.decl = decl + ";" + text[k + 1 : stop].rstrip()

        headers = [f"template <{s.header}>" for s in m.scopes if s.header is not None]
        pos = u.start
        while (h := re.compile(r"\s*template\s*<").match(code, pos)) and h.end() <= own:
            lt = h.end() - 1
            gt = closing(code, lt)
            headers.append(f"template <{self.cut_defaults(lt + 1, gt)}>")
            pos = gt + 1
        start = own + len(text[own:stop]) - len(text[own:stop].lstrip())
        spot = declarator(code, start, stop)
        assert spot is not None
        name_at, lp = spot
        rp = closing(code, lp)

        # The leading part: specifiers, then the return type.
        lead = text[start:name_at]
        spec_end = 0
        while (sm := SPECIFIER.match(lead, spec_end)) and sm.end() > spec_end:
            spec_end = sm.end()
        specs = lead[:spec_end]
        ret = lead[spec_end:]
        for word in DROPPED:
            specs = re.sub(rf"\b{word}\b\s*", "", specs)
        if add_inline and not re.search(r"\b(?:inline|constexpr|consteval)\b", specs):
            specs = "inline " + specs
        qual = "".join(s.name + s.args + "::" for s in m.scopes)
        types = set().union(*(s.types for s in m.scopes))
        named = [
            w
            for w in re.finditer(r"(?<![\w:.])(?<!->)\b([A-Za-z_]\w*)\b", ret)
            if w.group(1) in types
        ]
        params = without_defaults(text, code, lp + 1, rp)
        tail = re.sub(r"\s+\b(?:override|final)\b", "", text[rp + 1 : stop])
        nested = "(" in code[start:name_at]
        if named and not nested:
            req = re.search(r"\s*\brequires\b", tail)
            cut = req.start() if req else len(tail.rstrip())
            tail = tail[:cut] + " -> " + " ".join(ret.split()) + tail[cut:]
            ret = "auto "
        elif named:
            templated = any(s.header is not None for s in m.scopes)
            for w in reversed(named):
                scope = next(
                    k for k in range(len(m.scopes) - 1, -1, -1) if w.group(1) in m.scopes[k].types
                )
                q = "".join(s.name + s.args + "::" for s in m.scopes[: scope + 1])
                q = ("typename " if templated else "") + q
                ret = ret[: w.start()] + q + ret[w.start() :]
        head = specs + ret + qual + text[name_at:lp] + "(" + params + ")" + tail
        defn = head + text[stop : u.end]
        m.defn = "\n".join([*headers, self.dedent(defn, u, start)])

    def dedent(self, defn: str, u: Unit, start: int) -> str:
        """One indentation less on each line after the first, except column-0 and raw lines.

        Line k of defn is line k after the one holding `start`.
        """
        line_start = self.text.rfind("\n", 0, u.start) + 1
        indent = self.text[line_start : u.start]
        first = self.line(start)  # 1-based; self.raw holds 0-based lines
        out = []
        for k, ln in enumerate(defn.split("\n")):
            keep = k == 0 or first + k - 1 in self.raw or not ln.startswith(indent)
            out.append(ln if keep else ln[len(indent) :])
        return "\n".join(out)


@dataclass
class Group:
    header: str
    about: str
    keys: list[str]


@dataclass
class Map:
    options: dict[str, str]
    groups: list[Group]


def read_map(path: Path) -> Map:
    options: dict[str, str] = {}
    groups: list[Group] = []
    for raw in path.read_text().splitlines():
        if not raw.strip() or (raw.startswith("#") and not raw[0].isspace()):
            continue
        if raw[0].isspace():
            if not groups:
                raise SystemExit(f"outline: {path}: keys before any header: {raw.strip()}")
            groups[-1].keys += raw.split()
            continue
        key, _, value = raw.partition(":")
        key, value = key.strip(), value.strip()
        if Path(key).suffix:
            groups.append(Group(key, value, []))
        else:
            options[key] = value
    return Map(options, groups)


def assign(o: Outline, mp: Map) -> tuple[dict[int, str], dict[int, str]]:
    """Members (by index) and class-level preprocessor lines, each to its header."""
    keep_one = mp.options.get("keep-one-line", "no") == "yes"
    where: dict[int, str] = {}
    pp: dict[int, str] = {}
    for g in mp.groups:
        for key in g.keys:
            hits: list[int] = []
            if key.startswith("#"):
                lo, _, hi = key[1:].partition("-")
                lines = [n for n in o.pp if int(lo) <= n <= int(hi or lo)]
                if not lines:
                    raise SystemExit(f"outline: {key}: no class-level preprocessor line")
                for n in lines:
                    if n in pp:
                        raise SystemExit(f"outline: {key}: line {n} assigned twice")
                    pp[n] = g.header
                continue
            if re.fullmatch(r"\d+-\d+", key):
                lo, hi = map(int, key.split("-"))
                hits = [k for k, m in enumerate(o.members) if lo <= m.first <= hi]
            else:
                name, _, at = key.partition("@")
                hits = [
                    k
                    for k, m in enumerate(o.members)
                    if name in (m.name, m.qualified()) and (not at or m.first <= int(at) <= m.last)
                ]
            if keep_one and "@" not in key:
                hits = [k for k in hits if o.members[k].first != o.members[k].last]
            if not hits:
                raise SystemExit(f"outline: {key}: names no member defined in the class")
            for k in hits:
                if k in where:
                    raise SystemExit(f"outline: {key}: {o.members[k].name} assigned twice")
                where[k] = g.header
    return where, pp


def include_line(target: str, spec: str | None, default: str) -> str:
    """`#include SPEC` with `{}` replaced by target, or `#include "default"`."""
    if spec:
        return "#include " + spec.replace("{}", target)
    return f'#include "{default}"'


def apply(o: Outline, mp: Map, add_inline: bool) -> None:
    where, pp = assign(o, mp)
    for k in where:
        o.build(o.members[k], add_inline)
    chosen = sorted(where, key=lambda k: o.members[k].unit.start)
    lines = o.text.split("\n")
    offsets = [0]
    for ln in lines:
        offsets.append(offsets[-1] + len(ln) + 1)
    # Edits on the original text: each moved definition becomes its declaration, and each
    # leaving preprocessor run goes, with one of the blank lines around it.
    edits = [(o.members[k].unit.start, o.members[k].unit.end, o.members[k].decl) for k in chosen]
    removals = sorted(pp)
    runs: list[list[int]] = []
    for n in removals:
        if runs and all(not lines[j - 1].strip() for j in range(runs[-1][-1] + 1, n)):
            runs[-1].append(n)
        else:
            runs.append([n])
    for run in runs:
        lo, hi = run[0], run[-1]
        before = lines[lo - 2] if lo >= 2 else ""
        after = lines[hi] if hi < len(lines) else ""
        if not before.strip() and not after.strip() and hi < len(lines):
            hi += 1
        edits.append((offsets[lo - 1], min(offsets[hi], len(o.text)), ""))
    edits.sort()
    out: list[str] = []
    pos = 0
    for start, end, text in edits:
        out += [o.text[pos:start], text]
        pos = end
    out.append(o.text[pos:])
    result = "".join(out).split("\n")

    header_dir = o.path.parent
    includes = [
        include_line(g.header, mp.options.get("piece-include"), g.header) for g in mp.groups
    ]
    comment = mp.options.get("includes-comment")
    block = ([comment] if comment else []) + includes
    after_line = mp.options.get("includes-after")
    if after_line:
        spot = max((n for n, ln in enumerate(result) if ln.strip() == after_line), default=-1)
        if spot < 0:
            raise SystemExit(f"outline: includes-after: no line {after_line!r}")
        result[spot + 1 : spot + 1] = ["", *block]
    else:
        end = len(result)
        while end and not result[end - 1].strip():
            end -= 1
        guard = end and result[end - 1].startswith("#endif")
        if guard:
            end -= 1
            while end and not result[end - 1].strip():
                end -= 1
        result[end:end] = ["", *block, *([""] if guard else [])]
    o.path.write_text("\n".join(result))

    umbrella_spec = mp.options.get("umbrella-include")
    for g in mp.groups:
        target = header_dir / g.header
        items = [
            (o.members[k].unit.start, o.members[k].defn) for k in chosen if where[k] == g.header
        ]
        items += [(offsets[n - 1], lines[n - 1]) for n in removals if pp[n] == g.header]
        items.sort()
        body: list[str] = []
        prev_pp = False
        for _, text in items:
            is_pp = text.lstrip().startswith("#")
            if body and not (is_pp and prev_pp):
                body.append("")
            body.append(text)
            prev_pp = is_pp
        relative = os.path.relpath(o.path, target.parent)
        umbrella = include_line(o.path.name, umbrella_spec, relative)
        piece = [f"// {g.about}", "#pragma once", "", umbrella, ""]
        if o.namespaces:
            piece += [f"namespace {n} {{" for n in o.namespaces] + [""]
        piece += body
        if o.namespaces:
            piece += [""] + [f"}}  // namespace {n}" for n in reversed(o.namespaces)]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(piece) + "\n")


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("list", "apply"):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    cmd, header = argv[0], Path(argv[1])
    rest = [a for a in argv[2:] if not a.startswith("--")]
    add_inline = "--inline" in argv
    mp = read_map(Path(rest[0])) if rest else Map({}, [])
    o = Outline(header, mp.options.get("class"))
    if cmd == "list":
        where = assign(o, mp)[0] if mp.groups else {}
        for k, m in enumerate(o.members):
            size = m.last - m.first + 1
            print(f"{m.first:6}-{m.last:<6} {size:5} {where.get(k, '?'):28} {m.qualified()}")
        for n in o.pp:
            print(f"{n:6}  #     {'':28} {o.line_text(n).strip()}")
        return 0
    if not rest:
        print("outline: apply needs a MAP", file=sys.stderr)
        return 2
    apply(o, mp, add_inline)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
