import type { Cachetta } from "../Cachetta.js";
import { readCache, readStaleCache } from "../read-cache.js";
import type { CachableFunction } from "../types.js";
import { writeCache } from "../write-cache.js";
import { logger } from "./logger.js";

// In-flight promise deduplication keyed by resolved cache path (primary callers only)
const inFlight = new Map<string, Promise<unknown>>();
// Background refresh tracking (separate from inFlight so primary callers don't pick these up)
const backgroundRefreshes = new Set<string>();

export const cacheFn = (cache: Cachetta<any>, originalMethod: CachableFunction) => {
  async function wrapper(this: ThisParameterType<typeof originalMethod>, ...args: Parameters<typeof originalMethod>) {
    const data = await readCache(cache, ...args);
    if (data != null) {
      return data;
    }

    const cacheKey = cache._getPath(...args);

    // Stale-while-revalidate: return stale data and refresh in background
    if (cache.staleDuration) {
      const staleData = await readStaleCache(cache, ...args);
      if (staleData != null) {
        // Fire-and-forget background revalidation (only if not already refreshing)
        if (!backgroundRefreshes.has(cacheKey) && !inFlight.has(cacheKey)) {
          backgroundRefreshes.add(cacheKey);
          (async () => {
            try {
              const result = await originalMethod.apply(this, args);
              if (!cache.condition || cache.condition(result)) {
                await writeCache(cache, result, ...args);
              }
            } catch (error) {
              logger.error(`Background revalidation failed for ${cacheKey}: ${error}`);
            } finally {
              backgroundRefreshes.delete(cacheKey);
            }
          })();
        }
        return staleData;
      }
    }

    // If there's already an in-flight call for this path, return it
    const existing = inFlight.get(cacheKey);
    if (existing) {
      return existing;
    }

    const promise = (async () => {
      const result = await originalMethod.apply(this, args);
      if (!cache.condition || cache.condition(result)) {
        await writeCache(cache, result, ...args);
      }
      return result;
    })();

    inFlight.set(cacheKey, promise);
    try {
      return await promise;
    } finally {
      inFlight.delete(cacheKey);
    }
  }
  return wrapper;
}
