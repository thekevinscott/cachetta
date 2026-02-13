export class CachettaError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CachettaError';
  }
}

export class InvalidPathError extends CachettaError {
  constructor(cachePath: string) {
    super(`Invalid cache path (path traversal detected): ${cachePath}`);
    this.name = 'InvalidPathError';
  }
}

export class UnsupportedFormatError extends CachettaError {
  constructor(extension: string) {
    super(`Unsupported cache format: ${extension}`);
    this.name = 'UnsupportedFormatError';
  }
}
