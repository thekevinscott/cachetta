import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { promises as fs } from 'fs';
import { join } from 'path';
import { cacheFn, cacheFnSync } from './cache-fn.js';
import { Cachetta } from '../Cachetta.js'; // eslint-disable-line mock-isolation/collaborators -- real Cachetta config object used as a plain-data fixture
import { readCache, readStaleCache } from '../read-cache.js';
import { writeCache } from '../write-cache.js';
import type * as _readCacheTypes from '../read-cache.js';
import type * as _writeCacheTypes from '../write-cache.js';

// Mock the cache functions
vi.mock('../read-cache.js', async () => {
  const actualReadCache = await import('../read-cache.js') as typeof _readCacheTypes;
  return {
    ...actualReadCache,
    readCache: vi.fn() as unknown as typeof actualReadCache.readCache,
    readStaleCache: vi.fn() as unknown as typeof actualReadCache.readStaleCache,
  }
});

vi.mock('../write-cache.js', async () => {
  const actualWriteCache = await import('../write-cache.js') as typeof _writeCacheTypes;
  return {
    ...actualWriteCache,
    writeCache: vi.fn() as unknown as typeof actualWriteCache.writeCache,
  }
});


describe('cacheFn', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
  });

  it('should return cached data when available', async () => {
    const cache = new Cachetta({ path: './test-cache.json' });
    const originalMethod = vi.fn().mockResolvedValue('original result');
    const cachedData = 'cached result';

    vi.mocked(readCache).mockResolvedValue(cachedData);

    const wrappedFn = cacheFn(cache, originalMethod);
    const result = await wrappedFn.call({}, 'arg1', 'arg2');

    expect(result).toBe(cachedData);
    expect(readCache).toHaveBeenCalledWith(cache, 'arg1', 'arg2');
    expect(originalMethod).not.toHaveBeenCalled();
    expect(writeCache).not.toHaveBeenCalled();
  });

  it('should call original method and cache result when no cache exists', async () => {
    const cache = new Cachetta({ path: './test-cache.json' });
    const originalMethod = vi.fn().mockResolvedValue('original result');

    vi.mocked(readCache).mockResolvedValue(null);
    vi.mocked(writeCache).mockResolvedValue(undefined);

    const wrappedFn = cacheFn(cache, originalMethod);
    const result = await wrappedFn.call({}, 'arg1', 'arg2');

    expect(result).toBe('original result');
    expect(readCache).toHaveBeenCalledWith(cache, 'arg1', 'arg2');
    expect(originalMethod).toHaveBeenCalledWith('arg1', 'arg2');
    expect(writeCache).toHaveBeenCalledWith(cache, 'original result', 'arg1', 'arg2');
  });

  it('should handle sync functions', async () => {
    const cache = new Cachetta({ path: './test-cache.json' });
    const originalMethod = vi.fn().mockReturnValue('sync result');

    vi.mocked(readCache).mockResolvedValue(null);
    vi.mocked(writeCache).mockResolvedValue(undefined);

    const wrappedFn = cacheFn(cache, originalMethod);
    const result = await wrappedFn.call({}, 'arg1');

    expect(result).toBe('sync result');
    expect(originalMethod).toHaveBeenCalledWith('arg1');
    expect(writeCache).toHaveBeenCalledWith(cache, 'sync result', 'arg1');
  });

  it('should preserve this context', async () => {
    const cache = new Cachetta({ path: './test-cache.json' });
    const context = { value: 'test' };
    const originalMethod = vi.fn().mockResolvedValue('result');

    vi.mocked(readCache).mockResolvedValue(null);

    const wrappedFn = cacheFn(cache, originalMethod);
    await wrappedFn.call(context, 'arg1');

    expect(originalMethod).toHaveBeenCalledWith('arg1');
    expect(originalMethod.mock.instances[0]).toBe(context);
  });

  describe('falsy cached values', () => {
    it('should return cached 0 without calling original method', async () => {
      const cache = new Cachetta({ path: './test-cache.json' });
      const originalMethod = vi.fn().mockResolvedValue('should not be called');

      vi.mocked(readCache).mockResolvedValue(0);

      const wrappedFn = cacheFn(cache, originalMethod);
      const result = await wrappedFn.call({});

      expect(result).toBe(0);
      expect(originalMethod).not.toHaveBeenCalled();
    });

    it('should return cached false without calling original method', async () => {
      const cache = new Cachetta({ path: './test-cache.json' });
      const originalMethod = vi.fn().mockResolvedValue('should not be called');

      vi.mocked(readCache).mockResolvedValue(false);

      const wrappedFn = cacheFn(cache, originalMethod);
      const result = await wrappedFn.call({});

      expect(result).toBe(false);
      expect(originalMethod).not.toHaveBeenCalled();
    });

    it('should return cached empty string without calling original method', async () => {
      const cache = new Cachetta({ path: './test-cache.json' });
      const originalMethod = vi.fn().mockResolvedValue('should not be called');

      vi.mocked(readCache).mockResolvedValue('');

      const wrappedFn = cacheFn(cache, originalMethod);
      const result = await wrappedFn.call({});

      expect(result).toBe('');
      expect(originalMethod).not.toHaveBeenCalled();
    });

    it('should treat null as cache miss and call original method', async () => {
      const cache = new Cachetta({ path: './test-cache.json' });
      const originalMethod = vi.fn().mockResolvedValue('fresh result');

      vi.mocked(readCache).mockResolvedValue(null);
      vi.mocked(writeCache).mockResolvedValue(undefined);

      const wrappedFn = cacheFn(cache, originalMethod);
      const result = await wrappedFn.call({});

      expect(result).toBe('fresh result');
      expect(originalMethod).toHaveBeenCalled();
    });
  });

  describe('condition', () => {
    it('should write to cache when condition returns true', async () => {
      const cache = new Cachetta({
        path: './test-cache.json',
        condition: (result) => result !== null,
      });
      const originalMethod = vi.fn().mockResolvedValue('valid');

      vi.mocked(readCache).mockResolvedValue(null);
      vi.mocked(writeCache).mockResolvedValue(undefined);

      const wrappedFn = cacheFn(cache, originalMethod);
      const result = await wrappedFn.call({});

      expect(result).toBe('valid');
      expect(writeCache).toHaveBeenCalled();
    });

    it('should skip cache write when condition returns false', async () => {
      const cache = new Cachetta({
        path: './test-cache.json',
        condition: (result) => result !== null,
      });
      const originalMethod = vi.fn().mockResolvedValue(null);

      vi.mocked(readCache).mockResolvedValue(null);
      vi.mocked(writeCache).mockResolvedValue(undefined);

      const wrappedFn = cacheFn(cache, originalMethod);
      const result = await wrappedFn.call({});

      expect(result).toBeNull();
      expect(writeCache).not.toHaveBeenCalled();
    });

    it('should still return result when condition prevents caching', async () => {
      const cache = new Cachetta({
        path: './test-cache.json',
        condition: () => false,
      });
      const originalMethod = vi.fn().mockResolvedValue('result');

      vi.mocked(readCache).mockResolvedValue(null);

      const wrappedFn = cacheFn(cache, originalMethod);
      const result = await wrappedFn.call({});

      expect(result).toBe('result');
    });
  });

  describe('in-flight dedup scoping', () => {
    it('should not share in-flight promises between two instances wrapping different functions over the same path', async () => {
      const cacheA = new Cachetta({ path: './same-path.json' });
      const cacheB = new Cachetta({ path: './same-path.json' });

      let resolveA: (value: string) => void = () => {};
      const originalMethodA = vi.fn(() => new Promise<string>((resolve) => { resolveA = resolve; }));
      const originalMethodB = vi.fn().mockResolvedValue('result-b');

      vi.mocked(readCache).mockResolvedValue(null);
      vi.mocked(writeCache).mockResolvedValue(undefined);

      const wrappedA = cacheFn(cacheA, originalMethodA);
      const wrappedB = cacheFn(cacheB, originalMethodB);

      // Start A's call but don't resolve it yet - it will be "in flight" for the shared path.
      const pendingA = wrappedA.call({});
      await vi.waitFor(() => expect(originalMethodA).toHaveBeenCalled());

      // B should not receive A's in-flight promise just because the path collides.
      const resultB = await wrappedB.call({});

      expect(resultB).toBe('result-b');
      expect(originalMethodB).toHaveBeenCalled();

      resolveA('result-a');
      await pendingA;
    });

    it('should still dedup concurrent calls to a single wrapper', async () => {
      const cache = new Cachetta({ path: './same-path.json' });

      let resolveOriginal: (value: string) => void = () => {};
      const originalMethod = vi.fn(() => new Promise<string>((resolve) => { resolveOriginal = resolve; }));

      vi.mocked(readCache).mockResolvedValue(null);
      vi.mocked(writeCache).mockResolvedValue(undefined);

      const wrappedFn = cacheFn(cache, originalMethod);

      const call1 = wrappedFn.call({});
      const call2 = wrappedFn.call({});

      await vi.waitFor(() => expect(originalMethod).toHaveBeenCalled());
      resolveOriginal('shared result');

      const [result1, result2] = await Promise.all([call1, call2]);

      expect(result1).toBe('shared result');
      expect(result2).toBe('shared result');
      expect(originalMethod).toHaveBeenCalledTimes(1);
    });
  });

  describe('stale-while-revalidate', () => {
    it('should return stale data when available', async () => {
      const cache = new Cachetta({
        path: './test-cache.json',
        staleDuration: 30000,
      });
      const originalMethod = vi.fn().mockResolvedValue('fresh result');

      vi.mocked(readCache).mockResolvedValue(null);
      vi.mocked(readStaleCache).mockResolvedValue('stale result');
      vi.mocked(writeCache).mockResolvedValue(undefined);

      const wrappedFn = cacheFn(cache, originalMethod);
      const result = await wrappedFn.call({});

      expect(result).toBe('stale result');
    });

    it('should trigger background refresh when returning stale data', async () => {
      const cache = new Cachetta({
        path: './test-cache.json',
        staleDuration: 30000,
      });
      const originalMethod = vi.fn().mockResolvedValue('fresh result');

      vi.mocked(readCache).mockResolvedValue(null);
      vi.mocked(readStaleCache).mockResolvedValue('stale result');
      vi.mocked(writeCache).mockResolvedValue(undefined);

      const wrappedFn = cacheFn(cache, originalMethod);
      await wrappedFn.call({});

      // Wait for the background refresh to complete
      await vi.waitFor(() => {
        expect(originalMethod).toHaveBeenCalled();
      });
      await vi.waitFor(() => {
        expect(writeCache).toHaveBeenCalled();
      });
    });

    it('should evaluate the condition during a background refresh', async () => {
      const condition = vi.fn((result: unknown) => result === 'fresh result');
      const cache = new Cachetta({
        path: './test-cache.json',
        staleDuration: 30000,
        condition,
      });
      const originalMethod = vi.fn().mockResolvedValue('fresh result');

      vi.mocked(readCache).mockResolvedValue(null);
      vi.mocked(readStaleCache).mockResolvedValue('stale result');
      vi.mocked(writeCache).mockResolvedValue(undefined);

      const wrappedFn = cacheFn(cache, originalMethod);
      const result = await wrappedFn.call({});
      expect(result).toBe('stale result');

      // The background refresh must consult the condition before writing.
      await vi.waitFor(() => {
        expect(condition).toHaveBeenCalledWith('fresh result');
      });
      await vi.waitFor(() => {
        expect(writeCache).toHaveBeenCalled();
      });
    });

    it('should fall through to normal fetch when no stale data', async () => {
      const cache = new Cachetta({
        path: './test-cache.json',
        staleDuration: 30000,
      });
      const originalMethod = vi.fn().mockResolvedValue('fresh result');

      vi.mocked(readCache).mockResolvedValue(null);
      vi.mocked(readStaleCache).mockResolvedValue(null);
      vi.mocked(writeCache).mockResolvedValue(undefined);

      const wrappedFn = cacheFn(cache, originalMethod);
      const result = await wrappedFn.call({});

      expect(result).toBe('fresh result');
      expect(writeCache).toHaveBeenCalled();
    });

    it('should not let non-stale caller pick up a failing background refresh', async () => {
      const cache = new Cachetta({
        path: './test-cache.json',
        staleDuration: 30000,
      });

      let callCount = 0;
      const originalMethod = vi.fn().mockImplementation(async () => {
        callCount++;
        if (callCount === 1) {
          // Background refresh fails
          throw new Error('refresh failed');
        }
        return 'fresh result';
      });

      vi.mocked(writeCache).mockResolvedValue(undefined);

      // First call: stale hit triggers background refresh that will fail
      vi.mocked(readCache).mockResolvedValue(null);
      vi.mocked(readStaleCache).mockResolvedValue('stale data');

      const wrappedFn = cacheFn(cache, originalMethod);
      const result1 = await wrappedFn.call({});
      expect(result1).toBe('stale data');

      // Wait for the background refresh to fail
      await new Promise(r => setTimeout(r, 10));

      // Second call: non-stale (no stale data available), should run the function fresh
      vi.mocked(readCache).mockResolvedValue(null);
      vi.mocked(readStaleCache).mockResolvedValue(null);

      const result2 = await wrappedFn.call({});
      expect(result2).toBe('fresh result');
      expect(callCount).toBe(2);
    });
  });

  describe('in-flight deduplication', () => {
    it('should return the existing in-flight promise for concurrent identical calls', async () => {
      const cache = new Cachetta({ path: './test-cache.json' });

      let resolveOriginal: (value: string) => void = () => {};
      const originalMethod = vi.fn().mockImplementation(
        () => new Promise<string>((resolve) => { resolveOriginal = resolve; }),
      );

      vi.mocked(readCache).mockResolvedValue(null);
      vi.mocked(writeCache).mockResolvedValue(undefined);

      const wrappedFn = cacheFn(cache, originalMethod);

      // Fire two concurrent calls with the same cache key.
      const p1 = wrappedFn.call({});
      const p2 = wrappedFn.call({});

      // Let the microtasks settle so both callers pass the readCache await and
      // the in-flight promise is registered before the original method resolves.
      await vi.waitFor(() => {
        expect(originalMethod).toHaveBeenCalledTimes(1);
      });
      resolveOriginal('dedup result');

      const [r1, r2] = await Promise.all([p1, p2]);
      expect(r1).toBe('dedup result');
      expect(r2).toBe('dedup result');
      // The original method should only run once thanks to in-flight dedup.
      expect(originalMethod).toHaveBeenCalledTimes(1);
    });
  });
});

describe('cacheFnSync', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp('cachetta-test-');
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
    vi.restoreAllMocks();
  });

  it('should call the original method and cache the result on a miss', () => {
    const cachePath = join(tempDir, 'sync.json');
    const cache = new Cachetta({ path: cachePath });
    const originalMethod = vi.fn().mockReturnValue('sync result');

    const wrapped = cacheFnSync(cache, originalMethod);
    expect(wrapped.call({})).toBe('sync result');
    expect(originalMethod).toHaveBeenCalledTimes(1);
  });

  it('should return cached data without calling the original method', () => {
    const cachePath = join(tempDir, 'sync-hit.json');
    const cache = new Cachetta({ path: cachePath, duration: 60000 });
    const originalMethod = vi.fn().mockReturnValue('fresh');

    const wrapped = cacheFnSync(cache, originalMethod);
    expect(wrapped.call({})).toBe('fresh');
    // Second call hits the on-disk cache.
    expect(wrapped.call({})).toBe('fresh');
    expect(originalMethod).toHaveBeenCalledTimes(1);
  });

  it('should skip the cache write when the condition returns false', async () => {
    const cachePath = join(tempDir, 'sync-cond.json');
    const cache = new Cachetta({ path: cachePath, condition: () => false });
    const originalMethod = vi.fn().mockReturnValue('uncached');

    const wrapped = cacheFnSync(cache, originalMethod);
    expect(wrapped.call({})).toBe('uncached');
    await expect(fs.access(cachePath)).rejects.toThrow();
  });

  it('should return stale data when within the stale window', async () => {
    const cachePath = join(tempDir, 'sync-stale.json');
    const cache = new Cachetta({ path: cachePath, duration: 1000, staleDuration: 30000 });
    const originalMethod = vi.fn().mockReturnValue('first');

    const wrapped = cacheFnSync(cache, originalMethod);
    // Prime the cache.
    expect(wrapped.call({})).toBe('first');
    expect(originalMethod).toHaveBeenCalledTimes(1);

    // Age the file so it is expired but within the stale window.
    const oldTime = new Date(Date.now() - 5000);
    await fs.utimes(cachePath, oldTime, oldTime);

    // The stale read returns the original data; sync has no background refresh.
    expect(wrapped.call({})).toBe('first');
    expect(originalMethod).toHaveBeenCalledTimes(1);
  });

  it('should fall through to a fresh call when stale data is unavailable', async () => {
    const cachePath = join(tempDir, 'sync-no-stale.json');
    const cache = new Cachetta({ path: cachePath, duration: 1000, staleDuration: 5000 });
    let callCount = 0;
    const originalMethod = vi.fn().mockImplementation(() => `result-${++callCount}`);

    const wrapped = cacheFnSync(cache, originalMethod);
    expect(wrapped.call({})).toBe('result-1');

    // Age the file past both duration and the stale window.
    const oldTime = new Date(Date.now() - 60000);
    await fs.utimes(cachePath, oldTime, oldTime);

    expect(wrapped.call({})).toBe('result-2');
    expect(originalMethod).toHaveBeenCalledTimes(2);
  });
});
