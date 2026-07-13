import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// API base is injected at build time via VITE_API_BASE (the Cloud Run backend
// URL). Defaults to the local backend for development.
export default defineConfig({
  plugins: [react()],
  server: { port: 5174 },
})
