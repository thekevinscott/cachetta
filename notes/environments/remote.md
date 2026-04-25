# Remote / Managed-Agent Environment Rules

These rules apply whenever the agent is running in a remote or managed-agent context
(see [`agents.md`](./agents.md) for how to detect this). They are in addition to — and
override on conflict — the standard project rules in the repo-root `AGENTS.md`.

The principle: in a remote environment there is no human watching each step, so every
unit of work must be **traceable**, **reviewable**, and **verifiable** without anyone
needing to ask the agent what it did.

## Every unit of work has a GitHub issue

- Before starting work, ensure a GitHub issue exists that describes the change. If one
  doesn't, open one — title, short problem statement, and acceptance criteria.
- One issue per logical unit of work. If the task fans out, file sub-issues rather than
  bundling unrelated changes under a single number.
- The issue is the durable record of *why* the work happened. Decisions, scope changes,
  and links to related issues belong on the issue, not buried in commit messages.

## Every unit of work ends in a Pull Request that auto-closes its issue

- All changes ship via a PR. Never push directly to `main`.
- The PR description **must** contain a closing keyword that links the issue, so merging
  the PR closes the issue automatically. Use one of:
  `Closes #N`, `Fixes #N`, or `Resolves #N` (one per issue the PR resolves).
- Verify the link is live on the PR — GitHub will show "Closes #N" in the sidebar once
  the keyword is parsed correctly. If it doesn't, fix the description before asking for
  review.
- The PR title and body should stand alone: anyone reading just the PR should understand
  the change without opening the issue.

## The PR must be green and mergeable before the agent stops

The agent's job isn't done when the PR is opened — it's done when the PR is ready to
merge. Before reporting the task complete:

1. **CI is green.** All required checks pass. If a check fails, diagnose and fix the
   underlying cause; do not retry blindly, do not disable the check, and do not skip
   hooks (`--no-verify`) to get around it. Watch the run to completion (e.g.
   `gh pr checks <number> --watch`).
2. **No merge conflicts.** The PR's base branch may have advanced while CI ran. Rebase
   or merge `main` into the branch as needed and re-push so GitHub reports the PR as
   mergeable. Re-check after the push, since rebasing can introduce new conflicts or
   re-trigger CI.
3. **No outstanding "changes requested" reviews or unresolved review threads** that the
   agent itself can address. Reviewer questions that genuinely need a human decision
   should be flagged in a PR comment, not silently ignored.
4. **Branch is up to date with the merge target.** If the repo requires "branch up to
   date before merging," update the branch and wait for CI to re-run green.

Only once all four hold is the work complete. If any of them cannot be achieved (e.g. CI
is failing for an infrastructure reason outside the agent's control), say so explicitly
in a PR comment and stop — do not merge a red or conflicted PR.

## Handling failures mid-task

- If CI surfaces a real bug, fix it in the same PR with a new commit. Do not amend or
  force-push over already-reviewed history without a reason.
- If the fix is large enough to deserve its own issue (e.g. it uncovers a separate bug),
  file that issue, reference it from the current PR, and decide whether to address it in
  this PR or a follow-up.
- If the task turns out to be infeasible as specified, comment on the issue with what
  was tried and why it didn't work, and leave the PR in draft (or close it) rather than
  merging a half-finished change.
