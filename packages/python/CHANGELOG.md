# Changelog

All notable changes to the `cachetta` PyPI package are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This package does not strictly follow [Semantic Versioning](https://semver.org/) — see
[MIGRATIONS.md](./MIGRATIONS.md) for upgrade guides covering breaking changes.

## [Unreleased]

### Fixed
- `lru_size` now populates the in-memory LRU even when `write=False`.
  Previously, LRU population lived entirely inside the `write`-gated disk
  write path, so a read-only-from-memory config (`write=False` with
  `lru_size` set) never got the LRU benefit and recomputed on every call.
  (#79)

### Removed
- The `skip_self` flag — the receiver (`self`/`cls`) is now excluded from
  the cache key automatically. Drop `skip_self=`; see
  [MIGRATIONS.md](./MIGRATIONS.md). (#77)

### Added
- New `hashed: bool = False` field on `Cachetta`. When set, arg-bearing
  calls resolve to `{path}/{hash(*args, **kwargs)}` — one file per
  argument-set inside the folder named by `path` — the common LLM /
  embedding cache shape. Available at construction
  (`Cachetta(path=..., hashed=True)`), via `cache.copy(hashed=True)`,
  and as a per-decoration override (`@cache(hashed=True)`). Composes
  with a callable `path`: the callable produces the folder, the hash
  becomes the child filename. Honors `condition` and works with async
  functions. Off by default — preserves the post-#48
  literal-path semantics.

### Changed
- Both the source distribution and the installed wheel now ship `docs/`
  **recursively**, so markdown files under nested subdirectories (e.g.
  `docs/llm/python/index.md`) land in `site-packages/cachetta/docs/`
  alongside the top-level pages. Previously the `package-data` glob was
  flat (`docs/*.md`) and the sync script iterated `*.md` non-recursively,
  so subdirectories were dropped from the wheel and from the per-package
  `docs/` copy. (#56)

### Added
- `Cachetta.__truediv__` (the `/` operator) now accepts a callable as its
  right-hand operand. `cache / fn` returns a `Cachetta` whose path is
  resolved at call time as `base / fn(*args, **kwargs)`, suited to
  custom file layouts (e.g. kind-routing, id-not-hash filenames). The
  callable's return is validated against `..` traversal.
- Public `cachetta.hash(*args, **kwargs)` helper. Returns the same
  16-char hex digest the auto-keyed cache path uses internally, so
  consumers can build custom `path=` lambdas (or the `/` operator's
  callable form) or external indexes that line up with cachetta's own
  keying without re-implementing the hasher. Note: the digest is **not**
  cross-language portable with the JavaScript `hash` export.

### Fixed
- `cache / 'sub'` (string right-hand operand) now produces real
  subfolder semantics: the resulting cache's path is `base/sub` rather
  than a hyphenated `base/sub-...` sibling.

### Removed
- **Breaking:** Stopped rewriting `str` / `Path` `path` into a
  `{stem}-{hash}{ext}` sibling when the wrapped function is called with
  arguments. `path` is now used verbatim — arguments to the wrapped
  function no longer affect the cache file. To key cache files by
  arguments, pass `path` as a callable (e.g.
  `path=lambda x: f"cache/{x}.json"`). See `MIGRATIONS.md` for details.

## [0.6.2] - 2026-04-27

### Added
- The `docs/` folder now ships with the source distribution, so the full
  reference is available alongside the README inside the published sdist.

### Changed
- README restructured into concise `##` sections that mirror the `docs/`
  folder, with each section linking to the bundled docs page.
