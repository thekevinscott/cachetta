import { resolve, normalize } from 'path';
import { InvalidPathError } from '../errors.js';

export function validateCachePath(cachePath: string): string {
  const normalized = normalize(cachePath);

  // Check for path traversal segments
  const segments = normalized.split(/[/\\]/);
  if (segments.includes('..')) {
    throw new InvalidPathError(cachePath);
  }

  return resolve(normalized);
}
