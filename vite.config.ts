import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  // Chemins relatifs : l'app doit marcher servie depuis n'importe quel sous-chemin
  // (GitHub Pages /chess-local/) comme depuis la racine (dev, preview).
  base: './',
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      // Précache TOUT : l'app doit se lancer sans aucun réseau après la
      // première visite (moteur WASM 7 Mo + 120k puzzles 16 Mo + sons inclus).
      workbox: {
        globPatterns: ['**/*.{js,css,html,png,mp3,wasm,json,svg}'],
        maximumFileSizeToCacheInBytes: 25 * 1024 * 1024,
        navigateFallback: 'index.html',
      },
      manifest: {
        name: 'ChessLocal',
        short_name: 'ChessLocal',
        description: 'Échecs 100 % local : bots, puzzles, analyse, coach.',
        lang: 'fr',
        display: 'standalone',
        background_color: '#262421',
        theme_color: '#262421',
        start_url: '.',
        scope: '.',
        icons: [
          { src: 'pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'pwa-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
    }),
  ],
})
