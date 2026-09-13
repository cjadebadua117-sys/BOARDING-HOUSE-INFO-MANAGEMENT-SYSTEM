import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  build: {
    outDir: 'core/static/core/dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: './core/static/core/css/premium.css',
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});