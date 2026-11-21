# tools

Scripts shared by the Kronuz C++ repositories. Each documents its options in its header.

| Tool | Purpose |
|---|---|
| `split_check.py` | Proves a file split moved code and changed none. |
| `preflight.sh` | CI's matrix before a push, on this Mac and the Linux and FreeBSD gate VMs. |
| `selfcontained.sh` | Checks that every public header compiles alone. |
| `pins.sh` | Lists first-party FetchContent pins and whether each is behind its dependency. |
| `ab_compare.py` | Paired A/B comparison of benchmark outputs. |
| `nightly_dispatch.py`, `nightly_enroll.py` | The central nightly CI. |

## split_check.py

    tools/split_check.py [--base REF] [--max-lines N] PATH...

Run it from a quest or feature branch that splits big files into smaller ones. Between
`git merge-base REF HEAD` (REF defaults to the first of `main`, `master`, `origin/main`,
`origin/master` that exists) and HEAD, under the PATHs, it checks that:

1. Every non-blank line removed from a file reappears among the added lines.
2. Every added line that was not removed is a `#include`, `#pragma once`, a namespace opening or
   closing, a comment line, a blank line, or a class, struct, union or enum forward declaration.
3. No C or C++ file under the PATHs has more than N lines (default 1000).

Whitespace-only differences are ignored. Exit status 0 means every check passed; 1 means a check
failed, or the base or a PATH could not be resolved. Failures print as
`file:line: error: message: offending text`; for a removed line the line number is the base's.
A changed line shows both halves: the added line, naming the nearest removed one it may have
been changed from, and the removed line.

Warnings do not fail the check; review each one:

- `dropped 'static'` or `added 'static'`: a line equal to a removed (or added) line except for
  `static`, a linkage change.
- `anonymous namespace opened in new code`: a `namespace {` that was not removed from anywhere,
  so its contents now have internal linkage in a different translation unit.
- `dynamic initializer moved`: a namespace-scope object initialized by a call that moved to
  another file, whose initialization order against other translation units may change.

The check compares lines as a multiset: it does not see statements reordered inside a function.
Review that with `git diff --color-moved`. Python 3.9 or newer, standard library only; its tests
are `python3 tools/test_split_check.py`.
