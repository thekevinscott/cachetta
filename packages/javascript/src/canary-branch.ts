/**
 * CANARY — do not merge.
 *
 * One-line branch. The colocated unit test exercises only the `x > 0`
 * side, so the LINE is 100% covered but a BRANCH is missed. If CI is
 * green, branch coverage is not enforced on changed code.
 */
export const canaryBranch = (x: number): number => (x > 0 ? 1 : 2);
