import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  // Chemins relatifs : l'app doit marcher servie depuis n'importe quel sous-chemin
  // (GitHub Pages /chess-local/) comme depuis la racine (dev, preview).
  base: './',
  // Horodatage de build, affiché dans l'app pour vérifier qu'on est à jour.
  define: { __BUILD__: JSON.stringify(new Date().toISOString().slice(0, 16).replace('T', ' ')) },
  // Couche native de l'app iOS (docs/ios-app.md) : les chunks de @capacitor/* et du pilote haptique,
  // chargés seulement par l'app native, sont préfixés `native-` et exclus du précache : la PWA ne
  // les télécharge jamais. Simple renommage : le découpage, donc le bundle web, reste celui par défaut.
  build: {
    rolldownOptions: {
      output: {
        chunkFileNames: (chunk) =>
          chunk.moduleIds.some((id) => /@capacitor[\\/]|nativeHaptics/.test(id)) ? 'assets/native-[name]-[hash].js' : 'assets/[name]-[hash].js',
      },
    },
  },
  // Dev : pré-optimisés d'emblée, sinon leur découverte au premier import() natif fait recharger la page.
  optimizeDeps: { include: ['@capacitor/core', '@capacitor/haptics'] },
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      // Précache TOUT : l'app doit se lancer sans aucun réseau après la
      // première visite (moteur WASM 7 Mo + 120k puzzles 16 Mo + sons inclus).
      workbox: {
        globPatterns: ['**/*.{js,css,html,png,mp3,wasm,json,svg}'],
        globIgnores: ['**/assets/native-*.js'],
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
