import { describe, it, expect } from 'vitest';
import { canaryBranch } from './canary-branch.js';

/**
 * CANARY — do not merge.
 *
 * Deliberately exercises ONLY the positive branch. Line coverage of
 * canary-branch.ts is 100%; branch coverage is 50%.
 */
describe('canaryBranch (one branch only)', () => {
  it('covers the positive side', () => {
    expect(canaryBranch(5)).toBe(1);
  });
});
