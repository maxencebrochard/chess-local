// Pages chargées à la demande (découpage par route de App.tsx), sans chunk périmée après un
// déploiement.
//
// Au premier lancement qui suit un déploiement, l'ancien service worker sert l'ancien index ; le
// nouveau s'installe, prend la main (`skipWaiting` + `clientsClaim` de `registerType: 'autoUpdate'`)
// et retire de son précache les chunks de l'ancien build, que GitHub Pages ne sert plus non plus
// (la branche gh-pages est réécrite). Une page déjà chargée continue de marcher ; en ouvrir une
// nouvelle demanderait une chunk disparue. Deux protections :
// - dès qu'un nouveau service worker a pris la main, la prochaine chunk à charger recharge l'app au
//   lieu d'importer : l'URL est déjà celle de la page visée, et le state de navigation
//   (history.state) survit au rechargement ;
// - un import qui échoue quand même (réseau, déploiement sans service worker) recharge une fois ;
//   s'il échoue encore, l'erreur remonte à la frontière d'erreur de la coquille (« Recharger »).
import { lazy, type ComponentType } from 'react'

// Rechargement déjà tenté pour une chunk introuvable : jamais de boucle de rechargements.
const RELOAD_KEY = 'chess-local-chunk-reload'

// Vrai quand le service worker qui contrôle la page n'est plus celui qui l'a chargée.
let staleBuild = false
if ('serviceWorker' in navigator) {
  let controller = navigator.serviceWorker.controller
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    // Première installation (aucun contrôleur avant) : même build, rien de périmé.
    if (controller) staleBuild = true
    controller = navigator.serviceWorker.controller
  })
}

function reloadOnce(): boolean {
  // Hors ligne sans service worker, un rechargement afficherait la page d'erreur du navigateur.
  if (!navigator.onLine && !navigator.serviceWorker?.controller) return false
  try {
    if (sessionStorage.getItem(RELOAD_KEY)) return false
    sessionStorage.setItem(RELOAD_KEY, '1')
  } catch {
    return false // stockage indisponible : pas de garde, donc pas de rechargement automatique
  }
  location.reload()
  return true
}

// Promesse jamais résolue : Suspense (ou l'appelant) attend le rechargement.
function never<T>(): Promise<T> {
  return new Promise<T>(() => {})
}

/** Import dynamique protégé : à utiliser pour toute chunk chargée à la demande. */
export function loadChunk<T>(load: () => Promise<T>): Promise<T> {
  if (staleBuild) {
    location.reload()
    return never()
  }
  return load().then(
    (mod) => {
      try {
        sessionStorage.removeItem(RELOAD_KEY)
      } catch {
        // stockage indisponible : rien à nettoyer
      }
      return mod
    },
    (error: unknown) => (reloadOnce() ? never<T>() : Promise.reject(error)),
  )
}

// Même signature que `React.lazy`, dont le `any` est celui des props de la page chargée.
export function lazyPage<T extends ComponentType<any>>(load: () => Promise<{ default: T }>) {
  return lazy<T>(() => loadChunk(load))
}
