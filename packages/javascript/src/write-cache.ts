import type { Cachetta } from './Cachetta.js';
import { promises as fs } from 'fs';
import { dirname, join, resolve } from 'path';
import { randomBytes } from 'crypto';
import { getExtension } from './utils/get-extension.js';
import { validateCachePath } from './utils/validate-cache-path.js';
import { UnsupportedFormatError } from './errors.js';

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

  const ext = getExtension(cachePath);

  // Ensure directory exists (skip if already created in this process)
  const dir = resolve(dirname(cachePath));
  if (!createdDirs.has(dir)) {
    await fs.mkdir(dir, { recursive: true });
    createdDirs.add(dir);
  }

  if (ext === 'json') {
    const jsonData = JSON.stringify(data);
    // Atomic write: write to temp file then rename
    const tmpPath = join(dir, `.cachetta-${randomBytes(8).toString('hex')}.tmp`);
    try {
      await fs.writeFile(tmpPath, jsonData, 'utf8');
      await fs.rename(tmpPath, cachePath);
      // Populate LRU on successful write
      cache._lruSet(cachePath, data);
    } catch (error) {
      // Clean up temp file on failure
      try { await fs.unlink(tmpPath); } catch { /* ignore */ }
      throw error;
    }
  } else {
    throw new UnsupportedFormatError(ext);
  }
}
