import { describe, it, expect } from 'vitest';
import { hash } from './hash.js';

describe('hash', () => {
  it('returns a 16-char lowercase hex string', () => {
    const result = hash('a', 'b');
    expect(result).toHaveLength(16);
    expect(result).toMatch(/^[0-9a-f]{16}$/);
  });

  it('is deterministic across calls', () => {
    expect(hash(1, 2, { name: 'foo' })).toBe(hash(1, 2, { name: 'foo' }));
  });

  it('distinct positional inputs produce distinct digests', () => {
    expect(hash('a')).not.toBe(hash('b'));
    expect(hash(1)).not.toBe(hash(2));
  });

  it('object args participate in the digest', () => {
    expect(hash({ k: 1 })).not.toBe(hash({ k: 2 }));
    expect(hash({ k: 1 })).toBe(hash({ k: 1 }));
  });

  it('no args is stable across calls', () => {
    expect(hash()).toBe(hash());
  });
});
