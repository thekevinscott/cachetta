import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { promises as fs } from 'fs';
import { join } from 'path';
import { Cachetta, CachettaError } from 'cachetta';

describe('hashed decorator (issue #44)', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(`cachetta-hashed-${Date.now()}-`);
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  describe('basic usage', () => {
    it('writes to {path}/{hash} (bare hash, no extension) by default', async () => {
      const cacheDir = join(tempDir, 'llm');
      const cache = new Cachetta({ path: cacheDir });
      const cached = cache.hashed((prompt: string) => `response: ${prompt}`);

      const result = await cached('hello');
      expect(result).toBe('response: hello');

      const files = await fs.readdir(cacheDir);
      expect(files).toHaveLength(1);
      expect(files[0]).not.toContain('.');
      expect(files[0]).toHaveLength(16);
    });

    it('different args write different files', async () => {
      const cacheDir = join(tempDir, 'cache');
      const cache = new Cachetta({ path: cacheDir });
      const cached = cache.hashed((x: number) => x * 2);

      await cached(1);
      await cached(2);
      await cached(3);

      const files = await fs.readdir(cacheDir);
      expect(files).toHaveLength(3);
    });

    it('same args hit cache', async () => {
      let calls = 0;
      const cache = new Cachetta({ path: join(tempDir, 'cache') });
      const cached = cache.hashed((x: number) => { calls++; return x * 2; });

      expect(await cached(5)).toBe(10);
      expect(await cached(5)).toBe(10);
      expect(calls).toBe(1);
    });
  });

  describe('key option', () => {
    it('key override produces {path}/{key(args)}', async () => {
      const cacheDir = join(tempDir, 'cache');
      const cache = new Cachetta({ path: cacheDir });
      const cached = cache.hashed((x: number) => x * 2, { key: (x: number) => `id-${x}` });

      await cached(42);
      const files = await fs.readdir(cacheDir);
      expect(files[0]).toBe('id-42');
    });

    it('key rejects path traversal', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'cache') });
      const cached = cache.hashed((x: string) => x, { key: () => '../escape' });

      await expect(cached('a')).rejects.toThrow();
    });

    it('key rejects slashes', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'cache') });
      const cached = cache.hashed((x: string) => x, { key: () => 'sub/dir' });

      await expect(cached('a')).rejects.toThrow();
    });
  });

  describe('condition integration', () => {
    it('condition gates writes', async () => {
      const cacheDir = join(tempDir, 'cache');
      const cache = new Cachetta({
        path: cacheDir,
        condition: (r) => r !== null,
      });
      const cached = cache.hashed((x: string) => (x === 'skip' ? null : x));

      await cached('skip');
      let files: string[] = [];
      try {
        files = await fs.readdir(cacheDir);
      } catch {
        // dir may not exist
      }
      expect(files).toHaveLength(0);

      await cached('keep');
      files = await fs.readdir(cacheDir);
      expect(files).toHaveLength(1);
    });
  });

  describe('callable path disallowed', () => {
    it('throws when path is callable', () => {
      const cache = new Cachetta({ path: (() => 'x') });
      expect(() => cache.hashed((x: string) => x)).toThrow(CachettaError);
    });
  });
});
