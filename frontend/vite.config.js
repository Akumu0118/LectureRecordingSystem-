import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// In dev, /api/* is proxied to Django so the browser sees one origin
// (no CORS surprises, and <audio> Range requests just work).
// Processing runs inside the upload request in the MVP, so allow long waits.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.BACKEND_URL || 'http://127.0.0.1:8000',
        timeout: 10 * 60 * 1000,
        proxyTimeout: 10 * 60 * 1000,
      },
    },
  },
})
