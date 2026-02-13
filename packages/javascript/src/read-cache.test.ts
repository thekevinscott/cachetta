import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { promises as fs } from 'fs';
import { join } from 'path';
import { readCache, readStaleCache } from './read-cache.js';
import type { CacheConfig } from './types.js';
import { Cachetta } from './Cachetta.js';
import { CachettaError, InvalidPathError, UnsupportedFormatError } from './errors.js';


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

  it('should read JSON data from cache file', async () => {
    const cachePath = join(tempDir, 'test-cache.json');
    const cache = new Cachetta({
      path: cachePath,
      read: true
    });
    const testData = { key: 'value', number: 42 };

    // Write the cache first
    await fs.writeFile(cachePath, JSON.stringify(testData), 'utf8');

    const result = await readCache(cache);
    expect(result).toEqual(testData);
  });

  it('should throw a CachettaError when cache is not a Cachetta', async () => {
    await expect(readCache(null as unknown as Cachetta)).rejects.toThrow(CachettaError);
    await expect(readCache(null as unknown as Cachetta)).rejects.toThrow('Invalid value provided, you must provide an instance of Cachetta: null');
  });

  it('should return null when cache.read is false', async () => {
    const cachePath = join(tempDir, 'test-cache.json');
    const cache = new Cachetta({
      path: cachePath,
      read: false
    });

    const result = await readCache(cache);
    expect(result).toBeNull();
  });

  it('should return null when cache file does not exist', async () => {
    const cachePath = join(tempDir, 'nonexistent-cache.json');
    const cache = new Cachetta({
      path: cachePath,
      read: true
    });

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

    // Write the cache first
    await fs.writeFile(cachePath, JSON.stringify(testData), 'utf8');

    expect(await readCache(cache, 'dynamic')).toEqual(testData);
    expect(await readCache(cache, 'dynamic2')).toEqual(null);
  });

  it('should return null for corrupt JSON', async () => {
    const cachePath = join(tempDir, 'corrupt-cache.json');
    const cache = new Cachetta({
      path: cachePath,
      read: true
    });

    // Write corrupt JSON
    await fs.writeFile(cachePath, '{ invalid json', 'utf8');

    const result = await readCache(cache);
    expect(result).toBeNull();
  });

  it('should return null for unknown file extension when cache should not be used', async () => {
    const cachePath = join(tempDir, 'test-cache.txt');
    const cache = new Cachetta({
      path: cachePath,
      read: true
    });

    const result = await readCache(cache);
    expect(result).toBeNull();
  });

  it('should handle complex nested objects', async () => {
    const cachePath = join(tempDir, 'complex-cache.json');
    const cache = new Cachetta({
      path: cachePath,
      read: true
    });
    const testData = {
      string: 'hello',
      number: 123,
      boolean: true,
      null: null,
      array: [1, 2, 3],
      object: { nested: { deep: true } }
    };

    // Write the cache first
    await fs.writeFile(cachePath, JSON.stringify(testData), 'utf8');

    const result = await readCache(cache);
    expect(result).toEqual(testData);
  });

  it('should throw UnsupportedFormatError for unknown file extension when cache should be used', async () => {
    const cachePath = join(tempDir, 'test.unknown');
    const cache = new Cachetta({
      path: cachePath,
      read: true
    });

    // Create the file so it exists and shouldUseReadCache returns true
    await fs.writeFile(cachePath, 'test content', 'utf8');

    await expect(readCache(cache)).rejects.toThrow(UnsupportedFormatError);
  });

  it('should reject paths with traversal segments', async () => {
    const cache = new Cachetta({
      path: '../etc/passwd',
      read: true
    });

    await expect(readCache(cache)).rejects.toThrow(InvalidPathError);
  });

  it('should strip __proto__ keys from parsed JSON', async () => {
    const cachePath = join(tempDir, 'proto-cache.json');
    const cache = new Cachetta({
      path: cachePath,
      read: true
    });

    // Write JSON with __proto__ key
    await fs.writeFile(cachePath, '{"__proto__": {"polluted": true}, "safe": "value"}', 'utf8');

    const result = await readCache<Record<string, unknown>>(cache);
    expect(result).toEqual({ safe: 'value' });
    expect(result).not.toHaveProperty('__proto__.polluted');
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
    await fs.writeFile(cachePath, '{"data":1}');

    const cache = new Cachetta({ path: cachePath, duration: 1000 });
    expect(await readStaleCache(cache)).toBeNull();
  });

  it('should return null when read is false', async () => {
    const cachePath = join(tempDir, 'test.json');
    await fs.writeFile(cachePath, '{"data":1}');

    const cache = new Cachetta({ path: cachePath, duration: 1000, staleDuration: 5000, read: false });
    expect(await readStaleCache(cache)).toBeNull();
  });

  it('should return null when file does not exist', async () => {
    const cache = new Cachetta({ path: join(tempDir, 'missing.json'), duration: 1000, staleDuration: 5000 });
    expect(await readStaleCache(cache)).toBeNull();
  });

  it('should return null when cache is still fresh (not expired)', async () => {
    const cachePath = join(tempDir, 'test.json');
    await fs.writeFile(cachePath, '{"data":1}');

    const cache = new Cachetta({ path: cachePath, duration: 60000, staleDuration: 5000 });
    expect(await readStaleCache(cache)).toBeNull();
  });

  it('should return data when cache is expired but within stale window', async () => {
    const cachePath = join(tempDir, 'test.json');
    const testData = { data: 'stale' };
    await fs.writeFile(cachePath, JSON.stringify(testData));
    // Set file time to 5 seconds ago (expired with 1s duration, within 30s stale window)
    const oldTime = new Date(Date.now() - 5000);
    await fs.utimes(cachePath, oldTime, oldTime);

    const cache = new Cachetta({ path: cachePath, duration: 1000, staleDuration: 30000 });
    expect(await readStaleCache(cache)).toEqual(testData);
  });

  it('should return null when cache is past both duration and staleDuration', async () => {
    const cachePath = join(tempDir, 'test.json');
    await fs.writeFile(cachePath, '{"data":1}');
    // Set file time to 60 seconds ago (past 1s duration + 5s stale window)
    const oldTime = new Date(Date.now() - 60000);
    await fs.utimes(cachePath, oldTime, oldTime);

    const cache = new Cachetta({ path: cachePath, duration: 1000, staleDuration: 5000 });
    expect(await readStaleCache(cache)).toBeNull();
  });
});
