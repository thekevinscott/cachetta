import { describe, it, expect, vi, afterEach } from 'vitest';
import { setLogLevel, setLogger, logger } from './logger.js';

describe('logger', () => {
  describe('getConsoleFn / logAtLevel', () => {
    afterEach(() => {
      // Restore default log level so other tests are unaffected
      setLogLevel('warn');
      vi.restoreAllMocks();
    });

    it('routes each level to the matching console method when enabled', () => {
      const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});
      const infoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      // debug is the most verbose level: everything should pass the filter
      setLogLevel('debug');

      logger.debug('d');
      logger.info('i');
      logger.warn('w');
      logger.error('e');

      expect(debugSpy).toHaveBeenCalledWith('[Cachetta]', 'd');
      expect(infoSpy).toHaveBeenCalledWith('[Cachetta]', 'i');
      expect(warnSpy).toHaveBeenCalledWith('[Cachetta]', 'w');
      expect(errorSpy).toHaveBeenCalledWith('[Cachetta]', 'e');
    });

    it('suppresses messages below the configured level', () => {
      const debugSpy = vi.spyOn(console, 'debug').mockImplementation(() => {});
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      // error is the least verbose level: debug should be filtered out
      setLogLevel('error');

      logger.debug('hidden');
      logger.error('shown');

      expect(debugSpy).not.toHaveBeenCalled();
      expect(errorSpy).toHaveBeenCalledWith('[Cachetta]', 'shown');
    });
  });

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
