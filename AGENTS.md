@notes/agents.md

# Cachetta Development

## Test-driven workflow (read this first)

> **Start with a red failing integration test(s), and confirm that test(s)
> fails on CI _and all other checks go green_. Then proceed with
> implementation.**

For any new behavior or bug fix:

1. Write the integration test(s) first. The test must describe the
   consumer-visible behavior the change will introduce.
2. Commit and push the test alone (no implementation), then open the PR so
   CI runs. Verify two things at once:
   - the new test(s) actually fails (a passing test means it isn't
     exercising the intended behavior); and
   - **every other check is green** — lint, build, typecheck, changelog
     gate, docs gate, the rest of the test suite. A red test is only
     meaningful if it's the *only* red light.
3. Only after the red+green state is confirmed on CI, push the
   implementation in a follow-up commit and watch CI turn fully green.

If the unrelated checks aren't green at step 2, fix them first — the
failing test must be the only signal you carry into the implementation
step.

## Workflow
- **NEVER commit directly to main** - always create a PR
- **Before pushing**: run tests for the package(s) you changed (see Key Commands)
- **After pushing**: run `gh pr checks <number> --watch` to monitor CI. Fix any failures immediately before moving on
- **After a PR is merged**: pull main to keep local in sync

### PR Scope
- **Keep PRs minimal but complete** - each PR should deliver one useful, self-contained piece of functionality
- Don't add code that isn't used until a future PR
- Every PR must include tests for changed behavior

### Changelogs & Migrations
Each package owns its own `CHANGELOG.md` and `MIGRATIONS.md` (`packages/javascript/`, `packages/python/`). Packages release independently, so these files never share content across languages.

- **CHANGELOG.md** — follows [Keep a Changelog](https://keepachangelog.com/) (Added / Changed / Deprecated / Removed / Fixed). **Every PR must add an entry under `## [Unreleased]` in the affected package's CHANGELOG.** Scope is *any* observable change — new options, renamed exports, altered defaults, tweaked error messages, changed exit codes, etc. We are not strictly following semver, so the changelog is the authoritative record of what consumers will notice. **CI enforces this by default.** To waive the requirement, add a `Skip-Changelog: <reason>` trailer to any commit in the PR — use only for changes with no consumer-visible effect (internal refactors, CI/tooling tweaks, test-only edits, doc-only edits). The trailer value is the justification, recorded in git for reviewers and future readers. Edits to `MIGRATIONS.md` alone do not trigger the requirement.
- **MIGRATIONS.md** — required for breaking changes only. Each entry is headed by the version bump (e.g. `## v1.x → v2.0`) and **must** include all five sections below. Omit a section only if it truly has no content, and explicitly write "None." so reviewers know it wasn't forgotten.
  1. **Summary** — one paragraph: what broke and why.
  2. **Required changes** — table of before/after snippets for config, CLI, action inputs.
  3. **Deprecations removed** — anything previously warned about that's now gone.
  4. **Behavior changes without code changes** — same API, different runtime behavior (tag format, exit codes, etc.).
  5. **Verification** — how a consumer confirms the upgrade worked (dry-run command, expected output).
- For breaking changes, add a `Breaking-Change: <description>` trailer to any commit in the PR; CI will then require the affected package's `MIGRATIONS.md` to be updated. The `Skip-Changelog:` and `Breaking-Change:` trailers are mutually exclusive.
- Trailers go at the bottom of a commit message, separated from the body by a blank line. Example:
  ```
  refactor: extract internal hash helper

  Skip-Changelog: pure rename of a non-exported function
  ```
- `MIGRATIONS.md` is the source of truth. The docs site auto-pulls it during the Jekyll build — do not hand-edit migration content under `docs/`.

### Docs
The Jekyll site under `docs/` is the canonical reference for end users. Each package has a single docs page: `docs/javascript.md` and `docs/python.md`.

- **Any public-facing change must include a docs update.** A change is public-facing if it modifies the surface a consumer sees — a new option, a new method, altered defaults, changed error behavior, a renamed export, etc. The bar is the same as for CHANGELOG: if a consumer will notice, the docs need to reflect it.
- **CI enforces this by default.** If a PR modifies any file under `packages/<pkg>/src/`, CI requires `docs/<pkg>.md` to be updated in the same PR. To waive — for genuine internal refactors that don't change observable behavior — add a `Skip-Docs: <reason>` trailer to a commit in the PR. The trailer mirrors `Skip-Changelog:` semantics: the value records the justification in git.
- Keep `packages/<pkg>/README.md` aligned with the docs page where the two overlap. The README is intentionally a condensed mirror that links back to `docs/<pkg>.md`.

### Test coverage
CI requires the **unit suite** to be **100% covered, including branches**, on **both** packages. Integration tests are deliberately excluded from the measurement, so the figure reflects genuine unit coverage.

- **JS:** `vitest.config.unit.ts` sets `coverage.thresholds` to `100` for lines, branches, functions, and statements over `src/**/*.ts` (unit tests are `src/**/*.test.ts`).
- **Python:** the unit run is `pytest -m "not integration" --cov=cachetta --cov-branch --cov-fail-under=100`, so both line and branch coverage must be 100%.

Because the whole unit suite is held at 100%, any new or changed `src/` code is covered by construction; `diff-cover` still runs as a changed-lines backstop. Code covered *only* by an integration test counts as uncovered — the goal is to enforce unit tests.

- For genuinely unreachable / defensive code, use a coverage-ignore hint rather than a fake test: `/* v8 ignore next */` (JS) or `# pragma: no cover` (Python). Use sparingly and only where a test truly cannot reach the branch.
- Run coverage locally before pushing: `pnpm exec vitest run -c vitest.config.unit.ts --coverage` (JS) and `uv run pytest -m "not integration" --cov=cachetta --cov-branch` (Python).

## Project Structure
- `packages/javascript/` - TypeScript implementation (npm: `cachetta`)
- `packages/python/` - Python implementation (PyPI: `cachetta`)
- `docs/` - Jekyll static site deployed to GitHub Pages
- `.github/workflows/` - CI/CD (separate lint, test, build, publish per language)

Monorepo managed with `pnpm-workspace.yaml`. Packages are independent - separate versions, separate release cycles.

## Testing

### JavaScript (Vitest)
- **Unit tests**: `src/**/*.test.ts` - colocated with source
- **Integration tests**: `tests/**/*.test.ts` - end-to-end scenarios
- 5-second timeout configured globally

### Python (pytest)
- **Tests**: `packages/python/tests/`
- Uses `pytest-describe` (`describe_*` / `it_*` blocks) and `pytest-asyncio` (auto mode)
- Includes performance and developer experience tests

## Key Commands

### JavaScript (`packages/javascript/`)
```bash
pnpm test:unit                # Unit tests
pnpm test:unit:watch          # Unit tests (watch mode)
pnpm test:integration         # Integration tests
pnpm test:integration:watch   # Integration tests (watch mode)
pnpm lint                     # ESLint
pnpm typecheck                # TypeScript compiler check (no emit)
pnpm build                    # Vite build to dist/
```

### Python (`packages/python/`)
```bash
uv run pytest .               # All tests
make test                     # Same as above
make test_watch               # Watch mode (pytest-watcher)
make lint                     # Ruff check
uv build                      # Build wheel + sdist
```

## Versioning & Releases
- Versions are independent per package: JS in `package.json`, Python in `pyproject.toml`
- **Tag format**: `js/cachetta-v{version}` and `py/cachetta-v{version}`
- Releases are orchestrated by [putitoutthere](https://github.com/thekevinscott/put-it-out-there) via `putitoutthere.toml`
- **Trigger**: push to `main`. Any package whose `paths` matched changed files cascades at `patch`
- **Override**: add a `release: minor`, `release: major`, or `release: skip` trailer to the commit
- **Manual**: workflow dispatch with optional `dry_run` input
- Publishing uses OIDC trusted publishing for both npm and PyPI

## Code Style
- **JS**: TypeScript strict mode, ESLint flat config, ES2022 target, ESM only
- **Python**: Python 3.12+, ruff for linting
- camelCase in JS, snake_case in Python - APIs mirror each other with language-appropriate naming

## Guidelines
- **Do not chain commands** (e.g., `cmd1 && cmd2`) - the security hook blocks them
- Check lockfiles (`pnpm-lock.yaml`, `uv.lock`) for dependency versions before asking
- Write temp scripts to `/tmp/claude/` instead of `python -c`

## Commit Convention

| Type | Use for |
|------|---------|
| `feat:` | New user-facing functionality |
| `fix:` | Bug fixes |
| `test:` | Test additions/changes |
| `chore:` | Internal tooling, CI, maintenance |
| `refactor:` | Code restructuring without behavior change |
| `docs:` | Documentation only |
| `style:` | Formatting changes |
