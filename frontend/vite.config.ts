import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [react(), VitePWA({
    registerType: 'autoUpdate',
    manifest: {
      name: 'SALAR Personal Intelligence', short_name: 'SALAR',
      description: 'Your private intelligence, available everywhere.',
      theme_color: '#f5d8cb', background_color: '#f5d8cb', display: 'standalone',
      icons: [{ src: '/icon-192.png', sizes: '192x192', type: 'image/png' }, { src: '/icon-512.png', sizes: '512x512', type: 'image/png' }]
    }
  })],
  server: { port: 4173 },
  build: { target: 'es2022' }
})
