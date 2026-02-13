import type { Cachetta } from './Cachetta.js';
import { LRU_MISS } from './constants.js';
import { promises as fs } from 'fs';
import { getExtension } from './utils/get-extension.js';
import { getLastUpdated } from './utils/get-last-updated.js';
import { shouldUseReadCache } from './utils/should-use-read-cache.js';
import { validateCachePath } from './utils/validate-cache-path.js';
import { logger } from './utils/logger.js';
import { isCachetta } from './type-guards.js';
import { CachettaError, UnsupportedFormatError } from './errors.js';

const DANGEROUS_KEYS = new Set(['__proto__', 'constructor', 'prototype']);

/** Read raw JSON data from a cache file, ignoring expiry. Returns null on any failure. */
async function readJsonFile<T>(cachePath: string): Promise<T | null> {
  const ext = getExtension(cachePath);
  if (ext !== 'json') {
    throw new UnsupportedFormatError(ext);
  }
  try {
    const data = await fs.readFile(cachePath, 'utf8');
    return JSON.parse(data, (key, value) => {
      if (DANGEROUS_KEYS.has(key)) return undefined;
      return value;
    }) as T;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return null;
    } else if (error instanceof SyntaxError) {
      logger.error(`Corrupt JSON: ${error}`);
      return null;
    } else {
      logger.error(`Read error: ${error}`);
      return null;
    }
  }
}

export async function readCache<T>(cacheBuddy: Cachetta<any>, ...args: unknown[]): Promise<T | null> {
  if (!isCachetta(cacheBuddy)) {
    throw new CachettaError(`Invalid value provided, you must provide an instance of Cachetta: ${cacheBuddy}`)
  }

  const cachePath = cacheBuddy._getPath(...args);
  validateCachePath(cachePath);

  // Check in-memory LRU before hitting disk
  const lruResult = cacheBuddy._lruGet(cachePath);
  if (lruResult !== LRU_MISS) {
    logger.debug(`LRU cache hit for ${cachePath}`);
    return lruResult as T;
  }

  if (await shouldUseReadCache(cacheBuddy, cachePath)) {
    logger.debug(`Using cache at ${cachePath}`);
    const result = await readJsonFile<T>(cachePath);
    if (result !== null) {
      logger.debug(`Used cache at ${cachePath}`);
      cacheBuddy._lruSet(cachePath, result);
    }
    return result;
  } else {
    logger.debug("cache.read is false, skipping cache");
    return null;
  }
}

/**
 * Reads stale cache data: returns data only if the file exists and is within the
 * staleDuration window (expired but not yet past duration + staleDuration).
 * @internal
 */
export async function readStaleCache<T>(cacheBuddy: Cachetta<any>, ...args: unknown[]): Promise<T | null> {
  if (!cacheBuddy.staleDuration || !cacheBuddy.read) return null;

  const cachePath = cacheBuddy._getPath(...args);
  validateCachePath(cachePath);

  const mtime = await getLastUpdated(cachePath);
  if (mtime === null) return null;

  const ageMs = Date.now() - mtime;
  const isExpired = ageMs >= cacheBuddy.duration;
  const isWithinStaleWindow = ageMs < (cacheBuddy.duration + cacheBuddy.staleDuration);

  if (isExpired && isWithinStaleWindow) {
    logger.debug(`Returning stale cache for ${cachePath} (age: ${ageMs}ms)`);
    return readJsonFile<T>(cachePath);
  }

  return null;
}
