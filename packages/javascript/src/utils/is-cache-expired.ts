export function isCacheExpired(cacheTime: number, now: number, cacheLength: number): boolean {
  if (cacheTime > now) {
    throw new Error(
      `Invalid arguments, cache time ${cacheTime} cannot be greater than now ${now}`
    );
  }

  // cacheLength is already in milliseconds (JavaScript standard)
  return (now - cacheTime) >= cacheLength;
} 
