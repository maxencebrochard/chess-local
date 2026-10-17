// Parcours d'apprentissage (#/apprendre/parcours), façon chess.com Path : niveaux d'étapes à valider
// dans l'ordre, chacune une courte leçon (cours d'Apprendre ou cours détaillé) suivie d'exercices
// de validation. Données dans src/data/learningPath.json, contrôlées par
// scripts/check-learning-path.mjs (références, ids figés, ordre). Ce module est pur (aucun accès à
// la base) : la progression se calcule depuis des « faits » lus par learningPathStore.ts.
import pathData from '../data/learningPath.json'
import { BASES } from './basicsCourse'
import { ROQUE } from './attackCourse'
import { FINALES } from './endgameCourse'
import type { Course as LessonCourse, Lesson } from './lessonCourse'

export interface PuzzleExercise {
  kind: 'puzzles'
  themes: string[] // thèmes lichess, en union
  rating: [number, number]
  count: number
  pass: number
}

export interface OpeningExercise {
  kind: 'opening'
  family: string // clé lichess de la famille (« Italian Game »)
  color: 'w' | 'b'
  count: number
  pass: number
}

export interface EndgameExercise {
  kind: 'endgame'
  id: string // exercice de src/data/endgames.json
}

export type PathExercise = PuzzleExercise | OpeningExercise | EndgameExercise

export type PathStep = {
  id: string // figé : la progression des élèves y est rattachée
  icon: string
  title: string
  summary: string
  exercise: PathExercise
} & ({ lesson: string; read?: never } | { lesson?: never; read: string })

export interface PathLevel {
  id: string
  title: string
  elo: number
  color: string
  intro: string
  placement: { rating: [number, number] }
  steps: PathStep[]
}

export const LEVELS = (pathData as { levels: PathLevel[] }).levels
export const STEPS: PathStep[] = LEVELS.flatMap((l) => l.steps)
export const PLACEMENT_ID = 'placement'
export const PLACEMENT_PER_LEVEL = 3
export const PLACEMENT_PASS = 2

export const PATH_COURSES: Record<string, LessonCourse> = { [BASES.slug]: BASES, [FINALES.slug]: FINALES, [ROQUE.slug]: ROQUE }

export function stepById(id: string | null | undefined): PathStep | null {
  return STEPS.find((s) => s.id === id) ?? null
}

export function levelOf(step: PathStep): PathLevel {
  return LEVELS.find((l) => l.steps.includes(step))!
}

// Leçon d'un cours désignée par `<slug>:<id>`, avec son chemin dans l'app.
export function lessonRef(ref: string | undefined): { course: LessonCourse; id: string; lesson: Lesson; path: string } | null {
  if (!ref) return null
  const [slug, id] = ref.split(':')
  const course = PATH_COURSES[slug]
  const lesson = course?.lessonById(id) ?? null
  return course && lesson ? { course, id, lesson, path: `${course.path}/${id}` } : null
}

// Exercice noté : une série de N items avec seuil (puzzles, variantes d'ouverture).
export function isScored(ex: PathExercise | undefined): ex is PuzzleExercise | OpeningExercise {
  return ex?.kind === 'puzzles' || ex?.kind === 'opening'
}

// Étoiles d'une série notée selon le meilleur score : 3 sans faute, 1 au seuil, 2 entre les deux.
export function starsFor(best: number, count: number, pass: number): number {
  const s = Math.min(count, Math.max(0, Math.floor(best)))
  if (s >= count) return 3
  if (s < pass) return 0
  return Math.min(2, 1 + Math.floor((2 * (s - pass)) / (count - pass)))
}

// Ce que l'app sait de la progression, lu dans learnSessions par learningPathStore.ts.
export interface PathFacts {
  lessons: Set<string> // `<slug>:<id>` des leçons terminées (domaine `course`)
  endgames: Set<string> // exercices de finale réussis (domaine `endgame`)
  passed: Set<string> // étapes dont une série a atteint le seuil (domaine `path`)
  best: Map<string, number> // meilleur score par étape (domaine `path`)
  placement: number // niveaux acquis par le test de placement (le meilleur test)
}

export const EMPTY_FACTS: PathFacts = { lessons: new Set(), endgames: new Set(), passed: new Set(), best: new Map(), placement: 0 }

export interface StepState {
  step: PathStep
  index: number // index global, tous niveaux confondus
  level: number
  lessonDone: boolean | null // null : pas de leçon
  exerciseDone: boolean
  done: boolean
  acquired: boolean // niveau acquis par le test de placement
  unlocked: boolean
  current: boolean
  best: number | null // séries notées : meilleur score
  stars: number | null // séries notées : 0 à 3
}

export interface PathState {
  steps: StepState[]
  levels: { level: PathLevel; done: number; total: number; acquired: boolean; complete: boolean }[]
  current: StepState | null // null : parcours terminé
  done: number
  total: number
  placement: number
}

export function computePath(facts: PathFacts, levels: PathLevel[] = LEVELS): PathState {
  const placement = Math.max(0, Math.min(levels.length, Math.floor(facts.placement) || 0))
  const steps: StepState[] = []
  levels.forEach((level, li) => {
    for (const step of level.steps) {
      const lessonDone = step.lesson ? facts.lessons.has(step.lesson) : null
      const ex = step.exercise
      const exerciseDone = !ex ? false : ex.kind === 'endgame' ? facts.endgames.has(ex.id) || facts.passed.has(step.id) : facts.passed.has(step.id)
      const best = isScored(ex) ? (facts.best.get(step.id) ?? null) : null
      steps.push({
        step,
        index: steps.length,
        level: li,
        lessonDone,
        exerciseDone,
        done: (lessonDone === true || Boolean(step.read)) && exerciseDone === true,
        acquired: li < placement,
        unlocked: false,
        current: false,
        best,
        stars: isScored(ex) && best !== null ? starsFor(best, ex.count, ex.pass) : null,
      })
    }
  })
  for (const s of steps) {
    const prev = steps[s.index - 1]
    s.unlocked = !prev || prev.done || prev.acquired || s.done || s.acquired || s.level < placement
  }
  // Étape courante : la première ni validée ni acquise (des étapes validées plus loin par un cours
  // déjà fait n'y changent rien).
  const current = steps.find((s) => !s.done && !s.acquired) ?? null
  if (current) {
    current.current = true
    current.unlocked = true
  }
  return {
    steps,
    levels: levels.map((level, li) => {
      const mine = steps.filter((s) => s.level === li)
      const done = mine.filter((s) => s.done).length
      return { level, done, total: mine.length, acquired: li < placement, complete: mine.every((s) => s.done || s.acquired) }
    }),
    current,
    done: steps.filter((s) => s.done).length,
    total: steps.length,
    placement,
  }
}

// Résultat du test de placement : niveaux réussis d'affilée (PLACEMENT_PASS sur PLACEMENT_PER_LEVEL),
// depuis les verdicts dans l'ordre (un niveau inachevé ne compte pas).
export function placementLevels(results: boolean[], levelCount: number = LEVELS.length): number {
  let acquired = 0
  for (let li = 0; li < levelCount; li++) {
    const chunk = results.slice(li * PLACEMENT_PER_LEVEL, (li + 1) * PLACEMENT_PER_LEVEL)
    if (chunk.length < PLACEMENT_PER_LEVEL || chunk.filter(Boolean).length < PLACEMENT_PASS) break
    acquired++
  }
  return acquired
}

// Le test s'arrête au dernier puzzle, ou dès que le niveau en cours ne peut plus être réussi.
export function placementOver(results: boolean[], levelCount: number = LEVELS.length): boolean {
  if (results.length === 0) return false
  if (results.length >= levelCount * PLACEMENT_PER_LEVEL) return true
  const start = Math.floor((results.length - 1) / PLACEMENT_PER_LEVEL) * PLACEMENT_PER_LEVEL
  return results.slice(start).filter((r) => !r).length > PLACEMENT_PER_LEVEL - PLACEMENT_PASS
}

// Objectif de l'exercice, en une phrase.
// `label` : thème (puzzles), famille (ouverture) ou titre de la finale ; `draw` : finale à tenir.
export function exerciseGoal(ex: PathExercise, label: string, draw = false): string {
  if (ex.kind === 'puzzles') return `Réussis ${ex.pass} puzzles sur ${ex.count} : ${label}.`
  if (ex.kind === 'opening') return `Réussis ${ex.pass} variantes sur ${ex.count} de ${label}, avec les ${ex.color === 'w' ? 'Blancs' : 'Noirs'}.`
  return `${draw ? 'Tiens la nulle' : 'Gagne la position'} contre Stockfish : ${label}.`
}
