// Partie de Jouer en cours, mémorisée pour survivre à un changement d'onglet, au retour arrière iOS
// et à une PWA tuée en arrière-plan (sessionStorage ne survit pas à cette dernière). Transitoire :
// hors sauvegarde, expirée après 24 h, pendules figées pendant l'absence.
// Sans chess.js : l'accueil (bundle initial) lit la même reprise que Play.tsx, qui rejoue ensuite
// les coups à son montage et écarte une partie illisible ou terminée.
import { PLAY_MODES, type PlayMode } from '../store/settings'
import { PLAY_GAME_KEY } from './timeControls'

export const GAME_TTL_MS = 24 * 3600_000

export interface StoredGame {
  mode: PlayMode
  botId: string
  // Nom affiché par l'accueil, sans charger la liste des bots dans le bundle initial. Absent des
  // instantanés écrits avant son ajout : « Partie contre un bot ».
  botName?: string
  playerColor: 'w' | 'b'
  tcLabel: string
  sans: string[]
  clocks: { w: number; b: number }
  unrated: boolean
  lastWhiteCp: number
  // Mat annoncé par la dernière éval (côté blanc, en coups). Absent des instantanés écrits avant
  // son ajout : la reprise recalcule de toute façon l'éval.
  lastWhiteMate?: number | null
  // Alerte menace : demi-coups de la dernière position traitée (question répondue ou sans menace).
  // Une question en attente est reposée à la reprise, une question répondue jamais.
  threatPly?: number
  savedAt: number
}

export function readStoredGame(now = Date.now()): StoredGame | null {
  try {
    const raw = localStorage.getItem(PLAY_GAME_KEY)
    if (!raw) return null
    const g = JSON.parse(raw) as StoredGame
    if (!g || !Array.isArray(g.sans) || typeof g.savedAt !== 'number' || now - g.savedAt > GAME_TTL_MS) return null
    if (!PLAY_MODES.some((m) => m === g.mode)) return null
    return g
  } catch {
    return null
  }
}

export function writeStoredGame(g: StoredGame | null) {
  try {
    if (g) localStorage.setItem(PLAY_GAME_KEY, JSON.stringify(g))
    else localStorage.removeItem(PLAY_GAME_KEY)
  } catch {
    // stockage indisponible (navigation privée) : la partie vit seulement en mémoire
  }
}
