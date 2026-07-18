import { describe, it, expect } from 'vitest';
import {
  CachettaError,
} from './errors.js';

describe('errors', () => {
  it('CachettaError is an Error', () => {
    const err = new CachettaError('test');
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(CachettaError);
    expect(err.name).toBe('CachettaError');
    expect(err.message).toBe('test');
  });
});
