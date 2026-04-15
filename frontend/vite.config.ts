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
        assetFileNames: 'assets/[name].[ext]',
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          if (id.includes('@ant-design/icons')) return 'vendor-ant-icons';
          if (id.includes('@ant-design/cssinjs')) return 'vendor-antd-cssinjs';
          if (id.includes('@rc-component')) return 'vendor-rc-components';
          if (id.includes('antd') || id.includes('/rc-')) return 'vendor-antd-core';
          if (id.includes('seqviz') || id.includes('react-alignment-viewer')) return 'vendor-bio-viz';
          if (id.includes('lucide-react')) return 'vendor-lucide';
          if (id.includes('react') || id.includes('scheduler')) return 'vendor-react';
          if (id.includes('@babel/runtime')) return 'vendor-runtime';
          return 'vendor-misc';
        }
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
