import { createHash } from 'crypto';

/**
 * Return the 16-char SHA-256 prefix Cachetta uses to derive cache file names.
 *
 * Matches the digest the auto-keyed path embeds when a wrapped function is
 * called with the same args. Useful for building custom `path:` callables or
 * external indexes that line up with cachetta's own keying.
 *
 * @example
 * ```ts
 * import { hash } from 'cachetta';
 *
 * hash('user-123', { page: 1 });   // 16-char hex string
 * ```
 *
 * Note: the Python `hash` export uses a different stringifier (and includes
 * kwargs), so the same logical input produces different digests across
 * languages. Do not rely on cross-language equality.
 */
export function hash(...args: unknown[]): string {
  return createHash('sha256')
    .update(JSON.stringify(args))
    .digest('hex')
    .slice(0, 16);
}
