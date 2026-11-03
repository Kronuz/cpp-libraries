# Nightly CI

One workflow in this repository runs the nightly CI of every Kronuz repository that uses the
shared CMake workflow. The repositories have no schedule of their own.

## What runs when

- [`.github/workflows/nightly.yml`](../.github/workflows/nightly.yml) has the only cron, at
  06:17 UTC. It runs [`tools/nightly_dispatch.py`](../tools/nightly_dispatch.py).
- The script lists the owner's non-archived, non-fork repositories whose `.github/workflows/ci.yml`
  calls `cmake.yml@main`, and dispatches `ci.yml` with `nightly=true` in the ones that changed.
  A repository is dispatched when it has no earlier dispatched run, the last one did not succeed,
  its default branch moved since that run, or a Kronuz dependency it fetches at a moving ref
  (`GIT_TAG main`, a branch, no `GIT_TAG`) has a newer commit. A dependency pinned by commit or by
  version tag cannot change and does not count. The log gives the reason for every dispatch and skip.
- At most three repositories are in flight; the next starts when one finishes. Dispatch stops
  after 270 minutes and the rest is reported as not dispatched; the next night picks it up.
- `nightly=true` makes `cmake.yml` run the Linux jobs only: no macOS, no FreeBSD. Pushes and pull
  requests still run the whole matrix.

## Enrolling a repository

A repository joins by editing its `ci.yml` and pushing it to its default branch:

```sh
python3 tools/nightly_enroll.py ../some-repo      # a repository directory or a ci.yml
python3 tools/nightly_enroll.py --check ../repo*  # writes nothing; exit 1 when a file would change
```

It changes three things in `ci.yml`: the `schedule:` block goes, `workflow_dispatch:` gets
`inputs: nightly: { type: boolean, default: false }`, and the call of `cmake.yml@main` gets
`with: nightly: ${{ inputs.nightly || false }}`. It leaves an enrolled file alone and refuses
(exit 1, file untouched) a `ci.yml` of another shape. Until a repository is enrolled the
dispatcher skips it.

## Running it by hand

```sh
gh workflow run nightly.yml -R Kronuz/cpp-libraries -f dry_run=true
gh workflow run nightly.yml -R Kronuz/cpp-libraries -f only=bitpack,varint -f parallel=2
```

`dry_run=true` decides and prints, and dispatches nothing. `only` limits the run to the named
repositories (empty is all). `parallel` is the number in flight (default 3). Locally,
`python3 tools/nightly_dispatch.py --dry-run` does the same with your own `gh` login.

## Results

The job log prints one line per repository as it is decided, dispatched and finished. The same
table (repository, reason, run, result) ends the log and is the job summary on the run's page,
with a link to each dispatched run. The job fails when a dispatched run did not succeed, a dispatch
failed, or work was left over, and GitHub notifies the owner of a failed scheduled run.

## The token

The dispatcher needs the secret `NIGHTLY_DISPATCH_TOKEN` in this repository: `GITHUB_TOKEN` cannot
dispatch workflows in other repositories. It is a fine-grained personal access token with:

- Resource owner: `Kronuz`
- Repository access: all repositories
- Repository permissions: Actions read and write; Contents read-only (Metadata read-only is added
  automatically)
- An expiration date

At the start of every run the dispatcher reads the token's expiry. It prints a warning with the
date when fewer than 30 days remain, and fails the run when fewer than 7 remain or GitHub rejects
the token, so the failed scheduled run reaches the owner before dispatching stops.

### Renewing the token

1. On GitHub open Settings, Developer settings, Personal access tokens, Fine-grained tokens, and
   pick the token. Choose Regenerate token and a new expiration. The settings above stay.
2. Copy the new value, then store it:

   ```sh
   gh secret set NIGHTLY_DISPATCH_TOKEN -R Kronuz/cpp-libraries
   ```

   Paste the value at the prompt.
3. Check it: run `gh workflow run nightly.yml -R Kronuz/cpp-libraries -f dry_run=true` and read
   the `Token: expires ...` line at the top of the log.

When the token is lost, create a new one with the settings above and store it the same way.
