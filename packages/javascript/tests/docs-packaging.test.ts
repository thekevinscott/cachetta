import { describe, it, expect } from 'vitest';
import { execSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const pkgDir = resolve(here, '..');
const repoRoot = resolve(pkgDir, '../..');
const fixturePath = join(repoRoot, 'docs/_test/nested.md');

describe('docs packaging', () => {
  it('npm pack ships nested docs subdirectories', () => {
    expect(existsSync(fixturePath)).toBe(true);

    const raw = execSync('npm pack --dry-run --json', {
      cwd: pkgDir,
      encoding: 'utf-8',
    });

    const jsonStart = raw.indexOf('[');
    expect(jsonStart).toBeGreaterThanOrEqual(0);
    const manifest = JSON.parse(raw.slice(jsonStart)) as Array<{
      files: Array<{ path: string }>;
    }>;
    const paths = manifest[0]!.files.map((f) => f.path);

    expect(paths).toContain('docs/_test/nested.md');
  }, 30_000);
});
