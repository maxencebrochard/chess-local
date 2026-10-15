import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { installAudioUnlock } from './lib/sounds'

// Stockage persistant : sans cette demande, iOS/Safari peut purger IndexedDB
// (classements, parties, progrès) après une période d'inactivité.
if (navigator.storage?.persist) {
  void navigator.storage.persist()
}

// Sons : déverrouillage de l'audio au premier geste, et après chaque retour d'arrière-plan.
installAudioUnlock()

// WebKit décide du geste précédent/suivant dès le contact au bord du viewport.
// Protéger tous les échiquiers, même pendant la réflexion du moteur et sur les diagrammes.
// Seuls les 25 px des bords sont concernés : le centre des diagrammes reste défilable
// et les boutons comme le contenu hors échiquier gardent leurs gestes natifs.
// Ne pas arrêter la propagation : react-chessboard utilise touchstart pour le drag
// et touchend pour le clic-clic, même quand l'action native est annulée.
document.addEventListener('touchstart', (event) => {
  if (!(event.target instanceof Element) || !event.target.closest('[data-board] [data-square]')) return
  const touch = event.touches[0]
  if (touch && (touch.clientX < 25 || touch.clientX > window.innerWidth - 25)) {
    event.preventDefault()
  }
}, { passive: false })

// Une erreur attrapée par la frontière d'erreur (App.tsx) reste journalisée, avec la pile des
// composants (où le rendu a planté), ET ré-émise sur `window` : les suites E2E ne détectent un
// écran blanc que par `pageerror`.
createRoot(document.getElementById('root')!, {
  onCaughtError: (error, info) => {
    console.error(error, info.componentStack)
    reportError(error)
  },
}).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
