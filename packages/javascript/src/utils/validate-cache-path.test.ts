import { describe, it, expect } from 'vitest';
import { validateCachePath } from './validate-cache-path.js';
import { InvalidPathError } from '../errors.js';

describe('validateCachePath', () => {
  it('accepts a simple relative path', () => {
    const result = validateCachePath('cache/test.json');
    expect(result).toContain('cache');
    expect(result).toContain('test.json');
  });

  it('accepts an absolute path', () => {
    const result = validateCachePath('/tmp/cache/test.json');
    expect(result).toBe('/tmp/cache/test.json');
  });

  it('rejects paths with .. traversal', () => {
    expect(() => validateCachePath('../etc/passwd')).toThrow(InvalidPathError);
    expect(() => validateCachePath('cache/../../etc/passwd')).toThrow(InvalidPathError);
  });

  it('allows absolute paths where .. resolves within the path', () => {
    // /tmp/../etc/passwd normalizes to /etc/passwd (no remaining ..)
    const result = validateCachePath('/tmp/../etc/passwd');
    expect(result).toBe('/etc/passwd');
  });

  it('accepts paths with dots in filenames', () => {
    const result = validateCachePath('/tmp/my.cache.json');
    expect(result).toBe('/tmp/my.cache.json');
  });

  it('normalizes redundant separators', () => {
    const result = validateCachePath('/tmp//cache///test.json');
    expect(result).toBe('/tmp/cache/test.json');
  });

  it('normalizes . segments', () => {
    const result = validateCachePath('/tmp/./cache/./test.json');
    expect(result).toBe('/tmp/cache/test.json');
  });
});
