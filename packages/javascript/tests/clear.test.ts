import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { promises as fs } from 'fs';
import { join } from 'path';
import { Cachetta, writeCache } from 'cachetta';

const HOUR = 60 * 60 * 1000;

const backdate = async (path: string, ms: number) => {
  const t = new Date(Date.now() - ms);
  await fs.utimes(path, t, t);
};

describe('clear as an expiry-aware sweep (issue #110)', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(`cachetta-clear-${Date.now()}-`);
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  describe('folder sweep without force', () => {
    it('deletes dead entries, keeps fresh ones, and returns the deleted paths', async () => {
      const cacheDir = join(tempDir, 'cache');
      const cache = new Cachetta({ path: cacheDir, hashed: true, duration: HOUR });

      await writeCache(cache, { v: 1 }, 'fresh');
      await writeCache(cache, { v: 2 }, 'old-a');
      await writeCache(cache, { v: 3 }, 'old-b');
      await backdate(cache._getPath('old-a'), 2 * HOUR);
      await backdate(cache._getPath('old-b'), 3 * HOUR);

      const deleted = await cache.clear();

      expect(deleted.sort()).toEqual([cache._getPath('old-a'), cache._getPath('old-b')].sort());
      expect(await fs.readdir(cacheDir)).toHaveLength(1);
      expect(await cache.exists('fresh')).toBe(true);
      expect(await cache.exists('old-a')).toBe(false);
      expect(await cache.exists('old-b')).toBe(false);
    });

    it('keeps entries inside the stale-while-revalidate window', async () => {
      const cacheDir = join(tempDir, 'cache');
      const cache = new Cachetta({
        path: cacheDir,
        hashed: true,
        duration: HOUR,
        staleDuration: HOUR,
      });

      await writeCache(cache, { v: 1 }, 'fresh');
      await writeCache(cache, { v: 2 }, 'stale');
      await writeCache(cache, { v: 3 }, 'dead');
      // Expired but within duration + staleDuration: still servable via SWR.
      await backdate(cache._getPath('stale'), 1.5 * HOUR);
      // Past duration + staleDuration: never servable again.
      await backdate(cache._getPath('dead'), 2.5 * HOUR);

      const deleted = await cache.clear();

      expect(deleted).toEqual([cache._getPath('dead')]);
      expect(await cache.exists('fresh')).toBe(true);
      expect(await cache.exists('stale')).toBe(true);
      expect(await cache.exists('dead')).toBe(false);
    });

    it('recurses into subfolders and leaves the directories in place', async () => {
      const cacheDir = join(tempDir, 'cache');
      const cache = new Cachetta({ path: cacheDir, duration: HOUR });

      const nestedFile = join(cacheDir, 'nested', 'entry.json');
      await fs.mkdir(join(cacheDir, 'nested'), { recursive: true });
      await fs.writeFile(nestedFile, JSON.stringify({ v: 1 }));
      await backdate(nestedFile, 2 * HOUR);

      const deleted = await cache.clear();

      expect(deleted).toEqual([nestedFile]);
      // The (now empty) subfolder still exists.
      await expect(fs.access(join(cacheDir, 'nested'))).resolves.toBeUndefined();
    });
  });

  describe('force override', () => {
    it('wipes every entry in the folder regardless of freshness', async () => {
      const cacheDir = join(tempDir, 'cache');
      const cache = new Cachetta({ path: cacheDir, hashed: true, duration: HOUR });

      await writeCache(cache, { v: 1 }, 'fresh');
      await writeCache(cache, { v: 2 }, 'old');
      await backdate(cache._getPath('old'), 2 * HOUR);

      const deleted = await cache.clear({ force: true });

      expect(deleted.sort()).toEqual([cache._getPath('fresh'), cache._getPath('old')].sort());
      expect(await fs.readdir(cacheDir)).toHaveLength(0);
    });

    it('deletes a fresh single-file cache', async () => {
      const cachePath = join(tempDir, 'data.json');
      const cache = new Cachetta({ path: cachePath, duration: HOUR });

      await writeCache(cache, { v: 1 });

      const deleted = await cache.clear({ force: true });

      expect(deleted).toEqual([cachePath]);
      expect(await cache.exists()).toBe(false);
    });
  });

  describe('single-file cache without force', () => {
    it('deletes the file when it is no longer servable', async () => {
      const cachePath = join(tempDir, 'data.json');
      const cache = new Cachetta({ path: cachePath, duration: HOUR });

      await writeCache(cache, { v: 1 });
      await backdate(cachePath, 2 * HOUR);

      const deleted = await cache.clear();

      expect(deleted).toEqual([cachePath]);
      expect(await cache.exists()).toBe(false);
    });

    it('keeps the file while it is fresh', async () => {
      const cachePath = join(tempDir, 'data.json');
      const cache = new Cachetta({ path: cachePath, duration: HOUR });

      await writeCache(cache, { v: 1 });

      const deleted = await cache.clear();

      expect(deleted).toEqual([]);
      expect(await cache.exists()).toBe(true);
    });
  });

  describe('path resolution parity with other methods', () => {
    it('resolves callable paths with the given args, options-last', async () => {
      const cache = new Cachetta({
        path: ((model: string) => join(tempDir, model)) as any,
        hashed: true,
        duration: HOUR,
      });

      await writeCache(cache, { v: 1 }, 'gpt');
      await writeCache(cache, { v: 2 }, 'claude');

      // Both entries are fresh; force-clear only the 'gpt' entry.
      const deleted = await cache.clear('gpt', { force: true });

      expect(deleted).toEqual([cache._getPath('gpt')]);
      expect(await cache.exists('gpt')).toBe(false);
      expect(await cache.exists('claude')).toBe(true);
    });
  });

  describe('missing path', () => {
    it('is a no-op that returns an empty array', async () => {
      const cache = new Cachetta({ path: join(tempDir, 'nope'), duration: HOUR });
      await expect(cache.clear()).resolves.toEqual([]);
      await expect(cache.clear({ force: true })).resolves.toEqual([]);
    });
  });

  describe('clearSync', () => {
    it('mirrors clear, including force', async () => {
      const cacheDir = join(tempDir, 'cache');
      const cache = new Cachetta({ path: cacheDir, hashed: true, duration: HOUR });

      await writeCache(cache, { v: 1 }, 'fresh');
      await writeCache(cache, { v: 2 }, 'old');
      await backdate(cache._getPath('old'), 2 * HOUR);

      const deleted = cache.clearSync();
      expect(deleted).toEqual([cache._getPath('old')]);
      expect(cache.existsSync('fresh')).toBe(true);
      expect(cache.existsSync('old')).toBe(false);

      const forced = cache.clearSync({ force: true });
      expect(forced).toEqual([cache._getPath('fresh')]);
      expect(cache.existsSync('fresh')).toBe(false);
    });

    it('is a no-op on a missing path', () => {
      const cache = new Cachetta({ path: join(tempDir, 'nope'), duration: HOUR });
      expect(cache.clearSync()).toEqual([]);
    });
  });
});
