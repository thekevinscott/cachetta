import type { Cachetta } from "../Cachetta.js";
import { readCacheOrMiss, readStaleCache, readCacheSyncOrMiss, readStaleCacheSync } from "../read-cache.js";
import { CACHE_MISS } from "../constants.js";
import type { CachableFunction, CachableFunctionSync } from "../types.js";
import { writeCache, writeCacheSync } from "../write-cache.js";
import { logger } from "./logger.js";

export const cacheFn = (cache: Cachetta<any>, originalMethod: CachableFunction) => {
  // In-flight computation dedup keyed by resolved cache path. Both primary calls
  // and background SWR refreshes register here so the two paths see each other and
  // never compute the same key concurrently. Scoped to this wrapper instance so two
  // Cachetta instances (even over the same resolved path) never dedup against
  // each other's calls.
  const inFlight = new Map<string, Promise<unknown>>();

  async function wrapper(this: ThisParameterType<typeof originalMethod>, ...args: Parameters<typeof originalMethod>) {
    const data = await readCacheOrMiss(cache, ...args);
    if (data !== CACHE_MISS) {
      return data;
    }

    const cacheKey = cache._getPath(...args);

    // Registers the computation in inFlight synchronously with the caller's guard
    // check, so no other caller can start a duplicate before it lands in the map.
    const startComputation = () => {
      const promise = (async () => {
        const result = await originalMethod.apply(this, args);
        if (!cache.condition || cache.condition(result)) {
          await writeCache(cache, result, ...args);
        }
        return result;
      })();
      inFlight.set(cacheKey, promise);
      // Attached before any caller awaits, so cleanup runs ahead of resumed
      // callers and never deletes a successor's entry.
      promise.finally(() => {
        inFlight.delete(cacheKey);
      }).catch(() => {});
      return promise;
    };

    // Stale-while-revalidate: return stale data and refresh in background
    if (cache.staleDuration) {
      const staleData = await readStaleCache(cache, ...args);
      if (staleData != null) {
        // Fire-and-forget background revalidation (only if not already computing)
        if (!inFlight.has(cacheKey)) {
          startComputation().catch((error) => {
            logger.error(`Background revalidation failed for ${cacheKey}: ${error}`);
          });
        }
        return staleData;
      }
    }

    // Join any in-flight computation for this path (primary or background refresh)
    return inFlight.get(cacheKey) ?? startComputation();
  }
  return wrapper;
}

export const cacheFnSync = (cache: Cachetta<any>, originalMethod: CachableFunctionSync) => {
  function wrapper(this: any, ...args: unknown[]) {
    const data = readCacheSyncOrMiss(cache, ...args);
    if (data !== CACHE_MISS) {
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
