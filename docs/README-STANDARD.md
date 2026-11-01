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
10. `## ⚡ Performance`, only when the repository has a benchmark: one small table of
    current numbers, the machines by hardware (Apple M4 Pro, Intel Core i9-9980HK, ...),
    compiler and flags, and the exact command. Comparator rows name the comparator and its
    version. No before/after; that is changelog material. Link `docs/perf/`.
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
rendered with ELK, the Origami theme (id 302) and sketch mode, with the `.d2` source
committed beside the image. Size: landscape, 4:3 to 16:9, about 800 to 1,100 px wide and at
most about 600 px tall at 1x; four to eight nodes; labels of two to four words, readable at
page width; pale fills; nothing touching. A diagram outside those limits is fixed (direction,
grid, fewer nodes, shorter labels) or split; one that a sentence replaces is removed.
