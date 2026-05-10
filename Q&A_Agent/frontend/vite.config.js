import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    fs: {
      strict: false,
      // Needed when this project is started via SUBST drive (Q:) to avoid
      // Vite rejecting real-path C: module resolutions as outside root.
      allow: [
        'C:/pp/GitHub/AgenticAI-Usecases/Q&A_Agent/frontend',
        'Q:/frontend',
      ],
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
