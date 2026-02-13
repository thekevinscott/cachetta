import { describe, test, expect } from 'vitest';
import { getExtension } from './get-extension.js';
import { CachettaError } from '../errors.js';

describe('getExtension', () => {
  test('should return the extension of a simple file', () => {
    expect(getExtension('test.txt')).toBe('txt');
  });

  test('should return the extension of a file with multiple dots', () => {
    expect(getExtension('test.min.js')).toBe('js');
    expect(getExtension('config.prod.json')).toBe('json');
  });

  test('should return the extension of a file with path', () => {
    expect(getExtension('/path/to/file.json')).toBe('json');
    expect(getExtension('./cache/data.pkl')).toBe('pkl');
    expect(getExtension('../config/settings.yaml')).toBe('yaml');
  });

  test('should return the extension of a file with complex path', () => {
    expect(getExtension('/home/user/projects/cache/data.json')).toBe('json');
    expect(getExtension('C:\\Users\\username\\Documents\\file.txt')).toBe('txt');
  });

  test('should handle different file extensions', () => {
    expect(getExtension('data.json')).toBe('json');
    expect(getExtension('data.pkl')).toBe('pkl');
    expect(getExtension('data.yaml')).toBe('yaml');
    expect(getExtension('data.yml')).toBe('yml');
    expect(getExtension('data.xml')).toBe('xml');
    expect(getExtension('data.csv')).toBe('csv');
  });

  test('should throw CachettaError for file without extension', () => {
    expect(() => getExtension('file')).toThrow(CachettaError);
    expect(() => getExtension('/path/to/file')).toThrow(CachettaError);
    expect(() => getExtension('./cache/data')).toThrow(CachettaError);
  });

  test('should throw CachettaError for file ending with dot', () => {
    expect(() => getExtension('file.')).toThrow(CachettaError);
    expect(() => getExtension('/path/to/file.')).toThrow(CachettaError);
  });

  test('should handle PathLike objects', () => {
    const pathLike = new URL('file:///test.json');
    expect(getExtension(pathLike)).toBe('json');
  });

  test('should handle empty string', () => {
    expect(() => getExtension('')).toThrow(CachettaError);
  });
});
