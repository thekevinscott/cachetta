import { describe, test, expect, beforeEach, afterEach } from 'vitest';
import { writeFileSync, unlinkSync, rmdirSync, mkdtempSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { getLastUpdated, getLastUpdatedSync } from './get-last-updated.js';

describe('getLastUpdated', () => {
  let tempDir: string;
  let testFilePath: string;

  beforeEach(() => {
    tempDir = mkdtempSync(join(tmpdir(), 'cachetta-test-'));
    testFilePath = join(tempDir, 'test-file.txt');
  });

  afterEach(() => {
    try {
      unlinkSync(testFilePath);
      rmdirSync(tempDir);
    } catch {
      // Cleanup failed, which is fine
    }
  });

  test('should return null for non-existent file', async () => {
    expect(await getLastUpdated('./non-existent-file.txt')).toBe(null);
  });

  test('should return timestamp for existing file', async () => {
    // Create a test file
    writeFileSync(testFilePath, 'test content');

    const timestamp = await getLastUpdated(testFilePath);

    expect(timestamp).toBeTypeOf('number');
    expect(timestamp).toBeGreaterThan(0);
    // Allow for small timing differences
    expect(timestamp).toBeLessThanOrEqual(Date.now() + 100);
  });

  test('should return updated timestamp after file modification', async () => {
    // Create initial file
    writeFileSync(testFilePath, 'initial content');
    const initialTimestamp = await getLastUpdated(testFilePath);

    // Wait a bit to ensure timestamp difference
    await new Promise(resolve => setTimeout(resolve, 10));

    // Modify the file
    writeFileSync(testFilePath, 'updated content');
    const updatedTimestamp = await getLastUpdated(testFilePath);

    expect(updatedTimestamp).toBeGreaterThan(initialTimestamp!);
  });

  test('should handle PathLike objects', async () => {
    writeFileSync(testFilePath, 'test content');

    const pathLike = new URL(`file://${testFilePath}`);
    const timestamp = await getLastUpdated(pathLike);

    expect(timestamp).toBeTypeOf('number');
    expect(timestamp).toBeGreaterThan(0);
  });

  test('should handle absolute paths', async () => {
    writeFileSync(testFilePath, 'test content');

    const timestamp = await getLastUpdated(testFilePath);

    expect(timestamp).toBeTypeOf('number');
    expect(timestamp).toBeGreaterThan(0);
  });

  test('should handle relative paths', async () => {
    writeFileSync(testFilePath, 'test content');

    const relativePath = './test-file.txt';
    const timestamp = await getLastUpdated(relativePath);

    // This will likely return null since we're using temp files
    // but the function should handle it gracefully
    expect(typeof timestamp === 'number' || timestamp === null).toBe(true);
  });

  test('should rethrow non-ENOENT errors', async () => {
    // Create a regular file, then stat a path that treats it as a directory.
    // This yields ENOTDIR, which must be rethrown rather than swallowed.
    writeFileSync(testFilePath, 'test content');
    const badPath = join(testFilePath, 'child.txt');

    await expect(getLastUpdated(badPath)).rejects.toMatchObject({ code: 'ENOTDIR' });
  });
});

describe('getLastUpdatedSync', () => {
  let tempDir: string;
  let testFilePath: string;

  beforeEach(() => {
    tempDir = mkdtempSync(join(tmpdir(), 'cachetta-test-'));
    testFilePath = join(tempDir, 'test-file.txt');
  });

  afterEach(() => {
    try {
      unlinkSync(testFilePath);
      rmdirSync(tempDir);
    } catch {
      // Cleanup failed, which is fine
    }
  });

  test('should return null for non-existent file', () => {
    expect(getLastUpdatedSync(join(tempDir, 'nope.txt'))).toBe(null);
  });

  test('should return timestamp for existing file', () => {
    writeFileSync(testFilePath, 'test content');
    const timestamp = getLastUpdatedSync(testFilePath);
    expect(timestamp).toBeTypeOf('number');
    expect(timestamp).toBeGreaterThan(0);
  });

  test('should rethrow non-ENOENT errors', () => {
    writeFileSync(testFilePath, 'test content');
    const badPath = join(testFilePath, 'child.txt');
    expect(() => getLastUpdatedSync(badPath)).toThrow();
  });
});
