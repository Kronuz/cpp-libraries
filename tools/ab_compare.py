#!/usr/bin/env python3
"""Paired A/B comparison of benchmark outputs.

Per row it reports the median of the paired ratios (run i of A against run i of B), the range
of those ratios, the A/A ratio (A against A again, the noise of the measurement), and a verdict
(faster, slower, or noise). The summary gives the geometric mean over the rows and the
per-run geometric mean. The ratio is A/B for times and B/A for throughputs, so a ratio above 1
always means B is faster.

  ab_compare.py run [options] A B [-- ARGS...]
      Runs A, B and A again (the A/A control) every round, interleaved, with the same ARGS,
      and reports. Needs --rounds of at least 3 for a spread worth reading.

  ab_compare.py compare [options] --a FILE... --b FILE... [--aa FILE...]
      Reports on saved outputs. A FILE is one run; a directory is every file in it. The files of
      a series pair by position after a natural sort of their names (a-2 before a-10). Use
      zero-padded run numbers or one directory per series.

Inputs (--format):
  gbench  Google Benchmark JSON (--benchmark_format=json or --benchmark_out). The metric is
          real_time, cpu_time or a counter (--metric items_per_second). Aggregates are skipped
          and each repetition is a run.
  unit    Text rows: a label, then numbers followed by a time unit (ns, us, ms, or 12s). The
          label is the text before the first of them; --column picks which one (default 1).
              urldecode n=4 clean     7.2 ns  spread 3.7%
              vector<int> n=100 allocators 12.3 ns  std 14.5 ns  ratio 0.85
  table   Text rows: a label, then trailing numbers, with the first token as the label when the
          line is only numbers (a bitpack line "12 3.4 5.6" is row 12). --column picks one.
  auto    unit when a file has any unit rows, else table; JSON is gbench. The default.
  --regex REGEX   A line pattern with named groups: value (required), unit, chk, run, variant,
          and any others, which are joined into the row name. With a variant group, name the
          series FILE:VARIANT (--a all.txt:base --b all.txt:cand); rows of the same run
          group pair.

Every text format reads a `chk HEX` on the line as the row's checksum. A row whose paired
checksums differ is VOID: it is left out of the geomean and the exit status is 1.

Exit status: 0 ok; 1 a row is over --budget or void; 2 unusable input or arguments.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
NUM = r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?"
MICRO = "\u00b5"
UNIT_NS = {"ns": 1.0, "us": 1e3, MICRO + "s": 1e3, "ms": 1e6, "s": 1e9}
VALUE_UNIT = re.compile(
    rf"(?<![\w.])(?P<num>{NUM})(?:\s*(?P<unit>ns|us|{MICRO}s|ms)\b|(?P<sec>s)\b)"
)
NUMBER = re.compile(rf"^{NUM}$")
CHECKSUM = re.compile(r"\bchk\s*[:=]?\s*([0-9a-fA-F]{4,})\b")
RESERVED_GROUPS = frozenset({"value", "unit", "chk", "run", "variant"})
TIME_METRICS = frozenset({"real_time", "cpu_time"})
MIN_RUNS = 3
FORMATS = ("auto", "gbench", "unit", "table")
OUTPUTS = ("text", "markdown", "csv")


class InputError(Exception):
    """Unusable input or arguments (exit status 2)."""


@dataclass(frozen=True)
class Sample:
    """One measurement of one row in one run."""

    value: float
    chk: str | None = None


Run = dict[str, Sample]


@dataclass(frozen=True)
class ParseOptions:
    """How a file turns into rows."""

    format: str = "auto"
    column: int = 1
    metric: str = "real_time"
    regex: re.Pattern[str] | None = None
    section: re.Pattern[str] | None = None
    split: re.Pattern[str] | None = None
    include: re.Pattern[str] | None = None
    exclude: re.Pattern[str] | None = None


@dataclass(frozen=True)
class Parsed:
    """A row as read, before it is placed in a run."""

    key: str
    sample: Sample
    run: str | None = None
    variant: str | None = None


@dataclass(frozen=True)
class Settings:
    """What the comparison needs besides the runs."""

    higher_better: bool = False
    noise: float = 0.03
    budget: float | None = None
    label_a: str = "A"
    label_b: str = "B"


@dataclass(frozen=True)
class RowResult:
    """The comparison of one row."""

    key: str
    a: float
    b: float
    ratio: float
    low: float
    high: float
    pairs: int
    aa: float | None
    aa_dev: float | None
    verdict: str
    detail: str = ""


@dataclass
class Report:
    """Everything the output needs."""

    rows: list[RowResult] = field(default_factory=list)
    only_a: list[str] = field(default_factory=list)
    only_b: list[str] = field(default_factory=list)
    unpaired: list[str] = field(default_factory=list)
    runs: tuple[int, int, int] = (0, 0, 0)
    geomean: float | None = None
    aa_geomean: float | None = None
    run_geomeans: list[float] = field(default_factory=list)
    over_budget: list[RowResult] = field(default_factory=list)

    @property
    def voids(self) -> list[RowResult]:
        return [r for r in self.rows if r.verdict == "VOID"]


def natural_key(text: str) -> list[tuple[int, int, str]]:
    """A sort key that orders digit runs by value (a-2 before a-10)."""
    return [(0, int(t), "") if t.isdigit() else (1, 0, t) for t in re.split(r"(\d+)", text) if t]


def geomean(values: Sequence[float]) -> float:
    return math.exp(sum(math.log(v) for v in values) / len(values))


def speedup(a: float, b: float, higher_better: bool) -> float:
    """How many times faster B is than A: above 1 means faster, whatever the metric."""
    return b / a if higher_better else a / b


def classify(ratio: float, band: float) -> str:
    """faster or slower when the ratio is outside the noise band, else noise."""
    if ratio > 1.0 + band:
        return "faster"
    if ratio * (1.0 + band) < 1.0:
        return "slower"
    return "noise"


# -- reading ---------------------------------------------------------------------------------


def split_label(line: str, start: int) -> str:
    return re.sub(r"\s+", " ", line[:start]).strip(" \t|:,;")


def unit_values(line: str) -> tuple[str, list[float]] | None:
    """The label and the nanosecond values of a `label ... 7.2 ns ...` line."""
    found = list(VALUE_UNIT.finditer(line))
    if not found:
        return None
    label = split_label(line, found[0].start())
    if not label:
        return None
    values = [
        float(m.group("num")) * UNIT_NS[m.group("unit") or m.group("sec") or "ns"] for m in found
    ]
    return label, values


TABLE_ROW = re.compile(rf"(?P<label>\S.*?)\s{{2,}}(?P<nums>{NUM}(?:\s+{NUM})*)(?:\s+\S+)*")


def table_values(line: str) -> tuple[str, list[float]] | None:
    """The label and the numbers of a `label  1.5  2.5` or `12  1.5  2.5  yes` line.

    The numbers follow a gap of two or more spaces when the line has one; else they are the run
    that ends the line, or, when the line ends in a word, the run after a leading number, which
    is then the label (a bit width, a size).
    """
    text = line.strip()
    m = TABLE_ROW.fullmatch(text)
    if m is not None:
        return m.group("label"), [float(t) for t in m.group("nums").split()]
    tokens = [t for t in text.split() if t != "|"]
    values: list[float] = []
    while tokens and NUMBER.match(tokens[-1]):
        values.insert(0, float(tokens.pop()))
    if not tokens and len(values) > 1:
        return text.split(maxsplit=1)[0], values[1:]
    if tokens and values:
        return " ".join(tokens).strip(" \t|:,;"), values
    return None


def regex_values(rx: re.Pattern[str], line: str) -> Parsed | None:
    m = rx.search(line)
    if m is None:
        return None
    groups = m.groupdict()
    try:
        value = float(groups["value"])
    except (TypeError, ValueError):
        return None
    unit = groups.get("unit")
    if unit in UNIT_NS:
        value *= UNIT_NS[unit]
    key = " ".join(v for k, v in groups.items() if k not in RESERVED_GROUPS and v)
    return Parsed(
        re.sub(r"\s+", " ", key).strip(),
        Sample(value, groups.get("chk")),
        groups.get("run"),
        groups.get("variant"),
    )


def check_regex(rx: re.Pattern[str]) -> None:
    names = set(rx.groupindex)
    if "value" not in names:
        raise InputError("--regex needs a (?P<value>...) group")
    if not names - RESERVED_GROUPS:
        raise InputError("--regex needs a group for the row name, such as (?P<row>...)")


def text_rows(text: str, opts: ParseOptions, fmt: str) -> list[tuple[int, Parsed]]:
    """Rows of a text file with the index of the run (split section) each belongs to."""
    out: list[tuple[int, Parsed]] = []
    section = ""
    run = 0
    for raw in text.splitlines():
        line = ANSI.sub("", raw).rstrip()
        if not line.strip():
            continue
        if opts.split is not None and opts.split.search(line):
            run += 1
            section = ""
            continue
        if opts.section is not None:
            m = opts.section.search(line)
            if m is not None:
                section = (m.group(1) if m.groups() else line).strip()
                continue
        parsed: Parsed | None
        if opts.regex is not None:
            parsed = regex_values(opts.regex, line)
        else:
            reader = unit_values if fmt == "unit" else table_values
            got = reader(line)
            if got is None or len(got[1]) < opts.column:
                continue
            chk = CHECKSUM.search(line)
            parsed = Parsed(got[0], Sample(got[1][opts.column - 1], chk.group(1) if chk else None))
        if parsed is None:
            continue
        key = f"{section} / {parsed.key}" if section else parsed.key
        out.append((run, Parsed(key, parsed.sample, parsed.run, parsed.variant)))
    return out


def gbench_rows(text: str, opts: ParseOptions) -> list[tuple[int, Parsed]]:
    """Rows of Google Benchmark JSON; the repetition is the run."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise InputError(f"not valid JSON: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("benchmarks"), list):
        raise InputError("JSON without a benchmarks array is not Google Benchmark output")
    context = data.get("context")
    if isinstance(context, dict) and context.get("library_build_type") == "debug":
        print("warning: the benchmark library was built as debug", file=sys.stderr)
    out: list[tuple[int, Parsed]] = []
    for entry in data["benchmarks"]:
        if not isinstance(entry, dict):
            continue
        if entry.get("run_type") == "aggregate" or entry.get("error_occurred"):
            continue
        raw = entry.get(opts.metric)
        if not isinstance(raw, (int, float)) or not isinstance(entry.get("name"), str):
            continue
        value = float(raw)
        if opts.metric in TIME_METRICS:
            value *= UNIT_NS.get(str(entry.get("time_unit", "ns")), 1.0)
        counter = entry.get("chk", entry.get("checksum"))
        chk = None if counter is None else str(counter)
        run = entry.get("repetition_index", 0)
        out.append((run if isinstance(run, int) else 0, Parsed(entry["name"], Sample(value, chk))))
    return out


def keep(key: str, opts: ParseOptions) -> bool:
    if opts.include is not None and not opts.include.search(key):
        return False
    return not (opts.exclude is not None and opts.exclude.search(key))


def read_runs(text: str, opts: ParseOptions, variant: str | None = None) -> list[Run]:
    """The runs in one file's text; a run is a split section, a repetition, or a run group."""
    fmt = opts.format
    if fmt == "auto" and text.lstrip().startswith("{"):
        fmt = "gbench"
    if opts.regex is not None:
        check_regex(opts.regex)
    has_variant = opts.regex is not None and "variant" in opts.regex.groupindex
    if variant is not None and not has_variant:
        raise InputError("FILE:VARIANT needs a --regex with a (?P<variant>...) group")
    if has_variant and variant is None:
        raise InputError("the --regex has a variant group: name the series as FILE:VARIANT")
    if fmt == "gbench":
        rows = gbench_rows(text, opts)
    elif opts.regex is not None or fmt in ("unit", "table"):
        rows = text_rows(text, opts, fmt)
    else:
        rows = text_rows(text, opts, "unit") or text_rows(text, opts, "table")
    buckets: dict[str, Run] = {}
    seen: dict[tuple[str, str], int] = {}
    for index, parsed in rows:
        if variant is not None and parsed.variant != variant:
            continue
        if not keep(parsed.key, opts):
            continue
        bucket = parsed.run if parsed.run is not None else f"#{index}"
        run = buckets.setdefault(bucket, {})
        key = parsed.key
        count = seen.get((bucket, key), 0) + 1
        seen[(bucket, key)] = count
        if count > 1:
            key = f"{key}#{count}"
        run[key] = parsed.sample
    return list(buckets.values())


def split_spec(spec: str) -> tuple[Path, str | None]:
    """FILE or FILE:VARIANT."""
    path = Path(spec)
    if path.exists() or ":" not in spec:
        return path, None
    head, _, variant = spec.rpartition(":")
    return Path(head), variant or None


def load_series(specs: Sequence[str], opts: ParseOptions) -> list[Run]:
    items: list[tuple[Path, str | None]] = []
    for spec in specs:
        path, variant = split_spec(spec)
        if path.is_dir():
            files = [p for p in path.iterdir() if p.is_file() and not p.name.startswith(".")]
            items.extend((p, variant) for p in files)
        elif path.is_file():
            items.append((path, variant))
        else:
            raise InputError(f"{spec}: no such file or directory")
    items.sort(key=lambda item: natural_key(str(item[0])))
    runs: list[Run] = []
    for path, variant in items:
        try:
            runs.extend(read_runs(path.read_text(errors="replace"), opts, variant))
        except InputError as e:
            raise InputError(f"{path}: {e}") from e
    return runs


# -- comparing -------------------------------------------------------------------------------


def paired(a: list[Run], b: list[Run], key: str) -> dict[int, tuple[Sample, Sample]]:
    """The positive samples of a row in the runs both series have, by run index."""
    out: dict[int, tuple[Sample, Sample]] = {}
    for i in range(min(len(a), len(b))):
        x, y = a[i].get(key), b[i].get(key)
        if x is not None and y is not None and x.value > 0.0 and y.value > 0.0:
            out[i] = (x, y)
    return out


def compare_row(
    key: str, a: list[Run], b: list[Run], aa: list[Run], settings: Settings
) -> RowResult | None:
    hb = settings.higher_better
    pairs = list(paired(a, b, key).values())
    if not pairs:
        return None
    ratios = [speedup(x.value, y.value, hb) for x, y in pairs]
    controls = [speedup(x.value, y.value, hb) for x, y in paired(a, aa, key).values()]
    ratio = statistics.median(ratios)
    aa_dev = max(abs(c - 1.0) for c in controls) if controls else None
    verdict = classify(ratio, aa_dev if aa_dev is not None else settings.noise)
    detail = ""
    for x, y in pairs:
        if x.chk and y.chk and x.chk != y.chk:
            verdict, detail = "VOID", f"chk {x.chk} against {y.chk}"
            break
    return RowResult(
        key=key,
        a=statistics.median(r[key].value for r in a if key in r),
        b=statistics.median(r[key].value for r in b if key in r),
        ratio=ratio,
        low=min(ratios),
        high=max(ratios),
        pairs=len(pairs),
        aa=statistics.median(controls) if controls else None,
        aa_dev=aa_dev,
        verdict=verdict,
        detail=detail,
    )


def compare(a: list[Run], b: list[Run], aa: list[Run], settings: Settings) -> Report:
    report = Report(runs=(len(a), len(b), len(aa)))
    keys_a = list(dict.fromkeys(k for run in a for k in run))
    keys_b = list(dict.fromkeys(k for run in b for k in run))
    for key in keys_a:
        if key not in keys_b:
            report.only_a.append(key)
            continue
        row = compare_row(key, a, b, aa, settings)
        if row is None:
            report.unpaired.append(key)
        else:
            report.rows.append(row)
    report.only_b = [k for k in keys_b if k not in keys_a]
    live = [r for r in report.rows if r.verdict != "VOID"]
    if live:
        report.geomean = geomean([r.ratio for r in live])
        controls = [r.aa for r in live if r.aa is not None]
        report.aa_geomean = geomean(controls) if controls else None
        report.run_geomeans = run_geomeans(a, b, [r.key for r in live], settings.higher_better)
    if settings.budget is not None:
        limit = 1.0 / (1.0 + settings.budget)
        report.over_budget = [r for r in live if r.verdict == "slower" and r.ratio < limit]
    return report


def run_geomeans(
    a: list[Run], b: list[Run], keys: Sequence[str], higher_better: bool
) -> list[float]:
    """The geomean of each paired run over the rows every paired run has."""
    n = min(len(a), len(b))
    by_row = {k: paired(a, b, k) for k in keys}
    common = [k for k in keys if len(by_row[k]) == n]
    if not common:
        return []
    return [
        geomean(
            [speedup(by_row[k][i][0].value, by_row[k][i][1].value, higher_better) for k in common]
        )
        for i in range(n)
    ]


# -- output ----------------------------------------------------------------------------------


def num(v: float) -> str:
    if v >= 1e5:
        return f"{v:.0f}"
    if v >= 10:
        return f"{v:.1f}"
    return f"{v:.2f}" if v >= 1 else f"{v:.3f}"


def headers(settings: Settings, with_aa: bool) -> list[str]:
    a, b = settings.label_a, settings.label_b
    ratio = f"{b}/{a}" if settings.higher_better else f"{a}/{b}"
    cols = ["row", a, b, ratio, "range"]
    return [*cols, "A/A", "n", "verdict"] if with_aa else [*cols, "n", "verdict"]


def cells(r: RowResult, with_aa: bool, markdown: bool) -> list[str]:
    x = "x" if markdown else ""
    out = [r.key, num(r.a), num(r.b), f"{r.ratio:.3f}{x}", f"{r.low:.2f}-{r.high:.2f}"]
    if with_aa:
        out.append(f"{r.aa:.3f}" if r.aa is not None else "-")
    return [*out, str(r.pairs), r.verdict]


def table(head: list[str], body: list[list[str]], markdown: bool) -> list[str]:
    """Left-align the row name and right-align the numbers."""
    widths = [max(len(row[i]) for row in [head, *body]) for i in range(len(head))]

    def line(row: list[str]) -> str:
        cols = [c.ljust(w) if i == 0 else c.rjust(w) for i, (c, w) in enumerate(zip(row, widths))]
        return f"| {' | '.join(cols)} |" if markdown else "  ".join(cols).rstrip()

    out = [line(head)]
    if markdown:
        rules = [("-" * w if i == 0 else "-" * (w - 1) + ":") for i, w in enumerate(widths)]
        out.append(f"| {' | '.join(rules)} |")
    return [*out, *(line(row) for row in body)]


def summary(report: Report, settings: Settings) -> list[str]:
    a, b, aa = report.runs
    runs = f"runs: {settings.label_a} {a}, {settings.label_b} {b}" + (f", A/A {aa}" if aa else "")
    out = [f"{runs}; a ratio above 1 means {settings.label_b} is faster"]
    if min(a, b) < MIN_RUNS:
        out.append(f"warning: fewer than {MIN_RUNS} paired runs, so the range and A/A say little")
    live = [r for r in report.rows if r.verdict != "VOID"]
    if report.geomean is not None and live:
        lo = min(live, key=lambda r: r.ratio)
        hi = max(live, key=lambda r: r.ratio)
        out.append(
            f"geomean {report.geomean:.3f} over {len(live)} rows "
            f"(min {lo.ratio:.3f} {lo.key}; max {hi.ratio:.3f} {hi.key})"
        )
        if report.run_geomeans:
            g = report.run_geomeans
            out.append(
                f"per-run geomean: min {min(g):.3f}, median {statistics.median(g):.3f}, "
                f"max {max(g):.3f} over {len(g)} runs"
            )
        if report.aa_geomean is not None:
            out.append(f"A/A geomean {report.aa_geomean:.3f}")
    counts = {"only in A": report.only_a, "only in B": report.only_b, "unpaired": report.unpaired}
    skipped = [f"{name} {len(v)}" for name, v in counts.items() if v]
    if skipped:
        out.append("rows not compared: " + ", ".join(skipped))
    out.extend(f"VOID {r.key}: {r.detail}" for r in report.voids)
    if report.over_budget and settings.budget is not None:
        worst = min(report.over_budget, key=lambda r: r.ratio)
        out.append(
            f"over budget ({settings.budget:.1%}): {len(report.over_budget)} rows, "
            f"worst {worst.ratio:.3f} {worst.key}"
        )
    return out


CSV_HEADER = ["row", "a", "b", "ratio", "low", "high", "aa", "aa_dev", "pairs", "verdict", "detail"]


def render(report: Report, settings: Settings, output: str, out: TextIO) -> None:
    if output == "csv":
        writer = csv.writer(out)
        writer.writerow(CSV_HEADER)
        for r in report.rows:
            aa = "" if r.aa is None else r.aa
            dev = "" if r.aa_dev is None else r.aa_dev
            writer.writerow(
                [r.key, r.a, r.b, r.ratio, r.low, r.high, aa, dev, r.pairs, r.verdict, r.detail]
            )
        return
    with_aa = report.runs[2] > 0
    markdown = output == "markdown"
    body = [cells(r, with_aa, markdown) for r in report.rows]
    lines = table(headers(settings, with_aa), body, markdown) if body else ["no rows in common"]
    print("\n".join(lines), file=out)
    print(file=out)
    print("\n".join(summary(report, settings)), file=out)


# -- running ---------------------------------------------------------------------------------


def run_once(binary: str, args: Sequence[str], timeout: float | None) -> str:
    try:
        proc = subprocess.run(
            [binary, *args], capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        raise InputError(f"{binary}: {e}") from e
    if proc.returncode != 0:
        raise InputError(f"{binary} exited {proc.returncode}: {proc.stderr.strip()[-400:]}")
    return proc.stdout if proc.stdout.strip() else proc.stderr


def run_rounds(
    a: str, b: str, args: Sequence[str], ns: argparse.Namespace, opts: ParseOptions
) -> tuple[list[Run], list[Run], list[Run]]:
    series: tuple[list[Run], list[Run], list[Run]] = ([], [], [])
    plan = [(0, a, "a"), (1, b, "b")] + ([] if ns.no_aa else [(2, a, "aa")])
    save = Path(ns.save) if ns.save else None
    if save is not None:
        save.mkdir(parents=True, exist_ok=True)
    for n in range(1, ns.rounds + 1):
        for slot, binary, tag in plan:
            print(f"round {n}/{ns.rounds}: {tag}", file=sys.stderr)
            text = run_once(binary, args, ns.timeout)
            if save is not None:
                suffix = "json" if text.lstrip().startswith("{") else "txt"
                (save / f"{tag}-{n:03d}.{suffix}").write_text(text)
            try:
                series[slot].extend(read_runs(text, opts))
            except InputError as e:
                raise InputError(f"{binary}: {e}") from e
    return series


# -- command line ----------------------------------------------------------------------------


def pattern(text: str | None, flag: str) -> re.Pattern[str] | None:
    if text is None:
        return None
    try:
        return re.compile(text)
    except re.error as e:
        raise InputError(f"{flag}: {e}") from e


def common_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    g = p.add_argument_group("reading")
    g.add_argument("--format", choices=FORMATS, default="auto")
    g.add_argument("--column", type=int, default=1, help="which number of a text row (default 1)")
    g.add_argument("--metric", default="real_time", help="gbench: real_time, cpu_time or a counter")
    g.add_argument("--regex", help="a line pattern with value, unit, chk, run, variant groups")
    g.add_argument("--section", help="a line pattern that names the rows that follow it")
    g.add_argument("--split", help="a line pattern that starts a new run in the same file")
    g.add_argument("--include", help="keep the rows whose name matches")
    g.add_argument("--exclude", help="drop the rows whose name matches")
    g.add_argument("--higher-better", action="store_true", help="the numbers are throughputs")
    r = p.add_argument_group("reporting")
    r.add_argument("--label-a", default="A")
    r.add_argument("--label-b", default="B")
    r.add_argument("--noise", type=float, default=3.0, help="percent band without A/A (default 3)")
    r.add_argument("--budget", type=float, help="percent a row may be slower; over it, exit 1")
    r.add_argument("--output", choices=OUTPUTS, default="text")
    return p


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ab_compare.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    cmp = sub.add_parser("compare", parents=[common_parser()], help="report on saved outputs")
    cmp.add_argument("--a", nargs="+", required=True, metavar="FILE")
    cmp.add_argument("--b", nargs="+", required=True, metavar="FILE")
    cmp.add_argument("--aa", nargs="*", default=[], metavar="FILE")
    run = sub.add_parser("run", parents=[common_parser()], help="run A, B and A again, interleaved")
    run.add_argument("a", metavar="A")
    run.add_argument("b", metavar="B")
    run.add_argument("--rounds", type=int, default=5)
    run.add_argument("--no-aa", action="store_true", help="skip the A/A control run")
    run.add_argument("--save", metavar="DIR", help="write each run's output to DIR")
    run.add_argument("--timeout", type=float, help="seconds a run may take")
    return parser


def execute(argv: Sequence[str], out: TextIO) -> int:
    args: list[str] = []
    if "--" in argv:
        cut = list(argv).index("--")
        argv, args = list(argv[:cut]), list(argv[cut + 1 :])
    ns = build_parser().parse_args(argv)
    if ns.column < 1:
        raise InputError("--column starts at 1")
    opts = ParseOptions(
        format=ns.format,
        column=ns.column,
        metric=ns.metric,
        regex=pattern(ns.regex, "--regex"),
        section=pattern(ns.section, "--section"),
        split=pattern(ns.split, "--split"),
        include=pattern(ns.include, "--include"),
        exclude=pattern(ns.exclude, "--exclude"),
    )
    settings = Settings(
        higher_better=ns.higher_better or ns.metric not in TIME_METRICS,
        noise=ns.noise / 100.0,
        budget=None if ns.budget is None else ns.budget / 100.0,
        label_a=ns.label_a,
        label_b=ns.label_b,
    )
    if ns.command == "run":
        if ns.rounds < 1:
            raise InputError("--rounds starts at 1")
        a, b, aa = run_rounds(ns.a, ns.b, args, ns, opts)
    else:
        a, b, aa = (load_series(s, opts) for s in (ns.a, ns.b, ns.aa))
    if not a or not b:
        raise InputError("no rows were read from " + ("A" if not a else "B"))
    if len(a) != len(b) or (aa and len(aa) != len(a)):
        print(
            f"warning: {len(a)} A runs, {len(b)} B runs, {len(aa)} A/A runs; "
            "pairs stop at the fewest",
            file=sys.stderr,
        )
    report = compare(a, b, aa, settings)
    render(report, settings, ns.output, out)
    return 1 if report.voids or report.over_budget else 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return execute(sys.argv[1:] if argv is None else argv, sys.stdout)
    except InputError as e:
        print(f"ab_compare.py: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
