import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { promises as fs } from 'fs';
import { join } from 'path';
import { Cachetta, readCache, writeCache } from 'cachetta';

const setTimeOfFile = async (amount: number, cachePath: string) => {
  const oldTime = new Date(Date.now() - amount);
  await fs.utimes(cachePath, oldTime, oldTime);
};

describe('basic', () => {
  let tempDir: string;


  beforeEach(async () => {
    tempDir = await fs.mkdtemp('cachetta-test-');
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  it('should instantiate', async () => {
    const cache = new Cachetta({
      path: join(tempDir, 'test.json')
    });

    expect(cache.path).toBe(join(tempDir, 'test.json'));
  });

  it('should read and write to cache', async () => {
    const cache = new Cachetta({
      path: join(tempDir, 'test.json'),
      read: true,
      write: true
    });

    expect(await readCache(cache)).toBeNull();

    const data = {
      test: 'test'
    };

    await writeCache(cache, data);

    expect(await readCache(cache)).toEqual(data);
  });

  it('should not write to cache if write is false', async () => {
    const cache = new Cachetta({
      path: join(tempDir, 'test.json'),
      read: true,
      write: false
    });

    expect(await readCache(cache)).toBeNull();

    const data = {
      test: 'test'
    };

    await writeCache(cache, data);

    expect(await readCache(cache)).toBeNull();
  });

  it('should not read from cache if read is false', async () => {
    const cache = new Cachetta({
      path: join(tempDir, 'test.json'),
      read: false,
      write: true
    });

    expect(await readCache(cache)).toBeNull();

    const data = {
      test: 'test'
    };

    await writeCache(cache, data);

    expect(await readCache(cache)).toEqual(null);
  });

  it('should handle cache expiration times', async () => {
    const expirationTime = 1000;
    const cachePath = join(tempDir, 'test.json');

    const cache = new Cachetta({
      path: cachePath,
      read: true,
      write: true,
      duration: expirationTime,
    });

    const data = {
      test: 'test'
    };

    // Write data to cache
    await writeCache(cache, data);

    // Should read the data immediately after writing
    expect(await readCache(cache)).toEqual(data);

    // Set file time to just before expiration (should still return data)
    await setTimeOfFile(expirationTime - 10, cachePath);
    expect(await readCache(cache)).toEqual(data);

    // Set file time to exactly at expiration (should return null)
    await setTimeOfFile(expirationTime, cachePath);
    expect(await readCache(cache)).toEqual(null);
  });
});
