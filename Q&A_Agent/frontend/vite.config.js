import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Local backend URL — used by the dev-server proxy only.
// In production (Vercel), /api and /health are rewritten via vercel.json.
const BACKEND = process.env.VITE_BACKEND_URL || 'http://localhost:8000'

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
        target: BACKEND,
        changeOrigin: true,
      },
      '/health': {
        target: BACKEND,
        changeOrigin: true,
      },
    },
  },
})
