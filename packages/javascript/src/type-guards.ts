import { Cachetta } from './Cachetta.js';
import type { CacheConfig } from './types.js';

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null;
export const isCacheConfig = (value: unknown): value is CacheConfig => isObject(value) && 'path' in value;
export const isPartialCacheConfig = (value: unknown): value is Partial<CacheConfig> => isObject(value) && (
  'path' in value ||
  'write' in value ||
  'read' in value ||
  'duration' in value ||
  'condition' in value ||
  'staleDuration' in value ||
  'hashed' in value
);

export const isCachetta = (value: unknown): value is Cachetta<any> => typeof value === 'function' && '__cacheBuddy__' in value && value.__cacheBuddy__ === true;
