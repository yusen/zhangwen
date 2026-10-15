import { defineConfig } from 'vitest/config';
export default defineConfig({ test: { include: ['apps/web/tests/**/*.test.ts'], environment: 'node' } });
