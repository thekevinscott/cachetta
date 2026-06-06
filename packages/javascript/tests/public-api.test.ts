import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { promises as fs } from 'fs';
import { join } from 'path';
import { Cachetta, hash } from 'cachetta';

/**
 * Black-box tests for the public `cachetta` API surface.
 *
 * These tests treat the package as a black box: they import only from
 * `cachetta` (no internal modules, no private attributes), exercise
 * the public API, and assert against observable behavior such as files
 * written to disk.
 */
describe('public hash() export', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp('cachetta-public-api-');
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  it('digest matches the auto-keyed file written to disk', async () => {
    const cache = new Cachetta({ path: join(tempDir, 'data.json') });
    const wrapped = cache(async (a: string, b: string) => ({ a, b }));

    await wrapped('x', 'y');

    const digest = hash('x', 'y');
    const expected = join(tempDir, `data-${digest}.json`);
    await fs.access(expected);
  });

  it('digest matches when the path has no extension', async () => {
    const cache = new Cachetta({ path: join(tempDir, 'cache') });
    const wrapped = cache(async (k: string) => k);

    await wrapped('k');

    const digest = hash('k');
    const expected = join(tempDir, `cache-${digest}`);
    await fs.access(expected);
  });
});
