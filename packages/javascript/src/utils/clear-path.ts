import { promises as fs, readdirSync, statSync, unlinkSync } from 'fs';
import { join } from 'path';

/** Decides whether a file with the given mtime (ms epoch) should be deleted. */
export type ShouldClear = (mtimeMs: number) => boolean;

const isENOENT = (error: unknown): boolean => (error as NodeJS.ErrnoException).code === 'ENOENT';

/**
 * Deletes files under `target` for which `shouldClear(mtime)` returns true.
 * A directory is walked recursively (directories themselves are kept); a
 * file is checked in place; a missing path is a no-op. Returns the deleted
 * file paths.
 */
export async function clearPath(target: string, shouldClear: ShouldClear): Promise<string[]> {
  let stats;
  try {
    stats = await fs.stat(target);
  } catch (error) {
    if (isENOENT(error)) {
      return [];
    }
    throw error;
  }
  if (!stats.isDirectory()) {
    if (!shouldClear(stats.mtime.getTime())) {
      return [];
    }
    try {
      await fs.unlink(target);
    } catch (error) {
      // The file vanished between stat and unlink; it was not deleted by us.
      if (isENOENT(error)) {
        return [];
      }
      throw error;
    }
    return [target];
  }
  const deleted: string[] = [];
  for (const entry of await fs.readdir(target)) {
    deleted.push(...(await clearPath(join(target, entry), shouldClear)));
  }
  return deleted;
}

export function clearPathSync(target: string, shouldClear: ShouldClear): string[] {
  let stats;
  try {
    stats = statSync(target);
  } catch (error) {
    if (isENOENT(error)) {
      return [];
    }
    throw error;
  }
  if (!stats.isDirectory()) {
    if (!shouldClear(stats.mtime.getTime())) {
      return [];
    }
    try {
      unlinkSync(target);
    } catch (error) {
      // The file vanished between stat and unlink; it was not deleted by us.
      if (isENOENT(error)) {
        return [];
      }
      throw error;
    }
    return [target];
  }
  const deleted: string[] = [];
  for (const entry of readdirSync(target)) {
    deleted.push(...clearPathSync(join(target, entry), shouldClear));
  }
  return deleted;
}
