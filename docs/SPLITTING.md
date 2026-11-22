# Splitting large files

How the Kronuz repositories split a large source file: when, where to cut, and what proves the
split changed nothing. Every split quest follows this page, in any campaign. `tools/split_check.py`
enforces the mechanical part; the judgment part is read by a person before landing.

## When

Owner, 2026-11-21: "The split must make sense and improve maintainability. Let's not split for the
sake of splitting. For example, a 10K file might be ok if it makes complete sense to keep it that
way."

- A hand-written file over 1,000 lines gets a look. Size is never the reason for a cut: a file is
  split only when its pieces would each be easier to work on than the whole.
- Exempt: generated code, vendored third-party code, and frozen reference copies kept for
  differential tests (`*_old.*`, `test/old/`, `frozen_*`).
- A split waits until no open branch edits the file. A split under an open branch costs that
  branch its edits.

## Where to cut

- Cut along boundaries a maintainer recognizes: separate classes, algorithm families, subsystems,
  test topics. Each piece is a unit someone opens alone to work on one thing, and its first line
  is a comment saying what it holds.
- Keep whole, at any size, a file that is one coherent unit: one function or state machine, one
  class whose members only make sense together, a table, a test of one behavior. A library whose
  contract is a single file stays single-file unless the owner decides otherwise.
- Never cut inside a function, a `switch`, a class body or a namespace that lives in one
  translation unit: a fragment included there (`.inc` pieces) can't be read or compiled alone.
  Code like that stays where it is, or is restructured on its own reviewed quest.
- A piece under about 100 lines joins its natural neighbor.
- The repository's layout note (`docs/source-layout.md`, or the one its quest names) lists each
  new file and what it holds, and each file over 1,000 lines kept whole, with why.

## Shape

- A header keeps its path: it becomes an umbrella that includes its pieces, so no user changes an
  include. Installed headers stay installed: install rules and package include lists name the
  pieces.
- Every new header is self-contained: it includes what it uses (siblings and standard headers) and
  compiles alone, included twice in an otherwise empty translation unit, with `-fsyntax-only`.
  Run this over the new headers: `tools/selfcontained.sh` with `-x` globs for old headers, and `-t`
  for headers under `test/` and `tests/`.
- Pieces sit next to their file, named with its name as prefix (`serialize_guess.cc`), or in a
  directory named after it (`http_asio/connection_io.h`), following what the repository already
  does.
- A source piece joins the same target. A helper several pieces share moves to an internal header,
  in a `detail` namespace.
- Tests split by topic into separate translation units added to the same test target, with shared
  helpers in a support header, so `ctest -N` lists the same tests before and after.
- One commit per split file.

## Moves only

A split changes no code: bodies, names, the order of statements inside a function, and behavior
stay as they were. The only added lines are includes, `#pragma once` or an include guard,
namespace openings and closings, comments, blank lines, forward declarations of classes, structs,
unions and enums, namespace-scope function prototypes and `extern` declarations, and a
namespace-scope `using` of a detail namespace. Every other non-move goes in the quest's journal
with its reason:

- A function or variable that loses `static`, gains `inline` or leaves an anonymous namespace to be
  shared across pieces is a linkage change; shared helpers become `inline` in the detail header.
- A `using` of the detail namespace, added so moved bodies compile unchanged, can change name
  lookup.
- An include or comment dropped instead of moved (a section divider whose section became a file).
- A namespace-scope object with a dynamic initializer stays in the piece with what it depends on,
  since initialization order across translation units is unspecified.
- Moving a function to another translation unit can change its inlining. Release builds use
  `-flto`; for hot code, compare function sizes before and after (`tools/fnsizes.sh BINARY` on a
  Release build, once at the base and once at the split, then `diff`) and explain each difference.
  The tool works on Mach-O as well, where `nm -S` prints size 0 for every symbol.

## What `tools/split_check.py` checks

`split_check.py [--base REF] [--max-lines N] PATH...`, comparing the tree at HEAD with REF (the
default is the first existing of `main`, `master`, `origin/main` and `origin/master`):

1. Every line removed from a C or C++ file under PATHs reappears in a C or C++ piece, and nothing
   is lost. Other files (the layout note, CMake lists) are not compared, so a line moved into an
   `.inc` fragment counts as lost.
2. Every added line has one of the shapes listed in "Moves only". New prototypes, `extern`
   declarations and detail `using`s print as warnings, beside each dropped `static` and added
   `inline`. A removed include or comment that reappears nowhere is a warning, not a failure.
3. Each piece is contiguous slices of the old file, in order, cut only at top-level boundaries:
   moving a whole declaration passes, and a statement moved inside a function fails, naming the
   function. Namespace braces don't count as nesting; braces inside strings, characters and
   comments are skipped. Members of a class body are inside the class, so a class body can't be
   cut.
4. A namespace-scope object with a dynamic initializer that moved prints a warning.
5. C and C++ files over `--max-lines` are reported. The report never fails the check: whether a
   large file stays whole is the reader's call.

## What lands a split

Its quest proves each of these with a job at the split code, except the last two:

1. The build and the tests pass.
2. `split_check.py` passes, and the journal answers each warning.
3. `ctest -N` lists the same tests before and after. Compare only the test lines, since ctest also
   prints "could not find executable" lines for targets not built in that tree:

   ```sh
   keep='^ *Test +#|^Total Tests:'
   diff <(ctest --test-dir BASE_BUILD -N | grep -E "$keep") <(ctest --test-dir HEAD_BUILD -N | grep -E "$keep")
   ```
4. The new headers compile alone.
5. CI is green on every platform.
6. The layout note lists the pieces.
7. A person read the split and agrees that each piece is a unit and each file kept whole earns it.
