"""Tests for ab_compare.py: the readers on the benches' own line formats, the statistics, the CLI.

python3 -m unittest discover -s tools -p 'test_ab_compare.py'
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import re
import stat
import sys
import tempfile
import unittest
from pathlib import Path

import ab_compare as ab

URLDECODE = """\
urldecode n=4 clean                       7.2 ns  spread  3.7%
urldecode(qset) n=4 clean                 6.3 ns  spread  7.1%
urldecode n=4 dense                       8.5 ns  spread  7.4%
"""

ALLOCATORS = """\
  vector<int>                  n=16 allocators 4.15 ns  std 4.49 ns  ratio 0.92  (A/A 1.00)
  vector<string> push_back(&&) n=16 allocators 59.87 ns  std 24.47 ns  ratio 2.45  (A/A 1.01)
"""

BITPACK = """\
 bits       simd    simd+d1     scalar        ref     ref+d1     same   (integers per ns)
    1      22.95       3.44       6.78      27.21       3.42      yes
    2      23.33       3.42       3.55      25.26       3.40      yes
"""

DOCSET = """\
and d=0.001 100
test d=0.01 (ns/probe) 220
size 4096  123.4
"""

MSGPACK = """\
msgpack  small  read      312.5 ns  min  310.1  spread 1.2%  chk 00ab12cd34ef5678
msgpack  small  lookup3    41.0 ns  min   40.2  spread 0.9%  chk 1111222233334444
"""

LONG_FORM = """\
1 old base arm rows_a 10.0
1 old base arm rows_b 20.0
1 old cand arm rows_a 5.0
1 old cand arm rows_b 20.0
2 old base arm rows_a 12.0
2 old base arm rows_b 22.0
2 old cand arm rows_a 6.0
2 old cand arm rows_b 22.0
"""
LONG_REGEX = (
    r"^(?P<run>\d+) (?P<tool>\S+) (?P<variant>\S+) (?P<arm>\S+) (?P<row>\S+) (?P<value>[\d.]+)$"
)


def gbench(entries: list[dict[str, object]], build: str = "release") -> str:
    return json.dumps({"context": {"library_build_type": build}, "benchmarks": entries})


def entry(name: str, real: float, **extra: object) -> dict[str, object]:
    return {"name": name, "run_type": "iteration", "real_time": real, "time_unit": "ns", **extra}


def runs_of(
    text: str,
    *,
    column: int = 1,
    metric: str = "real_time",
    section: re.Pattern[str] | None = None,
    split: re.Pattern[str] | None = None,
    include: re.Pattern[str] | None = None,
    exclude: re.Pattern[str] | None = None,
) -> list[ab.Run]:
    opts = ab.ParseOptions(
        column=column, metric=metric, section=section, split=split, include=include, exclude=exclude
    )
    return ab.read_runs(text, opts)


def values(run: ab.Run) -> dict[str, float]:
    return {k: v.value for k, v in run.items()}


def compare(
    a: list[dict[str, float]],
    b: list[dict[str, float]],
    aa: list[dict[str, float]] | None = None,
    *,
    higher_better: bool = False,
    noise: float = 0.03,
    budget: float | None = None,
) -> ab.Report:
    def wrap(series: list[dict[str, float]]) -> list[ab.Run]:
        return [{k: ab.Sample(v) for k, v in run.items()} for run in series]

    settings = ab.Settings(higher_better=higher_better, noise=noise, budget=budget)
    return ab.compare(wrap(a), wrap(b), wrap(aa or []), settings)


class Cli:
    """Runs ab_compare.main on arguments and captures what it printed."""

    def __init__(self, *argv: str) -> None:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.code = ab.main(list(argv))
        self.out, self.err = out.getvalue(), err.getvalue()


class Reading(unittest.TestCase):
    def test_natural_sort(self) -> None:
        names = ["a-10.txt", "a-2.txt", "a-1.txt"]
        self.assertEqual(sorted(names, key=ab.natural_key), ["a-1.txt", "a-2.txt", "a-10.txt"])

    def test_unit_rows_take_the_label_before_the_first_number_with_a_unit(self) -> None:
        (run,) = runs_of(URLDECODE)
        self.assertEqual(
            values(run),
            {
                "urldecode n=4 clean": 7.2,
                "urldecode(qset) n=4 clean": 6.3,
                "urldecode n=4 dense": 8.5,
            },
        )

    def test_column_picks_the_second_timing_of_a_row(self) -> None:
        (run,) = runs_of(ALLOCATORS, column=2)
        self.assertEqual(values(run)["vector<int> n=16 allocators"], 4.49)
        (run,) = runs_of(ALLOCATORS)
        self.assertEqual(values(run)["vector<string> push_back(&&) n=16 allocators"], 59.87)

    def test_units_become_nanoseconds(self) -> None:
        (run,) = runs_of("a 2 us\nb 3 ms\nc 1.5s\nd 7ns\ne 4 \u00b5s\n")
        self.assertEqual(values(run), {"a": 2000.0, "b": 3e6, "c": 1.5e9, "d": 7.0, "e": 4000.0})

    def test_table_rows_when_a_file_has_no_unit(self) -> None:
        (run,) = runs_of(DOCSET)
        self.assertEqual(
            values(run),
            {"and d=0.001": 100.0, "test d=0.01 (ns/probe)": 220.0, "size 4096": 123.4},
        )

    def test_a_line_of_numbers_is_a_row_named_by_the_first(self) -> None:
        (run,) = runs_of(BITPACK)
        self.assertEqual(values(run), {"1": 22.95, "2": 23.33})
        (run,) = runs_of(BITPACK, column=2)
        self.assertEqual(values(run), {"1": 3.44, "2": 3.42})

    def test_a_row_without_enough_columns_is_skipped(self) -> None:
        self.assertEqual(runs_of(BITPACK, column=9), [])

    def test_duplicate_names_in_one_run_are_numbered(self) -> None:
        (run,) = runs_of("x 1 ns\nx 2 ns\nx 3 ns\n")
        self.assertEqual(values(run), {"x": 1.0, "x#2": 2.0, "x#3": 3.0})

    def test_sections_prefix_the_rows_that_follow(self) -> None:
        text = "<i8,u64>\n  n=10 find 5.0 ns\n<i16,u32>\n  n=10 find 6.0 ns\n"
        (run,) = runs_of(text, section=re.compile(r"^<.*>$"))
        self.assertEqual(values(run), {"<i8,u64> / n=10 find": 5.0, "<i16,u32> / n=10 find": 6.0})

    def test_split_starts_a_new_run_in_the_same_file(self) -> None:
        runs = runs_of("== run 1\nx 1 ns\n== run 2\nx 2 ns\n", split=re.compile(r"^== run"))
        self.assertEqual([values(r) for r in runs], [{"x": 1.0}, {"x": 2.0}])

    def test_include_and_exclude(self) -> None:
        text = "keep a 1 ns\nkeep b 2 ns\ndrop c 3 ns\n"
        (run,) = runs_of(text, include=re.compile("^keep"), exclude=re.compile(" b$"))
        self.assertEqual(values(run), {"keep a": 1.0})

    def test_ansi_escapes_are_dropped(self) -> None:
        (run,) = runs_of("\x1b[1mfoo\x1b[0m 4.0 ns\n")
        self.assertEqual(values(run), {"foo": 4.0})

    def test_checksum_column(self) -> None:
        (run,) = runs_of(MSGPACK)
        self.assertEqual(run["msgpack small read"].chk, "00ab12cd34ef5678")
        self.assertEqual(run["msgpack small read"].value, 312.5)

    def test_regex_with_variant_and_run_groups(self) -> None:
        rx = re.compile(LONG_REGEX)
        runs = ab.read_runs(LONG_FORM, ab.ParseOptions(regex=rx), "cand")
        self.assertEqual(
            [values(r) for r in runs],
            [
                {"old arm rows_a": 5.0, "old arm rows_b": 20.0},
                {"old arm rows_a": 6.0, "old arm rows_b": 22.0},
            ],
        )

    def test_regex_needs_value_and_a_name(self) -> None:
        with self.assertRaises(ab.InputError):
            ab.read_runs("x", ab.ParseOptions(regex=re.compile(r"(?P<row>\w+)")))
        with self.assertRaises(ab.InputError):
            ab.read_runs("x", ab.ParseOptions(regex=re.compile(r"(?P<value>\d+)")))

    def test_variant_rules(self) -> None:
        rx = re.compile(LONG_REGEX)
        with self.assertRaises(ab.InputError):
            ab.read_runs(LONG_FORM, ab.ParseOptions(regex=rx))
        with self.assertRaises(ab.InputError):
            ab.read_runs("x 1 ns", ab.ParseOptions(), "base")

    def test_gbench_skips_aggregates_and_converts_units(self) -> None:
        text = gbench(
            [
                entry("BM_a/16", 100.0),
                entry("BM_b", 2.0, time_unit="us"),
                entry("BM_a/16_mean", 99.0, run_type="aggregate"),
                entry("BM_bad", 1.0, error_occurred=True),
            ]
        )
        (run,) = runs_of(text)
        self.assertEqual(values(run), {"BM_a/16": 100.0, "BM_b": 2000.0})

    def test_gbench_repetitions_are_runs(self) -> None:
        text = gbench(
            [entry("BM_a", 10.0, repetition_index=0), entry("BM_a", 12.0, repetition_index=1)]
        )
        runs = runs_of(text)
        self.assertEqual([values(r) for r in runs], [{"BM_a": 10.0}, {"BM_a": 12.0}])

    def test_gbench_counters_and_checksums(self) -> None:
        text = gbench([entry("BM_a", 10.0, items_per_second=5e6, chk=77)])
        (run,) = runs_of(text, metric="items_per_second")
        self.assertEqual(run["BM_a"].value, 5e6)
        self.assertEqual(run["BM_a"].chk, "77")

    def test_json_that_is_not_gbench_is_refused(self) -> None:
        with self.assertRaises(ab.InputError):
            runs_of('{"x": 1}')

    def test_split_spec(self) -> None:
        self.assertEqual(ab.split_spec("no/such:base"), (Path("no/such"), "base"))
        self.assertEqual(ab.split_spec("plain.txt"), (Path("plain.txt"), None))


class Statistics(unittest.TestCase):
    def test_ratio_is_the_median_of_the_paired_ratios(self) -> None:
        # Paired ratios 2, 2, 1 (the third run is an outlier): the median is 2.
        r = compare([{"x": 10.0}, {"x": 20.0}, {"x": 10.0}], [{"x": 5.0}, {"x": 10.0}, {"x": 10.0}])
        (row,) = r.rows
        self.assertAlmostEqual(row.ratio, 2.0)
        self.assertAlmostEqual(row.low, 1.0)
        self.assertAlmostEqual(row.high, 2.0)
        self.assertEqual(row.pairs, 3)
        self.assertAlmostEqual(row.a, 10.0)
        self.assertAlmostEqual(row.b, 10.0)

    def test_pairs_follow_the_run_index(self) -> None:
        # Pairing run i with run i gives 2 and 4, not the ratio of the medians.
        r = compare([{"x": 10.0}, {"x": 40.0}], [{"x": 5.0}, {"x": 10.0}])
        self.assertAlmostEqual(r.rows[0].ratio, 3.0)

    def test_throughput_inverts_the_ratio(self) -> None:
        r = compare([{"x": 10.0}], [{"x": 20.0}], higher_better=True)
        self.assertAlmostEqual(r.rows[0].ratio, 2.0)
        self.assertEqual(r.rows[0].verdict, "faster")
        r = compare([{"x": 10.0}], [{"x": 20.0}])
        self.assertAlmostEqual(r.rows[0].ratio, 0.5)
        self.assertEqual(r.rows[0].verdict, "slower")

    def test_aa_sets_the_noise_band(self) -> None:
        a = [{"x": 100.0}, {"x": 100.0}]
        b = [{"x": 90.0}, {"x": 90.0}]  # 1.11x
        quiet = compare(a, b, [{"x": 100.5}, {"x": 99.5}])
        self.assertEqual(quiet.rows[0].verdict, "faster")
        loud = compare(a, b, [{"x": 85.0}, {"x": 100.0}])  # the same binary moves 15%
        self.assertEqual(loud.rows[0].verdict, "noise")
        self.assertAlmostEqual(loud.rows[0].aa_dev or 0.0, 100.0 / 85.0 - 1.0)

    def test_without_aa_the_band_is_the_noise_setting(self) -> None:
        a, b = [{"x": 100.0}], [{"x": 98.0}]
        self.assertEqual(compare(a, b).rows[0].verdict, "noise")
        self.assertEqual(compare(a, b, noise=0.01).rows[0].verdict, "faster")
        self.assertEqual(compare(b, a, noise=0.01).rows[0].verdict, "slower")

    def test_classify_is_symmetric_around_one(self) -> None:
        self.assertEqual(ab.classify(1.04, 0.03), "faster")
        self.assertEqual(ab.classify(1 / 1.04, 0.03), "slower")
        self.assertEqual(ab.classify(1.02, 0.03), "noise")
        self.assertEqual(ab.classify(1 / 1.02, 0.03), "noise")

    def test_geomean_and_per_run_geomean(self) -> None:
        r = compare(
            [{"x": 4.0, "y": 9.0}, {"x": 4.0, "y": 9.0}],
            [{"x": 1.0, "y": 1.0}, {"x": 2.0, "y": 1.0}],
        )
        self.assertAlmostEqual(r.geomean or 0.0, math.sqrt(3.0 * 9.0))  # x: median(4, 2) = 3
        self.assertEqual(len(r.run_geomeans), 2)
        self.assertAlmostEqual(r.run_geomeans[0], math.sqrt(4.0 * 9.0))
        self.assertAlmostEqual(r.run_geomeans[1], math.sqrt(2.0 * 9.0))

    def test_rows_in_one_series_only_are_listed_not_compared(self) -> None:
        r = compare([{"x": 1.0, "gone": 1.0}], [{"x": 1.0, "new": 1.0}])
        self.assertEqual([row.key for row in r.rows], ["x"])
        self.assertEqual((r.only_a, r.only_b), (["gone"], ["new"]))

    def test_checksum_mismatch_voids_the_row_and_leaves_it_out_of_the_geomean(self) -> None:
        a = [{"x": ab.Sample(4.0, "aa"), "y": ab.Sample(9.0, "bb")}]
        b = [{"x": ab.Sample(1.0, "aa"), "y": ab.Sample(1.0, "cc")}]
        r = ab.compare(a, b, [], ab.Settings())
        self.assertEqual([row.verdict for row in r.rows], ["faster", "VOID"])
        self.assertAlmostEqual(r.geomean or 0.0, 4.0)
        self.assertEqual(len(r.voids), 1)

    def test_budget_counts_slower_rows_past_it(self) -> None:
        a = [{"x": 100.0, "y": 100.0, "z": 100.0}]
        b = [{"x": 102.0, "y": 110.0, "z": 90.0}]
        r = compare(a, b, budget=0.03, noise=0.01)
        self.assertEqual([row.key for row in r.over_budget], ["y"])
        self.assertEqual(compare(a, b, noise=0.01).over_budget, [])

    def test_budget_is_a_slowdown_of_the_time_not_a_drop_of_the_ratio(self) -> None:
        # 103.05 ns against 100 ns is 3.05% more time: over a 3% budget, though the ratio is 0.9704.
        over = compare([{"x": 100.0}], [{"x": 103.05}], budget=0.03, noise=0.01)
        self.assertEqual([row.key for row in over.over_budget], ["x"])
        under = compare([{"x": 100.0}], [{"x": 102.95}], budget=0.03, noise=0.01)
        self.assertEqual(under.over_budget, [])

    def test_nonpositive_values_do_not_pair(self) -> None:
        r = compare([{"x": 0.0}], [{"x": 1.0}])
        self.assertEqual((r.rows, r.unpaired), ([], ["x"]))


class CommandLine(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, name: str, text: str) -> str:
        path = self.dir / name
        path.write_text(text)
        return str(path)

    def runs(self, prefix: str, values_: list[float]) -> list[str]:
        return [self.write(f"{prefix}-{i}.txt", f"row one {v} ns\n") for i, v in enumerate(values_)]

    def test_compare_reports_the_ratio_and_the_geomean(self) -> None:
        a = self.runs("a", [10.0, 10.0, 10.0])
        b = self.runs("b", [5.0, 5.0, 5.0])
        aa = self.runs("c", [10.0, 10.1, 9.9])
        cli = Cli("compare", "--a", *a, "--b", *b, "--aa", *aa)
        self.assertEqual(cli.code, 0, cli.err)
        self.assertIn("row one", cli.out)
        self.assertIn("2.000", cli.out)
        self.assertIn("faster", cli.out)
        self.assertIn("geomean 2.000 over 1 rows", cli.out)
        self.assertNotIn("warning", cli.out)
        self.assertIn("A/A geomean", cli.out)

    def test_a_directory_is_every_file_in_it_in_natural_order(self) -> None:
        (self.dir / "a").mkdir()
        (self.dir / "b").mkdir()
        for i, v in enumerate([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0, 110.0]):
            (self.dir / "a" / f"run-{i + 1}.txt").write_text(f"x {v} ns\n")
            (self.dir / "b" / f"run-{i + 1}.txt").write_text(f"x {v / 2} ns\n")
        cli = Cli(
            "compare", "--a", str(self.dir / "a"), "--b", str(self.dir / "b"), "--output", "csv"
        )
        self.assertEqual(cli.code, 0, cli.err)
        self.assertIn(
            "x,60.0,30.0,2.0,2.0,2.0", cli.out
        )  # the median of 11 runs; run-10 follows run-9

    def test_few_runs_warn(self) -> None:
        cli = Cli("compare", "--a", *self.runs("a", [10.0]), "--b", *self.runs("b", [5.0]))
        self.assertIn("warning: fewer than 3 paired runs", cli.out)

    def test_budget_exit_status(self) -> None:
        a = self.runs("a", [100.0, 100.0])
        b = self.runs("b", [110.0, 110.0])
        self.assertEqual(Cli("compare", "--a", *a, "--b", *b).code, 0)
        cli = Cli("compare", "--a", *a, "--b", *b, "--budget", "3")
        self.assertEqual(cli.code, 1)
        self.assertIn("over budget (3.0%): 1 rows", cli.out)
        self.assertEqual(Cli("compare", "--a", *a, "--b", *b, "--budget", "20").code, 0)

    def test_checksum_mismatch_exit_status(self) -> None:
        a = [self.write("a.txt", "r 1.0 ns chk deadbeef\n")]
        b = [self.write("b.txt", "r 1.0 ns chk feedface\n")]
        cli = Cli("compare", "--a", *a, "--b", *b)
        self.assertEqual(cli.code, 1)
        self.assertIn("VOID r: chk deadbeef against feedface", cli.out)

    def test_markdown_output(self) -> None:
        a = self.runs("a", [10.0])
        b = self.runs("b", [5.0])
        out = Cli("compare", "--a", *a, "--b", *b, "--output", "markdown", "--label-b", "new").out
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("| row"))
        self.assertIn("A/new", lines[0])
        self.assertTrue(set(lines[1]) <= set("|-: "))
        self.assertIn("2.000x", lines[2])

    def test_variant_logs(self) -> None:
        log = self.write("log.txt", LONG_FORM)
        cli = Cli(
            "compare",
            "--regex",
            LONG_REGEX,
            "--a",
            f"{log}:base",
            "--b",
            f"{log}:cand",
            "--output",
            "csv",
        )
        self.assertEqual(cli.code, 0, cli.err)
        self.assertIn("old arm rows_a,11.0,5.5,2.0", cli.out)  # medians 11 and 5.5, ratio 2
        self.assertIn("old arm rows_b,21.0,21.0,1.0", cli.out)

    def test_throughput_flag(self) -> None:
        a = [self.write("a.txt", "1 10.0 3.0\n2 20.0 3.0\n")]
        b = [self.write("b.txt", "1 20.0 3.0\n2 20.0 3.0\n")]
        out = Cli("compare", "--higher-better", "--a", *a, "--b", *b, "--output", "csv").out
        self.assertIn("1,10.0,20.0,2.0", out)

    def test_gbench_files_and_metric(self) -> None:
        a = [self.write("a.json", gbench([entry("BM_x", 100.0, items_per_second=1e6)]))]
        b = [self.write("b.json", gbench([entry("BM_x", 50.0, items_per_second=2e6)]))]
        both = Cli("compare", "--a", *a, "--b", *b, "--output", "csv")
        self.assertIn("BM_x,100.0,50.0,2.0", both.out)
        items = Cli(
            "compare", "--metric", "items_per_second", "--a", *a, "--b", *b, "--output", "csv"
        )
        self.assertIn("BM_x,1000000.0,2000000.0,2.0", items.out)

    def test_bad_input_exits_2(self) -> None:
        good = self.runs("a", [1.0])
        self.assertEqual(Cli("compare", "--a", str(self.dir / "missing"), "--b", *good).code, 2)
        empty = self.write("empty.txt", "nothing to see\n")
        cli = Cli("compare", "--a", empty, "--b", *good)
        self.assertEqual(cli.code, 2)
        self.assertIn("no rows were read from A", cli.err)
        bad = Cli("compare", "--a", *good, "--b", *good, "--regex", "(")
        self.assertEqual(bad.code, 2)

    def test_run_interleaves_a_b_a_each_round(self) -> None:
        log = self.dir / "order.log"
        scripts = {}
        for name, ns in (("alpha", 10), ("beta", 5)):
            path = self.dir / name
            path.write_text(
                f"#!{sys.executable}\n"
                "import sys\n"
                f"open(sys.argv[1], 'a').write('{name}\\n')\n"
                f"print('row one {ns} ns')\n"
            )
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
            scripts[name] = str(path)
        save = self.dir / "saved"
        cli = Cli(
            "run",
            "--rounds",
            "2",
            "--save",
            str(save),
            scripts["alpha"],
            scripts["beta"],
            "--",
            str(log),
        )
        self.assertEqual(cli.code, 0, cli.err)
        self.assertEqual(log.read_text().split(), ["alpha", "beta", "alpha"] * 2)
        self.assertIn("runs: A 2, B 2, A/A 2", cli.out)
        self.assertIn("2.000", cli.out)
        self.assertEqual(
            sorted(p.name for p in save.iterdir()),
            [
                "a-001.txt",
                "a-002.txt",
                "aa-001.txt",
                "aa-002.txt",
                "b-001.txt",
                "b-002.txt",
            ],
        )
        again = Cli(
            "compare",
            "--a",
            *map(str, sorted(save.glob("a-*"))),
            "--b",
            *map(str, sorted(save.glob("b-*"))),
        )
        self.assertIn("2.000", again.out)

    def test_run_reports_a_failing_binary(self) -> None:
        path = self.dir / "fails"
        path.write_text(f"#!{sys.executable}\nimport sys\nsys.exit(3)\n")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        cli = Cli("run", "--rounds", "1", str(path), str(path))
        self.assertEqual(cli.code, 2)
        self.assertIn("exited 3", cli.err)


if __name__ == "__main__":
    unittest.main()
