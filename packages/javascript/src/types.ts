export interface CacheConfig<Path extends string | PathFn<any> = string> {
  path: Path;
  write?: boolean;
  read?: boolean;
  duration?: number;
  /** Function that decides whether to cache a result. Return true to cache, false to skip. */
  condition?: (result: unknown) => boolean;
  /** Duration in ms after `duration` expires during which stale data is returned while a background refresh runs. */
  staleDuration?: number;
  /** When true, arg-bearing calls resolve to `{path}/{hash(...args)}` — one file per arg-set inside the folder. Off (default) keeps the literal-path semantic. */
  hashed?: boolean;
}

export interface CacheInfo {
  exists: boolean;
  age: number | null;
  expired: boolean;
  stale: boolean;
  path: string;
}

export type PathFn<T extends unknown[] = unknown[]> = (...args: T) => string;
export type CachableFunction = (...args: unknown[]) => unknown;
export type CachableFunctionSync = (...args: unknown[]) => unknown;

export interface Logger {
  debug: (...messages: unknown[]) => void;
  info: (...messages: unknown[]) => void;
  warn: (...messages: unknown[]) => void;
  error: (...messages: unknown[]) => void;
}

export type LogLevel = 'debug' | 'info' | 'warn' | 'error';
