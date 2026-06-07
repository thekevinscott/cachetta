import eslint from '@eslint/js';
import tseslint from 'typescript-eslint';
import mockCollaborators from './eslint-rules/mock-collaborators.js';

export default tseslint.config(
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    ignores: ['dist/', 'tests/', '*.config.*', 'eslint-rules/'],
  },
  {
    files: ['src/**/*.ts'],
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
      'no-empty': ['error', { allowEmptyCatch: true }],
    },
  },
  {
    files: ['src/**/*.test.ts'],
    plugins: { 'mock-isolation': { rules: { collaborators: mockCollaborators } } },
    rules: { 'mock-isolation/collaborators': 'error' },
  },
);
