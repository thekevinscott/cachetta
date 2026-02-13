import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    testTimeout: 5000,
    include: ['tests/**/*.test.ts'],
    exclude: ['src/**/*.test.ts'],
  },
});
