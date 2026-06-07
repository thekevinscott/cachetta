import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { promises as fs } from 'fs';
import { join } from 'path';
import { Cachetta, readCache, writeCache, hash } from 'cachetta';

describe('hashed flag (issue #44)', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(`cachetta-hashed-${Date.now()}-`);
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  describe('decorator-style override', () => {
    it('writes one file per arg-hash under the path folder', async () => {
      const cacheDir = join(tempDir, 'llm');
      const cache = new Cachetta({ path: cacheDir });
      const cached = cache((prompt: string) => `response: ${prompt}`, { hashed: true });

      const result = await cached('hello');
      expect(result).toBe('response: hello');

      const files = await fs.readdir(cacheDir);
      expect(files).toHaveLength(1);
      expect(files[0]).toHaveLength(16);
    });

    it('different args write different files', async () => {
      const cacheDir = join(tempDir, 'cache');
      const cache = new Cachetta({ path: cacheDir });
      const cached = cache((x: number) => x * 2, { hashed: true });

      await cached(1);
      await cached(2);
      await cached(3);

      const files = await fs.readdir(cacheDir);
      expect(files).toHaveLength(3);
    });

    it('same args hit the cache', async () => {
      let calls = 0;
      const cache = new Cachetta({ path: join(tempDir, 'cache') });
      const cached = cache((x: number) => { calls++; return x * 2; }, { hashed: true });

      expect(await cached(5)).toBe(10);
      expect(await cached(5)).toBe(10);
      expect(calls).toBe(1);
    });
  });

  describe('multi-decoration isolation', () => {
    it('base cache is not mutated by a (hashed: true) wrap', async () => {
      const literalPath = join(tempDir, 'literal.json');
      const hashedDir = join(tempDir, 'hashed');
      const cache = new Cachetta({ path: literalPath });

      const hashedFn = cache((x: string) => x, { path: hashedDir, hashed: true });
      const literalFn = cache(() => 'constant');

      await hashedFn('a');
      await hashedFn('b');
      await literalFn();
      await literalFn();

      const hashedFiles = await fs.readdir(hashedDir);
      expect(hashedFiles).toHaveLength(2);
      await expect(fs.access(literalPath)).resolves.toBeUndefined();

      // The base cache itself was never mutated
      expect(cache.hashed).toBe(false);
    });
  });

  describe('config-style on the constructor', () => {
    it('hashed=true applies to all entrypoints (read/write/exists/invalidate)', async () => {
      const cacheDir = join(tempDir, 'cache');
      const cache = new Cachetta({ path: cacheDir, hashed: true });

      await writeCache(cache, { x: 1 }, 'hello');

      expect(await cache.exists('hello')).toBe(true);
      expect(await cache.exists('other')).toBe(false);
      expect(await readCache(cache, 'hello')).toEqual({ x: 1 });

      await cache.invalidate('hello');
      expect(await cache.exists('hello')).toBe(false);
    });

    it('copy preserves and overrides hashed', () => {
      const cache = new Cachetta({ path: join(tempDir, 'c'), hashed: true });
      const preserved = cache.copy({});
      const overridden = cache.copy({ hashed: false });

      expect(preserved.hashed).toBe(true);
      expect(overridden.hashed).toBe(false);
    });
  });

  describe('composition with callable path', () => {
    it('callable path produces a folder, hash becomes the child filename', async () => {
      const cache = new Cachetta({
        path: ((model: string, _prompt: string) => join(tempDir, model)) as any,
        hashed: true,
      });
      const cached = cache((model: string, prompt: string) => `${model}: ${prompt}`);

      await cached('gpt', 'hi');
      await cached('gpt', 'bye');
      await cached('claude', 'hi');

      expect((await fs.readdir(join(tempDir, 'gpt')))).toHaveLength(2);
      expect((await fs.readdir(join(tempDir, 'claude')))).toHaveLength(1);
    });

    it('callable path + hashed flows through readCache/writeCache/exists/invalidate', async () => {
      const cache = new Cachetta({
        path: ((kind: string, _id: number) => join(tempDir, kind)) as any,
        hashed: true,
      });

      await writeCache(cache, { v: 1 }, 'users', 7);
      expect(await readCache(cache, 'users', 7)).toEqual({ v: 1 });
      expect(await cache.exists('users', 7)).toBe(true);
      expect(await cache.exists('users', 8)).toBe(false);

      await cache.invalidate('users', 7);
      expect(await cache.exists('users', 7)).toBe(false);
    });

    it('callable path supports isolated hashed + literal decorations on the same base', async () => {
      const cache = new Cachetta({
        path: ((kind: string) => join(tempDir, kind)) as any,
      });

      const hashedFn = cache((kind: string, prompt: string) => prompt, { hashed: true });
      const literalFn = cache((_kind: string) => 'constant');

      await hashedFn('users', 'a');
      await hashedFn('users', 'b');
      await literalFn('singletons');

      expect((await fs.readdir(join(tempDir, 'users')))).toHaveLength(2);
      await expect(fs.access(join(tempDir, 'singletons'))).resolves.toBeUndefined();

      expect(cache.hashed).toBe(false);
    });
  });

  describe('condition + hashed', () => {
    it('condition still gates writes when hashed=true', async () => {
      const cacheDir = join(tempDir, 'cache');
      const cache = new Cachetta({
        path: cacheDir,
        hashed: true,
        condition: (r) => r !== null,
      });
      const cached = cache((x: string) => (x === 'skip' ? null : x));

      await cached('skip');
      let files: string[] = [];
      try { files = await fs.readdir(cacheDir); } catch { /* dir may not exist */ }
      expect(files).toHaveLength(0);

      await cached('keep');
      files = await fs.readdir(cacheDir);
      expect(files).toHaveLength(1);
    });
  });

  describe('defaults + interop with hash export', () => {
    it('hashed defaults to false (post-#48 literal-path semantics)', () => {
      const cache = new Cachetta({ path: join(tempDir, 'data.json') });
      expect(cache.hashed).toBe(false);
      expect(cache._getPath('a')).toBe(join(tempDir, 'data.json'));
      expect(cache._getPath('a')).toBe(cache._getPath('b'));
    });

    it('the filename hashed=true writes is exactly the public hash() digest', async () => {
      const cacheDir = join(tempDir, 'cache');
      const cache = new Cachetta({ path: cacheDir, hashed: true });
      const cached = cache((x: string) => x);

      await cached('hello');
      const expected = hash('hello');
      const files = await fs.readdir(cacheDir);
      expect(files).toContain(expected);
    });
  });
});
