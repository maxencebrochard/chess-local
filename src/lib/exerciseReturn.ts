// Aller-retour vers l'analyseur pour les écrans d'exercice qui n'ont pas déjà leur propre séance
// persistée (comme `learn-session-v1` d'Apprendre) : drill d'ouverture, sorties du répertoire,
// bilans de séries (Puzzle Rush, Mats éclair, Finales au chrono), série de visualisation, leçon.
// Même mécanisme que les séances : l'écran écrit son état juste avant `navigate('/analyse', {
// state: { ..., returnTo } })`, et ne le relit qu'au retour (`location.state.restore`).
// Une seule clé sessionStorage pour tous ces écrans, effacée par importBackup et resetApp
// (SESSION_KEYS de backup.ts) ; `screen` empêche un écran de lire l'état d'un autre.
export const EXERCISE_RETURN_KEY = 'exercise-return-v1'

interface Stored {
  screen: string
  data: unknown
}

export function stashExercise(screen: string, data: unknown) {
  try {
    sessionStorage.setItem(EXERCISE_RETURN_KEY, JSON.stringify({ screen, data } satisfies Stored))
  } catch {}
}

// Lecture sans effacement, au rendu (StrictMode rejoue les initialiseurs) ; l'écran efface ensuite
// la clé dans l'effet de son montage (`clearExercise`), pour qu'un autre retour vers lui (lien
// d'analyse sans reprise, retour d'une autre page) ne reprenne jamais un état périmé.
export function readExercise<T>(screen: string): T | null {
  try {
    const raw = sessionStorage.getItem(EXERCISE_RETURN_KEY)
    const s = raw ? (JSON.parse(raw) as Stored) : null
    return s && s.screen === screen && s.data !== null && typeof s.data === 'object' ? (s.data as T) : null
  } catch {
    return null
  }
}

export function clearExercise() {
  try {
    sessionStorage.removeItem(EXERCISE_RETURN_KEY)
  } catch {}
}

// Retour de l'analyseur : le bouton « Retour » navigue avec `state: { restore: true }`.
export function isRestore(state: unknown): boolean {
  return !!(state as { restore?: boolean } | null)?.restore
}
