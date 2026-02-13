import { describe, it, expect, vi } from 'vitest';
import { setLogLevel, setLogger, logger } from './logger.js';

describe('logger', () => {
  describe('logger object', () => {
    it('should have debug, info, warn, error methods', () => {
      expect(typeof logger.debug).toBe('function');
      expect(typeof logger.info).toBe('function');
      expect(typeof logger.warn).toBe('function');
      expect(typeof logger.error).toBe('function');
    });
  });

  describe('setLogLevel', () => {
    it('should accept debug level', () => {
      expect(() => setLogLevel('debug')).not.toThrow();
    });

    it('should accept info level', () => {
      expect(() => setLogLevel('info')).not.toThrow();
    });

    it('should accept warn level', () => {
      expect(() => setLogLevel('warn')).not.toThrow();
    });

    it('should accept error level', () => {
      expect(() => setLogLevel('error')).not.toThrow();
    });
  });

  describe('setLogger', () => {
    it('should accept a custom logger and route calls to it', () => {
      const customLogger = {
        debug: vi.fn(),
        info: vi.fn(),
        warn: vi.fn(),
        error: vi.fn(),
      };
      setLogger(customLogger);

      // After setLogger, the module-level logger is replaced.
      // ESM live bindings mean our imported `logger` should reflect the change.
      logger.warn('test warn');
      logger.error('test error');

      expect(customLogger.warn).toHaveBeenCalledWith('test warn');
      expect(customLogger.error).toHaveBeenCalledWith('test error');
    });

    it('should accept a logger with no-op functions', () => {
      const noopLogger = {
        debug: () => {},
        info: () => {},
        warn: () => {},
        error: () => {},
      };
      expect(() => setLogger(noopLogger)).not.toThrow();
    });
  });
});
