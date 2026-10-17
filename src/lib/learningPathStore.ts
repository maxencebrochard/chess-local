// Progression du parcours d'apprentissage, sans nouvelle table : lue dans learnSessions (leçons
// `course`, finales `endgame`, séries et test de placement `path`), écrite dans le domaine `path`.
// Aucun Elo n'est modifié ici.
import type { PuzzleData } from '../components/PuzzlePlayer'
import { db } from './db'
import { LEVELS, PLACEMENT_ID, PLACEMENT_PER_LEVEL, type PathFacts, type PuzzleExercise } from './learningPath'
import { COURSE_DOMAIN } from './lessonCourse'

export const PATH_DOMAIN = 'path'
// Série en cours (puzzles, variantes, test de placement) : survit à un rechargement et à
// l'aller-retour vers l'analyseur. Effacée par l'import d'une sauvegarde et la réinitialisation.
export const PATH_SESSION_KEY = 'path-session-v1'

function validScore(score: unknown): number | null {
  return typeof score === 'number' && Number.isFinite(score) && score >= 0 ? score : null
}

export async function loadPathFacts(): Promise<PathFacts> {
  const rows = await db.learnSessions.where('domain').anyOf([COURSE_DOMAIN, 'endgame', PATH_DOMAIN]).toArray()
  const facts: PathFacts = { lessons: new Set(), endgames: new Set(), passed: new Set(), best: new Map(), placement: 0 }
  for (const r of rows) {
    if (r.domain === COURSE_DOMAIN) facts.lessons.add(r.itemId)
    else if (r.domain === 'endgame') {
      if (r.success) facts.endgames.add(r.itemId)
    } else if (r.itemId === PLACEMENT_ID) {
      facts.placement = Math.max(facts.placement, validScore(r.score) ?? 0)
    } else {
      if (r.success) facts.passed.add(r.itemId)
      const s = validScore(r.score)
      if (s !== null) facts.best.set(r.itemId, Math.max(facts.best.get(r.itemId) ?? 0, s))
    }
  }
  return facts
}

// Une ligne par série jouée jusqu'au bout : `score` = réussites, `success` = seuil atteint.
export async function recordPathRun(stepId: string, score: number, success: boolean): Promise<void> {
  await db.learnSessions.add({ date: Date.now(), domain: PATH_DOMAIN, itemId: stepId, success: success ? 1 : 0, ratingAfter: null, score })
}

export async function recordPlacement(levels: number): Promise<void> {
  await db.learnSessions.add({ date: Date.now(), domain: PATH_DOMAIN, itemId: PLACEMENT_ID, success: levels > 0 ? 1 : 0, ratingAfter: null, score: levels })
}

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

// `count` puzzles distincts de la bande, aux thèmes demandés (union) ; à défaut, les plus proches
// de la bande parmi ces thèmes (le contrôle des données garantit un vivier suffisant).
export function pickPuzzles(all: PuzzleData[], themes: string[] | null, [lo, hi]: [number, number], count: number): PuzzleData[] {
  const themed = themes ? all.filter((p) => themes.some((t) => p.themes.includes(t))) : all
  const inBand = themed.filter((p) => p.rating >= lo && p.rating <= hi)
  if (inBand.length >= count) return shuffle(inBand).slice(0, count)
  const mid = (lo + hi) / 2
  return [...themed].sort((a, b) => Math.abs(a.rating - mid) - Math.abs(b.rating - mid)).slice(0, count)
}

export function pickStepPuzzles(all: PuzzleData[], ex: PuzzleExercise): PuzzleData[] {
  return pickPuzzles(all, ex.themes, ex.rating, ex.count)
}

// Test de placement : PLACEMENT_PER_LEVEL puzzles par niveau, tous thèmes, dans l'ordre des niveaux.
export function pickPlacementPuzzles(all: PuzzleData[]): PuzzleData[] {
  return LEVELS.flatMap((l) => pickPuzzles(all, null, l.placement.rating, PLACEMENT_PER_LEVEL))
}
