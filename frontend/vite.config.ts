import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // REST API: Spring Boot 백엔드로 프록시
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      // WebSocket: AI 서버(FastAPI)로 프록시. ws:true 옵션이 핵심.
      // 운영 환경에서는 nginx 가 동일한 경로(/ws/*)로 ai-jipchak:8000 으로 프록시한다.
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
