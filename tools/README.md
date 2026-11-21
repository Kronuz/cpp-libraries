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

Run it from a branch that splits big files into smaller ones. The rules for splitting, and what
the check enforces, are in [docs/SPLITTING.md](../docs/SPLITTING.md). Between
`git merge-base REF HEAD` (REF defaults to the first of `main`, `master`, `origin/main`,
`origin/master` that exists) and HEAD, under the PATHs, it prints:

- Errors, which exit 1: a removed line that does not reappear, an added line that is not an
  allowed shape, and moved lines that start or end inside a function or statement. Each prints as
  `file:line: error: message: offending text`; for a removed line the line number is the base's.
- Warnings, which do not fail: a `static` dropped or added, a namespace-scope declaration added,
  an anonymous namespace opened in new code, and a dynamic initializer moved to another file.
- Notes, which do not fail: a C or C++ file over `--max-lines` (default 1000), as
  `file: note: file has N lines`.

Exit status 0 means no errors; 1 means an error, or that the base or a PATH could not be
resolved. Whitespace-only differences are ignored. The order check runs once the line checks
pass. Python 3.9 or newer, standard library only; its tests are
`python3 tools/test_split_check.py`.
