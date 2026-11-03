"""Tests for nightly_dispatch.py against a fake `gh`: discovery, dependency parsing, the
change detection and the pacing.

python3 -m unittest discover -s tools -p 'test_nightly_dispatch.py'
"""

from __future__ import annotations

import contextlib
import io
import json
import random
import re
import unittest
from collections.abc import Sequence
from typing import Any

import nightly_dispatch as nd

NOW = nd.parse_time("2026-11-03T06:17:00Z")
DAY = 86400.0
ENROLLED_CI = """\
on:
  workflow_dispatch:
    inputs:
      nightly: { type: boolean, default: false }
jobs:
  ci:
    uses: Kronuz/cpp-libraries/.github/workflows/cmake.yml@main  # shared
    with:
      nightly: ${{ inputs.nightly || false }}
"""
OLD_CI = """\
on:
  workflow_dispatch:
jobs:
  ci:
    uses: Kronuz/cpp-libraries/.github/workflows/cmake.yml@main
"""
OTHER_CI = "jobs:\n  ci:\n    uses: someone/else/.github/workflows/x.yml@main\n"
SHA = "a" * 40


def iso(seconds: float) -> str:
    return nd.datetime.fromtimestamp(seconds, nd.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Fake:
    """Canned `gh` answers; records every call. Runs finish after `finish` polls."""

    def __init__(self, clock: FakeClock | None = None) -> None:
        self.calls: list[list[str]] = []
        self.repos: list[dict[str, Any]] = []
        self.files: dict[str, dict[str, str]] = {}  # repo -> path -> text
        self.commits: dict[str, tuple[str, float]] = {}  # "repo@ref" -> sha, time
        self.runs: dict[str, list[dict[str, Any]]] = {}
        self.pages = 1
        self.next_id = 1000
        self.polls: dict[int, int] = {}
        self.finish = 1
        self.fail_dispatch: set[str] = set()
        self.print_url = True
        self.in_flight = 0
        self.peak = 0
        self.order: list[str] = []
        self.times: list[float] = []
        self.owner: dict[int, str] = {}
        self.conclusion: dict[str, str] = {}
        self.clock = clock
        self.expiry: str | None = None  # the token's expiration header
        self.reject_token = False

    def add_repo(self, name: str, ci: str, head: str = SHA, branch: str = "main") -> None:
        self.repos.append(
            {
                "name": name,
                "defaultBranchRef": {"name": branch, "target": {"oid": head}},
                "ci": {"text": ci},
            }
        )

    def add_run(self, repo: str, run_id: int, head: str, conclusion: str, created: float) -> None:
        self.runs.setdefault(repo, []).insert(
            0,
            {
                "id": run_id,
                "head_sha": head,
                "status": "completed" if conclusion else "in_progress",
                "conclusion": conclusion or None,
                "created_at": iso(created),
            },
        )

    def __call__(self, args: Sequence[str]) -> str:
        self.calls.append(list(args))
        if args[0] == "workflow":
            return self.workflow_run(args)
        path = args[1]
        if path == "-i":
            if self.reject_token:
                raise nd.GhError("gh api: HTTP 401: Bad credentials")
            head = "HTTP/2.0 200 OK\nServer: github.com\n"
            if self.expiry:
                head += f"Github-Authentication-Token-Expiration: {self.expiry}\n"
            return head + "\n" + '{"resources": {}}'
        if path == "graphql":
            query = args[3].removeprefix("query=")
            if "repositoryOwner" in query:
                return self.repo_page(args)
            return self.blobs(query)
        if "/git/trees/" in path:
            repo = path.split("/")[2]
            tree = [{"type": "blob", "path": p} for p in self.files.get(repo, {})]
            return json.dumps({"tree": [*tree, {"type": "tree", "path": "src"}]})
        if "/commits/" in path:
            repo, ref = path.split("/")[2], path.split("/commits/")[1]
            if f"{repo}@{ref}" not in self.commits:
                raise nd.GhError("HTTP 404")
            sha, when = self.commits[f"{repo}@{ref}"]
            return json.dumps({"sha": sha, "commit": {"committer": {"date": iso(when)}}})
        if "/actions/workflows/ci.yml/runs" in path:
            repo = path.split("/")[2]
            count = int(path.rsplit("per_page=", 1)[1])
            return json.dumps({"workflow_runs": self.runs.get(repo, [])[:count]})
        match = re.search(r"repos/Kronuz/([^/]+)/actions/runs/(\d+)$", path)
        if match:
            return json.dumps(self.poll(match.group(1), int(match.group(2))))
        raise AssertionError(f"unexpected call {args}")

    def repo_page(self, args: Sequence[str]) -> str:
        cursor = next((a.split("=", 1)[1] for a in args if a.startswith("cursor=")), "0")
        index = int(cursor)
        size = max(1, len(self.repos) // self.pages)
        nodes = self.repos[index * size : (index + 1) * size if index + 1 < self.pages else None]
        info = {"hasNextPage": index + 1 < self.pages, "endCursor": str(index + 1)}
        page = {"pageInfo": info, "nodes": nodes}
        return json.dumps({"data": {"repositoryOwner": {"repositories": page}}})

    def blobs(self, query: str) -> str:
        name = next(a for a in self.calls[-1] if a.startswith("name=")).split("=", 1)[1]
        found = re.findall(r"f(\d+): object\(expression: (\"(?:[^\"\\]|\\.)*\")\)", query)
        repo: dict[str, Any] = {}
        for index, expression in found:
            path = json.loads(expression).split(":", 1)[1]
            repo[f"f{index}"] = {"text": self.files[name][path]}
        return json.dumps({"data": {"repository": repo}})

    def workflow_run(self, args: Sequence[str]) -> str:
        repo = args[args.index("-R") + 1].split("/")[1]
        assert "nightly=true" in args
        assert args[args.index("--ref") + 1] in ("main", "master")
        if repo in self.fail_dispatch:
            raise nd.GhError("HTTP 422")
        self.next_id += 1
        run_id = self.next_id
        self.owner[run_id] = repo
        self.order.append(repo)
        self.times.append((self.clock.time() if self.clock else NOW) - NOW)
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)
        created = self.clock.time() if self.clock else NOW
        self.add_run(repo, run_id, SHA, "", created)
        if self.print_url:
            return f"https://github.com/Kronuz/{repo}/actions/runs/{run_id}\n"
        return ""

    def poll(self, repo: str, run_id: int) -> dict[str, Any]:
        self.polls[run_id] = self.polls.get(run_id, 0) + 1
        run = next(r for r in self.runs[repo] if r["id"] == run_id)
        if self.polls[run_id] >= self.finish and run["status"] != "completed":
            run["status"] = "completed"
            run["conclusion"] = self.conclusion.get(repo, "success")
            self.in_flight -= 1
        return run


class FakeClock(nd.Clock):
    def __init__(self) -> None:
        self.now = NOW

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def make(fake: Fake | None = None) -> tuple[nd.Github, Fake, FakeClock]:
    clock = FakeClock()
    fake = fake or Fake(clock)
    fake.clock = clock
    return nd.Github("Kronuz", fake, clock), fake, clock


def silent(_: str) -> None:
    return


class ParseDepsTest(unittest.TestCase):
    def names(self, text: str) -> list[tuple[str, str]]:
        return [(d.name, d.ref) for d in nd.parse_deps(text)]

    def test_pinned_by_sha_or_version_does_not_count(self) -> None:
        text = f"""
        FetchContent_Declare(v GIT_REPOSITORY https://github.com/Kronuz/v.git GIT_TAG {SHA})
        FetchContent_Declare(x GIT_REPOSITORY https://github.com/Kronuz/x.git GIT_TAG abc1234)
        FetchContent_Declare(y GIT_REPOSITORY https://github.com/Kronuz/y.git GIT_TAG v1.2.0)
        """
        self.assertEqual(self.names(text), [])

    def test_moving_refs(self) -> None:
        text = """
        FetchContent_Declare(a GIT_REPOSITORY https://github.com/Kronuz/a.git GIT_TAG main)
        FetchContent_Declare(
          b
          GIT_TAG        "master"
          GIT_REPOSITORY "https://github.com/Kronuz/b"
        )
        FetchContent_Declare(c GIT_REPOSITORY git@github.com:Kronuz/c.git)
        FetchContent_Declare(d GIT_REPOSITORY https://github.com/Kronuz/d.git GIT_TAG ${d_ref})
        ExternalProject_Add(e GIT_REPOSITORY https://github.com/Kronuz/e.git GIT_TAG feature/x)
        """
        self.assertEqual(
            self.names(text),
            [
                ("a", "main"),
                ("b", "master"),
                ("c", "HEAD"),
                ("d", "HEAD"),
                ("e", "feature/x"),
            ],
        )

    def test_ignores_comments_other_owners_and_other_calls(self) -> None:
        text = f"""
        # FetchContent_Declare(a GIT_REPOSITORY https://github.com/Kronuz/a.git GIT_TAG main)
        FetchContent_Declare(g GIT_REPOSITORY https://github.com/google/googletest.git GIT_TAG main)
        FetchContent_Declare(k GIT_REPOSITORY https://github.com/Kronuz/k.git GIT_TAG main) # tip
        message(STATUS "GIT_REPOSITORY https://github.com/Kronuz/m.git GIT_TAG main")
        FetchContent_Declare(p GIT_REPOSITORY https://github.com/Kronuz/p.git GIT_TAG {SHA})
        """
        self.assertEqual(self.names(text), [("k", "main")])

    def test_nested_parentheses_in_a_call(self) -> None:
        text = """
        FetchContent_Declare(n
          GIT_REPOSITORY https://github.com/Kronuz/n.git
          PATCH_COMMAND $<IF:$<BOOL:1>,echo (x),true>
          GIT_TAG main)
        """
        self.assertEqual(self.names(text), [("n", "main")])

    def test_cmake_paths(self) -> None:
        for path, expect in (
            ("CMakeLists.txt", True),
            ("cmake/deps.cmake", True),
            ("tests/CMakeLists.txt", True),
            ("build/_deps/CMakeLists.txt", False),
            ("build-rel/CMakeLists.txt", False),
            (".github/foo.cmake", False),
            ("src/main.cpp", False),
        ):
            self.assertEqual(nd.is_cmake_path(path), expect, path)

    def test_the_caller_and_the_input(self) -> None:
        self.assertTrue(nd.calls_shared_workflow(ENROLLED_CI))
        self.assertFalse(nd.calls_shared_workflow(OTHER_CI))
        self.assertFalse(nd.calls_shared_workflow("# uses: " + nd.CALLER))
        self.assertTrue(nd.has_nightly_input(ENROLLED_CI))
        self.assertFalse(nd.has_nightly_input(OLD_CI))


class ParseFuzzTest(unittest.TestCase):
    def test_mutated_input_never_raises_and_only_yields_moving_refs(self) -> None:
        seed = (
            "FetchContent_Declare(a GIT_REPOSITORY https://github.com/Kronuz/a.git GIT_TAG main)\n"
            f"FetchContent_Declare(\n b\n GIT_TAG {SHA}\n"
            " GIT_REPOSITORY git@github.com:Kronuz/b\n)\n"
            'ExternalProject_Add(c GIT_TAG ${x} GIT_REPOSITORY "https://github.com/Kronuz/c")\n'
        )
        rng = random.Random(7)
        alphabet = '()#"$<>{}\n ;GIT_TAGREPOSITORYmain0123abcdef/.:@'
        for _ in range(3000):
            chars = list(seed)
            for _ in range(rng.randint(1, 8)):
                at = rng.randrange(len(chars) + 1)
                if rng.random() < 0.5 and chars:
                    del chars[min(at, len(chars) - 1)]
                else:
                    chars.insert(at, rng.choice(alphabet))
            for dep in nd.parse_deps("".join(chars)):
                self.assertFalse(nd.PINNED.fullmatch(dep.ref), dep)
                self.assertTrue(dep.name and dep.ref)


class DecideTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = nd.Repo("lib", "main", "b" * 40, ENROLLED_CI)
        self.commits: dict[str, nd.Commit | None] = {}
        self.asked: list[str] = []

    def head(self, name: str, ref: str) -> nd.Commit | None:
        self.asked.append(f"{name}@{ref}")
        return self.commits.get(f"{name}@{ref}")

    def prior(
        self,
        status: str = "completed",
        conclusion: str = "success",
        head: str = "b" * 40,
        age: float = DAY,
    ) -> nd.Run:
        return nd.Run(7, head, status, conclusion, NOW - age)

    def decide(self, last: nd.Run | None, tracked: Sequence[nd.Dep] = ()) -> nd.Decision:
        return nd.decide(self.repo, last, tracked, self.head, NOW)

    def test_no_run_dispatches(self) -> None:
        d = self.decide(None)
        self.assertEqual((d.dispatch, d.reason), (True, "no earlier nightly"))

    def test_failed_run_dispatches_whatever_the_head(self) -> None:
        for conclusion in ("failure", "cancelled", "timed_out"):
            d = self.decide(self.prior(conclusion=conclusion))
            self.assertEqual((d.dispatch, d.reason), (True, f"last nightly 7 ended {conclusion}"))

    def test_running_run_skips_until_it_is_stale(self) -> None:
        d = self.decide(self.prior(status="in_progress", conclusion="", age=3600))
        self.assertEqual((d.dispatch, d.reason), (False, "run 7 is still in_progress"))
        d = self.decide(self.prior(status="queued", conclusion="", age=13 * 3600))
        self.assertEqual((d.dispatch, d.reason), (True, "run 7 never finished (queued)"))

    def test_head_moved_dispatches(self) -> None:
        d = self.decide(self.prior(head="c" * 40))
        self.assertEqual((d.dispatch, d.reason), (True, "head moved ccccccc -> bbbbbbb"))

    def test_unchanged_skips_and_asks_nothing_without_deps(self) -> None:
        d = self.decide(self.prior())
        self.assertEqual((d.dispatch, d.reason), (False, "unchanged since run 7 (head bbbbbbb)"))
        self.assertEqual(self.asked, [])

    def test_dependency_commit_after_the_run_dispatches(self) -> None:
        self.commits["dep@main"] = nd.Commit("d" * 40, NOW - DAY + 60)
        d = self.decide(self.prior(), [nd.Dep("dep", "main")])
        self.assertEqual((d.dispatch, d.reason), (True, "dependency dep@main moved to ddddddd"))

    def test_dependency_commit_before_the_run_skips(self) -> None:
        self.commits["dep@main"] = nd.Commit("d" * 40, NOW - DAY - 60)
        self.commits["two@HEAD"] = nd.Commit("e" * 40, NOW - 5 * DAY)
        d = self.decide(self.prior(), [nd.Dep("dep", "main"), nd.Dep("two", "HEAD")])
        self.assertEqual(
            (d.dispatch, d.reason),
            (False, "unchanged since run 7 (head bbbbbbb, 2 moving deps unchanged)"),
        )
        self.assertEqual(self.asked, ["dep@main", "two@HEAD"])

    def test_unresolved_dependency_dispatches(self) -> None:
        d = self.decide(self.prior(), [nd.Dep("gone", "main")])
        self.assertEqual((d.dispatch, d.reason), (True, "dependency gone@main does not resolve"))


def cmake_for(*deps: str) -> dict[str, str]:
    body = "\n".join(
        f"FetchContent_Declare({n} GIT_REPOSITORY https://github.com/Kronuz/{n}.git GIT_TAG {t})"
        for n, t in (dep.split(":") for dep in deps)
    )
    return {"CMakeLists.txt": body, "src/x.cpp": "int main() {}"}


class TrackerTest(unittest.TestCase):
    def test_follows_moving_edges_through_pinned_and_cycles(self) -> None:
        github, fake, _ = make()
        for name in ("app", "mid", "leaf", "ring", "pin"):
            fake.add_repo(name, ENROLLED_CI)
        fake.files["app"] = cmake_for("mid:main", f"pin:{SHA}", "ring:main")
        fake.files["mid"] = cmake_for("leaf:master")
        fake.files["leaf"] = cmake_for()
        fake.files["ring"] = cmake_for("app:main")  # a cycle
        fake.files["pin"] = cmake_for("never:main")  # behind a pin: not followed
        tracker = nd.Tracker(github, github.repos())
        got = [(d.name, d.ref) for d in tracker.tracked("app")]
        self.assertEqual(got, [("leaf", "master"), ("mid", "main"), ("ring", "main")])

    def test_unknown_dependency_is_a_leaf_and_files_are_read_once(self) -> None:
        github, fake, _ = make()
        fake.add_repo("app", ENROLLED_CI)
        fake.files["app"] = cmake_for("outside:main")
        tracker = nd.Tracker(github, github.repos())
        self.assertEqual([(d.name, d.ref) for d in tracker.tracked("app")], [("outside", "main")])
        before = len(fake.calls)
        tracker.tracked("app")
        self.assertEqual(len(fake.calls), before)


class PlanTest(unittest.TestCase):
    def build(self) -> tuple[nd.Github, Fake, FakeClock]:
        github, fake, clock = make()
        fake.pages = 3
        head = "b" * 40
        fake.add_repo("fresh", ENROLLED_CI, head)  # no run yet
        fake.add_repo("same", ENROLLED_CI, head)  # built this head
        fake.add_repo("moved", ENROLLED_CI, head)  # head moved
        fake.add_repo("broke", ENROLLED_CI, head)  # last nightly failed
        fake.add_repo("drift", ENROLLED_CI, head)  # a moving dep changed
        fake.add_repo("calm", ENROLLED_CI, head)  # a moving dep did not
        fake.add_repo("old-ci", OLD_CI, head)  # not enrolled yet
        fake.add_repo("other", OTHER_CI, head)  # does not call the shared workflow
        fake.add_repo("noci", "", head)
        fake.add_run("same", 1, head, "success", NOW - DAY)
        fake.add_run("moved", 2, "c" * 40, "success", NOW - DAY)
        fake.add_run("broke", 3, head, "failure", NOW - DAY)
        fake.add_run("drift", 4, head, "success", NOW - DAY)
        fake.add_run("calm", 5, head, "success", NOW - DAY)
        fake.files["drift"] = cmake_for("lib:main")
        fake.files["calm"] = cmake_for("lib:main", f"pinned:{SHA}")
        fake.files["same"] = cmake_for()
        fake.commits["lib@main"] = ("e" * 40, NOW - 60)
        return github, fake, clock

    def test_discovery_and_decisions(self) -> None:
        github, fake, _ = self.build()
        # `calm` tracks the same dep but its run is newer than the dep's commit
        fake.runs["calm"][0]["created_at"] = iso(NOW)
        lines: list[str] = []
        decisions, skipped = nd.plan(github, github.repos(), [], lines.append)
        self.assertEqual(
            [(d.repo.name, d.reason) for d in decisions],
            [
                ("fresh", "no earlier nightly"),
                ("moved", "head moved ccccccc -> bbbbbbb"),
                ("broke", "last nightly 3 ended failure"),
                ("drift", "dependency lib@main moved to eeeeeee"),
            ],
        )
        self.assertEqual(
            {(s.repo, s.reason) for s in skipped},
            {
                ("calm", "unchanged since run 5 (head bbbbbbb, 1 moving deps unchanged)"),
                ("old-ci", "ci.yml has no nightly input (nightly_enroll.py)"),
                ("same", "unchanged since run 1 (head bbbbbbb)"),
            },
        )
        self.assertEqual(len(lines), 7)
        self.assertTrue(lines[0].startswith("dispatch "))
        self.assertEqual(sum(line.startswith("skip") for line in lines), 3)

    def test_only_limits_the_repositories(self) -> None:
        github, _, _ = self.build()
        decisions, skipped = nd.plan(github, github.repos(), ["fresh", "same"], silent)
        self.assertEqual([d.repo.name for d in decisions], ["fresh"])
        self.assertEqual([s.repo for s in skipped], ["same"])

    def test_paging(self) -> None:
        github, fake, _ = self.build()
        names = [repo.name for repo in github.repos()]
        self.assertEqual(len(names), 9)
        self.assertEqual(sum("cursor=1" in c for c in fake.calls), 1)


class PaceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.github, self.fake, self.clock = make()
        self.logs: list[str] = []

    def decisions(self, count: int) -> list[nd.Decision]:
        repos = [nd.Repo(f"r{i:02}", "main", SHA, ENROLLED_CI) for i in range(count)]
        return [nd.Decision(repo, True, "why") for repo in repos]

    def pace(self, **changes: float) -> nd.Pace:
        values = {"parallel": 3, "stop_after": 3600.0, "wait_until": 7200.0, "poll": 60.0}
        values.update(changes)
        return nd.Pace(
            int(values["parallel"]), values["stop_after"], values["wait_until"], values["poll"]
        )

    def test_never_more_than_parallel_in_flight_and_all_finish(self) -> None:
        self.fake.finish = 3
        out = nd.run_paced(self.github, self.decisions(8), self.pace(), self.logs.append)
        self.assertEqual(self.fake.peak, 3)
        self.assertEqual(sorted(o.repo for o in out), [f"r{i:02}" for i in range(8)])
        self.assertEqual({o.result for o in out}, {"success"})
        self.assertTrue(all(o.run_id and o.reason == "why" for o in out))
        self.assertEqual(self.fake.order, [f"r{i:02}" for i in range(8)])

    def test_next_starts_when_one_finishes_not_when_all_do(self) -> None:
        self.fake.finish = 1
        self.fake.conclusion["r00"] = "failure"
        out = nd.run_paced(self.github, self.decisions(4), self.pace(parallel=2), self.logs.append)
        started = [line for line in self.logs if line.startswith("dispatched")]
        self.assertEqual(len(started), 4)
        # the first two start together; after the first poll both finished, then two more
        self.assertEqual(self.fake.peak, 2)
        self.assertEqual({o.repo: o.result for o in out}["r00"], "failure")
        self.assertEqual(self.clock.now - NOW, 120)

    def test_parallel_one_is_serial(self) -> None:
        self.fake.finish = 2
        nd.run_paced(self.github, self.decisions(3), self.pace(parallel=1), self.logs.append)
        self.assertEqual(self.fake.peak, 1)

    def test_stop_after_reports_what_remained(self) -> None:
        self.fake.finish = 5
        out = nd.run_paced(
            self.github, self.decisions(9), self.pace(stop_after=600, parallel=2), self.logs.append
        )
        results = {o.repo: o.result for o in out}
        started = [r for r, v in results.items() if v == "success"]
        left = [r for r, v in results.items() if v == "not dispatched (time)"]
        self.assertEqual(len(started) + len(left), 9)
        self.assertEqual(started, sorted(started))
        self.assertTrue(left)
        self.assertEqual(left, sorted(left))
        self.assertTrue(set(started).isdisjoint(left))
        self.assertTrue(all(t < 600 for t in self.fake.times))
        self.assertEqual(len(self.fake.times), len(started))

    def test_wait_until_reports_runs_still_going(self) -> None:
        self.fake.finish = 10**6
        out = nd.run_paced(
            self.github, self.decisions(5), self.pace(wait_until=300), self.logs.append
        )
        self.assertEqual(len(out), 3)
        self.assertEqual({o.result for o in out}, {"running (not awaited)"})
        self.assertEqual(self.fake.order, ["r00", "r01", "r02"])

    def test_failed_dispatch_is_recorded_and_the_rest_go_on(self) -> None:
        self.fake.fail_dispatch = {"r01"}
        out = nd.run_paced(self.github, self.decisions(3), self.pace(), self.logs.append)
        results = {o.repo: (o.run_id is not None, o.result) for o in out}
        self.assertEqual(results["r01"], (False, "dispatch failed"))
        self.assertEqual(results["r00"], (True, "success"))
        self.assertEqual(results["r02"], (True, "success"))

    def test_run_id_found_by_listing_when_gh_prints_no_url(self) -> None:
        self.fake.print_url = False
        out = nd.run_paced(self.github, self.decisions(2), self.pace(), self.logs.append)
        self.assertEqual({o.result for o in out}, {"success"})
        self.assertEqual(len({o.run_id for o in out}), 2)

    def test_poll_error_keeps_waiting(self) -> None:
        real = self.fake.poll
        failures = [1]

        def flaky(repo: str, run_id: int) -> dict[str, Any]:
            if failures:
                failures.pop()
                raise nd.GhError("HTTP 502")
            return real(repo, run_id)

        self.fake.poll = flaky  # type: ignore[method-assign]
        out = nd.run_paced(self.github, self.decisions(1), self.pace(), self.logs.append)
        self.assertEqual([o.result for o in out], ["success"])
        self.assertTrue(any(line.startswith("poll failed") for line in self.logs))


class TokenTest(unittest.TestCase):
    def check(self, expiry: str | None, reject: bool = False) -> tuple[bool, list[str]]:
        github, fake, _ = make()
        fake.expiry, fake.reject_token = expiry, reject
        lines: list[str] = []
        return nd.check_token(github, lines.append), lines

    def test_no_header_means_no_expiration(self) -> None:
        self.assertEqual(self.check(None), (True, ["Token: no expiration"]))

    def test_far_expiry_is_only_noted(self) -> None:
        ok, lines = self.check("2027-01-03 06:17:00 UTC")
        self.assertTrue(ok)
        self.assertEqual(lines, ["Token: expires 2027-01-03 (in 61 days)"])

    def test_thirty_days_exactly_is_not_a_warning(self) -> None:
        ok, lines = self.check("2026-12-03 06:17:00 UTC")
        self.assertEqual((ok, lines), (True, ["Token: expires 2026-12-03 (in 30 days)"]))

    def test_under_thirty_days_warns_with_the_date_and_the_runbook(self) -> None:
        ok, lines = self.check("2026-11-11 00:00:00 UTC")
        self.assertTrue(ok)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("::warning::The token expires 2026-11-11 (in 8 days)"))
        self.assertIn(nd.RUNBOOK, lines[0])

    def test_under_seven_days_or_expired_fails(self) -> None:
        for expiry in (
            "2026-11-09 06:17:00 UTC",
            "2026-11-03 06:17:01 UTC",
            "2026-10-01 00:00:00 UTC",
        ):
            ok, lines = self.check(expiry)
            self.assertFalse(ok, expiry)
            self.assertTrue(lines[0].startswith("::error::The token expires"), lines)
            self.assertIn(nd.RUNBOOK, lines[0])

    def test_rejected_token_fails(self) -> None:
        ok, lines = self.check(None, reject=True)
        self.assertFalse(ok)
        self.assertTrue(lines[0].startswith("::error::The token is rejected"))
        self.assertIn("401", lines[0])

    def test_main_stops_before_reading_or_dispatching(self) -> None:
        for expiry, reject in (("2026-11-05 00:00:00 UTC", False), (None, True)):
            _, fake, _ = make()
            fake.expiry, fake.reject_token = expiry, reject
            fake.add_repo("fresh", ENROLLED_CI)
            code, out, _ = MainTest().run_main([], fake)
            self.assertEqual(code, 1)
            self.assertIn("::error::", out)
            self.assertEqual([c for c in fake.calls if c[0] != "api" or c[1] != "-i"], [])

    def test_main_warns_and_goes_on(self) -> None:
        _, fake, _ = make()
        fake.expiry = "2026-11-20 00:00:00 UTC"
        fake.add_repo("fresh", ENROLLED_CI)
        fake.files["fresh"] = cmake_for()
        code, out, _ = MainTest().run_main(["--dry-run"], fake)
        self.assertEqual(code, 0)
        self.assertIn("::warning::The token expires 2026-11-20", out)
        self.assertIn("dry run", out)


class MainTest(unittest.TestCase):
    def run_main(self, argv: list[str], fake: Fake | None = None) -> tuple[int, str, Fake]:
        github, fake, _ = make(fake)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = nd.main(argv, github)
        return code, out.getvalue(), fake

    def populated(self) -> Fake:
        _, fake, _ = make()
        fake.add_repo("fresh", ENROLLED_CI)
        fake.add_repo("same", ENROLLED_CI)
        fake.add_run("same", 1, SHA, "success", NOW - DAY)
        fake.files["fresh"] = cmake_for()
        fake.files["same"] = cmake_for()
        return fake

    def test_dry_run_dispatches_nothing_and_prints_the_table(self) -> None:
        code, out, fake = self.run_main(["--dry-run"], self.populated())
        self.assertEqual(code, 0)
        self.assertFalse(any(call[0] == "workflow" for call in fake.calls))
        table = out.split("\n\n", 1)[1].splitlines()
        self.assertEqual(table[0].split(), ["repo", "reason", "run", "result"])
        self.assertEqual(table[1].split(), ["fresh", "no", "earlier", "nightly", "-", "dry", "run"])
        self.assertEqual(table[2].split()[-1], "skipped")

    def test_real_run_and_exit_status(self) -> None:
        fake = self.populated()
        code, out, fake = self.run_main(["--poll", "1"], fake)
        self.assertEqual(code, 0)
        self.assertEqual(fake.order, ["fresh"])
        self.assertRegex(out, r"fresh\s+no earlier nightly\s+1001\s+success")
        fake = self.populated()
        fake.conclusion["fresh"] = "failure"
        code, _, _ = self.run_main(["--poll", "1"], fake)
        self.assertEqual(code, 1)

    def test_unknown_repository_and_bad_parallel(self) -> None:
        self.assertEqual(self.run_main(["--dry-run", "--only", "nope"], self.populated())[0], 2)
        self.assertEqual(self.run_main(["--parallel", "0"], self.populated())[0], 2)

    def test_gh_failure_is_an_error_not_a_skip(self) -> None:
        def boom(args: Sequence[str]) -> str:
            if args[1] == "-i":
                return "HTTP/2.0 200 OK\n\n{}"
            raise nd.GhError("HTTP 500")

        github = nd.Github("Kronuz", boom, FakeClock())
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(nd.main(["--dry-run"], github), 2)

    def test_table_and_markdown(self) -> None:
        rows = [
            nd.Outcome("b", "unchanged", None, "skipped"),
            nd.Outcome("a", "no earlier nightly", 42, "success"),
        ]
        lines = nd.table(rows).splitlines()
        self.assertEqual([line.split()[0] for line in lines], ["repo", "a", "b"])
        md = nd.markdown(rows, "Kronuz")
        self.assertIn("[42](https://github.com/Kronuz/a/actions/runs/42)", md)


if __name__ == "__main__":
    unittest.main()
