"""Tests for nightly_enroll.py: the ci.yml shapes of the Kronuz repositories.

python3 -m unittest discover -s tools -p 'test_nightly_enroll.py'
"""

from __future__ import annotations

import contextlib
import io
import random
import tempfile
import unittest
from pathlib import Path

import nightly_enroll as ne

PLAIN = """\
name: CI
on:
  push:
    branches: [main, master]
  pull_request:
  workflow_dispatch:
  schedule:
    - cron: '23 7 * * *'  # nightly: flaky timing, and drift in libraries tracked at main
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  ci:
    uses: Kronuz/cpp-libraries/.github/workflows/cmake.yml@main
"""

PLAIN_AFTER = """\
name: CI
on:
  push:
    branches: [main, master]
  pull_request:
  workflow_dispatch:
    inputs:
      nightly: { type: boolean, default: false }
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  ci:
    uses: Kronuz/cpp-libraries/.github/workflows/cmake.yml@main
    with:
      nightly: ${{ inputs.nightly || false }}
"""

WITH = """\
name: CI
on:
  push:
    branches: [main, master]
  pull_request:
  workflow_dispatch:
  schedule:
    - cron: '23 7 * * *'
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  ci:
    uses: Kronuz/cpp-libraries/.github/workflows/cmake.yml@main
    with:
      # These containers provide no concurrent mutation API.
      tsan: false
"""

WITH_AFTER_JOBS = """\
jobs:
  ci:
    uses: Kronuz/cpp-libraries/.github/workflows/cmake.yml@main
    with:
      nightly: ${{ inputs.nightly || false }}
      # These containers provide no concurrent mutation API.
      tsan: false
"""

NO_SCHEDULE = """\
on:
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  ci:
    uses: Kronuz/cpp-libraries/.github/workflows/cmake.yml@main
    with:
      freebsd: false
  benchmarks:
    runs-on: ubuntu-24.04
"""


class EnrollTest(unittest.TestCase):
    def test_plain_file(self) -> None:
        self.assertEqual(ne.enroll(PLAIN), PLAIN_AFTER)

    def test_existing_with_block_gets_the_input_first(self) -> None:
        out = ne.enroll(WITH)
        self.assertTrue(out.endswith(WITH_AFTER_JOBS))
        self.assertNotIn("schedule", out)
        self.assertIn("permissions:\n  contents: read\nconcurrency:", out)

    def test_no_schedule_and_a_second_job(self) -> None:
        out = ne.enroll(NO_SCHEDULE)
        self.assertIn(
            "    with:\n      nightly: ${{ inputs.nightly || false }}\n      freebsd: false", out
        )
        self.assertIn("  benchmarks:\n    runs-on: ubuntu-24.04", out)
        self.assertEqual(out.count("nightly:"), 2)

    def test_idempotent(self) -> None:
        once = ne.enroll(PLAIN)
        self.assertEqual(ne.enroll(once), once)

    def test_refuses_what_it_does_not_know(self) -> None:
        for text, why in (
            (PLAIN.replace("  workflow_dispatch:\n", ""), "workflow_dispatch"),
            (
                PLAIN.replace(
                    "  workflow_dispatch:\n", "  workflow_dispatch:\n    inputs:\n      x: {}\n"
                ),
                "already has a body",
            ),
            (PLAIN.replace("@main", "@v1"), "0 calls"),
            (PLAIN + PLAIN.split("jobs:\n")[1].replace("  ci:", "  ci2:"), "2 calls"),
        ):
            with self.subTest(why=why), self.assertRaisesRegex(ne.Refused, why):
                ne.enroll(text)

    def test_mutated_files_are_refused_or_enrolled_to_a_fixed_point(self) -> None:
        rng = random.Random(11)
        for seed in (PLAIN, WITH, NO_SCHEDULE):
            for _ in range(1500):
                lines = seed.split("\n")
                for _ in range(rng.randint(1, 3)):
                    at = rng.randrange(len(lines))
                    choice = rng.random()
                    if choice < 0.4:
                        del lines[at]
                    elif choice < 0.7:
                        lines.insert(at, rng.choice(lines))
                    else:
                        lines[at] = lines[at].replace(" ", "", 1)
                text = "\n".join(lines)
                try:
                    once = ne.enroll(text)
                except ne.Refused:
                    continue
                self.assertEqual(ne.enroll(once), once)

    def test_cli_writes_checks_and_takes_a_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".github" / "workflows" / "ci.yml"
            path.parent.mkdir(parents=True)
            path.write_text(PLAIN, encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(ne.main(["--check", tmp]), 1)
                self.assertEqual(path.read_text(encoding="utf-8"), PLAIN)
                self.assertEqual(ne.main([tmp]), 0)
                self.assertEqual(ne.main(["--check", tmp]), 0)
            self.assertEqual(path.read_text(encoding="utf-8"), PLAIN_AFTER)
            self.assertIn("would change", out.getvalue())
            self.assertIn("already enrolled", out.getvalue())

    def test_cli_refusal_leaves_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ci.yml"
            path.write_text("on: push\n", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(ne.main([str(path)]), 1)
            self.assertEqual(path.read_text(encoding="utf-8"), "on: push\n")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(ne.main([str(path.with_name("none.yml"))]), 2)


if __name__ == "__main__":
    unittest.main()
