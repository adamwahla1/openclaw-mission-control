import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: parseInt(process.env.APP_PORT || process.env.VITE_PORT || '3000'),
    strictPort: true,
    proxy: {
      '/api': {
        target: `http://localhost:${parseInt(process.env.APP_PORT || process.env.VITE_PORT || '3000') + 100}`,
        changeOrigin: true,
      },
      '/events': {
        target: `http://localhost:${parseInt(process.env.APP_PORT || process.env.VITE_PORT || '3000') + 100}`,
        changeOrigin: true,
      },
    },
  },
})
