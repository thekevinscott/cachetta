import { describe, it, expect } from 'vitest';
import { isCachetta, isCacheConfig, isPartialCacheConfig } from './type-guards.js';
import type { CacheConfig } from './types.js';
import { Cachetta } from './Cachetta.js';

describe('type-guards', () => {
  describe('isCachetta', () => {
    it('should return false for an object', () => {
      expect(isCachetta({ path: 'foo ' })).toEqual(false);
    });

    it('should return true for an object', () => {
      expect(isCachetta(new Cachetta({ path: 'foobar' }))).toEqual(true);
    });
  });
  describe('isCacheConfig', () => {
    it('should return true for valid CacheConfig with path', () => {
      const config = { path: './test.json' };
      expect(isCacheConfig(config)).toBe(true);
    });
  });

  describe('isPartialCacheConfig', () => {
    it('should return true for valid CacheConfig with path', () => {
      const config = { path: './test.json' };
      expect(isPartialCacheConfig(config)).toBe(true);
    });

    it('should return true for valid CacheConfig with write', () => {
      const config = { write: true };
      expect(isPartialCacheConfig(config)).toBe(true);
    });

    it('should return true for valid CacheConfig with read', () => {
      const config = { read: false };
      expect(isPartialCacheConfig(config)).toBe(true);
    });

    it('should return true for valid CacheConfig with duration', () => {
      const config = { duration: 1000 };
      expect(isPartialCacheConfig(config)).toBe(true);
    });

    it('should return true for complete CacheConfig', () => {
      const config: CacheConfig = {
        path: './test.json',
        write: true,
        read: false,
        duration: 5000
      };
      expect(isCacheConfig(config)).toBe(true);
    });

    it('should return true for CacheConfig with function path', () => {
      const config = { path: () => './dynamic.json' };
      expect(isCacheConfig(config)).toBe(true);
    });

    it('should return false for null', () => {
      expect(isCacheConfig(null)).toBe(false);
    });

    it('should return false for undefined', () => {
      expect(isCacheConfig(undefined)).toBe(false);
    });

    it('should return false for string', () => {
      expect(isCacheConfig('not a config')).toBe(false);
    });

    it('should return false for number', () => {
      expect(isCacheConfig(123)).toBe(false);
    });

    it('should return false for boolean', () => {
      expect(isCacheConfig(true)).toBe(false);
    });

    it('should return false for array', () => {
      expect(isCacheConfig([])).toBe(false);
    });

    it('should return false for object without cache properties', () => {
      const obj = { name: 'test', value: 123 };
      expect(isCacheConfig(obj)).toBe(false);
    });

    it('should return false for function', () => {
      const fn = () => { };
      expect(isCacheConfig(fn)).toBe(false);
    });

    it('should return false for empty object', () => {
      expect(isCacheConfig({})).toBe(false);
    });

    it('should return true for config with condition', () => {
      expect(isPartialCacheConfig({ condition: () => true })).toBe(true);
    });

    it('should return true for config with staleDuration', () => {
      expect(isPartialCacheConfig({ staleDuration: 5000 })).toBe(true);
    });

    it('should return true for config with lruSize', () => {
      expect(isPartialCacheConfig({ lruSize: 10 })).toBe(true);
    });
  });
}); 
