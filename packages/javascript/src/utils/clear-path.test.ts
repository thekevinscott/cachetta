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
    it('is a no-op for a missing path', async () => {
      await expect(clearPath(join(tempDir, 'nope'), always)).resolves.toBeUndefined();
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
      await clearPath(file, always);
      await expect(fs.access(file)).rejects.toThrow();
    });

    it('keeps a file when shouldClear returns false', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      await clearPath(file, never);
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
      await clearPath(tempDir, always);
      await expect(fs.access(join(tempDir, 'a'))).rejects.toThrow();
      await expect(fs.access(join(tempDir, 'sub', 'b'))).rejects.toThrow();
      await expect(fs.access(join(tempDir, 'sub'))).resolves.toBeUndefined();
    });

    it('tolerates a file vanishing between stat and unlink', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      // shouldClear runs between stat and unlink — deleting the file here
      // reproduces the race deterministically.
      await expect(clearPath(file, () => {
        unlinkSync(file);
        return true;
      })).resolves.toBeUndefined();
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
    it('is a no-op for a missing path', () => {
      expect(clearPathSync(join(tempDir, 'nope'), always)).toBeUndefined();
    });

    it('rethrows non-ENOENT stat errors', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      expect(() => clearPathSync(join(file, 'child'), always)).toThrow();
    });

    it('deletes a file when shouldClear returns true', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      clearPathSync(file, always);
      await expect(fs.access(file)).rejects.toThrow();
    });

    it('keeps a file when shouldClear returns false', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      clearPathSync(file, never);
      await expect(fs.access(file)).resolves.toBeUndefined();
    });

    it('walks directories recursively, deleting files but keeping directories', async () => {
      await fs.mkdir(join(tempDir, 'sub'));
      await fs.writeFile(join(tempDir, 'a'), 'x');
      await fs.writeFile(join(tempDir, 'sub', 'b'), 'x');
      clearPathSync(tempDir, always);
      await expect(fs.access(join(tempDir, 'a'))).rejects.toThrow();
      await expect(fs.access(join(tempDir, 'sub', 'b'))).rejects.toThrow();
      await expect(fs.access(join(tempDir, 'sub'))).resolves.toBeUndefined();
    });

    it('tolerates a file vanishing between stat and unlink', async () => {
      const file = join(tempDir, 'a');
      await fs.writeFile(file, 'x');
      expect(clearPathSync(file, () => {
        unlinkSync(file);
        return true;
      })).toBeUndefined();
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
