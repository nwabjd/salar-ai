import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 4173 },
  build: { target: 'es2022' },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
})
