# Agent Notes

These notes apply to any agent (Claude Code, Claude Agent SDK, or similar harness) working
in this repository. They tell you how to recognize **local** vs **remote** sessions and
which files to read before touching the working tree, git, or GitHub.

## Detect the environment

Run this one-liner before doing anything else:

```bash
echo "${CLAUDE_CODE_REMOTE:-local}"
```

- `true` → **remote** session (Claude Code on the web, GitHub Actions, managed agents,
  cloud sandboxes — no human at the keyboard between steps).
- anything else (unset, `false`, `local`, …) → **local** session (a developer is running
  the agent in their own terminal).

If `CLAUDE_CODE_REMOTE` is unset and you cannot tell from other signals (CI variables,
ephemeral worktree paths, missing TTY) whether the session is remote, default to the
remote rules — they are a strict superset of the local defaults and are always safe to
follow.

## Required reading order

1. **Always read [`AGENTS.md`](../AGENTS.md)** at the repo root. It carries the universal
   workflow and process rules (PRs, tests, changelogs, commit conventions) and applies in
   every session, local or remote.
2. **If `CLAUDE_CODE_REMOTE=true`, read
   [`environments/remote.md`](./environments/remote.md) before any tool call that touches
   the working tree, git, or GitHub.** The remote file supplements `AGENTS.md` and
   overrides it on conflict — it tightens the rules because nobody is watching each step.
3. **If `CLAUDE_CODE_REMOTE` is unset**, no environment file is required. `AGENTS.md`
   alone is the whole picture for local interactive sessions.

## Design decisions

Settled questions live in [`notes/decisions/`](./decisions/). Read the relevant
record before re-proposing something it covers, and if you and the user reach a
durable conclusion on a recurring design question, record it there.

- [`no-cli.md`](./decisions/no-cli.md) — cachetta does not ship a CLI; verbs
  belong in consuming apps, built on the library's method primitives.

## Local interactive sessions

In a local interactive session the user is at the keyboard and can answer questions, so
the standard `AGENTS.md` rules are enough. The remote-only requirements in
`environments/remote.md` do not apply unless the user explicitly opts in.
