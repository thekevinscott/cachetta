import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { promises as fs } from 'fs';
import { join } from 'path';
import { serialize } from 'v8';
import { readCache, readCacheSync, readStaleCache, readStaleCacheSync } from './read-cache.js';
import { writeCache, writeCacheSync } from './write-cache.js';
import { Cachetta } from './Cachetta.js';
import { CachettaError, InvalidPathError } from './errors.js';
import * as shouldUseReadCacheModule from './utils/should-use-read-cache.js';


describe('readCache', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp('cachetta-test-');
    // Mock console.error to suppress error logs during tests
    vi.spyOn(console, 'error').mockImplementation(() => { });
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
    vi.restoreAllMocks();
  });

  it('should read data from cache file', async () => {
    const cachePath = join(tempDir, 'test-cache.json');
    const cache = new Cachetta({ path: cachePath, read: true });
    const testData = { key: 'value', number: 42 };

    // Write the cache using v8.serialize
    await fs.writeFile(cachePath, serialize(testData));

    const result = await readCache(cache);
    expect(result).toEqual(testData);
  });

  it('should throw a CachettaError when cache is not a Cachetta', async () => {
    await expect(readCache(null as unknown as Cachetta)).rejects.toThrow(CachettaError);
    await expect(readCache(null as unknown as Cachetta)).rejects.toThrow('Invalid value provided, you must provide an instance of Cachetta: null');
  });

  it('should return null when cache.read is false', async () => {
    const cachePath = join(tempDir, 'test-cache.json');
    const cache = new Cachetta({ path: cachePath, read: false });

    const result = await readCache(cache);
    expect(result).toBeNull();
  });

  it('should return null when cache file does not exist', async () => {
    const cachePath = join(tempDir, 'nonexistent-cache.json');
    const cache = new Cachetta({ path: cachePath, read: true });

    const result = await readCache(cache);
    expect(result).toBeNull();
  });

  it('should handle function-based cache paths', async () => {
    const cachePath = join(tempDir, 'dynamic-cache.json');
    const cache = new Cachetta({
      path: (...args: unknown[]) => join(tempDir, `${args[0] as string}-cache.json`),
      read: true
    });
    const testData = { dynamic: true };

    await fs.writeFile(cachePath, serialize(testData));

    expect(await readCache(cache, 'dynamic')).toEqual(testData);
    expect(await readCache(cache, 'dynamic2')).toEqual(null);
  });

  it('should return null for corrupt data', async () => {
    const cachePath = join(tempDir, 'corrupt-cache.json');
    const cache = new Cachetta({ path: cachePath, read: true });

    // Write invalid data (not v8 serialized)
    await fs.writeFile(cachePath, '{ invalid data', 'utf8');

    const result = await readCache(cache);
    expect(result).toBeNull();
  });

  it('should read any file extension', async () => {
    for (const ext of ['.json', '.dat', '.txt', '.cache']) {
      const cachePath = join(tempDir, `test${ext}`);
      const cache = new Cachetta({ path: cachePath, read: true });
      await fs.writeFile(cachePath, serialize({ ext }));
      expect(await readCache(cache)).toEqual({ ext });
    }
  });

  it('should handle complex nested objects', async () => {
    const cachePath = join(tempDir, 'complex-cache.json');
    const cache = new Cachetta({ path: cachePath, read: true });
    const testData = {
      string: 'hello',
      number: 123,
      boolean: true,
      null: null,
      array: [1, 2, 3],
      object: { nested: { deep: true } }
    };

    await fs.writeFile(cachePath, serialize(testData));

    const result = await readCache(cache);
    expect(result).toEqual(testData);
  });

  it('should reject paths with traversal segments', async () => {
    const cache = new Cachetta({ path: '../etc/passwd', read: true });

    await expect(readCache(cache)).rejects.toThrow(InvalidPathError);
  });

  it('should return the value from the LRU cache without touching disk', () => {
    const cachePath = join(tempDir, 'lru-async.json');
    const cache = new Cachetta({ path: cachePath, lruSize: 10, duration: 60000 });
    // Prime the LRU; the file does not exist so a disk read would return null.
    cache._lruSet(cachePath, { fromLru: true });
    return expect(readCache(cache)).resolves.toEqual({ fromLru: true });
  });

  it('should return null when the file vanishes after the freshness check (ENOENT in readCacheFile)', async () => {
    const cachePath = join(tempDir, 'vanishing.json');
    const cache = new Cachetta({ path: cachePath, read: true });
    // Force the freshness gate to pass even though the file is absent,
    // so we reach readCacheFile and hit its ENOENT branch.
    vi.spyOn(shouldUseReadCacheModule, 'shouldUseReadCache').mockResolvedValue(true);

    expect(await readCache(cache)).toBeNull();
  });
});

describe('readCacheSync', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp('cachetta-test-');
    vi.spyOn(console, 'error').mockImplementation(() => { });
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
    vi.restoreAllMocks();
  });

  it('should read data synchronously', async () => {
    const cachePath = join(tempDir, 'sync-read.json');
    const cache = new Cachetta({ path: cachePath });
    await fs.writeFile(cachePath, serialize({ sync: true }));
    expect(readCacheSync(cache)).toEqual({ sync: true });
  });

  it('should return null for nonexistent file', () => {
    const cache = new Cachetta({ path: '/tmp/claude/nonexistent-sync.json' });
    expect(readCacheSync(cache)).toBeNull();
  });

  it('should return null for corrupt data', async () => {
    const cachePath = join(tempDir, 'sync-corrupt.json');
    const cache = new Cachetta({ path: cachePath });
    await fs.writeFile(cachePath, 'not valid v8 data');
    expect(readCacheSync(cache)).toBeNull();
  });

  it('should throw CachettaError for non-Cachetta input', () => {
    expect(() => readCacheSync(null as any)).toThrow(CachettaError);
  });

  it('should reject paths with traversal segments', () => {
    const cache = new Cachetta({ path: '../etc/passwd' });
    expect(() => readCacheSync(cache)).toThrow(InvalidPathError);
  });

  it('should return the value from the LRU cache without touching disk', async () => {
    const cachePath = join(tempDir, 'sync-lru.json');
    const cache = new Cachetta({ path: cachePath, lruSize: 10, duration: 60000 });
    // Prime the LRU; the file does not exist so a disk read would return null.
    cache._lruSet(cachePath, { fromLru: true });
    expect(readCacheSync(cache)).toEqual({ fromLru: true });
  });

  it('should return null when the file vanishes after the freshness check (ENOENT in readCacheFileSync)', () => {
    const cachePath = join(tempDir, 'sync-vanishing.json');
    const cache = new Cachetta({ path: cachePath, read: true });
    // Force the freshness gate to pass even though the file is absent,
    // so we reach readCacheFileSync and hit its ENOENT branch.
    vi.spyOn(shouldUseReadCacheModule, 'shouldUseReadCacheSync').mockReturnValue(true);

    expect(readCacheSync(cache)).toBeNull();
  });
});

describe('readStaleCache', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp('cachetta-test-');
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  it('should return null when staleDuration is not set', async () => {
    const cachePath = join(tempDir, 'test.json');
    const cache = new Cachetta({ path: cachePath, duration: 1000 });
    // Write using writeCache so the file is v8-serialized
    await writeCache(cache, { data: 1 });
    expect(await readStaleCache(cache)).toBeNull();
  });

  it('should return null when read is false', async () => {
    const cachePath = join(tempDir, 'test.json');
    const cache = new Cachetta({ path: cachePath, duration: 1000, staleDuration: 5000, read: false });
    expect(await readStaleCache(cache)).toBeNull();
  });

  it('should return null when file does not exist', async () => {
    const cache = new Cachetta({ path: join(tempDir, 'missing.json'), duration: 1000, staleDuration: 5000 });
    expect(await readStaleCache(cache)).toBeNull();
  });

  it('should return null when cache is still fresh (not expired)', async () => {
    const cachePath = join(tempDir, 'test.json');
    const cache = new Cachetta({ path: cachePath, duration: 60000, staleDuration: 5000 });
    await writeCache(cache, { data: 1 });
    expect(await readStaleCache(cache)).toBeNull();
  });

  it('should return data when cache is expired but within stale window', async () => {
    const cachePath = join(tempDir, 'test.json');
    const testData = { data: 'stale' };
    const cache = new Cachetta({ path: cachePath, duration: 1000, staleDuration: 30000 });
    await writeCache(cache, testData);
    // Set file time to 5 seconds ago (expired with 1s duration, within 30s stale window)
    const oldTime = new Date(Date.now() - 5000);
    await fs.utimes(cachePath, oldTime, oldTime);

    expect(await readStaleCache(cache)).toEqual(testData);
  });

  it('should return null when cache is past both duration and staleDuration', async () => {
    const cachePath = join(tempDir, 'test.json');
    const cache = new Cachetta({ path: cachePath, duration: 1000, staleDuration: 5000 });
    await writeCache(cache, { data: 1 });
    // Set file time to 60 seconds ago (past 1s duration + 5s stale window)
    const oldTime = new Date(Date.now() - 60000);
    await fs.utimes(cachePath, oldTime, oldTime);

    expect(await readStaleCache(cache)).toBeNull();
  });
});

describe('readStaleCacheSync', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp('cachetta-test-');
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  it('should return null when staleDuration is not set', () => {
    const cachePath = join(tempDir, 'test.json');
    const cache = new Cachetta({ path: cachePath, duration: 1000 });
    writeCacheSync(cache, { data: 1 });
    expect(readStaleCacheSync(cache)).toBeNull();
  });

  it('should return data when in stale window', async () => {
    const cachePath = join(tempDir, 'test.json');
    const testData = { data: 'stale-sync' };
    const cache = new Cachetta({ path: cachePath, duration: 1000, staleDuration: 30000 });
    writeCacheSync(cache, testData);
    const oldTime = new Date(Date.now() - 5000);
    await fs.utimes(cachePath, oldTime, oldTime);

    expect(readStaleCacheSync(cache)).toEqual(testData);
  });

  it('should return null when past both duration and staleDuration', async () => {
    const cachePath = join(tempDir, 'test.json');
    const cache = new Cachetta({ path: cachePath, duration: 1000, staleDuration: 5000 });
    writeCacheSync(cache, { data: 1 });
    // 60s ago is well past the 1s duration + 5s stale window.
    const oldTime = new Date(Date.now() - 60000);
    await fs.utimes(cachePath, oldTime, oldTime);

    expect(readStaleCacheSync(cache)).toBeNull();
  });

  it('should return null when file does not exist', () => {
    const cache = new Cachetta({ path: join(tempDir, 'missing-sync.json'), duration: 1000, staleDuration: 5000 });
    expect(readStaleCacheSync(cache)).toBeNull();
  });
});
