import { describe, it, expect } from 'vitest';
import { CACHE_MISS } from './constants.js';

describe('constants', () => {
  it('CACHE_MISS is a symbol', () => {
    expect(typeof CACHE_MISS).toBe('symbol');
    expect(CACHE_MISS.toString()).toBe('Symbol(CACHE_MISS)');
  });

  it('CACHE_MISS is a unique sentinel, distinct from look-alike values', () => {
    // A fresh Symbol with the same description is still a different value,
    // which is the whole point of using a symbol as the miss sentinel.
    expect(CACHE_MISS).not.toBe(Symbol('CACHE_MISS'));
    expect(CACHE_MISS as unknown).not.toBe(undefined);
    expect(CACHE_MISS as unknown).not.toBe(null);
  });
});
