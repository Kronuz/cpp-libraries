#!/usr/bin/env python3
"""Central nightly CI dispatcher for the Kronuz repositories.

It finds the owner's repositories whose .github/workflows/ci.yml calls the shared CMake workflow
(cmake.yml@main), decides which of them changed since their last nightly, and runs ci.yml in
those with `nightly=true` (the Linux-only matrix), at most --parallel at a time, one after
another as runs finish. It prints the reason for every dispatch and skip, then a summary table.

A repository is dispatched when
  1. it has no earlier workflow_dispatch run of ci.yml on its default branch, or the last one
     did not succeed (or is a stale run that never finished),
  2. its default-branch head differs from the head the last run built, or
  3. a Kronuz dependency it fetches at a moving ref (GIT_TAG main, a branch, no GIT_TAG), found
     in its CMake files and, through moving refs, in its dependencies' CMake files, has a commit
     newer than the start of that run.
A dependency pinned by commit or by a version tag cannot drift and is not followed. A repository
whose ci.yml does not take the `nightly` input yet (tools/nightly_enroll.py adds it) is skipped.

Dispatch stops at --stop-after minutes (the rest is reported as not dispatched); runs still in
flight at --wait-until minutes are reported as running. Reads and dispatches use `gh`, so
GH_TOKEN must reach every repository (Actions read/write, Contents read).

  nightly_dispatch.py [--dry-run] [--parallel N] [--only NAME[,NAME...]] [--owner OWNER]

Exit status: 0 ok; 1 a dispatched run did not succeed, a dispatch failed, or work was left over;
2 unusable input or a failed read.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CALLER = "Kronuz/cpp-libraries/.github/workflows/cmake.yml@main"
WORKFLOW = "ci.yml"
STALE_SECONDS = 12 * 3600
FILES_PER_QUERY = 25

Call = Callable[[Sequence[str]], str]
Json = Any  # decoded GitHub API JSON


class GhError(RuntimeError):
    """A `gh` command failed."""


def gh_call(args: Sequence[str]) -> str:
    """Runs `gh ARGS` and returns its stdout."""
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise GhError(f"gh {' '.join(args[:2])}: {detail}")
    return proc.stdout


def parse_time(stamp: str) -> float:
    """Seconds since the epoch of an ISO 8601 stamp such as 2026-11-03T06:17:00Z."""
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


@dataclass(frozen=True)
class Repo:
    name: str
    branch: str
    head: str
    ci: str


@dataclass(frozen=True)
class Run:
    id: int
    head_sha: str
    status: str
    conclusion: str
    created: float


@dataclass(frozen=True)
class Commit:
    sha: str
    date: float


@dataclass(frozen=True)
class Dep:
    name: str
    ref: str  # "HEAD" is the dependency's default branch


@dataclass(frozen=True)
class Decision:
    repo: Repo
    dispatch: bool
    reason: str


@dataclass(frozen=True)
class Outcome:
    repo: str
    reason: str
    run_id: int | None
    result: str


class Clock:
    """Wall time and sleeping; tests replace it."""

    def time(self) -> float:
        return time.time()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


REPOS_QUERY = """
query($owner: String!, $cursor: String) {
  repositoryOwner(login: $owner) {
    repositories(first: 50, after: $cursor, isArchived: false, isFork: false,
                 ownerAffiliations: OWNER, orderBy: {field: NAME, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        defaultBranchRef { name target { oid } }
        ci: object(expression: "HEAD:.github/workflows/ci.yml") { ... on Blob { text } }
      }
    }
  }
}
"""


class Github:
    """The reads and writes the dispatcher needs, all through one `gh` entry point."""

    def __init__(self, owner: str, call: Call = gh_call, clock: Clock | None = None) -> None:
        self.owner = owner
        self.call = call
        self.clock = clock or Clock()

    def api(self, path: str) -> Json:
        return json.loads(self.call(["api", path]))

    def graphql(self, query: str, **variables: str) -> Json:
        args = ["api", "graphql", "-f", f"query={query}"]
        for key, value in variables.items():
            args += ["-f", f"{key}={value}"]
        reply = json.loads(self.call(args))
        if reply.get("errors"):
            raise GhError(f"graphql: {reply['errors'][0].get('message', reply['errors'])}")
        return reply["data"]

    def repos(self) -> list[Repo]:
        """The owner's non-archived, non-fork repositories with a default branch."""
        found: list[Repo] = []
        cursor = ""
        while True:
            variables = {"owner": self.owner}
            if cursor:
                variables["cursor"] = cursor
            page = self.graphql(REPOS_QUERY, **variables)["repositoryOwner"]["repositories"]
            for node in page["nodes"]:
                branch = node["defaultBranchRef"]
                if branch is None:
                    continue
                text = (node["ci"] or {}).get("text") or ""
                found.append(Repo(node["name"], branch["name"], branch["target"]["oid"], text))
            if not page["pageInfo"]["hasNextPage"]:
                return found
            cursor = page["pageInfo"]["endCursor"]

    def cmake_files(self, repo: str, ref: str) -> list[str]:
        """The text of every CMakeLists.txt and *.cmake in the repository at ref."""
        tree = self.api(f"repos/{self.owner}/{repo}/git/trees/{ref}?recursive=1")
        if tree.get("truncated"):
            print(f"warning: {repo}: file tree truncated", file=sys.stderr)
        paths = [
            entry["path"]
            for entry in tree["tree"]
            if entry["type"] == "blob" and is_cmake_path(entry["path"])
        ]
        texts: list[str] = []
        for start in range(0, len(paths), FILES_PER_QUERY):
            chunk = paths[start : start + FILES_PER_QUERY]
            fields = " ".join(
                f"f{i}: object(expression: {json.dumps(ref + ':' + path)}) "
                "{ ... on Blob { text } }"
                for i, path in enumerate(chunk)
            )
            query = (
                "query($owner: String!, $name: String!) "
                f"{{ repository(owner: $owner, name: $name) {{ {fields} }} }}"
            )
            data = self.graphql(query, owner=self.owner, name=repo)["repository"]
            texts += [(data[f"f{i}"] or {}).get("text") or "" for i in range(len(chunk))]
        return texts

    def head_commit(self, repo: str, ref: str) -> Commit | None:
        """The commit a ref points to now, or None when it does not resolve."""
        try:
            data = self.api(f"repos/{self.owner}/{repo}/commits/{ref}")
        except GhError as error:
            print(f"warning: {repo}@{ref}: {error}", file=sys.stderr)
            return None
        return Commit(data["sha"], parse_time(data["commit"]["committer"]["date"]))

    def runs(self, repo: str, branch: str, count: int = 5) -> list[Run]:
        """The newest workflow_dispatch runs of ci.yml on the branch, newest first."""
        path = (
            f"repos/{self.owner}/{repo}/actions/workflows/{WORKFLOW}/runs"
            f"?event=workflow_dispatch&branch={branch}&per_page={count}"
        )
        return [make_run(item) for item in self.api(path)["workflow_runs"]]

    def run(self, repo: str, run_id: int) -> Run:
        return make_run(self.api(f"repos/{self.owner}/{repo}/actions/runs/{run_id}"))

    def dispatch(self, repo: str, branch: str) -> int:
        """Starts ci.yml with nightly=true and returns the new run's id."""
        known = {run.id for run in self.runs(repo, branch)}
        started = self.clock.time()
        out = self.call(
            [
                "workflow",
                "run",
                WORKFLOW,
                "-R",
                f"{self.owner}/{repo}",
                "--ref",
                branch,
                "-f",
                "nightly=true",
            ]
        )
        match = re.search(r"/actions/runs/(\d+)", out)
        if match:
            return int(match.group(1))
        for _ in range(12):  # an older gh prints no URL: find the run it created
            self.clock.sleep(5)
            for run in self.runs(repo, branch):
                if run.id not in known and run.created >= started - 60:
                    return run.id
        raise GhError(f"{repo}: dispatched, but no new run appeared")


def make_run(item: dict[str, Any]) -> Run:
    return Run(
        int(item["id"]),
        item["head_sha"],
        item["status"],
        item.get("conclusion") or "",
        parse_time(item["created_at"]),
    )


def is_cmake_path(path: str) -> bool:
    parts = path.split("/")
    if any(part.startswith((".", "build", "_deps")) for part in parts[:-1]):
        return False
    return parts[-1] == "CMakeLists.txt" or parts[-1].endswith(".cmake")


def calls_shared_workflow(ci: str) -> bool:
    return re.search(rf"^\s*uses:\s*{re.escape(CALLER)}\s*(?:#.*)?$", ci, re.M) is not None


def has_nightly_input(ci: str) -> bool:
    return re.search(r"^\s+nightly:", ci, re.M) is not None


CMAKE_CALL = re.compile(r"\b(?:FetchContent_Declare|ExternalProject_Add)\s*\(", re.I)
GIT_REPOSITORY = re.compile(
    r"GIT_REPOSITORY\s+\"?(?:https://github\.com/|git@github\.com:)Kronuz/([\w.-]+?)(?:\.git)?\"?(?=\s|$)"
)
GIT_TAG = re.compile(r"GIT_TAG\s+\"?([^\s\")]+)\"?")
PINNED = re.compile(r"[0-9a-f]{7,40}|v?\d+(?:\.\d+)+\S*", re.I)


def call_bodies(text: str) -> list[str]:
    """The argument text of every FetchContent_Declare and ExternalProject_Add call."""
    text = re.sub(r"(?m)#.*$", "", text)
    bodies: list[str] = []
    for match in CMAKE_CALL.finditer(text):
        depth = 1
        end = match.end()
        while end < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[end], 0)
            end += 1
        bodies.append(text[match.end() : end - 1])
    return bodies


def parse_deps(text: str) -> list[Dep]:
    """The Kronuz dependencies fetched at a moving ref; pinned ones cannot drift."""
    found: dict[tuple[str, str], Dep] = {}
    for body in call_bodies(text):
        repo = GIT_REPOSITORY.search(body)
        if repo is None:
            continue
        tag = GIT_TAG.search(body)
        ref = tag.group(1) if tag else "HEAD"
        if "$" in ref:
            ref = "HEAD"
        if PINNED.fullmatch(ref):
            continue
        found[(repo.group(1), ref)] = Dep(repo.group(1), ref)
    return list(found.values())


class Tracker:
    """The moving-ref dependencies of each repository, followed through moving refs."""

    def __init__(self, github: Github, repos: Sequence[Repo]) -> None:
        self.github = github
        self.repos = {repo.name: repo for repo in repos}
        self.edges: dict[str, list[Dep]] = {}

    def direct(self, name: str) -> list[Dep]:
        if name not in self.edges:
            repo = self.repos.get(name)
            deps: dict[tuple[str, str], Dep] = {}
            if repo is not None:
                for text in self.github.cmake_files(name, repo.branch):
                    for dep in parse_deps(text):
                        deps[(dep.name, dep.ref)] = dep
            self.edges[name] = list(deps.values())
        return self.edges[name]

    def tracked(self, name: str) -> list[Dep]:
        seen: dict[tuple[str, str], Dep] = {}
        todo = deque(self.direct(name))
        while todo:
            dep = todo.popleft()
            if (dep.name, dep.ref) in seen or dep.name == name:
                continue
            seen[(dep.name, dep.ref)] = dep
            todo.extend(self.direct(dep.name))
        return sorted(seen.values(), key=lambda dep: (dep.name, dep.ref))


def decide(
    repo: Repo,
    last: Run | None,
    tracked: Sequence[Dep],
    head_commit: Callable[[str, str], Commit | None],
    now: float,
) -> Decision:
    """Whether to dispatch the repository tonight, and why."""

    def go(reason: str) -> Decision:
        return Decision(repo, True, reason)

    if last is None:
        return go("no earlier nightly")
    if last.status != "completed":
        if now - last.created < STALE_SECONDS:
            return Decision(repo, False, f"run {last.id} is still {last.status}")
        return go(f"run {last.id} never finished ({last.status})")
    if last.conclusion != "success":
        return go(f"last nightly {last.id} ended {last.conclusion}")
    if last.head_sha != repo.head:
        return go(f"head moved {last.head_sha[:7]} -> {repo.head[:7]}")
    for dep in tracked:
        commit = head_commit(dep.name, dep.ref)
        if commit is None:
            return go(f"dependency {dep.name}@{dep.ref} does not resolve")
        if commit.date > last.created:
            return go(f"dependency {dep.name}@{dep.ref} moved to {commit.sha[:7]}")
    deps = f", {len(tracked)} moving deps unchanged" if tracked else ""
    return Decision(repo, False, f"unchanged since run {last.id} (head {repo.head[:7]}{deps})")


def plan(
    github: Github,
    repos: Sequence[Repo],
    only: Sequence[str],
    log: Callable[[str], None],
) -> tuple[list[Decision], list[Outcome]]:
    """Decides every repository that calls the shared workflow; returns decisions and skips."""
    tracker = Tracker(github, repos)
    commits: dict[tuple[str, str], Commit | None] = {}

    def head_commit(name: str, ref: str) -> Commit | None:
        if (name, ref) not in commits:
            commits[(name, ref)] = github.head_commit(name, ref)
        return commits[(name, ref)]

    decisions: list[Decision] = []
    skipped: list[Outcome] = []
    for repo in repos:
        if only and repo.name not in only:
            continue
        if not calls_shared_workflow(repo.ci):
            continue
        if not has_nightly_input(repo.ci):
            decision = Decision(repo, False, "ci.yml has no nightly input (nightly_enroll.py)")
        else:
            runs = github.runs(repo.name, repo.branch, 1)
            decision = decide(
                repo,
                runs[0] if runs else None,
                tracker.tracked(repo.name),
                head_commit,
                github.clock.time(),
            )
        verb = "dispatch" if decision.dispatch else "skip"
        log(f"{verb:8} {repo.name}: {decision.reason}")
        if decision.dispatch:
            decisions.append(decision)
        else:
            skipped.append(Outcome(repo.name, decision.reason, None, "skipped"))
    return decisions, skipped


@dataclass(frozen=True)
class Pace:
    parallel: int  # runs in flight
    stop_after: float  # seconds after which nothing new is dispatched
    wait_until: float  # seconds after which in-flight runs are no longer awaited
    poll: float  # seconds between polls


def run_paced(
    github: Github,
    decisions: Sequence[Decision],
    pace: Pace,
    log: Callable[[str], None],
) -> list[Outcome]:
    """Dispatches with at most `pace.parallel` runs in flight, the next as one finishes."""
    parallel, stop_after, wait_until, poll = (
        pace.parallel,
        pace.stop_after,
        pace.wait_until,
        pace.poll,
    )
    clock = github.clock
    begin = clock.time()
    queue = deque(decisions)
    flying: dict[int, Decision] = {}
    outcomes: list[Outcome] = []
    while True:
        elapsed = clock.time() - begin
        while queue and len(flying) < parallel and elapsed < stop_after:
            decision = queue.popleft()
            repo = decision.repo
            try:
                run_id = github.dispatch(repo.name, repo.branch)
            except GhError as error:
                log(f"dispatch failed {repo.name}: {error}")
                outcomes.append(Outcome(repo.name, decision.reason, None, "dispatch failed"))
                continue
            log(f"dispatched {repo.name}: run {run_id}")
            flying[run_id] = decision
        if elapsed >= stop_after:
            for decision in queue:
                outcomes.append(
                    Outcome(decision.repo.name, decision.reason, None, "not dispatched (time)")
                )
            queue.clear()
        if not flying:
            return outcomes
        if elapsed >= wait_until:
            for run_id, decision in flying.items():
                outcomes.append(
                    Outcome(decision.repo.name, decision.reason, run_id, "running (not awaited)")
                )
            return outcomes
        clock.sleep(poll)
        for run_id, decision in list(flying.items()):
            try:
                run = github.run(decision.repo.name, run_id)
            except GhError as error:
                log(f"poll failed {decision.repo.name} run {run_id}: {error}")
                continue
            if run.status == "completed":
                log(f"finished {decision.repo.name}: run {run_id} {run.conclusion}")
                outcomes.append(
                    Outcome(decision.repo.name, decision.reason, run_id, run.conclusion)
                )
                del flying[run_id]


def table(outcomes: Sequence[Outcome]) -> str:
    """The outcomes as an aligned text table, dispatched repositories first."""
    rows = [("repo", "reason", "run", "result")]
    for item in sorted(outcomes, key=lambda o: (o.result == "skipped", o.repo)):
        rows.append((item.repo, item.reason, str(item.run_id or "-"), item.result))
    widths = [max(len(row[col]) for row in rows) for col in range(4)]
    return "\n".join(
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip() for row in rows
    )


def markdown(outcomes: Sequence[Outcome], owner: str) -> str:
    lines = ["| repo | reason | run | result |", "| --- | --- | --- | --- |"]
    for item in sorted(outcomes, key=lambda o: (o.result == "skipped", o.repo)):
        run = (
            f"[{item.run_id}](https://github.com/{owner}/{item.repo}/actions/runs/{item.run_id})"
            if item.run_id
            else "-"
        )
        lines.append(f"| {item.repo} | {item.reason} | {run} | {item.result} |")
    return "\n".join(lines) + "\n"


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dispatch the nightly CI of the owner's changed repositories.",
        epilog="See the module docstring for the rules.",
    )
    parser.add_argument("--owner", default="Kronuz")
    parser.add_argument("--dry-run", action="store_true", help="decide and print, dispatch nothing")
    parser.add_argument("--parallel", type=int, default=3, help="runs in flight (default 3)")
    parser.add_argument("--only", default="", help="comma-separated repository names")
    parser.add_argument("--stop-after", type=float, default=270, help="minutes (default 270)")
    parser.add_argument("--wait-until", type=float, default=335, help="minutes (default 335)")
    parser.add_argument("--poll", type=float, default=60, help="seconds between polls")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None, github: Github | None = None) -> int:
    args = parse_args(argv)
    if args.parallel < 1:
        print("--parallel must be at least 1", file=sys.stderr)
        return 2
    github = github or Github(args.owner)

    def log(message: str) -> None:
        print(message, flush=True)

    only = [name for name in args.only.split(",") if name]
    try:
        repos = github.repos()
        missing = sorted(set(only) - {repo.name for repo in repos})
        if missing:
            print(f"unknown repositories: {', '.join(missing)}", file=sys.stderr)
            return 2
        decisions, skipped = plan(github, repos, only, log)
        if args.dry_run:
            outcomes = [Outcome(d.repo.name, d.reason, None, "dry run") for d in decisions]
        else:
            pace = Pace(args.parallel, args.stop_after * 60, args.wait_until * 60, args.poll)
            outcomes = run_paced(github, decisions, pace, log)
    except GhError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    outcomes += skipped
    print()
    print(table(outcomes))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(markdown(outcomes, args.owner))
    good = {"success", "skipped", "dry run"}
    return 0 if all(item.result in good for item in outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
