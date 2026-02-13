import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { promises as fs } from 'fs';
import { join } from 'path';
import { Cachetta, readCache, writeCache, CachettaError, InvalidPathError, UnsupportedFormatError } from 'cachetta';

const setTimeOfFile = async (amount: number, cachePath: string) => {
  const oldTime = new Date(Date.now() - amount);
  await fs.utimes(cachePath, oldTime, oldTime);
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
    it('should write and read JSON data', async () => {
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
      // readCache returns null for both missing and null-valued, so this tests the write path
      const content = await fs.readFile(join(tempDir, 'null.json'), 'utf8');
      expect(content).toBe('null');
    });

    it('should handle string as cached value', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'str.json') });
      await writeCache(cache, 'hello world');
      const content = await fs.readFile(join(tempDir, 'str.json'), 'utf8');
      expect(JSON.parse(content)).toBe('hello world');
    });

    it('should handle number as cached value', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'num.json') });
      await writeCache(cache, 42);
      const content = await fs.readFile(join(tempDir, 'num.json'), 'utf8');
      expect(JSON.parse(content)).toBe(42);
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
      // File should exist
      const content = await fs.readFile(cachePath, 'utf8');
      expect(JSON.parse(content)).toEqual({ data: 1 });
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

  describe('auto cache key generation', () => {
    it('should auto-generate unique paths when wrapping with args', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'cache.json') });

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
      const content = await fs.readFile(join(tempDir, 'override.json'), 'utf8');
      expect(JSON.parse(content)).toBe(1);
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
    it('should return null for corrupt JSON', async () => {
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

    it('should return null for non-JSON content', async () => {
      const cachePath = join(tempDir, 'binary.json');
      const cache = new Cachetta({ path: cachePath });
      await fs.writeFile(cachePath, Buffer.from([0x00, 0x01, 0x02, 0xFF]));
      expect(await readCache(cache)).toBeNull();
    });
  });

  describe('path traversal rejection', () => {
    it('should throw InvalidPathError for .. segments in readCache', async () => {
      const cache = new Cachetta({ path: '../etc/passwd' });
      await expect(readCache(cache)).rejects.toThrow(InvalidPathError);
    });

    it('should throw InvalidPathError for .. segments in writeCache', async () => {
      const cache = new Cachetta({ path: join(tempDir, '../../escape.json') });
      await expect(writeCache(cache, { bad: true })).rejects.toThrow(InvalidPathError);
    });
  });

  describe('prototype pollution prevention', () => {
    it('should strip __proto__ from cached data', async () => {
      const cachePath = join(tempDir, 'proto.json');
      const cache = new Cachetta({ path: cachePath });
      await fs.writeFile(cachePath, '{"__proto__":{"admin":true},"safe":"ok"}');
      const result = await readCache<Record<string, unknown>>(cache);
      expect(result).toEqual({ safe: 'ok' });
      expect((result as any).__proto__?.admin).toBeUndefined();
    });

    it('should strip constructor and prototype keys', async () => {
      const cachePath = join(tempDir, 'proto2.json');
      const cache = new Cachetta({ path: cachePath });
      await fs.writeFile(cachePath, '{"constructor":{"hack":true},"prototype":{"evil":true},"data":1}');
      const result = await readCache<Record<string, unknown>>(cache);
      expect(result).toEqual({ data: 1 });
    });

    it('should strip dangerous keys in nested objects', async () => {
      const cachePath = join(tempDir, 'nested-proto.json');
      const cache = new Cachetta({ path: cachePath });
      await fs.writeFile(cachePath, '{"obj":{"__proto__":{"bad":true},"ok":"yes"}}');
      const result = await readCache<Record<string, any>>(cache);
      expect(result).toEqual({ obj: { ok: 'yes' } });
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

  describe('unsupported formats', () => {
    it('should throw UnsupportedFormatError for non-JSON extension on write', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'data.xml') });
      await expect(writeCache(cache, { data: 1 })).rejects.toThrow(UnsupportedFormatError);
    });

    it('should throw UnsupportedFormatError for non-JSON extension on read of existing file', async () => {
      const cachePath = join(tempDir, 'data.yaml');
      await fs.writeFile(cachePath, 'key: value');
      const cache = new Cachetta({ path: cachePath });
      await expect(readCache(cache)).rejects.toThrow(UnsupportedFormatError);
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

  describe('LRU cache integration', () => {
    it('should serve from LRU on second read', async () => {
      const cachePath = join(tempDir, 'lru.json');
      const cache = new Cachetta({ path: cachePath, lruSize: 5, duration: 60000 });

      await writeCache(cache, { lru: true });

      // First read populates LRU
      expect(await readCache(cache)).toEqual({ lru: true });

      // Delete the file - LRU should still serve
      await fs.unlink(cachePath);
      expect(await readCache(cache)).toEqual({ lru: true });
    });

    it('LRU should respect duration', async () => {
      vi.useFakeTimers();
      try {
        const cachePath = join(tempDir, 'lru-exp.json');
        const cache = new Cachetta({ path: cachePath, lruSize: 5, duration: 100 });

        await writeCache(cache, { data: 1 });
        expect(await readCache(cache)).toEqual({ data: 1 });

        // Advance fake clock past LRU expiry and age the file to match
        await vi.advanceTimersByTimeAsync(150);
        await setTimeOfFile(150, cachePath);

        // Both LRU entry and file are expired, so readCache should return null
        expect(await readCache(cache)).toBeNull();
      } finally {
        vi.useRealTimers();
      }
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

    it('clear should work as alias for invalidate', async () => {
      const cachePath = join(tempDir, 'clr.json');
      const cache = new Cachetta({ path: cachePath });
      await writeCache(cache, { data: 1 });
      await cache.clear();
      expect(await readCache(cache)).toBeNull();
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

      // Use fake timers to advance clock for LRU expiry and stale detection
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
        const freshContent = await fs.readFile(cachePath, 'utf8');
        expect(JSON.parse(freshContent)).toEqual({ version: 2 });
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
});
