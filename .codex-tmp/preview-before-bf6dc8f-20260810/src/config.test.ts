// @vitest-environment node

import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import tsconfig from '../tsconfig.json';
import viteConfig from '../vite.config';

describe('preview configuration', () => {
  it('refuses to fall back to a different development port', () => {
    expect(viteConfig.server).toMatchObject({
      host: '127.0.0.1',
      port: 4174,
      strictPort: true,
    });
  });

  it('maps the source alias consistently for Vite and TypeScript', () => {
    expect(viteConfig.resolve?.alias).toMatchObject({
      '@': resolve(process.cwd(), 'src'),
    });
    expect(tsconfig.compilerOptions).toMatchObject({
      paths: {
        '@/*': ['./src/*'],
      },
    });
  });
});
