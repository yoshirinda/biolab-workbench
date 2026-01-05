import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/static/react/',
  build: {
    rollupOptions: {
      output: {
        entryFileNames: 'assets/[name].js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name].[ext]'
      }
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: [
      '.devtunnels.ms',
      '.vscode-device.com',
      'localhost'
    ],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
      },
      '/sequence': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/blast': { target: 'http://127.0.0.1:5000', changeOrigin: true },
      '/phylo': { target: 'http://127.0.0.1:5000', changeOrigin: true },
    }
  }
})
