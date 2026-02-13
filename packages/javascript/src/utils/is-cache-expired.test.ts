import { describe, test, expect } from 'vitest';
import { isCacheExpired } from './is-cache-expired.js';

describe('isCacheExpired', () => {
  const now = Date.now();
  const oneHour = 60 * 60 * 1000; // 1 hour in milliseconds
  const oneDay = 24 * 60 * 60 * 1000; // 1 day in milliseconds

  test('should return false for non-expired cache', () => {
    const cacheTime = now - (oneHour / 2); // 30 minutes ago
    const cacheLength = oneHour; // 1 hour cache

    expect(isCacheExpired(cacheTime, now, cacheLength)).toBe(false);
  });

  test('should return true for expired cache', () => {
    const cacheTime = now - (oneHour * 2); // 2 hours ago
    const cacheLength = oneHour; // 1 hour cache

    expect(isCacheExpired(cacheTime, now, cacheLength)).toBe(true);
  });

  test('should return true for exactly expired cache', () => {
    const cacheTime = now - oneHour; // Exactly 1 hour ago
    const cacheLength = oneHour; // 1 hour cache

    expect(isCacheExpired(cacheTime, now, cacheLength)).toBe(true);
  });

  test('should return false for cache that just expired', () => {
    const cacheTime = now - (oneHour - 1000); // 59 minutes 59 seconds ago
    const cacheLength = oneHour; // 1 hour cache

    expect(isCacheExpired(cacheTime, now, cacheLength)).toBe(false);
  });

  test('should handle very short cache lengths', () => {
    const cacheTime = now - 1000; // 1 second ago
    const cacheLength = 500; // 0.5 seconds cache

    expect(isCacheExpired(cacheTime, now, cacheLength)).toBe(true);
  });

  test('should handle very long cache lengths', () => {
    const cacheTime = now - (oneDay * 30); // 30 days ago
    const cacheLength = oneDay * 365; // 1 year cache

    expect(isCacheExpired(cacheTime, now, cacheLength)).toBe(false);
  });

  test('should handle zero cache length', () => {
    const cacheTime = now - 1000; // 1 second ago
    const cacheLength = 0; // No cache

    expect(isCacheExpired(cacheTime, now, cacheLength)).toBe(true);
  });

  test('should handle negative cache length', () => {
    const cacheTime = now - 1000; // 1 second ago
    const cacheLength = -1000; // Negative cache (should always be expired)

    expect(isCacheExpired(cacheTime, now, cacheLength)).toBe(true);
  });

  test('should throw error when cache time is in the future', () => {
    const cacheTime = now + oneHour; // 1 hour in the future
    const cacheLength = oneHour;

    expect(() => isCacheExpired(cacheTime, now, cacheLength)).toThrow(
      'Invalid arguments, cache time'
    );
  });

  test('should handle current time cache', () => {
    const cacheTime = now; // Current time
    const cacheLength = oneHour; // 1 hour cache

    expect(isCacheExpired(cacheTime, now, cacheLength)).toBe(false);
  });

  test('should handle very old cache', () => {
    const cacheTime = now - (oneDay * 1000); // 1000 days ago
    const cacheLength = oneDay; // 1 day cache

    expect(isCacheExpired(cacheTime, now, cacheLength)).toBe(true);
  });

  test('should throw error when cache time is ahead of current time', () => {
    const futureTime = Date.now() + 1000; // 1 second in the future
    const currentTime = Date.now();
    const cacheLength = 5000; // 5 seconds

    expect(() => isCacheExpired(futureTime, currentTime, cacheLength)).toThrow();
  });
}); 
