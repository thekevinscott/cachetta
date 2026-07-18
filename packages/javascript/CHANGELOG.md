# Changelog

All notable changes to the `cachetta` npm package are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This package does not strictly follow [Semantic Versioning](https://semver.org/) — see
[MIGRATIONS.md](./MIGRATIONS.md) for upgrade guides covering breaking changes.

## [Unreleased]

### Added
- Public `hash(...args)` export. Returns the same 16-char hex digest the
  auto-keyed cache path uses internally, so consumers can build custom
  `path:` callables or external indexes that line up with cachetta's own
  keying without re-implementing the hasher. Note: the digest is **not**
  cross-language portable with the Python `hash` export.
- New `hashed: boolean` field on `CacheConfig`. When set, arg-bearing
  calls resolve to `{path}/{hash(...args)}` — one file per argument-set
  inside the folder named by `path` — the common LLM / embedding cache
  shape. Available at construction (`new Cachetta({ path, hashed: true })`),
  via `cache.copy({ hashed: true })`, and as a per-wrap override
  (`cache(fn, { hashed: true })`). Composes with a callable `path`: the
  callable produces the folder, the hash becomes the child filename.
  Honors `condition`. Off by default — preserves the post-#48
  literal-path semantics.

### Changed
- The published tarball now ships `docs/` **recursively**, so markdown
  files under nested subdirectories (e.g. `docs/llm/javascript/index.md`)
  land in `node_modules/cachetta/docs/` alongside the top-level pages.
  Previously only flat `docs/*.md` was synced into the package and any
  subdirectory was silently dropped. (#56)

### Removed
- **Breaking:** Stopped rewriting string `path` into a `{name}-{hash}{ext}`
  sibling when the wrapped function is called with arguments. A string
  `path` is now used verbatim — arguments to the wrapped function no
  longer affect the cache file. To key cache files by arguments, pass
  `path` as a function (e.g. `path: (id) => `cache/${id}.json``). See
  `MIGRATIONS.md` for details.

### Fixed
- Cached functions that legitimately return `null` or `undefined` are now
  treated as cache hits instead of misses. Previously, both the async and
  sync wrappers (`cache(fn)` / `cache.wrapSync(fn)`) checked
  `data != null` to decide whether a read was a hit, so a stored `null`/
  `undefined` value was indistinguishable from "nothing cached" and the
  wrapped function ran on every call. `readCache`/`readCacheSync` now
  route through an internal `CACHE_MISS` sentinel (mirroring the existing
  `LRU_MISS` pattern) so "file absent" and "cached nullish value" are no
  longer conflated. (#78)
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
- `isPartialCacheConfig` (used by `Cachetta.call`/`cache(...)` to decide
  whether an argument is a config object or a function to wrap) omitted
  `hashed` from its list of recognized keys. `cache({ hashed: true })`
  therefore fell through and was mishandled as a function to wrap. The
  guard now recognizes `hashed`, so a `hashed`-only config object produces
  a configured copy as expected. (#84)

## [0.3.2] - 2026-04-27

### Added
- The `docs/` folder now ships with the published package, so the full
  reference is available alongside the README in `node_modules/cachetta/docs/`.

### Changed
- README restructured into concise `##` sections that mirror the `docs/`
  folder, with each section linking to the bundled docs page.
