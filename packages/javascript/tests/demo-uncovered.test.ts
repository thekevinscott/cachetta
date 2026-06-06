import { describe, it, expect } from 'vitest';
import { demoUncovered } from 'cachetta';

/**
 * DEMONSTRATION ONLY — do not merge.
 *
 * This is an INTEGRATION test (lives under tests/). It fully exercises
 * `demoUncovered`, but there is deliberately NO colocated unit test at
 * `src/demo-uncovered.test.ts`. The coverage gate runs only the unit
 * suite, so this integration coverage must NOT satisfy the gate.
 */
describe('demoUncovered (integration only)', () => {
  it('adds when a <= b', () => {
    expect(demoUncovered(1, 2)).toBe(3);
  });

  it('subtracts when a > b', () => {
    expect(demoUncovered(5, 2)).toBe(3);
  });
});
