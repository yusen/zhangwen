import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: 'apps/web',
  plugins: [react()],
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy: { '/api': { target: 'http://127.0.0.1:3080', changeOrigin: true } } },
  build: { outDir: '../../dist', emptyOutDir: true, rollupOptions: { output: { manualChunks: { editor: ['codemirror', '@codemirror/lang-python', '@codemirror/state', '@codemirror/view'] } } } },
});
