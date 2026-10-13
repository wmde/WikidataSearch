import { defineConfig } from 'vite'

export default defineConfig({
  base: '/',
  server: {
    host: '0.0.0.0',
    watch: { usePolling: true },
    proxy: {
      '/feedback': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/item': 'http://127.0.0.1:8000',
      '/languages': 'http://127.0.0.1:8000',
      '/property': 'http://127.0.0.1:8000',
    },
  },
})
