import type { CacheConfig, CacheInfo, CachableFunction, CachableFunctionSync, PathFn } from './types.js';
import { isClearOptions, isPartialCacheConfig } from './type-guards.js';
import { cacheFn, cacheFnSync } from './utils/cache-fn.js';
import { clearPath, clearPathSync, type ShouldClear } from './utils/clear-path.js';
import { getLastUpdated, getLastUpdatedSync } from './utils/get-last-updated.js';
import { forgetCreatedDirs } from './write-cache.js';
import { promises as fs, rmSync, unlinkSync } from 'fs';
import { join } from 'path';
import { inspect } from 'util';

import { hash } from './hash.js';

const DEFAULT_DURATION = 7 * 24 * 60 * 60 * 1000; // Default 7 days in milliseconds

// A trailing `{ force: boolean }` object is the options; everything before
// it resolves the cache path, exactly like the other instance methods.
const splitClearArgs = (argsAndOptions: unknown[]): { args: unknown[]; force: boolean } => {
  const last = argsAndOptions[argsAndOptions.length - 1];
  if (isClearOptions(last)) {
    return { args: argsAndOptions.slice(0, -1), force: last.force };
  }
  return { args: argsAndOptions, force: false };
};

export class Cachetta<Path extends string | PathFn<any> = string> extends Function {
  protected __cacheBuddy__ = true;
  public path!: Path;
  public write!: boolean;
  public read!: boolean;
  public duration!: number; // milliseconds
  public condition!: ((result: unknown) => boolean) | undefined;
  public staleDuration!: number | undefined;
  public hashed!: boolean;

  constructor(config: CacheConfig<Path>) {
    super();
    this.path = config.path;
    this.write = config.write ?? true;
    this.read = config.read ?? true;
    this.duration = config.duration ?? DEFAULT_DURATION;
    this.condition = config.condition;
    this.staleDuration = config.staleDuration;
    this.hashed = config.hashed ?? false;
    const boundCall = this.call.bind(this);
    const result = Object.assign(
      boundCall,
      this,
      {
        copy: this.copy.bind(this),
        wrap: this.wrap.bind(this),
        wrapSync: this.wrapSync.bind(this),
        invalidate: this.invalidate.bind(this),
        invalidateSync: this.invalidateSync.bind(this),
        clear: this.clear.bind(this),
        clearSync: this.clearSync.bind(this),
        exists: this.exists.bind(this),
        existsSync: this.existsSync.bind(this),
        age: this.age.bind(this),
        ageSync: this.ageSync.bind(this),
        info: this.info.bind(this),
        infoSync: this.infoSync.bind(this),
        _getPath: this._getPath.bind(this),
        __cacheBuddy__: true,
        condition: this.condition,
        staleDuration: this.staleDuration,
      }) as unknown as typeof boundCall & typeof this & { [inspect.custom]: () => string };
    result[inspect.custom] = () => `Cachetta { path: '${this.path}', write: ${this.write}, read: ${this.read}, duration: ${this.duration} }`;
    return result;
  }

  copy<NewPath extends string | PathFn<any> = string>(kwargs: Partial<CacheConfig<NewPath>>): Cachetta<NewPath> {
    return new Cachetta({
      path: (kwargs.path ?? this.path) as NewPath,
      write: kwargs.write ?? this.write,
      read: kwargs.read ?? this.read,
      duration: kwargs.duration ?? this.duration,
      condition: kwargs.condition ?? this.condition,
      staleDuration: kwargs.staleDuration ?? this.staleDuration,
      hashed: kwargs.hashed ?? this.hashed,
    });
  }

  wrap(fn: CachableFunction): CachableFunction {
    return cacheFn(this as Cachetta, fn);
  }

  wrapSync(fn: CachableFunctionSync): CachableFunctionSync {
    return cacheFnSync(this as Cachetta, fn);
  }

  // A file is servable until it ages past `duration` plus the
  // stale-while-revalidate window, so a non-forced clear never deletes an
  // entry that a read could still return.
  private shouldClear(): ShouldClear {
    const threshold = this.duration + (this.staleDuration ?? 0);
    return (mtimeMs) => Math.max(0, Date.now() - mtimeMs) >= threshold;
  }

  /**
   * Sweeps the resolved cache path, deleting entries that are no longer
   * servable (age ≥ `duration` + `staleDuration`). A folder is walked
   * recursively; a file is checked in place; a missing path is a no-op.
   * A trailing `{ force: true }` skips the walk entirely and removes the
   * resolved path wholesale, folder and all; writes re-create the folder.
   */
  async clear(...argsAndOptions: unknown[]): Promise<void> {
    const { args, force } = splitClearArgs(argsAndOptions);
    const target = this._getPath(...args);
    if (force) {
      await fs.rm(target, { recursive: true, force: true });
      forgetCreatedDirs();
      return;
    }
    await clearPath(target, this.shouldClear());
  }

  clearSync(...argsAndOptions: unknown[]): void {
    const { args, force } = splitClearArgs(argsAndOptions);
    const target = this._getPath(...args);
    if (force) {
      rmSync(target, { recursive: true, force: true });
      forgetCreatedDirs();
      return;
    }
    clearPathSync(target, this.shouldClear());
  }

  async invalidate(...args: unknown[]): Promise<void> {
    const cachePath = this._getPath(...args);
    try {
      await fs.unlink(cachePath);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') {
        throw error;
      }
    }
  }

  invalidateSync(...args: unknown[]): void {
    const cachePath = this._getPath(...args);
    try {
      unlinkSync(cachePath);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'ENOENT') {
        throw error;
      }
    }
  }

  async exists(...args: unknown[]): Promise<boolean> {
    const cachePath = this._getPath(...args);
    const mtime = await getLastUpdated(cachePath);
    return mtime !== null;
  }

  existsSync(...args: unknown[]): boolean {
    const cachePath = this._getPath(...args);
    return getLastUpdatedSync(cachePath) !== null;
  }

  async age(...args: unknown[]): Promise<number | null> {
    const cachePath = this._getPath(...args);
    const mtime = await getLastUpdated(cachePath);
    if (mtime === null) return null;
    return Math.max(0, Date.now() - mtime);
  }

  ageSync(...args: unknown[]): number | null {
    const cachePath = this._getPath(...args);
    const mtime = getLastUpdatedSync(cachePath);
    if (mtime === null) return null;
    return Math.max(0, Date.now() - mtime);
  }

  async info(...args: unknown[]): Promise<CacheInfo> {
    const cachePath = this._getPath(...args);
    const mtime = await getLastUpdated(cachePath);
    if (mtime === null) {
      return { exists: false, age: null, expired: false, stale: false, path: cachePath };
    }
    const ageMs = Math.max(0, Date.now() - mtime);
    const expired = ageMs >= this.duration;
    const stale = expired && this.staleDuration != null && ageMs < (this.duration + this.staleDuration);
    return { exists: true, age: ageMs, expired, stale, path: cachePath };
  }

  infoSync(...args: unknown[]): CacheInfo {
    const cachePath = this._getPath(...args);
    const mtime = getLastUpdatedSync(cachePath);
    if (mtime === null) {
      return { exists: false, age: null, expired: false, stale: false, path: cachePath };
    }
    const ageMs = Math.max(0, Date.now() - mtime);
    const expired = ageMs >= this.duration;
    const stale = expired && this.staleDuration != null && ageMs < (this.duration + this.staleDuration);
    return { exists: true, age: ageMs, expired, stale, path: cachePath };
  }

  _getPath(...args: unknown[]): string {
    const base = typeof this.path === 'string' ? this.path : this.path(...args);
    if (this.hashed && args.length > 0) {
      return join(base, hash(...args));
    }
    return base;
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
      return this.copy(config);
    }
    if (descriptor) {
      const originalMethod = descriptor!.value;
      descriptor!.value = cacheFn(this as Cachetta, originalMethod);
      return descriptor;
    }
    const fn = configOrFn as CachableFunction;
    if (propertyKey) {
      const config = propertyKey as Partial<CacheConfig>;
      const newCache = this.copy(config);
      return cacheFn(newCache, fn);
    }
    return cacheFn(this as Cachetta, fn);
  }
}
