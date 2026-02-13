import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cacheFn } from './cache-fn.js';
import { Cachetta } from '../Cachetta.js';
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
});
