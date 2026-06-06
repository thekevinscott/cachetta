# Changelog

All notable changes to the `cachetta` PyPI package are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This package does not strictly follow [Semantic Versioning](https://semver.org/) — see
[MIGRATIONS.md](./MIGRATIONS.md) for upgrade guides covering breaking changes.

## [Unreleased]

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

### Fixed
- `cache / 'sub'` (string right-hand operand) now produces real
  subfolder semantics: when the resulting cache is used to auto-hash
  arguments, entries are written *inside* `base/sub/` rather than as
  hyphenated `base/sub-{hash}` siblings. More generally, hashed entries
  for any extension-less path now live inside the directory.

## [0.6.2] - 2026-04-27

### Added
- The `docs/` folder now ships with the source distribution, so the full
  reference is available alongside the README inside the published sdist.

### Changed
- README restructured into concise `##` sections that mirror the `docs/`
  folder, with each section linking to the bundled docs page.
