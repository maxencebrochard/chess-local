import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Stockage persistant : sans cette demande, iOS/Safari peut purger IndexedDB
// (classements, parties, progrès) après une période d'inactivité.
if (navigator.storage?.persist) {
  void navigator.storage.persist()
}

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
