import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // 루트 .env의 VITE_API_URL을 읽는다 (.env.example 참조)
  envDir: '..',
  server: {
    port: 5173,
    strictPort: true,
  },
})
