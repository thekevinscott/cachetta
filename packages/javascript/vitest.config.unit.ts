import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    testTimeout: 5000,
    include: ['src/**/*.test.ts'],
    exclude: ['tests/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      all: true,
      include: ['src/**/*.ts'],
      exclude: ['src/**/*.test.ts', 'src/index.ts', 'src/types.ts'],
      reporter: ['text', 'cobertura'],
      reportsDirectory: './coverage',
      thresholds: { lines: 81 },
    },
  },
});
