import type { CacheConfig, CacheInfo, CachableFunction, PathFn } from './types.js';
import { isPartialCacheConfig } from './type-guards.js';
import { cacheFn } from './utils/cache-fn.js';
import { getLastUpdated } from './utils/get-last-updated.js';
import { validateCachePath } from './utils/validate-cache-path.js';
import { promises as fs } from 'fs';
import { createHash } from 'crypto';
import { dirname, join } from 'path';
import { inspect } from 'util';

import { LRU_MISS } from './constants.js';

const DEFAULT_DURATION = 7 * 24 * 60 * 60 * 1000; // Default 7 days in milliseconds

interface LruEntry {
  value: unknown;
  timestamp: number;
}

export class Cachetta<Path extends string | PathFn<any> = string> extends Function {
  protected __cacheBuddy__ = true;
  public path!: Path;
  public write!: boolean;
  public read!: boolean;
  public duration!: number; // milliseconds
  public lruSize!: number | undefined;
  public condition!: ((result: unknown) => boolean) | undefined;
  public staleDuration!: number | undefined;
  /** Alias for {@link invalidate}. Deletes the cache file. */
  public clear!: (...args: unknown[]) => Promise<void>;
  /** @internal */
  _lru!: Map<string, LruEntry> | undefined;

  constructor(config: CacheConfig<Path>) {
    super();
    this.path = config.path;
    this.write = config.write ?? true;
    this.read = config.read ?? true;
    this.duration = config.duration ?? DEFAULT_DURATION;
    this.lruSize = config.lruSize;
    this.condition = config.condition;
    this.staleDuration = config.staleDuration;
    this._lru = this.lruSize ? new Map() : undefined;
    const boundCall = this.call.bind(this);
    const result = Object.assign(
      boundCall,
      this,
      {
        copy: this.copy.bind(this),
        wrap: this.wrap.bind(this),
        invalidate: this.invalidate.bind(this),
        clear: this.invalidate.bind(this), // alias
        exists: this.exists.bind(this),
        age: this.age.bind(this),
        info: this.info.bind(this),
        _getPath: this._getPath.bind(this),
        _lruGet: this._lruGet.bind(this),
        _lruSet: this._lruSet.bind(this),
        __cacheBuddy__: true,
        _lru: this._lru,
        lruSize: this.lruSize,
        condition: this.condition,
        staleDuration: this.staleDuration,
      }) as unknown as typeof boundCall & typeof this & { [inspect.custom]: () => string };
    result[inspect.custom] = () => `Cachetta { path: '${this.path}', write: ${this.write}, read: ${this.read}, duration: ${this.duration} }`;
    return result;
  }

  /**
   * Creates a copy of this Cachetta instance with overridden configuration.
   * Useful for creating variations of a base cache configuration.
   *
   * @param kwargs - Partial configuration to override
   * @returns A new Cachetta instance with the specified overrides
   */
  copy<NewPath extends string | PathFn<any> = string>(kwargs: Partial<CacheConfig<NewPath>>): Cachetta<NewPath> {
    return new Cachetta({
      path: (kwargs.path ?? this.path) as NewPath,
      write: kwargs.write ?? this.write,
      read: kwargs.read ?? this.read,
      duration: kwargs.duration ?? this.duration,
      lruSize: kwargs.lruSize ?? this.lruSize,
      condition: kwargs.condition ?? this.condition,
      staleDuration: kwargs.staleDuration ?? this.staleDuration,
    });
  }

  /**
   * Wraps a function with caching behavior. Alias for calling the cache instance directly.
   *
   * @param fn - The function to wrap
   * @returns A cached version of the function
   */
  wrap(fn: CachableFunction): CachableFunction {
    return cacheFn(this as Cachetta, fn);
  }

  /**
   * Deletes the cache file on disk and clears LRU entries for this path.
   * No-op if the cache file does not exist.
   *
   * @param args - Arguments to resolve the cache path (when using a path function)
   */
  async invalidate(...args: unknown[]): Promise<void> {
    const cachePath = this._getPath(...args);
    validateCachePath(cachePath);

    // Remove from LRU
    if (this._lru) {
      this._lru.delete(cachePath);
    }

    // Delete from disk
    try {
      await fs.unlink(cachePath);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') {
        throw error;
      }
    }
  }

  /**
   * Checks whether the cache file exists on disk.
   *
   * @param args - Arguments to resolve the cache path (when using a path function)
   * @returns true if the cache file exists
   */
  async exists(...args: unknown[]): Promise<boolean> {
    const cachePath = this._getPath(...args);
    validateCachePath(cachePath);
    const mtime = await getLastUpdated(cachePath);
    return mtime !== null;
  }

  /**
   * Returns the age of the cache file in milliseconds, or null if it does not exist.
   *
   * @param args - Arguments to resolve the cache path (when using a path function)
   * @returns Age in ms, or null
   */
  async age(...args: unknown[]): Promise<number | null> {
    const cachePath = this._getPath(...args);
    validateCachePath(cachePath);
    const mtime = await getLastUpdated(cachePath);
    if (mtime === null) return null;
    return Date.now() - mtime;
  }

  /**
   * Returns detailed information about the cache state.
   *
   * @param args - Arguments to resolve the cache path (when using a path function)
   * @returns CacheInfo with exists, age, expired, stale, and path fields
   */
  async info(...args: unknown[]): Promise<CacheInfo> {
    const cachePath = this._getPath(...args);
    validateCachePath(cachePath);
    const mtime = await getLastUpdated(cachePath);
    if (mtime === null) {
      return { exists: false, age: null, expired: false, stale: false, path: cachePath };
    }
    const ageMs = Date.now() - mtime;
    const expired = ageMs >= this.duration;
    const stale = expired && this.staleDuration != null && ageMs < (this.duration + this.staleDuration);
    return { exists: true, age: ageMs, expired, stale, path: cachePath };
  }

  /**
   * Internal method to resolve the cache path.
   * When path is a string and arguments are provided, auto-generates a unique
   * cache path by hashing the arguments.
   * @internal
   */
  _getPath(...args: unknown[]): string {
    if (typeof this.path === 'string') {
      if (args.length === 0) {
        return this.path;
      }
      // Auto cache key: hash arguments and embed in the path
      const hash = createHash('sha256')
        .update(JSON.stringify(args))
        .digest('hex')
        .slice(0, 16);
      const dir = dirname(this.path);
      const base = this.path.split('/').pop()!;
      const dotIndex = base.lastIndexOf('.');
      if (dotIndex === -1) {
        return join(dir, `${base}-${hash}`);
      }
      const name = base.slice(0, dotIndex);
      const ext = base.slice(dotIndex);
      return join(dir, `${name}-${hash}${ext}`);
    }
    return this.path(...args);
  }

  /**
   * Get a value from the in-memory LRU cache.
   * Returns undefined if LRU is disabled, key not found, or entry is expired.
   * @internal
   */
  _lruGet(key: string): unknown | typeof LRU_MISS {
    if (!this._lru) return LRU_MISS;
    const entry = this._lru.get(key);
    if (!entry) return LRU_MISS;

    // Lazy expiration: entries are evicted on access rather than via background timers.
    // This avoids the complexity of cleanup timers while keeping the LRU bounded by lruSize.
    const age = Date.now() - entry.timestamp;
    if (age > this.duration) {
      this._lru.delete(key);
      return LRU_MISS;
    }

    // Move to end (most recently used)
    this._lru.delete(key);
    this._lru.set(key, entry);
    return entry.value;
  }

  /**
   * Set a value in the in-memory LRU cache.
   * No-op if LRU is disabled.
   * @internal
   */
  _lruSet(key: string, value: unknown): void {
    if (!this._lru || !this.lruSize) return;

    // Evict oldest if at capacity
    if (this._lru.size >= this.lruSize && !this._lru.has(key)) {
      const firstKey = this._lru.keys().next().value;
      if (firstKey !== undefined) {
        this._lru.delete(firstKey);
      }
    }

    this._lru.set(key, { value, timestamp: Date.now() });
  }

  // Decorator usage: @cache
  call(target: CachableFunction, propertyKey: string, descriptor: PropertyDescriptor): PropertyDescriptor;
  // Function wrapper usage: cache(fn)
  call(target: CachableFunction): CachableFunction;
  // Configuration usage: cache(config)
  call(config: Partial<CacheConfig>): Cachetta;
  // Implementation signature
  call(configOrFn: CachableFunction | Partial<CacheConfig>, propertyKey?: string, descriptor?: PropertyDescriptor): PropertyDescriptor | CachableFunction | Cachetta {
    if (isPartialCacheConfig(configOrFn)) {
      const config = configOrFn as Partial<CacheConfig>;
      // it is being called as a class method decorator with args
      return this.copy(config);
    }
    if (descriptor) {
      // it is being called as a class method decorator without args
      const originalMethod = descriptor!.value;
      descriptor!.value = cacheFn(this as Cachetta, originalMethod);
      return descriptor;
    }
    const fn = configOrFn as CachableFunction;
    // it is being called as a function, wrapping another function
    if (propertyKey) {
      const config = propertyKey as Partial<CacheConfig>;
      const newCache = this.copy(config);
      return cacheFn(newCache, fn);
    }
    return cacheFn(this as Cachetta, fn);
  }
}
