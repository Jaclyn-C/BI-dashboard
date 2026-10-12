import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// DESIGN-20261012-01 §2.3：dev 代理 /api → 后端 8000（生产同源，无需代理）
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
