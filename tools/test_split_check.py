"""Tests for split_check.py over small git repositories built here.

python3 tools/test_split_check.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import split_check as sc

TOOL = Path(__file__).resolve().parent / "split_check.py"
OUTLINE = Path(__file__).resolve().parent / "outline.py"
MEMBERS = Path(__file__).resolve().parent / "testdata" / "members"
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

    def test_layout_note_and_cmake_lines_are_not_code(self) -> None:
        self.base({"src/big.cc": BIG, "CMakeLists.txt": "add_library(x src/big.cc)\n"})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G)
        self.repo.write("CMakeLists.txt", "add_library(x src/big.cc src/g.cc)\n")
        self.repo.write("docs/source-layout.md", "# Source layout\n\n| File | Holds |\n")
        self.repo.commit("split")
        self.assertPasses(self.repo.check(paths=(".",)))

    def test_line_moved_into_an_inc_fragment_is_lost(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G.replace("    return a - 1;\n", '#include "g.inc"\n'))
        self.repo.write("src/g.inc", "    return a - 1;\n")
        self.repo.commit("split")
        errors = self.repo.check().errors
        self.assertHas(errors, "src/big.cc:16: error:", "does not reappear", "return a - 1;")

    def test_include_guards_are_allowed(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write(
            "src/g.hh", "#ifndef SRC_G_HH_\n#define SRC_G_HH_\n" + G + "#endif  // SRC_G_HH_\n"
        )
        self.repo.commit("split")
        self.assertPasses(self.repo.check())

    def test_a_new_macro_is_not_a_guard(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", "#define USE_FAST_PATH\n" + G)
        self.repo.commit("split")
        self.assertHas(self.repo.check().errors, "src/g.cc:1: error:", "#define USE_FAST_PATH")

    def test_static_helper_becoming_inline_warns(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write(
            "src/big.cc",
            BIG_AFTER.replace(
                "static int helper(int a) {\n    return a + 1;\n}\n\n", '#include "h.hh"\n'
            ),
        )
        self.repo.write(
            "src/h.hh",
            "#pragma once\n\nnamespace x {\n\n"
            "inline int helper(int a) {\n    return a + 1;\n}\n\n}  // namespace x\n",
        )
        self.repo.write("src/g.cc", G)
        self.repo.commit("split")
        report = self.repo.check()
        self.assertPasses(report)
        self.assertHas(report.warnings, "src/h.hh:5: warning: added 'inline'", "src/big.cc:6")

    def test_inline_added_to_a_moved_definition_warns(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.hh", G.replace("int g(int a) {", "inline int g(int a) {"))
        self.repo.commit("split")
        report = self.repo.check()
        self.assertPasses(report)
        self.assertHas(report.warnings, "src/g.hh:5: warning: added 'inline'", "src/big.cc:15")

    def test_namespace_scope_using_warns(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write(
            "src/g.cc", G.replace("namespace x {\n", "namespace x {\n\nusing namespace detail;\n")
        )
        self.repo.commit("split")
        report = self.repo.check()
        self.assertPasses(report)
        self.assertHas(
            report.warnings, "src/g.cc:5: warning: using added", "using namespace detail;"
        )

    def test_using_inside_a_function_fails(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write(
            "src/g.cc",
            G.replace("    return a - 1;\n", "    using namespace detail;\n    return a - 1;\n"),
        )
        self.repo.commit("split")
        self.assertHas(self.repo.check().errors, "src/g.cc:6: error:", "using namespace detail;")

    def test_dropped_include_and_comment_warn(self) -> None:
        self.base({"src/big.cc": BIG.replace("int g(int a) {", "// --- g ---\nint g(int a) {")})
        self.repo.write("src/big.cc", BIG_AFTER.replace("#include <vector>\n", ""))
        self.repo.write("src/g.cc", G)
        self.repo.commit("split")
        report = self.repo.check()
        self.assertPasses(report)
        self.assertHas(
            report.warnings, "src/big.cc:2: warning: removed include", "#include <vector>"
        )
        self.assertHas(report.warnings, "src/big.cc:15: warning: removed comment", "// --- g ---")

    def test_added_statement_fails(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        extra = "    int extra = compute(a);\n    return"
        self.repo.write("src/g.cc", G.replace("    return", extra))
        self.repo.commit("split")
        errors = self.repo.check().errors
        self.assertEqual(len(errors), 1)
        self.assertHas(errors, "src/g.cc:6: error:", "int extra = compute(a);")

    def test_file_over_limit_is_a_note_not_a_failure(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G)
        self.repo.commit("split")
        report = self.repo.check(max_lines=12)
        self.assertEqual(report.errors, [])
        self.assertEqual(
            report.notes, ["src/big.cc: note: file has 15 lines (over --max-lines 12)"]
        )
        self.assertEqual(self.repo.check(max_lines=15).notes, [])

    def test_limit_ignores_non_source_files(self) -> None:
        self.base({"src/notes.md": "x\n" * 50, "src/a.cc": "int a;\n"})
        self.repo.write("src/a.cc", "int a;\n// c\n")
        self.repo.commit("touch")
        self.assertEqual(self.repo.check(max_lines=10).notes, [])

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
        self.repo.write("src/g.cc", G + "using namespace std;\nint counter = 0;\n#define X 1\n")
        self.repo.commit("split")
        errors = self.repo.check().errors
        self.assertEqual(len(errors), 3)
        self.assertHas(errors, "src/g.cc:10:", "using namespace std;")
        self.assertHas(errors, "src/g.cc:11:", "int counter = 0;")
        self.assertHas(errors, "src/g.cc:12:", "#define X 1")

    def test_declarations_are_allowed_with_warnings(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        decls = (
            "int helper(int a, int b);\nextern int counter;\nstatic int multi(int a,\n    int b);\n"
        )
        self.repo.write("src/g.cc", G + decls)
        self.repo.commit("split")
        report = self.repo.check()
        self.assertEqual(report.errors, [])
        self.assertEqual(len(report.warnings), 4, report.warnings)
        self.assertHas(report.warnings, "src/g.cc:10: warning: namespace-scope declaration added")
        self.assertHas(report.warnings, "src/g.cc:11:", "extern int counter;")
        self.assertHas(report.warnings, "src/g.cc:12:", "static int multi(int a,")
        self.assertHas(report.warnings, "src/g.cc:13:", "int b);")

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


SWAP = """\
namespace x {

int h(int a) {
    int p = a + 1;
    int q = a + 2;
    return p + q;
}

int k(int a) {
    return a;
}

}  // namespace x
"""

BRACES = """\
namespace x {

int h(int a) {
    const char* s = "{";  // {
    char c = '{';
    return a;
}

int k(int a) {
    return a;
}

}  // namespace x
"""


class OrderTest(Case):
    def test_reordered_statements_inside_a_function_fail(self) -> None:
        self.base({"src/h.cc": SWAP})
        self.repo.write(
            "src/h.cc",
            SWAP.replace(
                "    int p = a + 1;\n    int q = a + 2;\n",
                "    int q = a + 2;\n    int p = a + 1;\n",
            ),
        )
        self.repo.commit("swap")
        errors = self.repo.check().errors
        self.assertTrue(errors)
        for e in errors:
            self.assertIn("src/h.cc:", e)
            self.assertIn("error: moved lines", e)
            self.assertIn("within src/h.cc:3: int h(int a) {", e)

    def test_reordered_whole_functions_pass(self) -> None:
        self.base({"src/h.cc": SWAP})
        head, _, rest = SWAP.partition("int h(int a) {")
        h_body, _, k_part = rest.partition("int k(int a) {")
        k_body, _, tail = k_part.partition("}  // namespace x")
        swapped = (
            head
            + "int k(int a) {"
            + k_body
            + "int h(int a) {"
            + h_body
            + "}  // namespace x"
            + tail
        )
        self.assertNotEqual(swapped, SWAP)
        self.repo.write("src/h.cc", swapped)
        self.repo.commit("swap functions")
        report = self.repo.check()
        self.assertEqual((report.errors, report.warnings), ([], []))

    def test_braces_in_strings_and_comments_do_not_move_the_boundary(self) -> None:
        self.base({"src/h.cc": BRACES})
        self.repo.write("src/h.cc", BRACES.replace("int k(int a) {\n    return a;\n}\n\n", ""))
        self.repo.write("src/k.cc", "namespace x {\nint k(int a) {\n    return a;\n}\n}\n")
        self.repo.commit("move k")
        report = self.repo.check()
        self.assertEqual((report.errors, report.warnings), ([], []))

    def test_tail_of_a_function_moved_to_another_file_fails(self) -> None:
        self.base({"src/h.cc": SWAP})
        self.repo.write("src/h.cc", SWAP.replace("    int q = a + 2;\n    return p + q;\n", ""))
        self.repo.write("src/t.cc", "namespace x {\n    int q = a + 2;\n    return p + q;\n}\n")
        self.repo.commit("cut")
        errors = self.repo.check().errors
        self.assertEqual(len(errors), 2, errors)
        self.assertHas(errors, "src/t.cc:2: error: moved lines starts inside", "within src/h.cc:3")
        self.assertHas(errors, "src/t.cc:3: error: moved lines ends inside", "return p + q;")

    def test_edit_in_place_continues_through_unchanged_lines(self) -> None:
        self.base({"src/h.cc": SWAP})
        self.repo.write("src/h.cc", SWAP.replace("    int q = a + 2;", "\tint   q = a + 2;"))
        self.repo.commit("reindent")
        report = self.repo.check()
        self.assertEqual((report.errors, report.warnings), ([], []))


class WarningsTest(Case):
    def test_dropped_static_warns_and_passes(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG.replace("static int helper", "int helper"))
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
            'const std::string kName = make_name("x");\n'
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


class MacroShapesTest(Case):
    """Shapes a macro makes: the checker reads them as boundaries, not as cuts or initializers."""

    def split_in_two(self, text: str, cut: int, ext: str = "cc") -> sc.Report:
        """Splits `text` at line `cut` (0-based) into big and other, the head in both."""
        lines = text.splitlines(keepends=True)
        self.base({f"src/big.{ext}": text})
        self.repo.write(f"src/big.{ext}", "".join(lines[:cut]) + lines[-1])
        self.repo.write(f"src/other.{ext}", "namespace x {\n" + "".join(lines[cut:]))
        self.repo.commit("split")
        return self.repo.check()

    def test_macro_call_without_semicolon_ends_a_statement(self) -> None:
        text = (
            "namespace x {\n"
            "ENUM_CLASS(Kind, uint8_t,\n"
            "    A,\n"
            "    B\n"
            ")\n"
            "class Thing {\n"
            "};\n"
            "}  // namespace x\n"
        )
        report = self.split_in_two(text, 5)
        self.assertEqual((report.errors, report.warnings), ([], []))

    def test_cut_inside_a_function_still_fails(self) -> None:
        text = (
            "namespace x {\nENUM_CLASS(Kind, int, A)\n"
            "int f(int a) {\n    a += 1;\n    return a;\n}\n}  // namespace x\n"
        )
        self.base({"src/big.cc": text})
        self.repo.write("src/big.cc", text.replace("    return a;\n", ""))
        self.repo.write("src/other.cc", "namespace x {\n    return a;\n}  // namespace x\n")
        self.repo.commit("split")
        self.assertHas(self.repo.check().errors, "inside a function or statement")

    def test_namespace_opened_by_a_macro_holds_operators_quietly(self) -> None:
        text = (
            "MY_API_NAMESPACE(ns) {\n"
            "inline T& T::operator+=(int o) {\n"
            "    return *this;\n"
            "}\n"
            "inline T& T::operator=(const T& o) {\n"
            "    return *this;\n"
            "}\n"
            "}  // MY_API_NAMESPACE(ns)\n"
        )
        lines = text.splitlines(keepends=True)
        self.base({"src/big.cc": text})
        self.repo.write("src/big.cc", "".join(lines[:4]) + lines[7])
        self.repo.write("src/other.cc", "namespace ns {\n" + "".join(lines[4:7]) + "}\n")
        self.repo.commit("split")
        report = self.repo.check()
        self.assertEqual((report.errors, report.warnings), ([], []))

    def test_local_in_a_define_body_is_not_a_namespace_scope_initializer(self) -> None:
        text = (
            "#define CHECK_SEEN(got) \\\n"
            "    do { \\\n"
            "        const std::string got_ = (got); \\\n"
            "        check(got_); \\\n"
            "    } while (0)\n"
            "namespace x {\n"
            "}  // namespace x\n"
        )
        self.base({"src/big.cc": text})
        self.repo.write("src/big.cc", "namespace x {\n}  // namespace x\n")
        self.repo.write("src/other.cc", text.split("namespace x", maxsplit=1)[0])
        self.repo.commit("move")
        report = self.repo.check()
        self.assertEqual((report.errors, report.warnings), ([], []))

    def test_new_license_comment_does_not_take_a_moved_comment(self) -> None:
        license = "/*\n * License.\n */\n\n"
        f = "int f(int a) {\n    /*\n     * Why f doubles.\n     */\n    return a * 2;\n}\n"
        g = "int g(int a) {\n    return a - 1;\n}\n"
        self.base({"src/big.cc": license + f + "\n" + g})
        self.repo.write("src/big.cc", license + g)
        self.repo.write("src/a.cc", license + f)
        self.repo.commit("split")
        self.assertEqual((self.repo.check().errors, self.repo.check().warnings), ([], []))

    def test_dropped_static_does_not_take_an_equal_line_moved_elsewhere(self) -> None:
        p = "static inline bool\np(int k)\n{\n    return k > 0;\n}\n"
        q = "inline bool\nq(int k)\n{\n    return k < 0;\n}\n"
        self.base({"src/big.cc": p + "\n" + q + "\nint r() { return 0; }\n"})
        self.repo.write("src/big.cc", "int r() { return 0; }\n")
        self.repo.write("src/a.hh", "#pragma once\n\n" + p.replace("static ", ""))
        self.repo.write("src/b.hh", "#pragma once\n\n" + q)
        self.repo.commit("split")
        report = self.repo.check()
        self.assertPasses(report)
        self.assertHas(report.warnings, "src/a.hh:3: warning: dropped 'static'", "src/big.cc:1")

    def test_repeated_line_matches_the_occurrence_beside_its_declaration(self) -> None:
        text = (
            "namespace x {\n"
            "template <typename M, typename>\n"
            "int first(M&& o) {\n"
            "    return 1;\n"
            "}\n"
            "template <typename M, typename>\n"
            "int second(M&& o) {\n"
            "    return 2;\n"
            "}\n"
            "}  // namespace x\n"
        )
        report = self.split_in_two(text, 5)
        self.assertEqual((report.errors, report.warnings), ([], []))

    def test_operator_definition_is_not_a_dynamic_initializer(self) -> None:
        line = sc.scan("namespace x {\ninline T& T::operator+=(int o) {\n}\n}\n")[1]
        self.assertFalse(sc.is_dynamic_initializer(line))


class ScanTest(unittest.TestCase):
    def test_comments_strings_and_raw_strings_hide_braces(self) -> None:
        lines = sc.scan(
            "namespace x {\n"
            'const char* s = "}{ // not a comment";  // } trailing\n'
            "/* }\n"
            " } */ int a;\n"
            'const char* r = R"lua(\n'
            "}\n"
            ')lua";\n'
            "}\n"
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
        self.assertEqual(
            (ok.returncode, ok.stdout), (0, "split_check: 0 error(s), 0 warning(s), 0 note(s)\n")
        )
        self.repo.write("src/g.cc", G.replace("a - 1", "a - 2"))
        self.repo.commit("break")
        bad = self.run_tool("--max-lines", "1000", "g.cc", "big.cc")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("src/g.cc:6: error:", bad.stdout)
        self.assertIn("return a - 2;", bad.stdout)
        self.assertIn("2 error(s)", bad.stdout)

    def test_large_file_passes_with_a_note(self) -> None:
        self.base({"src/big.cc": BIG})
        self.repo.write("src/big.cc", BIG_AFTER)
        self.repo.write("src/g.cc", G)
        self.repo.commit("split")
        proc = self.run_tool("--max-lines", "12", ".")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("big.cc: note: file has 15 lines (over --max-lines 12)", proc.stdout)
        self.assertIn("0 error(s), 0 warning(s), 1 note(s)", proc.stdout)

    def test_path_outside_the_repository_fails(self) -> None:
        self.base({"src/a.cc": "int a;\n"})
        outside = self.run_tool("../..")
        self.assertEqual(outside.returncode, 1)
        self.assertIn("outside the repository", outside.stdout)


class Outlined(Case):
    """A fixture class at the base, and outline.py's move of it at HEAD (not yet committed)."""

    def outline(self, name: str, *flags: str) -> None:
        self.base({f"src/{name}.hh": (MEMBERS / f"{name}.hh").read_text()})
        self.run_outline(name, *flags)

    def run_outline(self, name: str, *flags: str) -> None:
        args = ["apply", f"src/{name}.hh", str(MEMBERS / f"{name}.map"), *flags]
        proc = subprocess.run(
            [sys.executable, str(OUTLINE), *args],
            cwd=self.repo.root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual((proc.returncode, proc.stderr), (0, ""))

    def read(self, path: str) -> str:
        return (self.repo.root / path).read_text()

    def edit(self, path: str, old: str, new: str) -> None:
        text = self.read(path)
        self.assertIn(old, text)
        self.repo.write(path, text.replace(old, new, 1))

    def members(self) -> sc.Report:
        self.repo.commit("move")
        return sc.check(self.repo.root, None, 100000, ["src"], members=True)

    def compiles(self, source: str) -> None:
        cxx = shutil.which("c++")
        if cxx is None:
            self.skipTest("no c++ compiler")
        tu = self.repo.root / "src" / "tu.cc"
        tu.write_text(source)
        proc = subprocess.run(
            [cxx, "-std=c++20", "-fsyntax-only", "-Wall", "-Wextra", "-Werror", str(tu)],
            capture_output=True,
            text=True,
            check=False,
        )
        tu.unlink()
        self.assertEqual(proc.returncode, 0, proc.stderr)


STORE_TU = '#include "store.hh"\ntemplate class demo::store<int>;\nint main() { return 0; }\n'
WIDE_TU = textwrap.dedent(
    """\
    #include "wide.hh"
    #include "wide.hh"
    int main() {
        wide w(3);
        int x[2] = {1, 2};
        return static_cast<int>(*w.first() + wide::sum(x, 2) + wide::selector(true)(5));
    }
    """
)


class OutlineTest(Outlined):
    """outline.py's moves pass the member mode, for both restructures' shapes (A5)."""

    def test_class_template_move_passes(self) -> None:
        self.outline("store")
        report = self.members()
        self.assertEqual((report.errors, report.warnings), ([], []))
        umbrella = self.read("src/store.hh")
        self.assertIn("\tstatic entry make(int key, int value = 1);\n", umbrella)
        self.assertIn("\tint operator()(int key) const { return get(key); }\n", umbrella)
        self.assertIn('#include "store_read.hh"\n', umbrella)
        life = self.read("src/store_life.hh")
        self.assertIn(
            "template <class Layout>\nstore<Layout>::store(int capacity, int fill) : capacity_",
            life,
        )
        self.assertIn("auto store<Layout>::operator=(const store& o) -> store& {", life)
        read = self.read("src/store_read.hh")
        self.assertIn("auto store<Layout>::size() const noexcept -> size_type {", read)
        self.assertIn("auto store<Layout>::stats() const -> std::pair<size_type, int> {", read)
        self.assertIn("template <class Layout>\ntemplate <class F, class G>\nvoid", read)
        self.assertIn("\n#if defined(DEMO_TRACE)\n\t\ttrace(e.key);\n#endif\n", read)
        self.assertIn('return R"(store\n\tof items)";\n', read)
        write = self.read("src/store_write.hh")
        self.assertIn(
            "void store<Layout>::reserve(int n)\n\trequires(sizeof(Layout) > 0)\n{", write
        )
        self.assertIn("auto store<Layout>::make(int key, int value) -> entry {", write)
        self.assertTrue(write.startswith("// store's writes"))

    def test_class_template_move_compiles(self) -> None:
        self.base({"src/store.hh": (MEMBERS / "store.hh").read_text()})
        self.compiles(STORE_TU)
        self.run_outline("store")
        self.compiles(STORE_TU)
        for piece in ("store_life", "store_read", "store_write"):
            self.compiles(f'#include "{piece}.hh"\n#include "{piece}.hh"\n')

    def test_non_template_class_move_passes(self) -> None:
        self.outline("wide", "--inline")
        report = self.members()
        self.assertEqual((report.errors, report.warnings), ([], []))
        umbrella = self.read("src/wide.hh")
        self.assertIn('#undef WIDE_PRIVATE\n\n#include "wide/container.hh"\n', umbrella)
        self.assertIn("\t\tcontainer() noexcept;\n", umbrella)
        self.assertIn("\tstatic digit (*selector(bool hi))(digit);\n", umbrella)
        self.assertNotIn("WIDE_UNROLL", umbrella)
        box = self.read("src/wide/container.hh")
        self.assertIn('#include "../wide.hh"\n', box)
        self.assertIn(
            "inline wide::container::container() noexcept : _p(_local), _size(0) { }\n", box
        )
        self.assertIn(
            "inline auto wide::container::begin() noexcept -> iterator { return _p; }", box
        )
        self.assertIn("\tfor (size_type i = 0; i < o._size; ++i) {\n\t\t_local[i]", box)
        emit = self.read("src/wide/emit.hh")
        self.assertIn("inline void (*wide::pick(unsigned k))(const digit&, unsigned char*) {", emit)
        self.assertIn("#  define WIDE_UNROLL\n#endif\n\ninline int wide::sum(", emit)
        self.assertIn(
            "}\n\n#undef WIDE_UNROLL\n\ninline auto wide::first() -> container::iterator", emit
        )
        value = self.read("src/wide/value.hh")
        self.assertIn("inline wide::digit (*wide::selector(bool hi))(digit) {", value)
        self.assertIn("inline auto wide::low(digit x, unsigned bits) -> digit {", value)
        self.assertIn("inline WIDE_NOINLINE auto wide::high(digit x) const -> digit {", value)
        self.assertIn("template <typename T, typename>\ninline void wide::set(T v) {", value)
        self.assertIn("inline wide::wide(digit v) : _value() {", value)
        self.assertIn('\n#if defined(WIDE_DEBUG)\n\tout += "dbg";\n#endif\n', value)

    def test_non_template_class_move_compiles(self) -> None:
        self.base({"src/wide.hh": (MEMBERS / "wide.hh").read_text()})
        self.compiles(WIDE_TU)
        self.run_outline("wide", "--inline")
        self.compiles(WIDE_TU)
        for piece in ("container", "emit", "value"):
            self.compiles(f'#include "wide/{piece}.hh"\n#include "wide/{piece}.hh"\n')

    def test_list_names_each_member_and_its_header(self) -> None:
        self.base({"src/store.hh": (MEMBERS / "store.hh").read_text()})
        proc = subprocess.run(
            [sys.executable, str(OUTLINE), "list", "src/store.hh", str(MEMBERS / "store.map")],
            cwd=self.repo.root,
            capture_output=True,
            text=True,
            check=True,
        )
        rows = {" ".join(r.split()[2:]) for r in proc.stdout.splitlines()}
        self.assertIn("store_life.hh ~store", rows)
        self.assertIn("? operator()", rows)
        self.assertIn("? entry::operator==", rows)

    def test_a_key_naming_nothing_fails(self) -> None:
        self.base({"src/store.hh": (MEMBERS / "store.hh").read_text()})
        bad = self.repo.root / "bad.map"
        bad.write_text("x.hh: nothing\n\tnosuch\n")
        proc = subprocess.run(
            [sys.executable, str(OUTLINE), "apply", "src/store.hh", str(bad)],
            cwd=self.repo.root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("nosuch: names no member", proc.stderr)


class MembersTest(Outlined):
    """What the member mode accepts and refuses beyond outline.py's output (A1)."""

    def test_a_qualified_member_type_in_the_return_passes(self) -> None:
        self.outline("wide", "--inline")
        self.edit(
            "src/wide/container.hh",
            "inline auto wide::container::begin() noexcept -> iterator {",
            "inline wide::container::iterator wide::container::begin() noexcept {",
        )
        self.edit(
            "src/wide/value.hh",
            "inline auto wide::low(digit x, unsigned bits) -> digit {",
            "inline wide::digit wide::low(digit x, unsigned bits) {",
        )
        self.assertPasses(self.members())

    def test_an_unqualified_member_type_in_the_return_fails(self) -> None:
        self.outline("wide", "--inline")
        self.edit(
            "src/wide/container.hh",
            "inline auto wide::container::begin() noexcept -> iterator {",
            "inline iterator wide::container::begin() noexcept {",
        )
        self.assertHas(
            self.members().errors,
            "member wide::container::begin",
            "names the class's 'iterator' unqualified",
        )

    def test_a_template_without_inline_passes_and_a_plain_member_needs_it(self) -> None:
        self.outline("wide", "--inline")
        self.edit(
            "src/wide/value.hh",
            "template <typename T, typename>\ninline void",
            "template <typename T, typename>\nvoid",
        )
        self.edit("src/wide/value.hh", "inline wide::wide(digit v)", "wide::wide(digit v)")
        errors = self.members().errors
        self.assertHas(errors, "src/wide/value.hh:", "member wide::wide", "needs 'inline'")
        self.assertEqual(len(errors), 1, errors)

    def test_a_specifier_kept_on_the_definition_fails(self) -> None:
        self.outline("wide", "--inline")
        self.edit("src/wide/value.hh", "inline auto wide::low(", "static inline auto wide::low(")
        self.assertHas(self.members().errors, "member wide::low", "the definition's head is not")

    def test_a_definition_left_in_the_class_too_fails(self) -> None:
        self.outline("store")
        self.edit("src/store.hh", "\t~store();\n", "\t~store() {\n\t\titems_.clear();\n\t}\n")
        self.assertHas(self.members().errors, "member store::~store", "the class changed")

    def test_another_change_in_the_class_fails(self) -> None:
        self.outline("store")
        self.edit("src/store.hh", "\tint capacity_;\n", "\tlong capacity_;\n")
        self.assertHas(self.members().errors, "src/store.hh:", "class store", "long capacity_;")

    def test_a_raw_string_must_keep_its_lines(self) -> None:
        self.outline("store")
        self.edit("src/store_read.hh", '\n\tof items)";', '\nof items)";')
        self.assertHas(self.members().errors, "member store::describe", "the body changed")

    def test_a_non_uniform_dedent_fails(self) -> None:
        self.outline("wide", "--inline")
        self.edit("src/wide/emit.hh", "\t\ts += x[i];\n", "\ts += x[i];\n")
        self.assertHas(self.members().errors, "member wide::sum", "the body changed", "s += x[i];")

    def test_a_preprocessor_line_must_stay_beside_its_members(self) -> None:
        self.outline("wide", "--inline")
        self.edit("src/wide/emit.hh", "#undef WIDE_UNROLL\n", "")
        self.edit(
            "src/wide/value.hh",
            "\n\ninline auto wide::low(",
            "\n\n#undef WIDE_UNROLL\n\ninline auto wide::low(",
        )
        self.assertHas(
            self.members().errors, "class wide", "#undef WIDE_UNROLL", "does not sit beside"
        )

    def test_without_the_flag_the_move_is_not_a_split(self) -> None:
        self.outline("store")
        self.repo.commit("move")
        self.assertTrue(sc.check(self.repo.root, None, 100000, ["src"]).errors)


class MutatedMoveTest(Outlined):
    """A mutated move fails with the member named (A2)."""

    def test_a_changed_statement_fails(self) -> None:
        self.outline("store")
        self.edit("src/store_read.hh", "return items_.size();", "return items_.size() + 1;")
        errors = self.members().errors
        self.assertHas(errors, "src/store_read.hh:", "member store::size", "the body changed")
        self.assertEqual(len(errors), 1, errors)

    def test_a_reordered_statement_fails(self) -> None:
        self.outline("store")
        self.edit(
            "src/store_write.hh",
            "\te.key = key;\n\te.value = value;\n",
            "\te.value = value;\n\te.key = key;\n",
        )
        errors = self.members().errors
        self.assertHas(errors, "member store::make", "the body changed", "e.value = value;")
        self.assertEqual(len(errors), 1, errors)

    def test_a_dropped_definition_fails(self) -> None:
        self.outline("wide", "--inline")
        text = self.read("src/wide/emit.hh")
        start = text.index("inline void wide::emit0(")
        end = text.index("\n", start) + 1
        self.repo.write("src/wide/emit.hh", text[:start] + text[end:])
        errors = self.members().errors
        self.assertHas(errors, "member wide::emit0", "no out-of-class definition matches it")

    def test_a_changed_default_argument_fails(self) -> None:
        self.outline("store")
        self.edit("src/store.hh", "int value = 1);", "int value = 2);")
        errors = self.members().errors
        self.assertHas(errors, "member store::make", "the declaration left in the class differs")
        self.assertEqual(len(errors), 1, errors)

    def test_a_changed_signature_fails(self) -> None:
        self.outline("store")
        self.edit(
            "src/store_read.hh",
            "get(int key, int fallback) const {",
            "get(int key, long fallback) const {",
        )
        errors = self.members().errors
        self.assertHas(
            errors, "member store::get", "the definition's head is not the declaration's"
        )


class MembersCommandLineTest(Outlined):
    def run_tool(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(TOOL), *args],
            cwd=self.repo.root / "src",
            capture_output=True,
            text=True,
            env=self.repo.env,
            check=False,
        )

    def test_members_flag(self) -> None:
        self.outline("wide", "--inline")
        self.repo.commit("move")
        proc = self.run_tool("--members", ".")
        self.assertEqual(
            (proc.returncode, proc.stdout),
            (
                0,
                "split_check: wide: 20 member definition(s) moved out of the class\n"
                "split_check: 0 error(s), 0 warning(s), 0 note(s)\n",
            ),
        )
        plain = self.run_tool(".")
        self.assertEqual(plain.returncode, 1)


if __name__ == "__main__":
    unittest.main()
