# Changelog

All notable changes to the `cachetta` npm package are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This package does not strictly follow [Semantic Versioning](https://semver.org/) — see
[MIGRATIONS.md](./MIGRATIONS.md) for upgrade guides covering breaking changes.

## [Unreleased]

### Fixed
- Restored the compiled `dist/` directory in the published tarball.
  Versions 0.3.1 and 0.3.2 shipped with `dist/` missing — the publish
  pipeline didn't build before packing — so installing those versions
  produced a broken module that couldn't be imported. Upgrade to this
  release for a working install.

## [0.3.2] - 2026-04-27

### Added
- The `docs/` folder now ships with the published package, so the full
  reference is available alongside the README in `node_modules/cachetta/docs/`.

### Changed
- README restructured into concise `##` sections that mirror the `docs/`
  folder, with each section linking to the bundled docs page.
