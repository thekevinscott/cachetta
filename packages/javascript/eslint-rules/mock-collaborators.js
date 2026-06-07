import path from 'node:path';

// A unit test (`foo.test.ts`) should exercise one module in isolation. Every
// other first-party module it imports is a collaborator that must be mocked,
// otherwise the test silently leans on a real implementation. This rule flags
// any cross-module import that is left as the real thing.
//
// An import is allowed when it is one of:
//   1. the module under test (colocated `foo.test.ts` <-> `foo.ts`);
//   2. a pure value module (constants, error classes, type declarations) --
//      there is nothing behavioral to mock;
//   3. mocked via `vi.mock('<specifier>')`.
//
// To intentionally use a real collaborator, disable the rule on the import with
// a reason, e.g.
//   // eslint-disable-next-line mock-isolation/collaborators -- <reason>

const PURE_VALUE_MODULES = new Set(['constants', 'errors', 'types']);

/** @type {import('eslint').Rule.RuleModule} */
export default {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Require unit tests to mock every cross-module collaborator (anything but the module under test or a pure value module).',
    },
    schema: [],
    messages: {
      unmocked:
        "Unit test imports real cross-module collaborator '{{specifier}}'. Mock it with vi.mock('{{specifier}}'), or add an eslint-disable comment with a reason if using the real module is intentional.",
    },
  },
  create(context) {
    const filename = context.filename ?? context.getFilename();
    if (!/\.test\.ts$/.test(filename)) return {};

    const dir = path.dirname(filename);
    const underTest = path.resolve(dir, path.basename(filename).replace(/\.test\.ts$/, '.ts'));

    /** @type {Set<string>} */
    const mocked = new Set();
    /** @type {{ node: import('estree').ImportDeclaration, specifier: string }[]} */
    const imports = [];

    return {
      CallExpression(node) {
        const callee = node.callee;
        if (
          callee.type === 'MemberExpression' &&
          callee.object.type === 'Identifier' &&
          callee.object.name === 'vi' &&
          callee.property.type === 'Identifier' &&
          callee.property.name === 'mock' &&
          node.arguments.length > 0 &&
          node.arguments[0].type === 'Literal' &&
          typeof node.arguments[0].value === 'string'
        ) {
          mocked.add(node.arguments[0].value);
        }
      },
      ImportDeclaration(node) {
        // Type-only imports are erased at runtime, so they execute no code.
        if (node.importKind === 'type') return;
        const specifier = node.source.value;
        if (typeof specifier !== 'string' || !specifier.startsWith('.')) return;
        // `import { type A, type B }` with no value binding is also type-only.
        const specs = node.specifiers;
        const allType =
          specs.length > 0 &&
          specs.every((s) => s.type === 'ImportSpecifier' && s.importKind === 'type');
        if (allType) return;
        imports.push({ node, specifier });
      },
      'Program:exit'() {
        for (const { node, specifier } of imports) {
          const resolved = path.resolve(dir, specifier).replace(/\.js$/, '.ts');
          if (resolved === underTest) continue;
          if (PURE_VALUE_MODULES.has(path.basename(resolved, path.extname(resolved)))) continue;
          if (mocked.has(specifier)) continue;
          context.report({ node, messageId: 'unmocked', data: { specifier } });
        }
      },
    };
  },
};
