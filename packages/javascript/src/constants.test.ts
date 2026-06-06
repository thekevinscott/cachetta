import { describe, it, expect } from 'vitest';
import { LRU_MISS } from './constants.js';

describe('constants', () => {
  it('LRU_MISS is a symbol', () => {
    expect(typeof LRU_MISS).toBe('symbol');
    expect(LRU_MISS.toString()).toBe('Symbol(LRU_MISS)');
  });

  it('LRU_MISS is a unique sentinel, distinct from look-alike values', () => {
    // A fresh Symbol with the same description is still a different value,
    // which is the whole point of using a symbol as the miss sentinel.
    expect(LRU_MISS).not.toBe(Symbol('LRU_MISS'));
    expect(LRU_MISS as unknown).not.toBe(undefined);
    expect(LRU_MISS as unknown).not.toBe(null);
  });
});
