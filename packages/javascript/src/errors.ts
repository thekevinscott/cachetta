export class CachettaError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CachettaError';
  }
}
