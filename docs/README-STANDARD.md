# README standard for the Kronuz C++ libraries

Every library README in the family has the same shape, so a reader who has seen one can
find anything in the next. A README is the front door: what the library is, whether it
fits, and how to use it. History goes in `CHANGELOG.md`, internals in `ARCHITECTURE.md`,
measurements in `docs/perf/`, agent rules in `AGENTS.md`.

## Layout

In this order. Omit a section that would be empty; never pad one.

1. `# <repo-name>`
2. `Part of [Kronuz C++ Libraries](https://github.com/Kronuz/cpp-libraries), a collection
   of small, reusable C++ libraries.`
3. Badges, one per line, in this order: CI, license, C++ standard, and `header-only`
   when the CMake target is `INTERFACE`.
4. **Pitch**, one paragraph of two to four sentences. The first sentence is the GitHub
   description, word for word. Then the mechanism in a phrase, and when to reach for it.
5. **Diagram**, optional: one, only when the mechanism is the reason to choose the
   library (see "Diagrams").
6. `## ✨ Highlights`: up to seven bullets, each a bold property and one sentence of
   fact. No adjectives without a number or a mechanism behind them.
7. `## 🚀 Quick start`: the smallest complete program (includes and `main`) that shows the
   main use, with the expected output in comments. It compiles as written.
8. `## 📦 Installation`: requirements first (C++ standard, CMake version, first-party and
   third-party dependencies, the platforms and sanitizers CI covers), then the
   FetchContent snippet with `GIT_TAG <pinned sha>` and a comment that `main` tracks the
   tip, the target name and the include line.
9. `## 🎯 When to use it`: when it fits, then "Not for" bullets: the limits and gotchas
   as present-tense facts.
10. `## ⚡ Performance`, only when the repository has a benchmark (rules below).
11. `## 📚 Documentation`: links to `docs/API.md`, `ARCHITECTURE.md`, `docs/perf/`,
    `CHANGELOG.md`, `AGENTS.md`, and the catalog entry.
12. `## 🛠️ Building and testing`: configure, build, `ctest`, and the bench option
    (`-D<LIB>_BUILD_BENCH=ON`).
13. `## 🤝 Contributing`: one line pointing to `AGENTS.md` and the catalog's rules.
14. `## 📄 License`: the license name, the link, and upstream credit when derived.

## Rules

- **Present tense, no history.** No "now", "new", "fixed", "previously", "was", campaign,
  review or agent narrative. Run the `docs-cleanup` shape over every edit.
- **Every claim checks.** Each number names its machine and command; each feature exists;
  each snippet compiles (copy it into a scratch file and build it).
- **Length:** about 80 to 200 lines. Move depth out instead of compressing prose.
- **Shared facts use shared words:** the catalog line, the badge set, the installation
  requirements sentence, the license line and the building commands read the same in
  every repository, changing only the names.
- Code blocks carry a language tag. Shell blocks hold commands only.

## Performance sections

The section answers one question: how fast is this, and how does it compare with what a
reader would otherwise use. Its shape is the same in every repository:

- **One sentence above each table** says what is timed (the call, the input, the unit) and
  what every column and row label means. A label that names a mode, a target or an option
  (for example `none` and `truecolor` as term-color's output depths) is explained there,
  so no reader mistakes it for a competing library.
- **Comparators.** When the domain has a well-known alternative (the standard library, a
  widely used library, the obvious hand-written loop), at least one is in the table. Each
  comparator names its version (release tag or commit), links to its project, and is
  built with the same compiler and flags. The sentence says the comparator returns the
  same results on the bench inputs. When no fair comparator exists, one line says why.
- **Columns** are implementations or machines; **rows** are workloads, smallest first.
  Units are in the header (`ns`, `GB/s`, `Mitems/s`), and a ratio column says its
  direction ("× faster than X").
- **Machines** by hardware and OS (Apple M4 Pro, macOS; Intel Core i9-9980HK, macOS
  x86-64; a Linux x86-64 VM when used), compiler and flags, then the exact commands to
  rebuild and rerun the table.
- **Current numbers only.** No before/after against older versions of the library: that
  belongs in `CHANGELOG.md`. Losses against a comparator are shown, not hidden.
- Depth (method, A/A spread, every row, other machines) goes in `docs/perf/`, linked from
  the section.

## Repository description and topics

- Description, set with `gh repo edit Kronuz/<repo> --description "..."`: one line, at most
  about 120 characters, identical to the README's first sentence. Shape:
  `<What it is> for C++<NN>: <the distinctive property>`. Say "header-only" only when the
  target is `INTERFACE`. No provenance ("extracted from Xapiand"; that goes in the
  README's license or credits), no hype, nothing the code doesn't back, no trailing period.
- Topics: `cpp`, the standard (`cpp17` or `cpp20`), `header-only` when true, and two or
  three domain words (`parser`, `hash`, `cache`, ...).

## Diagrams

Draw one only when a picture explains the mechanism faster than the pitch paragraph. A
dependency list, a file list or a single arrow does not need one. Diagrams are D2,
rendered with ELK, sketch mode and the Origami theme (id 302) with mid-tone lines and edge
labels on a transparent background, so the one SVG reads on GitHub's light and dark pages.
Every source starts with the same two lines:

```d2
vars: { d2-config: { layout-engine: elk; theme-id: 302; sketch: true; pad: 24; theme-overrides: { B1: "#8C7B7E"; B2: "#C25B73"; N2: "#C25B73" } } }
style.fill: transparent
```

and renders with `d2 docs/<name>.d2 docs/<name>.svg`. Text stays inside shapes: free text
draws dark and disappears on a dark page. The `.d2` source is committed beside the image.

Size: landscape, 4:3 to 16:9, about 800 to 1,100 px wide and at
most about 600 px tall at 1x; four to eight nodes; labels of two to four words, readable at
page width; pale fills; nothing touching. A diagram outside those limits is fixed (direction,
grid, fewer nodes, shorter labels) or split; one that a sentence replaces is removed.
