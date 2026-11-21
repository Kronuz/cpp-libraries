"""Tests for split_check.py over small git repositories built here.

python3 tools/test_split_check.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import split_check as sc

TOOL = Path(__file__).resolve().parent / "split_check.py"
SCRATCH = Path(__file__).resolve().parent.parent / ".scratch" / "split-check-tests"

BIG = """\
#include <string>
#include <vector>

namespace x {

static int helper(int a) {
    return a + 1;
}

int f(int a) {
    int b = helper(a);
    return b * 2;
}

int g(int a) {
    return a - 1;
}

}  // namespace x
"""

# BIG with g moved to g.cc.
BIG_AFTER = """\
#include <string>
#include <vector>

namespace x {

static int helper(int a) {
    return a + 1;
}

int f(int a) {
    int b = helper(a);
    return b * 2;
}

}  // namespace x
"""

G = """\
#include <string>

namespace x {

int g(int a) {
    return a - 1;
}

}  // namespace x
"""


def setUpModule() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / ".purpose").write_text("tools/test_split_check.py: fixture repositories, per run\n")


def tearDownModule() -> None:
    shutil.rmtree(SCRATCH, ignore_errors=True)


class Repo:
    """A git repository whose `main` holds the base and whose HEAD holds the split."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.env = {
            **os.environ,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
        self.git("init", "-q")
        self.git("checkout", "-q", "-b", "main")

    def git(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(self.root), *args],
            capture_output=True,
            text=True,
            env=self.env,
            check=True,
        )
        return proc.stdout

    def write(self, path: str, text: str) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def split(self) -> None:
        """Starts the branch holding the split; later writes are committed by `commit`."""
        self.git("checkout", "-q", "-b", "split")

    def check(
        self, paths: tuple[str, ...] = ("src",), max_lines: int = 1000, base: str | None = None
    ) -> sc.Report:
        return sc.check(self.root, base, max_lines, list(paths))


class Case(unittest.TestCase):
    def setUp(self) -> None:
        SCRATCH.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=SCRATCH)
        self.addCleanup(self.tmp.cleanup)
        self.repo = Repo(Path(self.tmp.name))

    def base(self, files: dict[str, str]) -> None:
        for path, text in files.items():
            self.repo.write(path, text)
        self.repo.commit("base")
        self.repo.split()

    def assertPasses(self, report: sc.Report) -> None:
        self.assertEqual(report.errors, [])

    def assertHas(self, messages: list[str], *parts: str) -> None:
        for m in messages:
            if all(p in m for p in parts):
                return
        self.fail(f"no message with {parts!r} in {messages!r}")


class MovesTest(Case):
    def test_pure_split_passes(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G)
        self.repo.commit("split")
        report = self.repo.check()
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])

    def test_changed_line_fails_with_file_line_and_text(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G.replace("a - 1", "a - 2"))
        self.repo.commit("split")
        errors = self.repo.check().errors
        self.assertHas(errors, "src/g.cc:6: error:", "return a - 2;", "changed from src/big.cc:16")
        self.assertHas(errors, "src/big.cc:16: error:", "return a - 1;")
        self.assertEqual(len(errors), 2)

    def test_dropped_line_fails(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G.replace("    return a - 1;\n", ""))
        self.repo.commit("split")
        errors = self.repo.check().errors
        self.assertEqual(len(errors), 1)
        self.assertHas(errors, "src/big.cc:16: error:", "does not reappear", "return a - 1;")

    def test_added_statement_fails(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G.replace("    return", "    int extra = compute(a);\n    return"))
        self.repo.commit("split")
        errors = self.repo.check().errors
        self.assertEqual(len(errors), 1)
        self.assertHas(errors, "src/g.cc:6: error:", "int extra = compute(a);")

    def test_file_over_limit_fails(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G)
        self.repo.commit("split")
        errors = self.repo.check(max_lines=15).errors
        self.assertEqual(len(errors), 1)
        self.assertHas(errors, "src/big.cc:16: error:", "file has 17 lines", "limit is 15")
        self.assertPasses(self.repo.check(max_lines=17))

    def test_limit_ignores_non_source_files(self) -> None:
        self.base({"src/notes.md": "x\n" * 50, "src/a.cc": "int a;\n"})
        self.repo.write("src/a.cc", "int a;\n// c\n")
        self.repo.commit("touch")
        self.assertPasses(self.repo.check(max_lines=10))

    def test_whitespace_only_changes_are_ignored(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G.replace("    return a - 1;", "\treturn   a - 1;  "))
        self.repo.commit("split")
        self.assertPasses(self.repo.check())

    def test_allowed_added_shapes(self) -> None:
        self.base({"src/big.cc": BIG})
        extra = (
            "#pragma once\n#include <map>\n// comment\n/* block\n * continued\n"
            "   int not_code_inside = comment();\n */\nnamespace {\n}\n"
            "namespace y::z {\nclass Fwd;\nstruct S;\ntemplate <class T> class Tpl;\n"
            "enum class E : int;\n}\n"
        )
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G + extra)
        self.repo.commit("split")
        self.assertPasses(self.repo.check())

    def test_other_added_shapes_fail(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G + "using namespace std;\nextern int counter;\n#define X 1\n")
        self.repo.commit("split")
        errors = self.repo.check().errors
        self.assertEqual(len(errors), 3)
        self.assertHas(errors, "src/g.cc:11:", "using namespace std;")
        self.assertHas(errors, "src/g.cc:12:", "extern int counter;")
        self.assertHas(errors, "src/g.cc:13:", "#define X 1")

    def test_bare_namespace_close_is_allowed_only_for_namespaces(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G.replace("}  // namespace x", "}"))
        self.repo.commit("split")
        self.assertPasses(self.repo.check())
        self.repo.write("src/h.cc", "namespace x {\n}\n}\n")
        self.repo.commit("stray")
        self.assertHas(self.repo.check().errors, "src/h.cc:3: error:", "}")

    def test_removed_bare_namespace_close_need_not_reappear(self) -> None:
        self.base({"src/big.cc": "namespace x {\nint a;\n}\n"})
        self.repo.git("rm", "-q", "src/big.cc")
        self.repo.write("src/a.cc", "namespace x {\nint a;\n}  // namespace x\n")
        self.repo.commit("move")
        self.assertPasses(self.repo.check())

    def test_whole_file_rename_passes(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.git("mv", "src/big.cc", "src/other.cc")
        self.repo.commit("rename")
        self.assertPasses(self.repo.check())

    def test_paths_limit_the_check(self) -> None:
        self.base({"src/big.cc": BIG, "other/o.cc": "int o;\n"})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G)
        self.repo.write("other/o.cc", "int changed;\n")
        self.repo.commit("split")
        self.assertPasses(self.repo.check(("src",)))
        self.assertHas(self.repo.check(("other",)).errors, "other/o.cc:1: error:", "int changed;")

    def test_base_is_the_merge_base(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G)
        self.repo.commit("split")
        self.repo.git("checkout", "-q", "main")
        self.repo.write("src/unrelated.cc", "int unrelated();\n")
        self.repo.commit("main moves on")
        self.repo.git("checkout", "-q", "split")
        self.assertPasses(self.repo.check())
        self.assertPasses(self.repo.check(base="main"))

    def test_missing_base_is_an_error(self) -> None:
        self.base({"src/a.cc": "int a;\n"})
        with self.assertRaises(sc.GitError):
            self.repo.check(base="no-such-ref")

    def test_master_is_the_fallback_base(self) -> None:
        self.base({"src/a.cc": "int a;\n"})
        self.repo.git("branch", "-m", "main", "master")
        self.repo.write("src/a.cc", "int a;\nint b;\n")
        self.repo.commit("add")
        self.assertHas(self.repo.check().errors, "src/a.cc:2: error:", "int b;")


class WarningsTest(Case):
    def test_dropped_static_warns_and_passes(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER.replace("static int helper", "int helper"))
        self.repo.commit("unstatic")
        report = self.repo.check()
        self.assertEqual(report.errors, [])
        self.assertEqual(len(report.warnings), 1)
        self.assertHas(
            report.warnings,
            "src/big.cc:6: warning: dropped 'static'",
            "was src/big.cc:6",
            "int helper(int a) {",
        )

    def test_added_static_warns(self) -> None:
        self.base({"src/a.cc": "int helper(int a) {\n    return a;\n}\n"})
        self.repo.write("src/a.cc", "static int helper(int a) {\n    return a;\n}\n")
        self.repo.commit("static")
        report = self.repo.check()
        self.assertEqual(report.errors, [])
        self.assertHas(report.warnings, "src/a.cc:1: warning: added 'static'")

    def test_static_in_other_words_is_not_a_linkage_change(self) -> None:
        self.base({"src/a.cc": "void f() {\n    static_assert(true);\n}\n"})
        self.repo.write("src/a.cc", "void f() {\n    assert(true);\n}\n")
        self.repo.commit("edit")
        self.assertEqual(len(self.repo.check().errors), 2)

    def test_dynamic_initializer_moved_to_another_file_warns(self) -> None:
        text = (
            "namespace x {\n"
            "constexpr int kConst = compute(3);\n"
            "const int kPlain = 3;\n"
            "const std::string kName = make_name(\"x\");\n"
            "auto kLambda = [](int a) { return a; };\n"
            "int bump(int a = defaults());\n"
            "void f() {\n"
            "    int local = make_local(1);\n"
            "}\n"
            "}  // namespace x\n"
        )
        self.base({"src/big.cc": text})
        self.repo.write("src/big.cc", "namespace x {\n}  // namespace x\n")
        self.repo.write("src/other.cc", text)
        self.repo.commit("move")
        report = self.repo.check()
        self.assertEqual(report.errors, [])
        self.assertEqual(len(report.warnings), 1, report.warnings)
        self.assertHas(
            report.warnings,
            "src/other.cc:4: warning: dynamic initializer moved from src/big.cc:4",
            "make_name",
        )

    def test_dynamic_initializer_moved_inside_one_file_is_quiet(self) -> None:
        self.base({"src/a.cc": "int a = make();\nint b;\n"})
        self.repo.write("src/a.cc", "int b;\nint a = make();\n")
        self.repo.commit("reorder")
        report = self.repo.check()
        self.assertEqual((report.errors, report.warnings), ([], []))

    def test_new_anonymous_namespace_warns(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G.replace("namespace x {\n", "namespace x {\nnamespace {\n"))
        self.repo.commit("split")
        report = self.repo.check()
        self.assertEqual(report.errors, [])
        self.assertHas(report.warnings, "src/g.cc:4: warning: anonymous namespace", "namespace {")


class ScanTest(unittest.TestCase):
    def test_comments_strings_and_raw_strings_hide_braces(self) -> None:
        lines = sc.scan(
            'namespace x {\n'
            'const char* s = "}{ // not a comment";  // } trailing\n'
            '/* }\n'
            ' } */ int a;\n'
            'const char* r = R"lua(\n'
            '}\n'
            ')lua";\n'
            '}\n'
        )
        self.assertEqual(lines[1].code, 'const char* s = "";')
        self.assertEqual(lines[2].code, "")
        self.assertEqual(lines[3].code, "int a;")
        self.assertTrue(lines[5].code != "")  # raw string interior is not a comment line
        self.assertFalse(lines[5].ns_close)
        self.assertTrue(lines[7].ns_close)

    def test_function_close_is_not_a_namespace_close(self) -> None:
        lines = sc.scan("namespace x {\nvoid f() {\n}\n}\n")
        self.assertEqual([ln.ns_close for ln in lines], [False, False, False, True])
        self.assertEqual([ln.ns_only for ln in lines], [True, True, False, True])

    def test_digit_separators_are_not_char_literals(self) -> None:
        lines = sc.scan("int a = 1'000'000; }\n")
        self.assertEqual(lines[0].code, "int a = 1'000'000; }")

    def test_macro_bodies_are_not_scanned(self) -> None:
        lines = sc.scan("#define X { \\\n  1 \\\n}\nnamespace a {\n}\n")
        self.assertTrue(lines[4].ns_close)


class CommandLineTest(Case):
    def run_tool(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(TOOL), *args],
            cwd=self.repo.root / "src",
            capture_output=True,
            text=True,
            env=self.repo.env,
            check=False,
        )

    def test_exit_codes_and_messages(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G)
        self.repo.commit("split")
        ok = self.run_tool("--base", "main", ".")
        self.assertEqual((ok.returncode, ok.stdout), (0, "split_check: 0 error(s), 0 warning(s)\n"))
        self.repo.write("src/g.cc", G.replace("a - 1", "a - 2"))
        self.repo.commit("break")
        bad = self.run_tool("--max-lines", "1000", "g.cc", "big.cc")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("src/g.cc:6: error:", bad.stdout)
        self.assertIn("return a - 2;", bad.stdout)
        self.assertIn("2 error(s)", bad.stdout)

    def test_path_outside_the_repository_fails(self) -> None:
        self.base({"src/a.cc": "int a;\n"})
        outside = self.run_tool("../..")
        self.assertEqual(outside.returncode, 1)
        self.assertIn("outside the repository", outside.stdout)


if __name__ == "__main__":
    unittest.main()
