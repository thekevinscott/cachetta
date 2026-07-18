import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import path from 'path';
import { promises as fs } from 'fs';
import { Cachetta } from 'cachetta';

describe('nullish cached values (issue #78)', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(`cachetta-test-${Date.now()}-${Math.random().toString(36).substring(2, 15)}`);
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  it('caches a function that returns null (async)', async () => {
    const cache = new Cachetta({ path: path.join(tempDir, 'null-async.json') });

    let calls = 0;
    async function bar() {
      calls++;
      return null;
    }
    const cachedBar = cache(bar);

    expect(await cachedBar()).toBeNull();
    expect(await cachedBar()).toBeNull();
    expect(calls).toBe(1);
  });

  it('caches a function that returns undefined (async)', async () => {
    const cache = new Cachetta({ path: path.join(tempDir, 'undefined-async.json') });

    let calls = 0;
    async function bar() {
      calls++;
      return undefined;
    }
    const cachedBar = cache(bar);

    expect(await cachedBar()).toBeUndefined();
    expect(await cachedBar()).toBeUndefined();
    expect(calls).toBe(1);
  });

  it('caches a function that returns null (sync)', async () => {
    const cache = new Cachetta({ path: path.join(tempDir, 'null-sync.json') });

    let calls = 0;
    function bar() {
      calls++;
      return null;
    }
    const cachedBar = cache.wrapSync(bar);

    expect(cachedBar()).toBeNull();
    expect(cachedBar()).toBeNull();
    expect(calls).toBe(1);
  });

  it('caches a function that returns undefined (sync)', async () => {
    const cache = new Cachetta({ path: path.join(tempDir, 'undefined-sync.json') });

    let calls = 0;
    function bar() {
      calls++;
      return undefined;
    }
    const cachedBar = cache.wrapSync(bar);

    expect(cachedBar()).toBeUndefined();
    expect(cachedBar()).toBeUndefined();
    expect(calls).toBe(1);
  });
});
