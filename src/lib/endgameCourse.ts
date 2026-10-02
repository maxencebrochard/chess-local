// Parcours « Cours de finales » d'Apprendre (src/data/endgameCourse.json) : chapitres,
// leçons faites de diagrammes commentés et de lignes jouables, progression.
// Contenu vérifié par scripts/verify-endgame-course.py (tables de finales) et
// scripts/check-endgame-course.mjs (contrôle hors ligne lancé par les E2E).
import { Chess } from 'chess.js'
import courseData from '../data/endgameCourse.json'
import { db } from './db'

export type MarkColor = 'green' | 'red' | 'blue' | 'yellow'

// Flèche [départ, arrivée] ou [départ, arrivée, 'red'] pour un coup à ne pas jouer.
export type CourseArrow = [string, string] | [string, string, 'red']

export interface DiagramStep {
  kind: 'diagram'
  fen: string
  text: string
  orientation?: 'w' | 'b'
  arrows?: CourseArrow[]
  marks?: Record<string, MarkColor>
  // Verdict des tables de finales, quand le texte en affirme un : qui gagne, ou nulle.
  claim?: 'w' | 'b' | 'draw'
}

export interface LineMove {
  san: string // notation anglaise (chess.js), affichée en figurines
  text?: string
  only?: true // seul coup qui garde le résultat (vérifié)
  keeps?: string[] // coups de l'élève (UCI) qui gardent le résultat, générés par le script de vérification
}

// Ligne jouable : l'élève joue le camp qui a le trait dans `fen`, l'app joue l'autre.
export interface LineStep {
  kind: 'line'
  fen: string
  text: string
  result: 'win' | 'draw'
  moves: LineMove[]
  end: string
}

export type CourseStep = DiagramStep | LineStep

export interface Lesson {
  title: string
  summary: string
  exercise?: string // id d'un exercice de src/data/endgames.json
  keyPoints: string[]
  steps: CourseStep[]
}

export interface Chapter {
  id: string
  title: string
  lessons: string[]
}

const DATA = courseData as unknown as { chapters: Chapter[]; lessons: Record<string, Lesson> }

export const CHAPTERS = DATA.chapters
export const LESSON_IDS = CHAPTERS.flatMap((c) => c.lessons)

export function lessonById(id: string | undefined): Lesson | null {
  return id && Object.hasOwn(DATA.lessons, id) ? DATA.lessons[id] : null
}

// Leçon qui enseigne un exercice de finale donné (lien « Voir la leçon »).
export function lessonForExercise(endgameId: string): string | null {
  return LESSON_IDS.find((id) => DATA.lessons[id].exercise === endgameId) ?? null
}

export function nextLessonId(id: string): string | null {
  const i = LESSON_IDS.indexOf(id)
  return i >= 0 && i + 1 < LESSON_IDS.length ? LESSON_IDS[i + 1] : null
}

// Coups de la ligne en UCI, pour comparer le coup joué sans dépendre de la notation.
export function lineUci(step: LineStep): string[] {
  const c = new Chess(step.fen)
  return step.moves.map((m) => {
    const mv = c.move(m.san)
    return mv.from + mv.to + (mv.promotion ?? '')
  })
}

// ---------- Progression ----------
// Une leçon terminée = une ligne `learnSessions` { domain: 'course', itemId: 'finales:<id>' },
// écrite une seule fois : déjà sauvegardée et restaurée avec le reste, sans changement de schéma.
export const COURSE_DOMAIN = 'course'
const ITEM_PREFIX = 'finales:'

export async function completedLessons(): Promise<Set<string>> {
  const rows = await db.learnSessions.where('domain').equals(COURSE_DOMAIN).toArray()
  return new Set(rows.filter((r) => r.itemId.startsWith(ITEM_PREFIX)).map((r) => r.itemId.slice(ITEM_PREFIX.length)))
}

export async function markLessonDone(id: string): Promise<void> {
  const itemId = ITEM_PREFIX + id
  await db.transaction('rw', db.learnSessions, async () => {
    const already = await db.learnSessions.where('domain').equals(COURSE_DOMAIN).filter((r) => r.itemId === itemId).count()
    if (!already) await db.learnSessions.add({ date: Date.now(), domain: COURSE_DOMAIN, itemId, success: 1, ratingAfter: null })
  })
}
