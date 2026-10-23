// Séance du jour : séance en cours (sessionStorage) et séances terminées (`learnSessions`, domaine
// `seance`), sans les banques ni le calcul du plan de seanceRun.ts. L'accueil lit la reprise et la
// série de jours d'ici : il n'a pas à charger, avant son premier affichage, les ouvertures, les
// attaques, Insights et la révision que tire seanceRun.ts.
import { db } from './db'
import type { ReviewPayload } from './revision'
import type { BlockKind, StepResult } from './seance'
import type { PuzzleData } from '../components/PuzzlePlayer'

// Une étape de la séance, sérialisable (sessionStorage) : les positions d'attaque, finales et
// variantes se résolvent au rendu depuis les banques bundlées.
export type Step =
  | { kind: 'revision'; payload: ReviewPayload }
  | { kind: 'puzzles'; puzzle: PuzzleData }
  | { kind: 'opening'; color: 'w' | 'b'; uci: string; label: string }
  | { kind: 'endgame'; id: string }
  | { kind: 'attack'; id: string }

export const SEANCE_DOMAIN = 'seance'

// ---------- Séance en cours (sessionStorage) ----------

// Clé effacée par importBackup et resetApp (SESSION_KEYS de backup.ts), comme celles d'Apprendre
// et de la révision.
export const SEANCE_SESSION_KEY = 'seance-session-v1'
// Une séance se reprend dans les 6 heures qui suivent son départ, même passé minuit.
export const RESUME_MS = 6 * 3_600_000

export type StepPhase = 'play' | 'success' | 'fail'

export interface SeanceResult extends StepResult {
  note: string | null // « Revient dans 3 jours », « Classement 1512 (+8) »...
  rating?: number // puzzle classé : classement après ce puzzle
}

export interface StoredSeance {
  startedAt: number
  steps: Step[]
  idx: number
  phase: StepPhase
  results: SeanceResult[]
  stepStartedAt: number
  opened: number[] // étapes attaque et finale déjà ouvertes : leur partie se reprend telle quelle
  ratingStart: number
}

export function readStoredSeance(now = Date.now()): StoredSeance | null {
  try {
    const raw = sessionStorage.getItem(SEANCE_SESSION_KEY)
    const s = raw ? (JSON.parse(raw) as StoredSeance) : null
    if (!s || typeof s.startedAt !== 'number' || now - s.startedAt > RESUME_MS || now < s.startedAt) return null
    if (!Array.isArray(s.steps) || !s.steps.length || !Array.isArray(s.results) || !Array.isArray(s.opened)) return null
    if (!Number.isInteger(s.idx) || s.idx < 0 || s.idx >= s.steps.length) return null
    return s
  } catch {
    return null
  }
}

export function writeStoredSeance(s: StoredSeance | null) {
  try {
    if (s) sessionStorage.setItem(SEANCE_SESSION_KEY, JSON.stringify(s))
    else sessionStorage.removeItem(SEANCE_SESSION_KEY)
  } catch {}
}

// ---------- Séances terminées (learnSessions, domaine `seance`) ----------

// Une ligne par séance menée jusqu'au bilan : itemId = types des blocs joints par « + »
// (`revision+puzzles+attack`), score = étapes réussies. Aucun Elo.
export async function recordSeance(kinds: BlockKind[], ok: number): Promise<void> {
  const blocks = kinds.filter((k, i) => k !== kinds[i - 1])
  await db.learnSessions.add({ date: Date.now(), domain: SEANCE_DOMAIN, itemId: blocks.join('+'), success: 1, score: ok, ratingAfter: null })
}

// Dates des séances terminées, pour la série de jours (requête indexée, jamais puzzles.json).
export async function seanceDates(): Promise<number[]> {
  return (await db.learnSessions.where('domain').equals(SEANCE_DOMAIN).toArray()).map((r) => r.date)
}
