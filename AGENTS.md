# Cachetta Development

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

- **CHANGELOG.md** — follows [Keep a Changelog](https://keepachangelog.com/) (Added / Changed / Deprecated / Removed / Fixed). **Every PR must add an entry under `## [Unreleased]` in the affected package's CHANGELOG.** Scope is *any* observable change — new options, renamed exports, altered defaults, tweaked error messages, changed exit codes, etc. We are not strictly following semver, so the changelog is the authoritative record of what consumers will notice. **CI enforces this by default.** To waive the requirement, apply the `skip-changelog` label — use only for changes with no consumer-visible effect (internal refactors, CI/tooling tweaks, test-only edits, doc-only edits).
- **MIGRATIONS.md** — required for breaking changes only. Each entry is headed by the version bump (e.g. `## v1.x → v2.0`) and **must** include all five sections below. Omit a section only if it truly has no content, and explicitly write "None." so reviewers know it wasn't forgotten.
  1. **Summary** — one paragraph: what broke and why.
  2. **Required changes** — table of before/after snippets for config, CLI, action inputs.
  3. **Deprecations removed** — anything previously warned about that's now gone.
  4. **Behavior changes without code changes** — same API, different runtime behavior (tag format, exit codes, etc.).
  5. **Verification** — how a consumer confirms the upgrade worked (dry-run command, expected output).
- `MIGRATIONS.md` is the source of truth. The docs site auto-pulls it during the Jekyll build — do not hand-edit migration content under `docs/`.

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

## Architecture
- File-based caching library with matching APIs in JS/TS and Python
- **JS serialization**: `v8.serialize()` / `v8.deserialize()` (binary, not JSON)
- **Python serialization**: `pickle`
- `Cachetta` class is the main entry point - configurable with path, duration, read/write flags, LRU size, stale-while-revalidate
- Arguments are hashed to generate unique cache file paths
- Optional in-memory LRU layer sits in front of disk reads
- Both sync and async APIs in each language

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
- **Release trigger**: manual workflow dispatch or daily cron (2 AM UTC)
- Supports patch or minor version bumps
- JS publishes to npm with `--provenance`, Python publishes to PyPI via trusted publishing

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
