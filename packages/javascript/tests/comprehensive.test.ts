import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { promises as fs, utimesSync, accessSync, writeFileSync as fsWriteFileSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { deserialize } from 'v8';
import { Cachetta, readCache, writeCache, readCacheSync, writeCacheSync, CachettaError } from 'cachetta';

const setTimeOfFile = async (amount: number, cachePath: string) => {
  const oldTime = new Date(Date.now() - amount);
  await fs.utimes(cachePath, oldTime, oldTime);
};

const setTimeOfFileSync = (amount: number, cachePath: string) => {
  const oldTime = new Date(Date.now() - amount);
  utimesSync(cachePath, oldTime, oldTime);
};

describe('comprehensive integration tests', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp('cachetta-comprehensive-');
  });

  afterEach(async () => {
    vi.useRealTimers();
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  describe('basic read/write cycle', () => {
    it('should write and read data', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'data.json') });
      const data = { key: 'value', nested: { arr: [1, 2, 3] } };
      await writeCache(cache, data);
      expect(await readCache(cache)).toEqual(data);
    });

    it('should return null for nonexistent cache', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'nope.json') });
      expect(await readCache(cache)).toBeNull();
    });

    it('should handle arrays as top-level data', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'arr.json') });
      const data = [1, 'two', { three: 3 }];
      await writeCache(cache, data);
      expect(await readCache(cache)).toEqual(data);
    });

    it('should handle null as cached value', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'null.json') });
      await writeCache(cache, null);
      // readCache returns null for both missing and null-valued, so verify file was written
      const buffer = await fs.readFile(join(tempDir, 'null.json'));
      expect(deserialize(buffer)).toBeNull();
    });

    it('should handle string as cached value', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'str.json') });
      await writeCache(cache, 'hello world');
      const buffer = await fs.readFile(join(tempDir, 'str.json'));
      expect(deserialize(buffer)).toBe('hello world');
    });

    it('should handle number as cached value', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'num.json') });
      await writeCache(cache, 42);
      const buffer = await fs.readFile(join(tempDir, 'num.json'));
      expect(deserialize(buffer)).toBe(42);
    });

    it('should handle Date objects', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'date.dat') });
      const now = new Date();
      await writeCache(cache, now);
      const result = await readCache<Date>(cache);
      expect(result).toBeInstanceOf(Date);
      expect(result!.getTime()).toBe(now.getTime());
    });

    it('should handle Map objects', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'map.dat') });
      const data = new Map([['a', 1], ['b', 2]]);
      await writeCache(cache, data);
      const result = await readCache<Map<string, number>>(cache);
      expect(result).toBeInstanceOf(Map);
      expect(result!.get('a')).toBe(1);
      expect(result!.get('b')).toBe(2);
    });

    it('should handle Set objects', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'set.dat') });
      const data = new Set([1, 2, 3]);
      await writeCache(cache, data);
      const result = await readCache<Set<number>>(cache);
      expect(result).toBeInstanceOf(Set);
      expect(result!.has(1)).toBe(true);
      expect(result!.size).toBe(3);
    });

    it('should handle RegExp objects', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'regex.dat') });
      const data = /hello\s+world/gi;
      await writeCache(cache, data);
      const result = await readCache<RegExp>(cache);
      expect(result).toBeInstanceOf(RegExp);
      expect(result!.source).toBe(data.source);
      expect(result!.flags).toBe(data.flags);
    });

    it('should handle Buffer/TypedArray objects', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'buffer.dat') });
      const data = Buffer.from([1, 2, 3, 4, 5]);
      await writeCache(cache, data);
      const result = await readCache<Buffer>(cache);
      expect(Buffer.isBuffer(result)).toBe(true);
      expect(result).toEqual(data);
    });

    it('should work with any file extension', async () => {
      for (const ext of ['.json', '.dat', '.cache', '.yaml', '.xml', '.foo', '']) {
        const cache = new Cachetta({ path: join(tempDir, `data${ext}`) });
        await writeCache(cache, { ext });
        expect(await readCache(cache)).toEqual({ ext });
      }
    });
  });

  describe('cache expiration', () => {
    it('should return data before expiration', async () => {
      const cachePath = join(tempDir, 'exp.json');
      const cache = new Cachetta({ path: cachePath, duration: 5000 });
      await writeCache(cache, { fresh: true });
      expect(await readCache(cache)).toEqual({ fresh: true });
    });

    it('should return null after expiration', async () => {
      const cachePath = join(tempDir, 'exp.json');
      const cache = new Cachetta({ path: cachePath, duration: 1000 });
      await writeCache(cache, { fresh: true });
      await setTimeOfFile(2000, cachePath);
      expect(await readCache(cache)).toBeNull();
    });

    it('should treat zero duration as always expired', async () => {
      const cachePath = join(tempDir, 'zero.json');
      const cache = new Cachetta({ path: cachePath, duration: 0 });
      await writeCache(cache, { data: true });
      expect(await readCache(cache)).toBeNull();
    });

    it('should treat negative duration as always expired', async () => {
      const cachePath = join(tempDir, 'neg.json');
      const cache = new Cachetta({ path: cachePath, duration: -1000 });
      await writeCache(cache, { data: true });
      expect(await readCache(cache)).toBeNull();
    });
  });

  describe('read/write flag combinations', () => {
    it('read=false, write=true: writes but does not read', async () => {
      const cachePath = join(tempDir, 'rw.json');
      const cache = new Cachetta({ path: cachePath, read: false, write: true });
      await writeCache(cache, { data: 1 });
      // File should exist with correct data
      const buffer = await fs.readFile(cachePath);
      expect(deserialize(buffer)).toEqual({ data: 1 });
      // But readCache should skip
      expect(await readCache(cache)).toBeNull();
    });

    it('read=true, write=false: does not write', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'ro.json'), read: true, write: false });
      await writeCache(cache, { data: 1 });
      // File should not exist
      await expect(fs.access(join(tempDir, 'ro.json'))).rejects.toThrow();
    });

    it('read=false, write=false: completely disabled', async () => {
      const cachePath = join(tempDir, 'disabled.json');
      const cache = new Cachetta({ path: cachePath, read: false, write: false });
      await writeCache(cache, { data: 1 });
      expect(await readCache(cache)).toBeNull();
      await expect(fs.access(cachePath)).rejects.toThrow();
    });
  });

  describe('dynamic path functions', () => {
    it('should resolve path from arguments', async () => {
      const cache = new Cachetta({
        path: (id: string) => join(tempDir, `${id}.json`),
      });

      await writeCache(cache, { id: 'a' }, 'a');
      await writeCache(cache, { id: 'b' }, 'b');

      expect(await readCache(cache, 'a')).toEqual({ id: 'a' });
      expect(await readCache(cache, 'b')).toEqual({ id: 'b' });
      expect(await readCache(cache, 'c')).toBeNull();
    });

    it('should support multi-arg path functions', async () => {
      const cache = new Cachetta({
        path: (type: string, id: string) => join(tempDir, type, `${id}.json`),
      });

      await writeCache(cache, { type: 'user', id: '1' }, 'user', '1');
      expect(await readCache(cache, 'user', '1')).toEqual({ type: 'user', id: '1' });
    });
  });

  describe('path function generates per-arg cache files', () => {
    it('produces distinct cache files for distinct args', async () => {
      const cache = new Cachetta({ path: (x: number) => join(tempDir, `${x}.json`) });

      let callCount = 0;
      const fn = (x: number) => {
        callCount++;
        return x * 2;
      };
      const cached = cache(fn);

      expect(await cached(5)).toBe(10);
      expect(await cached(5)).toBe(10); // served from cache
      expect(callCount).toBe(1);

      expect(await cached(10)).toBe(20);
      expect(callCount).toBe(2);
    });
  });

  describe('function wrapper patterns', () => {
    it('cache(fn) should wrap and cache', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'wrap.json') });
      let calls = 0;
      const fn = () => { calls++; return { result: calls }; };
      const cached = cache(fn);

      expect(await cached()).toEqual({ result: 1 });
      expect(await cached()).toEqual({ result: 1 });
      expect(calls).toBe(1);
    });

    it('cache.wrap(fn) should work identically', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'wrap2.json') });
      let calls = 0;
      const fn = () => { calls++; return { result: calls }; };
      const cached = cache.wrap(fn);

      expect(await cached()).toEqual({ result: 1 });
      expect(await cached()).toEqual({ result: 1 });
      expect(calls).toBe(1);
    });

    it('cache(fn, config) should apply config overrides', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'base.json') });
      let calls = 0;
      const fn = () => { calls++; return calls; };
      const cached = cache(fn, { path: join(tempDir, 'override.json'), duration: 60000 });

      expect(await cached()).toBe(1);
      expect(await cached()).toBe(1);

      // Verify it wrote to the override path
      const buffer = await fs.readFile(join(tempDir, 'override.json'));
      expect(deserialize(buffer)).toBe(1);
    });
  });

  describe('copy', () => {
    it('should create independent cache with overrides', async () => {
      const base = new Cachetta({
        path: join(tempDir, 'base.json'),
        duration: 1000,
        write: true,
        read: true,
      });

      const copy = base.copy({ path: join(tempDir, 'copy.json'), duration: 5000 });

      expect(copy.path).toBe(join(tempDir, 'copy.json'));
      expect(copy.duration).toBe(5000);
      expect(copy.write).toBe(true); // inherited
      expect(copy.read).toBe(true); // inherited
    });

    it('copy should function independently', async () => {
      const base = new Cachetta({ path: join(tempDir, 'base.json') });
      const copy = base.copy({ path: join(tempDir, 'copy.json') });

      await writeCache(base, { source: 'base' });
      await writeCache(copy, { source: 'copy' });

      expect(await readCache(base)).toEqual({ source: 'base' });
      expect(await readCache(copy)).toEqual({ source: 'copy' });
    });
  });

  describe('corrupt cache recovery', () => {
    it('should return null for corrupt data', async () => {
      const cachePath = join(tempDir, 'corrupt.json');
      const cache = new Cachetta({ path: cachePath });
      await fs.writeFile(cachePath, '{ broken json !!!');
      expect(await readCache(cache)).toBeNull();
    });

    it('should return null for empty file', async () => {
      const cachePath = join(tempDir, 'empty.json');
      const cache = new Cachetta({ path: cachePath });
      await fs.writeFile(cachePath, '');
      expect(await readCache(cache)).toBeNull();
    });

    it('should return null for random binary content', async () => {
      const cachePath = join(tempDir, 'binary.json');
      const cache = new Cachetta({ path: cachePath });
      await fs.writeFile(cachePath, Buffer.from([0x00, 0x01, 0x02, 0xFF]));
      expect(await readCache(cache)).toBeNull();
    });
  });

  describe('trusted path contract', () => {
    it('should write and read via an absolute path outside the CWD', async () => {
      const outsideDir = await fs.mkdtemp(join(tmpdir(), 'cachetta-trust-'));
      try {
        const cachePath = join(outsideDir, 'trusted.json');
        const cache = new Cachetta({ path: cachePath, write: true, read: true });
        await writeCache(cache, { trusted: true });
        expect(await readCache(cache)).toEqual({ trusted: true });
      } finally {
        await fs.rm(outsideDir, { recursive: true, force: true });
      }
    });
  });

  describe('atomic write safety', () => {
    it('should not leave partial files on write error', async () => {
      const cachePath = join(tempDir, 'atomic.json');
      const cache = new Cachetta({ path: cachePath });

      // Write valid data first
      await writeCache(cache, { first: true });
      expect(await readCache(cache)).toEqual({ first: true });

      // Write again - should atomically replace
      await writeCache(cache, { second: true });
      expect(await readCache(cache)).toEqual({ second: true });

      // Verify no .tmp files lingering
      const files = await fs.readdir(tempDir);
      const tmpFiles = files.filter(f => f.endsWith('.tmp'));
      expect(tmpFiles).toHaveLength(0);
    });
  });

  describe('missing directory auto-creation', () => {
    it('should create nested directories on write', async () => {
      const cachePath = join(tempDir, 'a', 'b', 'c', 'data.json');
      const cache = new Cachetta({ path: cachePath });
      await writeCache(cache, { nested: true });
      expect(await readCache(cache)).toEqual({ nested: true });
    });
  });

  describe('large data', () => {
    it('should handle deeply nested objects', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'large.json') });
      const data = {
        level1: {
          level2: {
            level3: {
              level4: {
                level5: {
                  array: Array.from({ length: 100 }, (_, i) => ({
                    id: i,
                    name: `item-${i}`,
                    tags: ['tag1', 'tag2', 'tag3'],
                  })),
                },
              },
            },
          },
        },
      };
      await writeCache(cache, data);
      expect(await readCache(cache)).toEqual(data);
    });
  });

  describe('CachettaError on invalid input', () => {
    it('should throw when readCache receives non-Cachetta', async () => {
      await expect(readCache({} as any)).rejects.toThrow(CachettaError);
    });

    it('should throw when readCache receives null', async () => {
      await expect(readCache(null as any)).rejects.toThrow(CachettaError);
    });
  });

  describe('promise deduplication', () => {
    it('should deduplicate concurrent calls to same cache path', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'dedup.json') });
      let callCount = 0;
      const slowFn = async () => {
        callCount++;
        await new Promise(r => setTimeout(r, 50));
        return { count: callCount };
      };
      const cached = cache(slowFn);

      // Fire two concurrent calls without awaiting
      const promise = Promise.all([cached(), cached()]);
      // Activate fake timers after promises are fired (readCache runs with real I/O),
      // then advance to resolve slowFn's setTimeout
      vi.useFakeTimers();
      await vi.advanceTimersByTimeAsync(50);
      vi.useRealTimers();
      const [r1, r2] = await promise;

      expect(r1).toEqual(r2);
      expect(callCount).toBe(1);
    });
  });

  describe('cache invalidation integration', () => {
    it('invalidate should delete cache and force re-fetch', async () => {
      const cachePath = join(tempDir, 'inv.json');
      const cache = new Cachetta({ path: cachePath });

      await writeCache(cache, { version: 1 });
      expect(await readCache(cache)).toEqual({ version: 1 });

      await cache.invalidate();
      expect(await readCache(cache)).toBeNull();

      await writeCache(cache, { version: 2 });
      expect(await readCache(cache)).toEqual({ version: 2 });
    });

    it('clear should keep a fresh entry unless forced', async () => {
      const cachePath = join(tempDir, 'clr.json');
      const cache = new Cachetta({ path: cachePath });
      await writeCache(cache, { data: 1 });
      await cache.clear();
      expect(await readCache(cache)).toEqual({ data: 1 });
      await cache.clear({ force: true });
      expect(await cache.exists()).toBe(false);
    });
  });

  describe('cache inspection integration', () => {
    it('exists should reflect file state', async () => {
      const cachePath = join(tempDir, 'inspect.json');
      const cache = new Cachetta({ path: cachePath });

      expect(await cache.exists()).toBe(false);
      await writeCache(cache, { data: 1 });
      expect(await cache.exists()).toBe(true);
      await cache.invalidate();
      expect(await cache.exists()).toBe(false);
    });

    it('age should return time since write', async () => {
      vi.useFakeTimers();
      try {
        const cachePath = join(tempDir, 'age.json');
        const cache = new Cachetta({ path: cachePath });

        expect(await cache.age()).toBeNull();
        await writeCache(cache, { data: 1 });
        // Align file mtime with fake clock
        await setTimeOfFile(0, cachePath);
        const ageMs = await cache.age();
        expect(ageMs).toBeGreaterThanOrEqual(0);
        expect(ageMs!).toBeLessThan(1000);
      } finally {
        vi.useRealTimers();
      }
    });

    it('info should return complete cache state', async () => {
      const cachePath = join(tempDir, 'info.json');
      const cache = new Cachetta({ path: cachePath, duration: 1000 });

      // Non-existent
      let info = await cache.info();
      expect(info.exists).toBe(false);
      expect(info.expired).toBe(false);

      // Fresh
      await writeCache(cache, { data: 1 });
      info = await cache.info();
      expect(info.exists).toBe(true);
      expect(info.expired).toBe(false);

      // Expired
      await setTimeOfFile(2000, cachePath);
      info = await cache.info();
      expect(info.exists).toBe(true);
      expect(info.expired).toBe(true);
    });
  });

  describe('conditional caching integration', () => {
    it('should skip caching when condition returns false', async () => {
      const cache = new Cachetta({
        path: join(tempDir, 'cond.json'),
        condition: (result) => result !== null && result !== undefined,
      });

      let calls = 0;
      const fn = () => {
        calls++;
        return calls <= 1 ? null : { data: calls };
      };
      const cached = cache(fn);

      // First call returns null, condition is false, not cached
      expect(await cached()).toBeNull();
      expect(calls).toBe(1);

      // Second call also runs (nothing cached)
      expect(await cached()).toEqual({ data: 2 });
      expect(calls).toBe(2);

      // Third call is cached (condition was true for {data: 2})
      expect(await cached()).toEqual({ data: 2 });
      expect(calls).toBe(2);
    });
  });

  describe('stale-while-revalidate integration', () => {
    it('should return stale data and refresh in background', async () => {
      const cachePath = join(tempDir, 'swr.json');
      const cache = new Cachetta({
        path: cachePath,
        duration: 1000,
        staleDuration: 30000,
      });

      let callCount = 0;
      const fn = () => {
        callCount++;
        return { version: callCount };
      };
      const cached = cache(fn);

      // First call: no cache, calls fn
      expect(await cached()).toEqual({ version: 1 });
      expect(callCount).toBe(1);

      // Use fake timers to advance clock for stale detection
      vi.useFakeTimers();
      await vi.advanceTimersByTimeAsync(2000);
      await setTimeOfFile(2000, cachePath);

      // Second call: should return stale data quickly
      const result = await cached();
      expect(result).toEqual({ version: 1 }); // stale data

      // Restore real timers so background refresh I/O can complete
      vi.useRealTimers();

      // Wait for the fire-and-forget background refresh to write updated data
      await vi.waitFor(async () => {
        const buffer = await fs.readFile(cachePath);
        expect(deserialize(buffer)).toEqual({ version: 2 });
      });
    });
  });

  describe('invalidation with path functions', () => {
    it('should invalidate specific path variants', async () => {
      const cache = new Cachetta({
        path: (id: string) => join(tempDir, `${id}.json`),
      });

      await writeCache(cache, { id: 'a' }, 'a');
      await writeCache(cache, { id: 'b' }, 'b');

      await cache.invalidate('a');
      expect(await readCache(cache, 'a')).toBeNull();
      expect(await readCache(cache, 'b')).toEqual({ id: 'b' });
    });
  });

  describe('inspection with path functions', () => {
    it('should check existence of specific path variants', async () => {
      const cache = new Cachetta({
        path: (id: string) => join(tempDir, `${id}.json`),
      });

      await writeCache(cache, { id: 'a' }, 'a');

      expect(await cache.exists('a')).toBe(true);
      expect(await cache.exists('b')).toBe(false);
    });

    it('should return age for specific path variants', async () => {
      vi.useFakeTimers();
      try {
        const cache = new Cachetta({
          path: (id: string) => join(tempDir, `${id}.json`),
        });

        await writeCache(cache, { id: 'a' }, 'a');
        // Align file mtime with fake clock
        const cachePath = join(tempDir, 'a.json');
        await setTimeOfFile(0, cachePath);
        const ageA = await cache.age('a');
        expect(ageA).not.toBeNull();
        expect(ageA!).toBeGreaterThanOrEqual(0);
        expect(ageA!).toBeLessThan(1000);
        expect(await cache.age('b')).toBeNull();
      } finally {
        vi.useRealTimers();
      }
    });
  });

  // =============================================
  // Sync API tests
  // =============================================

  describe('sync: basic read/write cycle', () => {
    it('should write and read data synchronously', () => {
      const cache = new Cachetta({ path: join(tempDir, 'sync-data.json') });
      const data = { key: 'value', nested: { arr: [1, 2, 3] } };
      writeCacheSync(cache, data);
      expect(readCacheSync(cache)).toEqual(data);
    });

    it('should return null for nonexistent cache', () => {
      const cache = new Cachetta({ path: join(tempDir, 'sync-nope.json') });
      expect(readCacheSync(cache)).toBeNull();
    });

    it('should handle complex types (Date, Map, Set)', () => {
      const dateCache = new Cachetta({ path: join(tempDir, 'sync-date.dat') });
      const now = new Date();
      writeCacheSync(dateCache, now);
      const dateResult = readCacheSync<Date>(dateCache);
      expect(dateResult).toBeInstanceOf(Date);
      expect(dateResult!.getTime()).toBe(now.getTime());

      const mapCache = new Cachetta({ path: join(tempDir, 'sync-map.dat') });
      const map = new Map([['x', 10]]);
      writeCacheSync(mapCache, map);
      const mapResult = readCacheSync<Map<string, number>>(mapCache);
      expect(mapResult).toBeInstanceOf(Map);
      expect(mapResult!.get('x')).toBe(10);
    });

    it('should work with any file extension', () => {
      for (const ext of ['.json', '.dat', '.cache', '.foo', '']) {
        const cache = new Cachetta({ path: join(tempDir, `sync${ext}`) });
        writeCacheSync(cache, { ext });
        expect(readCacheSync(cache)).toEqual({ ext });
      }
    });
  });

  describe('sync: cache expiration', () => {
    it('should return data before expiration', () => {
      const cachePath = join(tempDir, 'sync-exp.json');
      const cache = new Cachetta({ path: cachePath, duration: 5000 });
      writeCacheSync(cache, { fresh: true });
      expect(readCacheSync(cache)).toEqual({ fresh: true });
    });

    it('should return null after expiration', () => {
      const cachePath = join(tempDir, 'sync-exp.json');
      const cache = new Cachetta({ path: cachePath, duration: 1000 });
      writeCacheSync(cache, { fresh: true });
      setTimeOfFileSync(2000, cachePath);
      expect(readCacheSync(cache)).toBeNull();
    });
  });

  describe('sync: read/write flag combinations', () => {
    it('read=false: writes but does not read', () => {
      const cachePath = join(tempDir, 'sync-rw.json');
      const cache = new Cachetta({ path: cachePath, read: false, write: true });
      writeCacheSync(cache, { data: 1 });
      expect(readCacheSync(cache)).toBeNull();
    });

    it('write=false: does not write', () => {
      const cachePath = join(tempDir, 'sync-ro.json');
      const cache = new Cachetta({ path: cachePath, read: true, write: false });
      writeCacheSync(cache, { data: 1 });
      expect(() => accessSync(cachePath)).toThrow();
    });
  });

  describe('sync: wrapSync', () => {
    it('should wrap a sync function and cache its result', () => {
      const cache = new Cachetta({ path: join(tempDir, 'sync-wrap.json') });
      let calls = 0;
      const fn = () => { calls++; return { result: calls }; };
      const cached = cache.wrapSync(fn);

      expect(cached()).toEqual({ result: 1 });
      expect(cached()).toEqual({ result: 1 });
      expect(calls).toBe(1);
    });

    it('should respect expiration for wrapped sync functions', () => {
      const cachePath = join(tempDir, 'sync-wrap-exp.json');
      const cache = new Cachetta({ path: cachePath, duration: 1000 });
      let calls = 0;
      const fn = () => { calls++; return calls; };
      const cached = cache.wrapSync(fn);

      expect(cached()).toBe(1);
      expect(cached()).toBe(1);
      expect(calls).toBe(1);

      setTimeOfFileSync(2000, cachePath);
      expect(cached()).toBe(2);
      expect(calls).toBe(2);
    });

    it('should respect condition for sync wrapping', () => {
      const cache = new Cachetta({
        path: join(tempDir, 'sync-cond.json'),
        condition: (result) => result !== null,
      });
      let calls = 0;
      const fn = () => {
        calls++;
        return calls <= 1 ? null : { data: calls };
      };
      const cached = cache.wrapSync(fn);

      expect(cached()).toBeNull();
      expect(calls).toBe(1);
      expect(cached()).toEqual({ data: 2 });
      expect(calls).toBe(2);
      expect(cached()).toEqual({ data: 2 });
      expect(calls).toBe(2);
    });
  });

  describe('sync: stale-while-revalidate', () => {
    it('should return stale data without background refresh', () => {
      const cachePath = join(tempDir, 'sync-swr.json');
      const cache = new Cachetta({ path: cachePath, duration: 1000, staleDuration: 30000 });
      let calls = 0;
      const fn = () => { calls++; return { version: calls }; };
      const cached = cache.wrapSync(fn);

      expect(cached()).toEqual({ version: 1 });
      expect(calls).toBe(1);

      // Age the file past duration but within staleDuration
      setTimeOfFileSync(2000, cachePath);

      expect(cached()).toEqual({ version: 1 }); // stale data returned
      // In sync mode, no background refresh fires, so calls stays at 1
      // (the stale data is returned directly)
    });
  });

  describe('sync: invalidateSync', () => {
    it('should delete cache file synchronously', () => {
      const cachePath = join(tempDir, 'sync-inv.json');
      const cache = new Cachetta({ path: cachePath });
      writeCacheSync(cache, { data: 1 });
      expect(readCacheSync(cache)).toEqual({ data: 1 });

      cache.invalidateSync();
      expect(readCacheSync(cache)).toBeNull();
    });

    it('clearSync should keep a fresh entry unless forced', () => {
      const cachePath = join(tempDir, 'sync-clr.json');
      const cache = new Cachetta({ path: cachePath });
      writeCacheSync(cache, { data: 1 });
      cache.clearSync();
      expect(readCacheSync(cache)).toEqual({ data: 1 });
      cache.clearSync({ force: true });
      expect(cache.existsSync()).toBe(false);
    });
  });

  describe('sync: existsSync / ageSync / infoSync', () => {
    it('existsSync should reflect file state', () => {
      const cachePath = join(tempDir, 'sync-exists.json');
      const cache = new Cachetta({ path: cachePath });

      expect(cache.existsSync()).toBe(false);
      writeCacheSync(cache, { data: 1 });
      expect(cache.existsSync()).toBe(true);
      cache.invalidateSync();
      expect(cache.existsSync()).toBe(false);
    });

    it('ageSync should return time since write', () => {
      const cachePath = join(tempDir, 'sync-age.json');
      const cache = new Cachetta({ path: cachePath });

      expect(cache.ageSync()).toBeNull();
      writeCacheSync(cache, { data: 1 });
      const ageMs = cache.ageSync();
      expect(ageMs).toBeGreaterThanOrEqual(0);
      expect(ageMs!).toBeLessThan(1000);
    });

    it('infoSync should return complete cache state', () => {
      const cachePath = join(tempDir, 'sync-info.json');
      const cache = new Cachetta({ path: cachePath, duration: 1000 });

      let info = cache.infoSync();
      expect(info.exists).toBe(false);
      expect(info.expired).toBe(false);

      writeCacheSync(cache, { data: 1 });
      info = cache.infoSync();
      expect(info.exists).toBe(true);
      expect(info.expired).toBe(false);

      setTimeOfFileSync(2000, cachePath);
      info = cache.infoSync();
      expect(info.exists).toBe(true);
      expect(info.expired).toBe(true);
    });
  });

  describe('sync: directory auto-creation', () => {
    it('should create nested directories on sync write', () => {
      const cachePath = join(tempDir, 'a', 'b', 'c', 'sync-data.json');
      const cache = new Cachetta({ path: cachePath });
      writeCacheSync(cache, { nested: true });
      expect(readCacheSync(cache)).toEqual({ nested: true });
    });
  });

  describe('sync: corrupt cache recovery', () => {
    it('should return null for corrupt data', () => {
      const cachePath = join(tempDir, 'sync-corrupt.json');
      const cache = new Cachetta({ path: cachePath });
      fsWriteFileSync(cachePath, '{ broken data !!!');
      expect(readCacheSync(cache)).toBeNull();
    });
  });

  describe('sync: trusted path contract', () => {
    it('should write and read via an absolute path outside the CWD', async () => {
      const outsideDir = await fs.mkdtemp(join(tmpdir(), 'cachetta-trust-sync-'));
      try {
        const cachePath = join(outsideDir, 'trusted.json');
        const cache = new Cachetta({ path: cachePath, write: true, read: true });
        writeCacheSync(cache, { trusted: true });
        expect(readCacheSync(cache)).toEqual({ trusted: true });
      } finally {
        await fs.rm(outsideDir, { recursive: true, force: true });
      }
    });
  });

  // Literal string path with args — post sibling-removal semantics (issue #45).
  // A string path is now used verbatim; arguments to the wrapped function do
  // not produce a `{name}-{hash}{ext}` sibling. Consumers wanting arg-keyed
  // caching should use a path function (or `.hashed` once it ships).
  describe('literal string path with args (issue #45)', () => {
    it('_getPath returns the literal path regardless of args', () => {
      const cache = new Cachetta({ path: './data/cache.json' });
      expect(cache._getPath('arg1')).toBe('./data/cache.json');
      expect(cache._getPath('arg1', 'arg2')).toBe('./data/cache.json');
      expect(cache._getPath('a')).toBe(cache._getPath('b'));
    });

    it('_getPath returns the literal path for extensionless paths', () => {
      const cache = new Cachetta({ path: './data/cache' });
      expect(cache._getPath('arg1')).toBe('./data/cache');
      expect(cache._getPath('a')).toBe(cache._getPath('b'));
    });

    it('decorator writes only the literal file, no sibling-hash files', async () => {
      const cachePath = join(tempDir, 'data.json');
      const cache = new Cachetta({ path: cachePath });

      let callCount = 0;
      const compute = cache((x: string) => {
        callCount++;
        return { x };
      });

      const r1 = await compute('a');
      const r2 = await compute('b');
      const r3 = await compute('a');

      // Only the literal cache file exists — no `data-<hash>.json` siblings.
      const entries = (await fs.readdir(tempDir)).sort();
      expect(entries).toEqual(['data.json']);

      // All three calls return the first-written value; the body runs once.
      expect(r1).toEqual({ x: 'a' });
      expect(r2).toEqual({ x: 'a' });
      expect(r3).toEqual({ x: 'a' });
      expect(callCount).toBe(1);
    });

    it('invalidate with args removes the literal file', async () => {
      const cachePath = join(tempDir, 'data.json');
      const cache = new Cachetta({ path: cachePath });

      const compute = cache((x: string) => ({ x }));
      await compute('a');
      await expect(fs.access(cachePath)).resolves.toBeUndefined();

      await cache.invalidate('anything');
      await expect(fs.access(cachePath)).rejects.toThrow();
    });
  });
});
