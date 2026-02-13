import { describe, test, expect, beforeEach, afterEach } from 'vitest';
import { writeFileSync, unlinkSync, rmdirSync, mkdtempSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { shouldUseReadCache } from './should-use-read-cache.js';
import type { CacheConfig } from '../types.js';

describe('shouldUseReadCache', () => {
  let tempDir: string;
  let testFilePath: string;

  beforeEach(() => {
    tempDir = mkdtempSync(join(tmpdir(), 'cachetta-test-'));
    testFilePath = join(tempDir, 'test-cache.json');
  });

  afterEach(() => {
    try {
      unlinkSync(testFilePath);
      rmdirSync(tempDir);
    } catch {
      // Cleanup failed, which is fine
    }
  });

  test('should return false for non-existent cache file', async () => {
    const cache: CacheConfig = {
      path: testFilePath,
      read: true,
      duration: 24 * 60 * 60 * 1000, // 1 day
    };

    expect(await shouldUseReadCache(cache, testFilePath)).toBe(false);
  });

  test('should return false when cache.read is false', async () => {
    // Create a cache file
    writeFileSync(testFilePath, '{"data": "test"}');

    const cache: CacheConfig = {
      path: testFilePath,
      read: false,
      duration: 24 * 60 * 60 * 1000, // 1 day
    };

    expect(await shouldUseReadCache(cache, testFilePath)).toBe(false);
  });

  test('should return true for valid non-expired cache', async () => {
    // Create a cache file
    writeFileSync(testFilePath, '{"data": "test"}');

    const cache: CacheConfig = {
      path: testFilePath,
      read: true,
      duration: 24 * 60 * 60 * 1000, // 1 day
    };

    expect(await shouldUseReadCache(cache, testFilePath)).toBe(true);
  });

  test('should return false for expired cache', async () => {
    // Create a cache file
    writeFileSync(testFilePath, '{"data": "test"}');

    // Wait a bit to ensure the file is older than our cache length
    await new Promise(resolve => setTimeout(resolve, 10));

    const cache: CacheConfig = {
      path: testFilePath,
      read: true,
      duration: 1, // 1 millisecond cache (very short)
    };

    expect(await shouldUseReadCache(cache, testFilePath)).toBe(false);
  });

  test('should return true when cache.read is undefined (defaults to true)', async () => {
    // Create a cache file
    writeFileSync(testFilePath, '{"data": "test"}');

    const cache: CacheConfig = {
      path: testFilePath,
      // read is undefined
      duration: 24 * 60 * 60 * 1000, // 1 day
    };

    expect(await shouldUseReadCache(cache, testFilePath)).toBe(true);
  });

  test('should use default cache length when not specified', async () => {
    // Create a cache file
    writeFileSync(testFilePath, '{"data": "test"}');

    const cache: CacheConfig = {
      path: testFilePath,
      read: true,
      // length is undefined
    };

    expect(await shouldUseReadCache(cache, testFilePath)).toBe(true);
  });

  test('should return false for very old cache with short cache length', async () => {
    // Create a cache file
    writeFileSync(testFilePath, '{"data": "test"}');

    // Wait to make the file older
    await new Promise(resolve => setTimeout(resolve, 10));

    const cache: CacheConfig = {
      path: testFilePath,
      read: true,
      duration: 1, // 1 millisecond
    };

    expect(await shouldUseReadCache(cache, testFilePath)).toBe(false);
  });

  test('should return true for recent cache with long cache length', async () => {
    // Create a cache file
    writeFileSync(testFilePath, '{"data": "test"}');

    const cache: CacheConfig = {
      path: testFilePath,
      read: true,
      duration: 365 * 24 * 60 * 60 * 1000, // 1 year
    };

    expect(await shouldUseReadCache(cache, testFilePath)).toBe(true);
  });

  test('should handle zero cache length', async () => {
    // Create a cache file
    writeFileSync(testFilePath, '{"data": "test"}');

    const cache: CacheConfig = {
      path: testFilePath,
      read: true,
      duration: 0, // No cache
    };

    expect(await shouldUseReadCache(cache, testFilePath)).toBe(false);
  });

  test('should handle negative cache length', async () => {
    // Create a cache file
    writeFileSync(testFilePath, '{"data": "test"}');

    const cache: CacheConfig = {
      path: testFilePath,
      read: true,
      duration: -1000, // Negative cache
    };

    expect(await shouldUseReadCache(cache, testFilePath)).toBe(false);
  });
});
