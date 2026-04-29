import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';
import { defineConfig } from 'vite';
import dts from 'vite-plugin-dts';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export default defineConfig({
  build: {
    lib: {
      entry: {
        index: resolve(__dirname, 'src/index.ts'),
      },
      formats: ['es'],
    },
    rollupOptions: {
      external: ['fs', 'path', 'util', 'crypto', 'v8'],
    },
  },
  plugins: [
    dts({
      entryRoot: 'src',
      exclude: ['**/*.test.ts'],
      afterDiagnostic: (diagnostics) => {
        if (diagnostics.length) {
          throw new Error("type error");
        }
      },
    }),
  ],
  // Ensure TypeScript errors cause build to fail
  esbuild: {
    target: 'es2022',
  },
});
