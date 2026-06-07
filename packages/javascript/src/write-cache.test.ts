import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { promises as fs, renameSync as realRenameSync, unlinkSync as realUnlinkSync } from 'fs';
import { join } from 'path';
import { deserialize } from 'v8';
import { writeCache, writeCacheSync } from './write-cache.js';
import { Cachetta } from './Cachetta.js'; // eslint-disable-line mock-isolation/collaborators -- real Cachetta config object used as a plain-data fixture
import { InvalidPathError } from './errors.js';
import type * as _fs from 'fs';

// Wrap the sync fs primitives in spies so individual tests can force failures
// in the atomic-write/cleanup path while everything else uses the real fs.
vi.mock('fs', async () => {
  const actual = await vi.importActual<typeof _fs>('fs');
  return {
    ...actual,
    renameSync: vi.fn(actual.renameSync),
    unlinkSync: vi.fn(actual.unlinkSync),
  };
});

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

  it('should clean up the temp file and rethrow when the rename fails', async () => {
    // Make the destination an existing directory so the atomic rename fails.
    const cachePath = join(tempDir, 'dir-collision');
    await fs.mkdir(cachePath);
    await fs.writeFile(join(cachePath, 'placeholder'), 'x');

    const cache = new Cachetta({ path: cachePath, write: true });

    await expect(writeCache(cache, { data: 1 })).rejects.toThrow();

    // No temp files should be left behind after the failure.
    const files = await fs.readdir(tempDir);
    expect(files.filter(f => f.endsWith('.tmp'))).toHaveLength(0);
  });

  it('should swallow a temp-file cleanup failure and still rethrow the original error', async () => {
    const cachePath = join(tempDir, 'cleanup-fail.json');
    const cache = new Cachetta({ path: cachePath, write: true });

    // Make the rename fail to trigger the cleanup path...
    const renameSpy = vi.spyOn(fs, 'rename').mockRejectedValue(new Error('rename boom'));
    // ...and make the cleanup unlink fail too, exercising the ignored catch.
    const unlinkSpy = vi.spyOn(fs, 'unlink').mockRejectedValue(new Error('unlink boom'));

    await expect(writeCache(cache, { data: 1 })).rejects.toThrow('rename boom');

    renameSpy.mockRestore();
    unlinkSpy.mockRestore();
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

  it('should clean up the temp file and rethrow when the rename fails', async () => {
    const cachePath = join(tempDir, 'sync-dir-collision');
    await fs.mkdir(cachePath);
    await fs.writeFile(join(cachePath, 'placeholder'), 'x');

    const cache = new Cachetta({ path: cachePath, write: true });

    expect(() => writeCacheSync(cache, { data: 1 })).toThrow();

    const files = await fs.readdir(tempDir);
    expect(files.filter(f => f.endsWith('.tmp'))).toHaveLength(0);
  });

  it('should swallow a temp-file cleanup failure and still rethrow the original error', () => {
    const cachePath = join(tempDir, 'sync-cleanup-fail.json');
    const cache = new Cachetta({ path: cachePath, write: true });

    // Make the rename fail to trigger the cleanup path...
    vi.mocked(realRenameSync).mockImplementationOnce(() => {
      throw new Error('rename boom');
    });
    // ...and make the cleanup unlink fail too, exercising the ignored catch.
    vi.mocked(realUnlinkSync).mockImplementationOnce(() => {
      throw new Error('unlink boom');
    });

    expect(() => writeCacheSync(cache, { data: 1 })).toThrow('rename boom');
  });
});
