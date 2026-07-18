import type { Cachetta } from './Cachetta.js';
import { LRU_MISS, CACHE_MISS } from './constants.js';
import { promises as fs, readFileSync } from 'fs';
import { deserialize } from 'v8';
import { getLastUpdated, getLastUpdatedSync } from './utils/get-last-updated.js';
import { shouldUseReadCache, shouldUseReadCacheSync } from './utils/should-use-read-cache.js';
import { validateCachePath } from './utils/validate-cache-path.js';
import { logger } from './utils/logger.js';
import { isCachetta } from './type-guards.js';
import { CachettaError } from './errors.js';

/** Read raw data from a cache file, ignoring expiry. Returns CACHE_MISS on any failure (file absent or unreadable). */
async function readCacheFile<T>(cachePath: string): Promise<T | typeof CACHE_MISS> {
  try {
    const buffer = await fs.readFile(cachePath);
    return deserialize(buffer) as T;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return CACHE_MISS;
    } else {
      logger.error(`Read error: ${error}`);
      return CACHE_MISS;
    }
  }
}

/** Sync version of readCacheFile. */
function readCacheFileSync<T>(cachePath: string): T | typeof CACHE_MISS {
  try {
    const buffer = readFileSync(cachePath);
    return deserialize(buffer) as T;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return CACHE_MISS;
    } else {
      logger.error(`Read error: ${error}`);
      return CACHE_MISS;
    }
  }
}

/**
 * Internal variant of readCache that distinguishes "no cached value" from a
 * cached value that happens to be null/undefined, via the CACHE_MISS sentinel.
 * @internal
 */
export async function readCacheOrMiss<T>(cacheBuddy: Cachetta<any>, ...args: unknown[]): Promise<T | typeof CACHE_MISS> {
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
    const result = await readCacheFile<T>(cachePath);
    if (result !== CACHE_MISS) {
      logger.debug(`Used cache at ${cachePath}`);
      cacheBuddy._lruSet(cachePath, result);
    }
    return result;
  } else {
    logger.debug("cache.read is false, skipping cache");
    return CACHE_MISS;
  }
}

/** Sync variant of readCacheOrMiss. @internal */
export function readCacheSyncOrMiss<T>(cacheBuddy: Cachetta<any>, ...args: unknown[]): T | typeof CACHE_MISS {
  if (!isCachetta(cacheBuddy)) {
    throw new CachettaError(`Invalid value provided, you must provide an instance of Cachetta: ${cacheBuddy}`)
  }

  const cachePath = cacheBuddy._getPath(...args);
  validateCachePath(cachePath);

  const lruResult = cacheBuddy._lruGet(cachePath);
  if (lruResult !== LRU_MISS) {
    logger.debug(`LRU cache hit for ${cachePath}`);
    return lruResult as T;
  }

  if (shouldUseReadCacheSync(cacheBuddy, cachePath)) {
    logger.debug(`Using cache at ${cachePath}`);
    const result = readCacheFileSync<T>(cachePath);
    if (result !== CACHE_MISS) {
      logger.debug(`Used cache at ${cachePath}`);
      cacheBuddy._lruSet(cachePath, result);
    }
    return result;
  } else {
    logger.debug("cache.read is false, skipping cache");
    return CACHE_MISS;
  }
}

export async function readCache<T>(cacheBuddy: Cachetta<any>, ...args: unknown[]): Promise<T | null> {
  const result = await readCacheOrMiss<T>(cacheBuddy, ...args);
  return result === CACHE_MISS ? null : result;
}

export function readCacheSync<T>(cacheBuddy: Cachetta<any>, ...args: unknown[]): T | null {
  const result = readCacheSyncOrMiss<T>(cacheBuddy, ...args);
  return result === CACHE_MISS ? null : result;
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
    const result = await readCacheFile<T>(cachePath);
    return result === CACHE_MISS ? null : result;
  }

  return null;
}

/** @internal */
export function readStaleCacheSync<T>(cacheBuddy: Cachetta<any>, ...args: unknown[]): T | null {
  if (!cacheBuddy.staleDuration || !cacheBuddy.read) return null;

  const cachePath = cacheBuddy._getPath(...args);
  validateCachePath(cachePath);

  const mtime = getLastUpdatedSync(cachePath);
  if (mtime === null) return null;

  const ageMs = Date.now() - mtime;
  const isExpired = ageMs >= cacheBuddy.duration;
  const isWithinStaleWindow = ageMs < (cacheBuddy.duration + cacheBuddy.staleDuration);

  if (isExpired && isWithinStaleWindow) {
    logger.debug(`Returning stale cache for ${cachePath} (age: ${ageMs}ms)`);
    const result = readCacheFileSync<T>(cachePath);
    return result === CACHE_MISS ? null : result;
  }

  return null;
}
