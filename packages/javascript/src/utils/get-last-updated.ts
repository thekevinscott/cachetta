import { promises as fs, statSync } from 'fs';
import { PathLike } from 'fs';

export async function getLastUpdated(filePath: string | PathLike): Promise<number | null> {
  try {
    const stats = await fs.stat(filePath);
    return stats.mtime.getTime();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return null;
    }
    throw error;
  }
}

export function getLastUpdatedSync(filePath: string | PathLike): number | null {
  try {
    const stats = statSync(filePath);
    return stats.mtime.getTime();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return null;
    }
    throw error;
  }
}
