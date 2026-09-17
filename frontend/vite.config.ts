import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// 开发期通过 Vite 代理把 /api 转发到 Django，保持与生产（Nginx 同域）一致的
// 同源会话与 CSRF 行为，不依赖跨域 Cookie。
const backendTarget = process.env.VITE_DEV_BACKEND ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: backendTarget, changeOrigin: false },
      '/admin': { target: backendTarget, changeOrigin: false },
      '/static': { target: backendTarget, changeOrigin: false },
      '/media': { target: backendTarget, changeOrigin: false },
      '/healthz': { target: backendTarget, changeOrigin: false },
      '/readyz': { target: backendTarget, changeOrigin: false },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks: {
          vue: ['vue', 'vue-router', 'pinia'],
          element: ['element-plus'],
          chart: ['echarts'],
        },
      },
    },
  },
})