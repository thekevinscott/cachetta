import type { Logger, LogLevel } from '../types.js';

let logLevel: LogLevel = 'warn';
const logLevels = ['error', 'warn', 'info', 'debug'];
const isAcceptableLogLevel = (level: LogLevel) => {
  const currentIndex = logLevels.indexOf(logLevel);
  const messageIndex = logLevels.indexOf(level);
  return messageIndex <= currentIndex;
};
const getConsoleFn = (level: LogLevel) => {
  switch (level) {
    case 'debug':
      return console.debug;
    case 'info':
      return console.info;
    case 'warn':
      return console.warn;
    case 'error':
      return console.error;
  }
};
const logAtLevel = (level: LogLevel) => (...messages: unknown[]) => {
  if (isAcceptableLogLevel(level)) {
    const fn = getConsoleFn(level);
    if (fn) {
      fn(`[Cachetta]`, ...messages);
    }
  }
};

// Simple logger instance, matching the Python implementation
export let logger: Logger = {
  debug: logAtLevel('debug'),
  info: logAtLevel('info'),
  warn: logAtLevel('warn'),
  error: logAtLevel('error'),
};

// Configuration functions for the README examples
export function setLogLevel(level: LogLevel) {
  logLevel = level;
}

export function setLogger(customLogger: Logger) {
  logger = customLogger;
}
