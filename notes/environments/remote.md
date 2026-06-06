# Remote / Managed-Agent Environment Rules

These rules apply whenever the agent is running in a remote or managed-agent context
(see [`../agents.md`](../agents.md) for how to detect this). They **supplement** the
universal rules in the repo-root [`AGENTS.md`](../../AGENTS.md) and **override** them on
conflict.

The principle: in a remote environment there is no human watching each step, so every
unit of work must be **traceable**, **reviewable**, and **verifiable** without anyone
needing to ask the agent what it did.

## Tracking system: GitHub issues

All issue tracking lives in **GitHub issues** on this repository. Do not introduce or
expect a local issue database, a sqlite tracker, or any other side-channel system.
GitHub issues are the durable record; the PR is how the work lands.

## Every unit of work has a GitHub issue

- Before starting work, ensure a GitHub issue exists that describes the change. If one
  doesn't, open one — title, short problem statement, and acceptance criteria.
- One issue per logical unit of work. If the task fans out, file sub-issues rather than
  bundling unrelated changes under a single number.
- Decisions, scope changes, and links to related issues belong on the issue, not buried
  in commit messages.

## Branch off the assigned session branch, not `main`

- Remote sessions are launched against a designated branch (commonly
  `claude/<adjective>-<noun>-XXXXX`). Develop on that branch — do not check out `main`
  and start committing.
- This matches the repo-root rule in `AGENTS.md` ("never commit directly to `main`") and
  keeps every session's work isolated to its own PR.
- If you need to incorporate updates from `main`, merge `main` into the session branch.
  Never rebase the session branch over work that wasn't yours, and never force-push to
  another agent's branch.

## Every unit of work ends in a Pull Request that auto-closes its issue

- All changes ship via a PR. **One issue, one PR.**
- The PR description **must** contain a closing keyword that links the issue, so merging
  the PR closes the issue automatically. Use one of:
  `Closes #N`, `Fixes #N`, or `Resolves #N` (one per issue the PR resolves).
- Verify the link is live on the PR — GitHub shows "Closes #N" in the sidebar once the
  keyword is parsed correctly. If it doesn't, fix the description before asking for
  review.
- The PR title and body should stand alone: a reader who only sees the PR should
  understand the change without opening the issue.

## CI green + mergeable gate

The agent's job isn't done when the PR is opened — it's done when the PR is ready to
merge. Before reporting the task complete:

1. **CI is green.** All required checks pass. Watch the run to completion (e.g.
   `gh pr checks <number> --watch`). If a check fails, diagnose and fix the underlying
   cause — do not retry blindly, do not disable the check, and **never** skip hooks
   (`--no-verify`) to get around it.
2. **No merge conflicts.** The base branch may have advanced while CI ran. Resolve
   conflicts by **merging the base branch into the PR branch** (never by discarding base
   commits) and re-push so GitHub reports the PR as mergeable. Re-check after the push,
   since the merge can re-trigger CI or introduce new conflicts.
3. **No outstanding "changes requested" reviews or unresolved review threads** that the
   agent itself can address. Reviewer questions that genuinely need a human decision
   should be flagged in a PR comment, not silently ignored.
4. **Branch is up to date with the merge target.** If the repo requires "branch up to
   date before merging," update the branch and wait for CI to re-run green.

Only once all four hold is the work complete.

## Reporting back

When you stop, report three things to the user (or in the final PR comment):

- The **PR URL**.
- The **issue it closes** (`Closes #N`).
- The **final CI status** (all checks green, mergeable: yes).

If any of the gates above cannot be achieved (e.g. CI is red for an infrastructure
reason outside the agent's control), say so explicitly in a PR comment and stop — do not
merge a red or conflicted PR.

## Cachetta-specific notes

- Two packages live in `packages/javascript/` and `packages/python/`. Run the tests for
  the package(s) you touched before pushing (`pnpm test:unit` / `pnpm test:integration`
  for JS; `uv run pytest .` for Python). See `AGENTS.md` for the full command list.
- Releases are orchestrated by **putitoutthere** off `main` once your PR lands. Tag
  format is `js/cachetta-v{version}` and `py/cachetta-v{version}`. You don't tag from
  the PR — putitoutthere does it after merge.
- Every PR must add an entry under `## [Unreleased]` in the affected package's
  `CHANGELOG.md`, or carry a `Skip-Changelog: <reason>` trailer. CI enforces this.

## Quick checklist

Before you call the work done, walk this list:

- [ ] A GitHub issue exists for this change.
- [ ] You branched off the assigned session branch, not `main`.
- [ ] The PR description contains `Closes #N` (or `Fixes #N` / `Resolves #N`) and the
      sidebar shows the linked issue.
- [ ] Tests for every package you touched were run locally and passed.
- [ ] Each affected package's `CHANGELOG.md` has an `## [Unreleased]` entry, or a
      `Skip-Changelog:` trailer justifies the omission.
- [ ] All required CI checks are green (`gh pr checks <number> --watch` came back clean).
- [ ] GitHub reports the PR as mergeable, with no conflicts and no unresolved review
      threads you can address.
- [ ] Your final message includes the PR URL, the closed issue number, and the CI status.
