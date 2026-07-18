import type { Cachetta } from "../Cachetta.js";
import { readCache, readStaleCache, readCacheSync, readStaleCacheSync } from "../read-cache.js";
import type { CachableFunction, CachableFunctionSync } from "../types.js";
import { writeCache, writeCacheSync } from "../write-cache.js";
import { logger } from "./logger.js";

export const cacheFn = (cache: Cachetta<any>, originalMethod: CachableFunction) => {
  // In-flight promise deduplication keyed by resolved cache path (primary callers only).
  // Scoped to this wrapper instance so two Cachetta instances (even over the same
  // resolved path) never dedup against each other's calls.
  const inFlight = new Map<string, Promise<unknown>>();
  // Background refresh tracking (separate from inFlight so primary callers don't pick these up)
  const backgroundRefreshes = new Set<string>();

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

export const cacheFnSync = (cache: Cachetta<any>, originalMethod: CachableFunctionSync) => {
  function wrapper(this: any, ...args: unknown[]) {
    const data = readCacheSync(cache, ...args);
    if (data != null) {
      return data;
    }

    // Stale-while-revalidate: return stale data, no background refresh in sync context
    if (cache.staleDuration) {
      const staleData = readStaleCacheSync(cache, ...args);
      if (staleData != null) {
        return staleData;
      }
    }

    // No in-flight dedup for sync (sequential by definition)
    const result = originalMethod.apply(this, args);
    if (!cache.condition || cache.condition(result)) {
      writeCacheSync(cache, result, ...args);
    }
    return result;
  }
  return wrapper;
}
