// Couche native : app iOS Capacitor (voir docs/ios-app.md). Sur le web (PWA, GitHub Pages), tout
// est un no-op synchrone et rien de Capacitor n'est importé : le comportement de la PWA reste identique.
//
// Détection : la native-bridge de Capacitor pose `window.Capacitor.isNativePlatform` par un
// script injecté avant tout autre ; sa présence suffit, sans importer @capacitor/core.

type Bridge = { isNativePlatform?: () => boolean }

function detect(): boolean {
  try {
    return (window as Window & { Capacitor?: Bridge }).Capacitor?.isNativePlatform?.() === true
  } catch {
    return false
  }
}

export const isNative = detect()

// lift : saisie d'une pièce ; move : pose d'un coup ; capture : pose d'une prise ;
// refuse : coup refusé ; premove : prémouvement mis en file ; reply : coup de l'ordinateur ;
// reply-strong : coup de l'ordinateur qui prend, fait échec ou promeut. Intensités : docs/ios-app.md.
export type HapticKind = 'lift' | 'move' | 'capture' | 'refuse' | 'premove' | 'reply' | 'reply-strong'

type Driver = (kind: HapticKind) => Promise<void>
let driver: Driver | null = null

// Chargé dès le démarrage de l'app native, dans son propre chunk : le premier geste trouve le
// plugin prêt. Avant sa résolution, un retour est simplement perdu, jamais différé.
if (isNative) {
  void import('./nativeHaptics').then((m) => { driver = m.playHaptic }).catch((err: unknown) => {
    console.warn('Haptique indisponible :', err)
  })
}

// Déclenché pendant le geste ou à l'arrivée du coup de l'ordinateur, jamais attendu : un retour tardif ou en échec ne bloque rien.
export function haptic(kind: HapticKind) {
  if (!driver) return
  void driver(kind).catch(() => {})
}

// Carte « Tu jouais déjà sur la PWA ? » de l'accueil : refusée une fois pour toutes par « Non merci ».
// Effacée par la réinitialisation (APP_LOCAL_KEYS de backup.ts).
export const NATIVE_MIGRATION_KEY = 'chess-local-native-migration'

export function migrationDismissed(): boolean {
  try {
    return localStorage.getItem(NATIVE_MIGRATION_KEY) !== null
  } catch {
    return false
  }
}

export function dismissMigration() {
  try {
    localStorage.setItem(NATIVE_MIGRATION_KEY, String(Date.now()))
  } catch {
    // Stockage indisponible : la carte reviendra au prochain lancement, sans autre effet.
  }
}
