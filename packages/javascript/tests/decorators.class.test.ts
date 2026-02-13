import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import path from 'path';
import { promises as fs } from 'fs';
import { Cachetta } from 'cachetta';

describe('decorators', () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(`cachetta-test-${Date.now()}-${Math.random().toString(36).substring(2, 15)}`);
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  describe('functions', () => {
    it('should decorate functions', async () => {
      const cache = new Cachetta({ path: path.join(tempDir, './async-cache.json') });

      let i = 0;
      function bar() {
        i++;
        return i;
      }
      const cachedBar = cache(bar);

      expect(await cachedBar()).toEqual(1);
      expect(await cachedBar()).toEqual(1);
    });

    it('should decorate functions with args', async () => {
      const cache = new Cachetta({ path: path.join(tempDir, './async-cache.json') });

      let i = 0;
      function bar() {
        i++;
        return i;
      }
      const cachedBar = cache(bar, { duration: 2000 });

      expect(await cachedBar()).toEqual(1);
      expect(await cachedBar()).toEqual(1);
    });

    it('should decorate functions with args including string path', async () => {
      const cache = new Cachetta({ path: path.join(tempDir, './root') });

      let i = 0;
      function bar() {
        i++;
        return i;
      }
      const cachedBar = cache(bar, { path: path.join(cache.path, 'foo', 'bar.json') });

      expect(await cachedBar()).toEqual(1);
      expect(await cachedBar()).toEqual(1);
    });

    it('should decorate functions with args including path function', async () => {
      const cache = new Cachetta({ path: path.join(tempDir, './root') });

      let i = 0;
      function bar(arg1: string, arg2: string) {
        i++;
        return i + arg1 + arg2;
      }
      const pathFn = (arg1: string, arg2: string) => path.join(tempDir, arg1, arg2, 'cache.json');
      const cachedBar = cache(bar, { path: pathFn });

      expect(await cachedBar('a', 'b')).toEqual(1 + 'a' + 'b');
      expect(await cachedBar('a', 'b')).toEqual(1 + 'a' + 'b');
      expect(await cachedBar('b', 'c')).toEqual(2 + 'b' + 'c');
    });
  });


  describe('classes', () => {
    it('should decorate a sync function using instance without args', async () => {
      const cache = new Cachetta({ path: path.join(tempDir, './sync-cache.json') });

      let i = 0;

      class Foo {
        @cache
        bar() {
          i++;
          return i;
        }
      }

      const foo = new Foo();
      expect(await foo.bar()).toEqual(1);
      expect(await foo.bar()).toEqual(1);
    });

    it('should decorate an async fn using instance without args', async () => {
      const cache = new Cachetta({ path: path.join(tempDir, './async-fn-cache.json') });

      let i = 0;

      class Foo {
        @cache
        async bar() {
          i++;
          return i;
        }
      }

      const foo = new Foo();
      expect(await foo.bar()).toEqual(1);
      expect(await foo.bar()).toEqual(1);
    });

    it('should decorate using instance with args', async () => {
      const cache = new Cachetta({ path: path.join(tempDir, './async-cache.json') });

      let i = 0;

      class Foo {
        @cache({ duration: 1000 })
        bar() {
          i++;
          return i;
        }
      }

      const foo = new Foo();
      expect(await foo.bar()).toEqual(1);
      expect(await foo.bar()).toEqual(1);
    });


  });
});

