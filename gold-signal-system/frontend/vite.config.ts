import crypto from 'node:crypto'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Polyfill webcrypto for Node 16 compatibility
if (!(crypto as any).getRandomValues && (crypto as any).webcrypto) {
  ;(crypto as any).getRandomValues = (crypto as any).webcrypto.getRandomValues.bind(
    (crypto as any).webcrypto
  )
}
if (!globalThis.crypto && (crypto as any).webcrypto) {
  ;(globalThis as any).crypto = (crypto as any).webcrypto
}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      // Proxy all /api requests to the FastAPI backend during development
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
