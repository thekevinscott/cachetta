import { promises as fs, readdirSync, statSync, unlinkSync } from 'fs';
import { join } from 'path';

/** Decides whether a file with the given mtime (ms epoch) should be deleted. */
export type ShouldClear = (mtimeMs: number) => boolean;

const isENOENT = (error: unknown): boolean => (error as NodeJS.ErrnoException).code === 'ENOENT';

/**
 * Deletes files under `target` for which `shouldClear(mtime)` returns true.
 * A directory is walked recursively (directories themselves are kept); a
 * file is checked in place; a missing path is a no-op.
 */
export async function clearPath(target: string, shouldClear: ShouldClear): Promise<void> {
  let stats;
  try {
    stats = await fs.stat(target);
  } catch (error) {
    if (isENOENT(error)) {
      return;
    }
    throw error;
  }
  if (stats.isDirectory()) {
    for (const entry of await fs.readdir(target)) {
      await clearPath(join(target, entry), shouldClear);
    }
    return;
  }
  if (!shouldClear(stats.mtime.getTime())) {
    return;
  }
  try {
    await fs.unlink(target);
  } catch (error) {
    // The file vanished between stat and unlink; nothing left to do.
    if (!isENOENT(error)) {
      throw error;
    }
  }
}

export function clearPathSync(target: string, shouldClear: ShouldClear): void {
  let stats;
  try {
    stats = statSync(target);
  } catch (error) {
    if (isENOENT(error)) {
      return;
    }
    throw error;
  }
  if (stats.isDirectory()) {
    for (const entry of readdirSync(target)) {
      clearPathSync(join(target, entry), shouldClear);
    }
    return;
  }
  if (!shouldClear(stats.mtime.getTime())) {
    return;
  }
  try {
    unlinkSync(target);
  } catch (error) {
    // The file vanished between stat and unlink; nothing left to do.
    if (!isENOENT(error)) {
      throw error;
    }
  }
}
