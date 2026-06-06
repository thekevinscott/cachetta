/**
 * DEMONSTRATION ONLY — do not merge.
 *
 * New `src/` code that is exercised purely by an integration test
 * (`tests/demo-uncovered.test.ts`) and has NO colocated unit test
 * (`src/demo-uncovered.test.ts`). Used to confirm the coverage gate
 * fails when `src/` lacks unit coverage.
 */
export const demoUncovered = (a: number, b: number): number => {
  if (a > b) {
    return a - b;
  }
  return a + b;
};
