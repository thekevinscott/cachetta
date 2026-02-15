import type { Cachetta } from './Cachetta.js';
import { promises as fs, mkdirSync, writeFileSync, renameSync, unlinkSync } from 'fs';
import { dirname, join, resolve } from 'path';
import { randomBytes } from 'crypto';
import { serialize } from 'v8';
import { validateCachePath } from './utils/validate-cache-path.js';

// Track directories already created in this process to skip redundant mkdir calls.
// Growth is bounded by the number of unique cache directories, which in practice is small.
// If an entry were evicted, mkdir(recursive:true) is idempotent so correctness is preserved.
const createdDirs = new Set<string>();

export async function writeCache<T>(cache: Cachetta<any>, data: T, ...args: unknown[]): Promise<void> {
  if (!cache || !cache.write) {
    return;
  }

  const cachePath = cache._getPath(...args);
  validateCachePath(cachePath);

  // Ensure directory exists (skip if already created in this process)
  const dir = resolve(dirname(cachePath));
  if (!createdDirs.has(dir)) {
    await fs.mkdir(dir, { recursive: true });
    createdDirs.add(dir);
  }

  const serialized = serialize(data);
  // Atomic write: write to temp file then rename
  const tmpPath = join(dir, `.cachetta-${randomBytes(8).toString('hex')}.tmp`);
  try {
    await fs.writeFile(tmpPath, serialized);
    await fs.rename(tmpPath, cachePath);
    // Populate LRU on successful write
    cache._lruSet(cachePath, data);
  } catch (error) {
    // Clean up temp file on failure
    try { await fs.unlink(tmpPath); } catch { /* ignore */ }
    throw error;
  }
}

export function writeCacheSync<T>(cache: Cachetta<any>, data: T, ...args: unknown[]): void {
  if (!cache || !cache.write) {
    return;
  }

  const cachePath = cache._getPath(...args);
  validateCachePath(cachePath);

  const dir = resolve(dirname(cachePath));
  if (!createdDirs.has(dir)) {
    mkdirSync(dir, { recursive: true });
    createdDirs.add(dir);
  }

  const serialized = serialize(data);
  const tmpPath = join(dir, `.cachetta-${randomBytes(8).toString('hex')}.tmp`);
  try {
    writeFileSync(tmpPath, serialized);
    renameSync(tmpPath, cachePath);
    cache._lruSet(cachePath, data);
  } catch (error) {
    try { unlinkSync(tmpPath); } catch { /* ignore */ }
    throw error;
  }
}
