import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
  },
  server: {
    // Match production Caddy: /token, /menu, /health → token server
    proxy: {
      '/token': 'http://127.0.0.1:8001',
      '/menu': 'http://127.0.0.1:8001',
      '/health': 'http://127.0.0.1:8001',
    },
  },
})
