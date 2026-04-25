# Agent Environments

These notes describe the execution contexts an agent (Claude Code, Claude Agent SDK, or any
similar harness) may find itself running in, and the rules that apply to each.

## Detecting a remote / managed-agent environment

"Remote" here means the agent is running non-interactively on infrastructure the user does
not have a terminal attached to: Claude Code on the web, GitHub Actions runners, the
Managed Agents product, sandboxed cloud worktrees, or any similar setup.

There is no single officially-documented flag for this, so detection relies on a
combination of signals. Treat the session as remote if **any** of the following are true:

- An obvious CI/runner variable is set: `GITHUB_ACTIONS`, `CI`, `BUILDKITE`,
  `GITLAB_CI`, `CIRCLECI`, etc.
- A Claude Code harness variable indicates a non-local entrypoint:
  - `CLAUDE_CODE_ENTRYPOINT` is set to anything other than `cli` (e.g. it is empty,
    `web`, or a managed-agent value).
  - `CLAUDE_CODE_ENVIRONMENT_KIND` is set (e.g. `bridge`, `managed`, `remote`).
  - `CLAUDE_CODE_REMOTE` is set.
- The process has no controlling TTY (stdin/stdout are not a terminal) **and** the
  working directory looks like an ephemeral worktree (e.g. under `/home/user/`,
  `/workspace/`, or a path created by the harness rather than the user).
- The repository was cloned with credentials provided by the harness rather than the
  user's own SSH/HTTPS config (e.g. a GitHub App token in the environment).

These signals are heuristic. The Claude Code harness variables above are internal and
undocumented as of writing; prefer the CI variables and TTY check, and use the
`CLAUDE_CODE_*` variables only as a tiebreaker.

## What to do when remote is detected

**Before doing any other work, read [`remote.md`](./remote.md) in this directory and
follow its rules.** The remote rules are stricter than the local defaults (issue
tracking, PR-only workflow, CI-must-be-green) because there is no human at the keyboard
to catch mistakes between steps.

If you cannot determine the environment with confidence, default to the remote rules —
they are a strict superset of the local rules and are always safe to follow.

## Local interactive sessions

In a local interactive session (a developer running `claude` in their own terminal),
follow the standard project rules in the repo-root `AGENTS.md` / `CLAUDE.md`. The
remote-only requirements in `remote.md` do not apply unless the user explicitly opts in.
