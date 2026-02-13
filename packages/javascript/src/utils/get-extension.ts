import { PathLike } from 'fs';
import { CachettaError } from '../errors.js';

export function getExtension(cachePath: string | PathLike): string {
  const pathStr = String(cachePath);
  const parts = pathStr.split('/').pop()?.split('.');

  if (!parts || parts.length === 1 || parts[parts.length - 1] === '') {
    throw new CachettaError(`Missing file extension: ${cachePath}`);
  }

  return parts[parts.length - 1];
}
