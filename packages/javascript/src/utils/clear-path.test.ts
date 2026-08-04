import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { promises as fs, mkdirSync, unlinkSync } from 'fs';
import { join } from 'path';
import { clearPath, clearPathSync } from './clear-path.js';

const always = () => true;
const never = () => false;

describe('clearPath', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp('cachetta-clear-path-');
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  describe('async', () => {
    it('returns [] for a missing path', async () => {
      expect(await clearPath(join(tempDir, 'nope'), always)).toEqual([]);
    });

    it('rethrows non-ENOENT stat errors', async () => {
      // Statting a path that treats a regular file as a directory yields
      // ENOTDIR, which must be rethrown rather than swallowed.
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      await expect(clearPath(join(file, 'child'), always)).rejects.toMatchObject({ code: 'ENOTDIR' });
    });

    it('deletes a file when shouldClear returns true', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      expect(await clearPath(file, always)).toEqual([file]);
      await expect(fs.access(file)).rejects.toThrow();
    });

    it('keeps a file when shouldClear returns false', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      expect(await clearPath(file, never)).toEqual([]);
      await expect(fs.access(file)).resolves.toBeUndefined();
    });

    it('passes the file mtime to shouldClear', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      const t = new Date(Date.now() - 5000);
      await fs.utimes(file, t, t);
      const seen: number[] = [];
      await clearPath(file, (mtime) => {
        seen.push(mtime);
        return false;
      });
      expect(seen).toEqual([t.getTime()]);
    });

    it('walks directories recursively, deleting files but keeping directories', async () => {
      await fs.mkdir(join(tempDir, 'sub'));
      await fs.writeFile(join(tempDir, 'a'), 'x');
      await fs.writeFile(join(tempDir, 'sub', 'b'), 'x');
      const deleted = await clearPath(tempDir, always);
      expect(deleted.sort()).toEqual([join(tempDir, 'a'), join(tempDir, 'sub', 'b')].sort());
      await expect(fs.access(join(tempDir, 'sub'))).resolves.toBeUndefined();
    });

    it('treats a file vanishing between stat and unlink as not deleted', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      // shouldClear runs between stat and unlink — deleting the file here
      // reproduces the race deterministically.
      const deleted = await clearPath(file, () => {
        unlinkSync(file);
        return true;
      });
      expect(deleted).toEqual([]);
    });

    it('rethrows non-ENOENT unlink errors', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      // Swap the file for a directory between stat and unlink so unlink
      // fails with EISDIR/EPERM instead of ENOENT.
      await expect(clearPath(file, () => {
        unlinkSync(file);
        mkdirSync(file);
        return true;
      })).rejects.toThrow();
    });
  });

  describe('sync', () => {
    it('returns [] for a missing path', () => {
      expect(clearPathSync(join(tempDir, 'nope'), always)).toEqual([]);
    });

    it('rethrows non-ENOENT stat errors', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      expect(() => clearPathSync(join(file, 'child'), always)).toThrow();
    });

    it('deletes a file when shouldClear returns true', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      expect(clearPathSync(file, always)).toEqual([file]);
      await expect(fs.access(file)).rejects.toThrow();
    });

    it('keeps a file when shouldClear returns false', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      expect(clearPathSync(file, never)).toEqual([]);
      await expect(fs.access(file)).resolves.toBeUndefined();
    });

    it('walks directories recursively, deleting files but keeping directories', async () => {
      await fs.mkdir(join(tempDir, 'sub'));
      await fs.writeFile(join(tempDir, 'a'), 'x');
      await fs.writeFile(join(tempDir, 'sub', 'b'), 'x');
      const deleted = clearPathSync(tempDir, always);
      expect(deleted.sort()).toEqual([join(tempDir, 'a'), join(tempDir, 'sub', 'b')].sort());
      await expect(fs.access(join(tempDir, 'sub'))).resolves.toBeUndefined();
    });

    it('treats a file vanishing between stat and unlink as not deleted', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      const deleted = clearPathSync(file, () => {
        unlinkSync(file);
        return true;
      });
      expect(deleted).toEqual([]);
    });

    it('rethrows non-ENOENT unlink errors', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      expect(() => clearPathSync(file, () => {
        unlinkSync(file);
        mkdirSync(file);
        return true;
      })).toThrow();
    });
  });
});
