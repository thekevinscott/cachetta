import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { Cachetta } from './Cachetta.js';
import { LRU_MISS } from './constants.js';
import type { CacheConfig } from './types.js';
import { cacheFn } from './utils/cache-fn.js';
import { promises as fs } from 'fs';
import { join } from 'path';
import type * as _cacheFnTypes from './utils/cache-fn.js';

// Mock the cache functions
vi.mock('./utils/cache-fn.js', async () => {
  const actualCacheFn = await import('./utils/cache-fn.js') as typeof _cacheFnTypes;
  return {
    ...actualCacheFn,
    cacheFn: vi.fn() as unknown as typeof actualCacheFn.cacheFn,
  }
});

describe('Cachetta', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
  });

  describe('constructor', () => {
    it('should create instance with default values', () => {
      const cache = new Cachetta({ path: './test.json' });

      expect(cache.path).toBe('./test.json');
      expect(cache.write).toBe(true);
      expect(cache.read).toBe(true);
      expect(cache.duration).toBe(7 * 24 * 60 * 60 * 1000); // 7 days
      expect(cache.lruSize).toBeUndefined();
    });

    it('should create instance with custom values', () => {
      const config: CacheConfig = {
        path: './custom.json',
        write: false,
        read: false,
        duration: 1000
      };

      const cache = new Cachetta(config);

      expect(cache.path).toBe('./custom.json');
      expect(cache.write).toBe(false);
      expect(cache.read).toBe(false);
      expect(cache.duration).toBe(1000);
    });

    it('should handle function path', () => {
      const pathFn = () => './dynamic.json';
      const cache = new Cachetta({ path: pathFn });

      expect(cache.path).toBe(pathFn);
    });

    it('should be callable as a decorator', () => {
      const cache = new Cachetta({ path: './test.json' });

      expect(typeof cache).toBe('function');
    });
  });

  describe('copy', () => {
    it('should create a copy with new values', () => {
      const original = new Cachetta({ path: './original.json' });
      const copy = original.copy({ path: './copy.json', duration: 5000 });

      expect(copy.path).toBe('./copy.json');
      expect(copy.write).toBe(true); // inherited
      expect(copy.read).toBe(true); // inherited
      expect(copy.duration).toBe(5000); // overridden
    });

    it('should create a copy with all original values when no overrides', () => {
      const original = new Cachetta({ path: './original.json', write: false, read: false, duration: 1000 });
      const copy = original.copy({});

      expect(copy.path).toBe('./original.json');
      expect(copy.write).toBe(false);
      expect(copy.read).toBe(false);
      expect(copy.duration).toBe(1000);
    });
  });

  describe('call (decorator)', () => {
    it('should be callable as a decorator', () => {
      const cache = new Cachetta({ path: './test.json' });
      expect(typeof cache).toBe('function');
    });
  });

  describe('wrap', () => {
    it('should wrap a function with caching', () => {
      const cache = new Cachetta({ path: './test.json' });
      const originalFn = () => 'test';
      vi.mocked(cacheFn).mockReturnValue(() => Promise.resolve('wrapped'));

      const wrappedFn = cache(originalFn);

      expect(cacheFn).toHaveBeenCalled();
      expect(wrappedFn).toBeDefined();
    });
  });

  describe('console output', () => {
    it('should have custom inspect output', () => {
      const cache = new Cachetta({ path: './test.json', write: false, read: false, duration: 5000 });

      // The inspect custom symbol should be defined
      const inspectSymbol = Symbol.for('nodejs.util.inspect.custom');
      expect((cache as any)[inspectSymbol]).toBeDefined();

      // Test the inspect function
      const inspectFn = (cache as any)[inspectSymbol] as () => string;
      const output = inspectFn();
      expect(output).toContain('Cachetta');
      expect(output).toContain('./test.json');
      expect(output).toContain('write: false');
      expect(output).toContain('read: false');
      expect(output).toContain('duration: 5000');
    });
  });

  describe('LRU cache', () => {
    it('should not create LRU when lruSize is not set', () => {
      const cache = new Cachetta({ path: './test.json' });
      expect(cache._lru).toBeUndefined();
    });

    it('should create LRU when lruSize is set', () => {
      const cache = new Cachetta({ path: './test.json', lruSize: 10 });
      expect(cache._lru).toBeInstanceOf(Map);
      expect(cache.lruSize).toBe(10);
    });

    it('should store and retrieve values from LRU', () => {
      const cache = new Cachetta({ path: './test.json', lruSize: 10, duration: 60000 });
      cache._lruSet('key1', { data: 'test' });

      expect(cache._lruGet('key1')).toEqual({ data: 'test' });
    });

    it('should return LRU_MISS for missing LRU keys', () => {
      const cache = new Cachetta({ path: './test.json', lruSize: 10, duration: 60000 });

      expect(cache._lruGet('missing')).toBe(LRU_MISS);
    });

    it('should evict oldest entry when at capacity', () => {
      const cache = new Cachetta({ path: './test.json', lruSize: 2, duration: 60000 });
      cache._lruSet('key1', 'value1');
      cache._lruSet('key2', 'value2');
      cache._lruSet('key3', 'value3'); // should evict key1

      expect(cache._lruGet('key1')).toBe(LRU_MISS);
      expect(cache._lruGet('key2')).toBe('value2');
      expect(cache._lruGet('key3')).toBe('value3');
    });

    it('should return LRU_MISS when LRU is disabled', () => {
      const cache = new Cachetta({ path: './test.json' });
      cache._lruSet('key1', 'value1');

      expect(cache._lruGet('key1')).toBe(LRU_MISS);
    });

    it('should copy lruSize to copies', () => {
      const original = new Cachetta({ path: './test.json', lruSize: 5 });
      const copy = original.copy({});

      expect(copy.lruSize).toBe(5);
    });
  });

  describe('condition', () => {
    it('should store condition function', () => {
      const condFn = (result: unknown) => result !== null;
      const cache = new Cachetta({ path: './test.json', condition: condFn });
      expect(cache.condition).toBe(condFn);
    });

    it('should default condition to undefined', () => {
      const cache = new Cachetta({ path: './test.json' });
      expect(cache.condition).toBeUndefined();
    });

    it('should copy condition to copies', () => {
      const condFn = (result: unknown) => result !== null;
      const original = new Cachetta({ path: './test.json', condition: condFn });
      const copy = original.copy({});
      expect(copy.condition).toBe(condFn);
    });
  });

  describe('staleDuration', () => {
    it('should store staleDuration', () => {
      const cache = new Cachetta({ path: './test.json', staleDuration: 30000 });
      expect(cache.staleDuration).toBe(30000);
    });

    it('should default staleDuration to undefined', () => {
      const cache = new Cachetta({ path: './test.json' });
      expect(cache.staleDuration).toBeUndefined();
    });

    it('should copy staleDuration to copies', () => {
      const original = new Cachetta({ path: './test.json', staleDuration: 5000 });
      const copy = original.copy({});
      expect(copy.staleDuration).toBe(5000);
    });
  });

  describe('wrap (explicit)', () => {
    it('should be an alias that calls cacheFn', () => {
      const cache = new Cachetta({ path: './test.json' });
      const fn = () => 'result';
      vi.mocked(cacheFn).mockReturnValue(() => Promise.resolve('wrapped'));

      const wrapped = cache.wrap(fn);

      expect(cacheFn).toHaveBeenCalledTimes(1);
      // The first arg is the bound Cachetta (a function), second is our fn
      const callArgs = vi.mocked(cacheFn).mock.calls[0];
      expect(callArgs[1]).toBe(fn);
      expect(wrapped).toBeDefined();
    });
  });

  describe('_getPath with auto cache key', () => {
    it('should return path as-is when no args', () => {
      const cache = new Cachetta({ path: './data/cache.json' });
      expect(cache._getPath()).toBe('./data/cache.json');
    });

    it('should generate hashed path when args are provided', () => {
      const cache = new Cachetta({ path: './data/cache.json' });
      const path1 = cache._getPath('arg1', 'arg2');
      expect(path1).toMatch(/^data\/cache-[a-f0-9]{16}\.json$/);
    });

    it('should generate different paths for different args', () => {
      const cache = new Cachetta({ path: './data/cache.json' });
      const path1 = cache._getPath('arg1');
      const path2 = cache._getPath('arg2');
      expect(path1).not.toBe(path2);
    });

    it('should generate same path for same args', () => {
      const cache = new Cachetta({ path: './data/cache.json' });
      const path1 = cache._getPath('arg1', 'arg2');
      const path2 = cache._getPath('arg1', 'arg2');
      expect(path1).toBe(path2);
    });

    it('should handle paths without extension', () => {
      const cache = new Cachetta({ path: './data/cache' });
      const path = cache._getPath('arg1');
      expect(path).toMatch(/^data\/cache-[a-f0-9]{16}$/);
    });

    it('should still use pathFn when path is a function', () => {
      const pathFn = (a: string, b: string) => `./data/${a}-${b}.json`;
      const cache = new Cachetta({ path: pathFn });
      expect(cache._getPath('foo', 'bar')).toBe('./data/foo-bar.json');
    });
  });

  describe('invalidate', () => {
    let tempDir: string;

    beforeEach(async () => {
      tempDir = await fs.mkdtemp('cachetta-test-');
    });

    afterEach(async () => {
      await fs.rm(tempDir, { recursive: true, force: true });
    });

    it('should delete the cache file', async () => {
      const cachePath = join(tempDir, 'test.json');
      await fs.writeFile(cachePath, '{"data":1}');

      const cache = new Cachetta({ path: cachePath });
      await cache.invalidate();

      await expect(fs.access(cachePath)).rejects.toThrow();
    });

    it('should not throw when file does not exist', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'nonexistent.json') });
      await expect(cache.invalidate()).resolves.toBeUndefined();
    });

    it('should remove entry from LRU cache', async () => {
      const cachePath = join(tempDir, 'test.json');
      await fs.writeFile(cachePath, '{"data":1}');

      const cache = new Cachetta({ path: cachePath, lruSize: 10, duration: 60000 });
      cache._lruSet(cachePath, { data: 1 });
      expect(cache._lruGet(cachePath)).toEqual({ data: 1 });

      await cache.invalidate();
      expect(cache._lruGet(cachePath)).toBe(LRU_MISS);
    });

    it('clear should be an alias for invalidate', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'test.json') });
      expect(cache.clear).toBeDefined();
      expect(typeof cache.clear).toBe('function');
    });
  });

  describe('exists', () => {
    let tempDir: string;

    beforeEach(async () => {
      tempDir = await fs.mkdtemp('cachetta-test-');
    });

    afterEach(async () => {
      await fs.rm(tempDir, { recursive: true, force: true });
    });

    it('should return true when cache file exists', async () => {
      const cachePath = join(tempDir, 'test.json');
      await fs.writeFile(cachePath, '{"data":1}');

      const cache = new Cachetta({ path: cachePath });
      expect(await cache.exists()).toBe(true);
    });

    it('should return false when cache file does not exist', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'nonexistent.json') });
      expect(await cache.exists()).toBe(false);
    });
  });

  describe('age', () => {
    let tempDir: string;

    beforeEach(async () => {
      tempDir = await fs.mkdtemp('cachetta-test-');
    });

    afterEach(async () => {
      await fs.rm(tempDir, { recursive: true, force: true });
    });

    it('should return age in ms when file exists', async () => {
      const cachePath = join(tempDir, 'test.json');
      await fs.writeFile(cachePath, '{"data":1}');

      const cache = new Cachetta({ path: cachePath });
      const ageMs = await cache.age();
      expect(ageMs).toBeGreaterThanOrEqual(0);
      expect(ageMs).toBeLessThan(5000); // should be very recent
    });

    it('should return null when file does not exist', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'nonexistent.json') });
      expect(await cache.age()).toBeNull();
    });
  });

  describe('info', () => {
    let tempDir: string;

    beforeEach(async () => {
      tempDir = await fs.mkdtemp('cachetta-test-');
    });

    afterEach(async () => {
      await fs.rm(tempDir, { recursive: true, force: true });
    });

    it('should return info for nonexistent file', async () => {
      const cachePath = join(tempDir, 'nonexistent.json');
      const cache = new Cachetta({ path: cachePath });
      const result = await cache.info();

      expect(result.exists).toBe(false);
      expect(result.age).toBeNull();
      expect(result.expired).toBe(false);
      expect(result.stale).toBe(false);
      expect(result.path).toBe(cachePath);
    });

    it('should return info for fresh cache', async () => {
      const cachePath = join(tempDir, 'test.json');
      await fs.writeFile(cachePath, '{"data":1}');

      const cache = new Cachetta({ path: cachePath, duration: 60000 });
      const result = await cache.info();

      expect(result.exists).toBe(true);
      expect(result.age).toBeGreaterThanOrEqual(0);
      expect(result.expired).toBe(false);
      expect(result.stale).toBe(false);
    });

    it('should return expired=true for old cache', async () => {
      const cachePath = join(tempDir, 'test.json');
      await fs.writeFile(cachePath, '{"data":1}');
      // Set file time to 10 seconds ago
      const oldTime = new Date(Date.now() - 10000);
      await fs.utimes(cachePath, oldTime, oldTime);

      const cache = new Cachetta({ path: cachePath, duration: 1000 });
      const result = await cache.info();

      expect(result.exists).toBe(true);
      expect(result.expired).toBe(true);
      expect(result.stale).toBe(false); // no staleDuration set
    });

    it('should return stale=true when within stale window', async () => {
      const cachePath = join(tempDir, 'test.json');
      await fs.writeFile(cachePath, '{"data":1}');
      // Set file time to 5 seconds ago
      const oldTime = new Date(Date.now() - 5000);
      await fs.utimes(cachePath, oldTime, oldTime);

      const cache = new Cachetta({ path: cachePath, duration: 1000, staleDuration: 30000 });
      const result = await cache.info();

      expect(result.exists).toBe(true);
      expect(result.expired).toBe(true);
      expect(result.stale).toBe(true);
    });

    it('should return stale=false when past stale window', async () => {
      const cachePath = join(tempDir, 'test.json');
      await fs.writeFile(cachePath, '{"data":1}');
      // Set file time to 60 seconds ago
      const oldTime = new Date(Date.now() - 60000);
      await fs.utimes(cachePath, oldTime, oldTime);

      const cache = new Cachetta({ path: cachePath, duration: 1000, staleDuration: 5000 });
      const result = await cache.info();

      expect(result.exists).toBe(true);
      expect(result.expired).toBe(true);
      expect(result.stale).toBe(false); // past duration + staleDuration
    });
  });
});
