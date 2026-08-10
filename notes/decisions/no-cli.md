# Decision: cachetta does not ship a CLI

**Status:** decided (2026-08-10) · **Scope:** both packages (`js/cachetta`, `py/cachetta`)

The question "should cachetta expose CLI commands (`clear`, `ls`, …)?" has come
up repeatedly — at least three times as of this writing — and the answer has
come back **no** every time. This note records the reasoning so future sessions
(human or agent) don't re-derive it. Prior rounds of this question produced
library primitives instead: `clear()` / `invalidate()` / `exists()` / `age()` /
`info()` (see PRs #110, #111).

## The proposal that kept recurring

A small binary — `cachetta ls <path>` and `cachetta clear <path>` — plus,
in its strongest form, a read-only `cachetta inspect <module[:attr]> --json`
that imports a consuming app's `Cachetta` instance and reports its config
(path, duration, flags) and state (entries, ages).

## Why the answer is no

### 1. The CLI would have no privileged information

There is no manifest, no registry, and no on-disk marker; a cache entry is an
ordinary file at a caller-chosen path, and the only metadata is filesystem
mtime. So `cachetta ls` is `find -mtime` with extra steps, and
`cachetta clear` is worse than `rm`: it *implies* it knows what is safe to
delete, but everything it "knows" arrives via a `--duration` flag the caller
must supply. The library default (7 days) vs. an app override (e.g. 30 days)
means the natural invocation silently deletes entries the app still considers
servable — exit 0, no error. `rm` makes no claims; a branded deletion tool
carrying false authority is a step down from coreutils, and every
wrong-directory incident becomes a cachetta bug report.

### 2. Cache config lives in code, and discovery dominates

Cachetta roots, durations, and stale windows are defined in consuming source
code. Any terminal workflow therefore *starts* with finding that config (grep
for `Cachetta(` or the import line) — and a CLI only helps *after* discovery,
at which point `.clear()` / `.info()` is one line of Python away. The
motivating evidence was an agent transcript that grepped a consumer's
`DEFAULT_DURATION` and ran `inspect.signature(Cachetta.__init__)`: its actual
questions were "how is this app's cache configured" and "what does the
installed version accept" — questions a CLI takes as *inputs* (flags), not
ones it answers.

### 3. The right layer for CLI verbs is the consuming app

An app that wants `--clear-cache` can add it in three lines by calling
`instance.clear()` — with the real path, real duration, and real stale window,
zero flags to get wrong. Cachetta's contribution is making that trivial via
its method surface. A library-level CLI is the same verb with the config
amputated, and would discourage apps from exposing the better version.

### 4. The maintenance asymmetry is steep in this repo

Under this repo's own rules, a CLI's output format, exit codes, and error
messages become frozen consumer-visible API (changelog bar: "anything a
consumer will notice"), gated at 100% unit coverage including branches, with a
docs page, and subject to the JS/Python parity ethos — a Python-only CLI
breaks the mirror; a JS `bin` means build infra the JS package doesn't have.
That tax is paid on every future change, against a benefit collected only when
someone investigates a cache from a terminal — a rare event per consumer.

### 5. The agent-ergonomics accounting doesn't clear the bar

The stated bar: a new primitive is worth it if it's the difference between
agent success and failure; not worth it if it saves a line or two. The
evidence shows the median agent answers these questions in one turn with
introspection one-liners (its native idiom) — a CLI saves ~1 turn and ~15
lines. Not success-vs-failure. The genuine tail case is hook-restricted
harnesses that block `python -c` and chained commands (this repo's own agent
environment is one), where a single allowlistable read-only command would
replace a multi-turn temp-script detour — but that failure mode has not been
observed in the wild, only predicted.

## Alternatives considered and rejected

- **`module:attr` import mode** (uvicorn-style): reuses the in-code config,
  but is arbitrary code execution at CLI time, requires the host venv and
  tolerating import side effects, and still needs the grep to find the
  reference. Only the easiest step gets wrapped.
- **Declared-roots config** (`[tool.cachetta]`, `cachetta.toml`): a second
  copy of config that drifts from the code — the same disease in a new file.
- **An agent-facing docs recipe** (canonical introspection snippet under
  `docs/llm/`): near-zero cost, but LLMs don't reliably read shipped docs
  proactively, so it wouldn't change behavior.

## What would reopen this

Observed evidence — not prediction — of agents failing or burning multiple
turns on cache introspection despite the existing method primitives;
concretely, repeated hook-blocked `python -c` detours in restricted
harnesses. If that appears, the candidate is the **read-only**
`inspect <module[:attr]> --json` form only (bare-module form enumerates
instances so discovery needs just the import line). Destructive verbs
(`clear`, `rm`-alikes) stay out regardless: a reporting tool that's wrong
costs nothing; a deletion tool that's wrong costs data.
