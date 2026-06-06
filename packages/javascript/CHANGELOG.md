# Changelog

All notable changes to the `cachetta` npm package are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This package does not strictly follow [Semantic Versioning](https://semver.org/) — see
[MIGRATIONS.md](./MIGRATIONS.md) for upgrade guides covering breaking changes.

## [Unreleased]

### Changed
- The published tarball now ships `docs/` **recursively**, so markdown
  files under nested subdirectories (e.g. `docs/llm/javascript/index.md`)
  land in `node_modules/cachetta/docs/` alongside the top-level pages.
  Previously only flat `docs/*.md` was synced into the package and any
  subdirectory was silently dropped. (#56)

### Fixed
- Restored the compiled `dist/` directory in the published tarball.
  Versions 0.3.1 and 0.3.2 shipped with `dist/` missing — the publish
  pipeline didn't build before packing — so installing those versions
  produced a broken module that couldn't be imported. Upgrade to this
  release for a working install.
- Fixed TypeScript type resolution for consumers. Version 0.3.3 emitted
  declarations to `dist/src/index.d.ts` while `package.json` pointed at
  `dist/index.d.ts`, so importing `cachetta` from a TypeScript project
  failed with "Cannot find module 'cachetta' or its corresponding type
  declarations." Declarations now land at the declared path.
- Stopped shipping test `*.test.d.ts` declarations in the published
  tarball.

## [0.3.2] - 2026-04-27

### Added
- The `docs/` folder now ships with the published package, so the full
  reference is available alongside the README in `node_modules/cachetta/docs/`.

### Changed
- README restructured into concise `##` sections that mirror the `docs/`
  folder, with each section linking to the bundled docs page.
