# tools

Scripts shared by the Kronuz C++ repositories. Each documents its options in its header.

| Tool | Purpose |
|---|---|
| `split_check.py` | Proves a file split moved code and changed none. |
| `outline.py` | Moves a class's member definitions out of its body, one header per map group. |
| `preflight.sh` | CI's matrix before a push, on this Mac and the Linux and FreeBSD gate VMs. |
| `selfcontained.sh` | Checks that every public header compiles alone. |
| `fnsizes.sh` | Prints per-function sizes of a binary or object, on Mach-O and ELF. |
| `pins.sh` | Lists first-party FetchContent pins and whether each is behind its dependency. |
| `ab_compare.py` | Paired A/B comparison of benchmark outputs. |
| `nightly_dispatch.py`, `nightly_enroll.py` | The central nightly CI. |

## split_check.py

    tools/split_check.py [--base REF] [--max-lines N] [--members] PATH...

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

`--members` also accepts a class restructure: member function definitions moved out of a class
body into headers, each with its declaration left in the class and a noinline attribute moved to
the definition (SPLITTING.md, "Restructuring a large class", lists what may change). A failure there names the member, as
`file:line: error: member C::f (base file:line): ...`.

Exit status 0 means no errors; 1 means an error, or that the base or a PATH could not be
resolved. Whitespace-only differences are ignored. The order check runs once the line checks
pass. Python 3.9 or newer, standard library only; its tests are
`python3 tools/test_split_check.py`.

## outline.py

    tools/outline.py list HEADER [MAP]
    tools/outline.py apply HEADER MAP [--inline]

Moves a class's member function definitions out of its body: `list` prints each member with its
lines and the header the map gives it, `apply` rewrites HEADER (each moved definition becomes its
declaration, and the pieces' includes go after the class) and writes the pieces. `--inline` marks
each definition `inline`, for a non-template class. A noinline attribute leaves the declaration
for the definition, which GCC needs. The map format is in the tool's header. It
shares no code with `split_check.py`, so `split_check.py --members` is a second reading of the
move; its tests are in `tools/test_split_check.py`, over the fixtures in
`tools/testdata/members/`.
