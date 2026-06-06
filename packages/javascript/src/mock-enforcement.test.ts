import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'fs';
import { basename, dirname, extname, join, relative, resolve } from 'path';
import { fileURLToPath } from 'url';
import ts from 'typescript';

// A unit test should exercise one module in isolation: every *other*
// first-party module it pulls in is a collaborator that must be mocked, so the
// test can't silently lean on a real implementation. This check scans the unit
// suite and fails if any cross-module import is left as the real thing.
//
// An import is allowed when it is one of:
//   1. the module under test (colocated `foo.test.ts` ↔ `foo.ts`);
//   2. a pure value module (constants, error classes, type declarations) —
//      there is nothing behavioral to mock;
//   3. mocked via `vi.mock('<specifier>')`;
//   4. waived with an inline `// mock-enforce-ignore: <reason>` comment, which
//      records in-tree why using the real collaborator is intentional.
//
// The scan is a cheap static AST pass, so it lives in the unit suite rather
// than a separate CI job.

const SRC_DIR = dirname(fileURLToPath(import.meta.url));
const SELF = basename(fileURLToPath(import.meta.url));

const PURE_VALUE_MODULES = new Set(['constants', 'errors', 'types']);

const WAIVER = /mock-enforce-ignore:\s*\S/;

function findTestFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...findTestFiles(full));
    } else if (entry.name.endsWith('.test.ts') && entry.name !== SELF) {
      out.push(full);
    }
  }
  return out;
}

function isTypeOnlyImport(decl: ts.ImportDeclaration): boolean {
  const clause = decl.importClause;
  if (!clause) return false; // side-effect import: real module executes
  if (clause.isTypeOnly) return true;
  // `import { type A, type B } from '...'` with no value binding.
  const bindings = clause.namedBindings;
  if (!clause.name && bindings && ts.isNamedImports(bindings)) {
    return bindings.elements.length > 0 && bindings.elements.every((e) => e.isTypeOnly);
  }
  return false;
}

function analyze(file: string): string[] {
  const text = readFileSync(file, 'utf8');
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
  const lines = text.split('\n');

  const underTestPath = resolve(dirname(file), basename(file).replace(/\.test\.ts$/, '.ts'));

  const mocked = new Set<string>();
  const imports: { specifier: string; line: number }[] = [];

  sf.forEachChild((node) => {
    if (ts.isExpressionStatement(node) && ts.isCallExpression(node.expression)) {
      const callee = node.expression.expression;
      if (
        ts.isPropertyAccessExpression(callee) &&
        ts.isIdentifier(callee.expression) &&
        callee.expression.text === 'vi' &&
        callee.name.text === 'mock'
      ) {
        const arg = node.expression.arguments[0];
        if (arg && ts.isStringLiteralLike(arg)) {
          mocked.add(arg.text);
        }
      }
    }
    if (ts.isImportDeclaration(node)) {
      if (isTypeOnlyImport(node)) return;
      const spec = node.moduleSpecifier;
      if (!ts.isStringLiteralLike(spec) || !spec.text.startsWith('.')) return;
      const line = sf.getLineAndCharacterOfPosition(node.getStart(sf)).line;
      imports.push({ specifier: spec.text, line });
    }
  });

  const problems: string[] = [];
  for (const imp of imports) {
    const resolved = resolve(dirname(file), imp.specifier).replace(/\.js$/, '.ts');
    if (resolved === underTestPath) continue;
    if (PURE_VALUE_MODULES.has(basename(resolved, extname(resolved)))) continue;
    if (mocked.has(imp.specifier)) continue;
    const onLine = lines[imp.line] ?? '';
    const aboveLine = lines[imp.line - 1] ?? '';
    if (WAIVER.test(onLine) || WAIVER.test(aboveLine)) continue;
    problems.push(
      `  ${relative(SRC_DIR, file)}:${imp.line + 1} imports '${imp.specifier}' — real cross-module ` +
        `collaborator. Mock it with vi.mock('${imp.specifier}'), or add a ` +
        `'// mock-enforce-ignore: <reason>' comment if using the real module is intentional.`,
    );
  }
  return problems;
}

describe('mock enforcement', () => {
  it('every cross-module collaborator in a unit test is mocked, allowlisted, or waived', () => {
    const problems = findTestFiles(SRC_DIR).flatMap(analyze);
    expect(
      problems.join('\n'),
      problems.length ? `Un-mocked collaborators found in unit tests:\n${problems.join('\n')}` : undefined,
    ).toBe('');
  });
});
