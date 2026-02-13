import { describe, it, expect } from 'vitest';
import {
  CachettaError,
  InvalidPathError,
  UnsupportedFormatError,
} from './errors.js';

describe('errors', () => {
  it('CachettaError is an Error', () => {
    const err = new CachettaError('test');
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(CachettaError);
    expect(err.name).toBe('CachettaError');
    expect(err.message).toBe('test');
  });

  it('InvalidPathError', () => {
    const err = new InvalidPathError('../etc/passwd');
    expect(err).toBeInstanceOf(CachettaError);
    expect(err.name).toBe('InvalidPathError');
    expect(err.message).toContain('path traversal');
  });

  it('UnsupportedFormatError', () => {
    const err = new UnsupportedFormatError('xml');
    expect(err).toBeInstanceOf(CachettaError);
    expect(err.name).toBe('UnsupportedFormatError');
    expect(err.message).toContain('xml');
  });
});
