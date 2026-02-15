import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { promises as fs } from 'fs';
import { join } from 'path';
import { deserialize } from 'v8';
import { writeCache, writeCacheSync } from './write-cache.js';
import { Cachetta } from './Cachetta.js';
import { InvalidPathError } from './errors.js';

describe('writeCache', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp('cachetta-test-');
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  it('should write data to cache file', async () => {
    const cachePath = join(tempDir, 'test-cache.json');
    const cache = new Cachetta({
      path: cachePath,
      write: true
    });
    const testData = { key: 'value', number: 42 };

    await writeCache(cache, testData);

    const buffer = await fs.readFile(cachePath);
    expect(deserialize(buffer)).toEqual(testData);
  });

  it('should create directory structure if it does not exist', async () => {
    const cachePath = join(tempDir, 'nested', 'deep', 'test-cache.json');
    const cache = new Cachetta({
      path: cachePath,
      write: true
    });
    const testData = { nested: true };

    await writeCache(cache, testData);

    const buffer = await fs.readFile(cachePath);
    expect(deserialize(buffer)).toEqual(testData);
  });

  it('should handle function-based cache paths', async () => {
    const cachePath = join(tempDir, 'dynamic-cache.json');
    const cache = new Cachetta({
      path: (...args: unknown[]) => join(tempDir, `${args[0] as string}-cache.json`),
      write: true
    });
    const testData = { dynamic: true };

    await writeCache(cache, testData, 'dynamic');
    const buffer = await fs.readFile(cachePath);
    expect(deserialize(buffer)).toEqual(testData);
  });

  it('should not write when cache.write is false', async () => {
    const cachePath = join(tempDir, 'no-write-cache.json');
    const cache = new Cachetta({
      path: cachePath,
      write: false
    });
    const testData = { shouldNotWrite: true };

    await writeCache(cache, testData);

    // File should not exist
    await expect(fs.readFile(cachePath)).rejects.toThrow();
  });

  it('should not write when cache is null', async () => {
    const cachePath = join(tempDir, 'null-cache.json');
    const testData = { shouldNotWrite: true };

    await writeCache(null as unknown as Cachetta, testData);

    // File should not exist
    await expect(fs.readFile(cachePath)).rejects.toThrow();
  });

  it('should write any file extension', async () => {
    for (const ext of ['.json', '.dat', '.cache', '.xml', '.foo']) {
      const cachePath = join(tempDir, `test${ext}`);
      const cache = new Cachetta({ path: cachePath, write: true });
      await writeCache(cache, { ext });
      const buffer = await fs.readFile(cachePath);
      expect(deserialize(buffer)).toEqual({ ext });
    }
  });

  it('should reject paths with traversal segments', async () => {
    const cache = new Cachetta({
      path: '../etc/evil.json',
      write: true
    });

    await expect(writeCache(cache, { key: 'value' })).rejects.toThrow(InvalidPathError);
  });

  it('should write atomically (no partial files on crash)', async () => {
    const cachePath = join(tempDir, 'atomic-cache.json');
    const cache = new Cachetta({
      path: cachePath,
      write: true
    });
    const testData = { atomic: true };

    await writeCache(cache, testData);

    // Verify the final file exists and is valid
    const buffer = await fs.readFile(cachePath);
    expect(deserialize(buffer)).toEqual(testData);

    // Verify no temp files left behind
    const files = await fs.readdir(tempDir);
    const tmpFiles = files.filter(f => f.endsWith('.tmp'));
    expect(tmpFiles).toHaveLength(0);
  });

  it('should handle complex nested objects', async () => {
    const cachePath = join(tempDir, 'complex-cache.json');
    const cache = new Cachetta({
      path: cachePath,
      write: true
    });
    const testData = {
      string: 'hello',
      number: 123,
      boolean: true,
      null: null,
      array: [1, 2, 3],
      object: { nested: { deep: true } }
    };

    await writeCache(cache, testData);

    const buffer = await fs.readFile(cachePath);
    expect(deserialize(buffer)).toEqual(testData);
  });
});

describe('writeCacheSync', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp('cachetta-test-');
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  it('should write data synchronously', async () => {
    const cachePath = join(tempDir, 'sync-test.json');
    const cache = new Cachetta({ path: cachePath, write: true });
    writeCacheSync(cache, { key: 'sync' });

    const buffer = await fs.readFile(cachePath);
    expect(deserialize(buffer)).toEqual({ key: 'sync' });
  });

  it('should create directory structure synchronously', async () => {
    const cachePath = join(tempDir, 'a', 'b', 'sync-test.json');
    const cache = new Cachetta({ path: cachePath, write: true });
    writeCacheSync(cache, { nested: true });

    const buffer = await fs.readFile(cachePath);
    expect(deserialize(buffer)).toEqual({ nested: true });
  });

  it('should not write when cache.write is false', async () => {
    const cachePath = join(tempDir, 'sync-no-write.json');
    const cache = new Cachetta({ path: cachePath, write: false });
    writeCacheSync(cache, { data: 1 });
    await expect(fs.readFile(cachePath)).rejects.toThrow();
  });

  it('should reject paths with traversal segments', () => {
    const cache = new Cachetta({ path: '../etc/evil.json', write: true });
    expect(() => writeCacheSync(cache, { key: 'value' })).toThrow(InvalidPathError);
  });
});
