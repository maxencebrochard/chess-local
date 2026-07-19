import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Stockage persistant : sans cette demande, iOS/Safari peut purger IndexedDB
// (classements, parties, progrès) après une période d'inactivité.
if (navigator.storage?.persist) {
  void navigator.storage.persist()
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
