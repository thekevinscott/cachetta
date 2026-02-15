import { getLastUpdated, getLastUpdatedSync } from './get-last-updated.js';
import { isCacheExpired } from './is-cache-expired.js';
import { logger } from './logger.js';
import type { CacheConfig } from '../types.js';

export async function shouldUseReadCache({ duration, read }: Pick<CacheConfig, 'duration' | 'read'>, cachePath: string): Promise<boolean> {
  const cacheLength = duration ?? 7 * 24 * 60 * 60 * 1000; // Default 7 days in milliseconds
  const cacheTime = await getLastUpdated(cachePath);

  if (cacheTime === null) {
    logger.debug(`Cache time is null for ${cachePath}`);
    return false;
  }

  // If cache length is 0 or negative, always consider it expired (regardless of timing)
  if (cacheLength <= 0) {
    logger.debug(`Cache length is ${cacheLength}, considering expired for ${cachePath}`);
    return false;
  }

  const now = Date.now();

  // Handle the case where cache time might be slightly ahead due to file system timing
  if (cacheTime > now) {
    logger.debug(`Cache time ${cacheTime} is ahead of now ${now}, treating as valid cache for ${cachePath}`);
    // Treat as a valid cache, but still respect the read setting
    return read ?? true;
  }

  if (isCacheExpired(cacheTime, now, cacheLength)) {
    logger.debug(
      `Cache is expired (${cacheTime}, expected ${cacheTime + cacheLength}) for ${cachePath}`
    );
    return false;
  }

  logger.debug(
    `Cache is not expired (${cacheTime}, expected ${cacheTime + cacheLength}) for ${cachePath}`
  );

  return read ?? true; // Default to true if not specified
}

export function shouldUseReadCacheSync({ duration, read }: Pick<CacheConfig, 'duration' | 'read'>, cachePath: string): boolean {
  const cacheLength = duration ?? 7 * 24 * 60 * 60 * 1000;
  const cacheTime = getLastUpdatedSync(cachePath);

  if (cacheTime === null) {
    logger.debug(`Cache time is null for ${cachePath}`);
    return false;
  }

  if (cacheLength <= 0) {
    logger.debug(`Cache length is ${cacheLength}, considering expired for ${cachePath}`);
    return false;
  }

  const now = Date.now();

  if (cacheTime > now) {
    logger.debug(`Cache time ${cacheTime} is ahead of now ${now}, treating as valid cache for ${cachePath}`);
    return read ?? true;
  }

  if (isCacheExpired(cacheTime, now, cacheLength)) {
    logger.debug(
      `Cache is expired (${cacheTime}, expected ${cacheTime + cacheLength}) for ${cachePath}`
    );
    return false;
  }

  logger.debug(
    `Cache is not expired (${cacheTime}, expected ${cacheTime + cacheLength}) for ${cachePath}`
  );

  return read ?? true;
}
