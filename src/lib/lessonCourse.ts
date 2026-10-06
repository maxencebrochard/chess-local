// Moteur commun des cours d'Apprendre (cours de finales, « Démolir le roque ») : chapitres,
// leçons faites de diagrammes commentés et de lignes jouables, progression.
// Chaque cours est une instance de `makeCourse` sur son JSON, vérifié hors ligne par son script
// (tables de finales ou Stockfish) et contrôlé par les E2E (tampon du JSON vérifié).
import { Chess } from 'chess.js'
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
  // Verdict vérifié, quand le texte en affirme un : qui gagne (ou garde un avantage décisif),
  // nulle (tables de finales) ou équilibre (Stockfish).
  claim?: 'w' | 'b' | 'draw' | 'equal'
  fails?: string // coup (notation anglaise) dont l'échec est vérifié par Stockfish
  eval?: string // évaluation vérifiée, écrite par le script de vérification (« +4.2 », « #5 »)
}

export interface LineMove {
  san: string // notation anglaise (chess.js), affichée en figurines
  text?: string
  hint?: string // indice affiché au premier mauvais coup
  only?: true // seul coup qui garde le résultat (vérifié)
  keeps?: string[] // coups de l'élève (UCI) qui gardent le résultat, générés par le script de vérification
  close?: string[] // coups de l'élève (UCI) juste sous le palier (zone grise), générés par le script de vérification
  weak?: true // réponse adverse vérifiée nettement plus faible que la meilleure défense (affichée « ? »)
}

// Résultat d'une ligne, du point de vue de l'élève : gain ou nulle (tables de finales), avantage
// décisif (`win`, Stockfish) ou nette avance (`edge`, Stockfish).
export type LineResult = 'win' | 'draw' | 'edge'

// Ligne jouable : l'élève joue le camp qui a le trait dans `fen`, l'app joue l'autre.
export interface LineStep {
  kind: 'line'
  fen: string
  text: string
  result: LineResult
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

export interface CourseData {
  chapters: Chapter[]
  lessons: Record<string, Lesson>
}

// Ce que l'interface dit d'un coup refusé, selon le résultat de la ligne.
export interface RefusalTexts {
  alsoGood: (result: LineResult) => string // le coup garde le résultat, mais la leçon suit une autre idée
  bad: (result: LineResult) => string // le coup lâche le résultat
  close?: string // le coup reste juste sous le palier (zone grise du moteur)
}

export interface CourseDef {
  slug: string // chemin sous /apprendre et préfixe des lignes de progression
  title: string
  emoji: string
  intro: string
  refusals: RefusalTexts
}

export interface Course extends CourseDef {
  chapters: Chapter[]
  lessonIds: string[]
  path: string
  lessonById: (id: string | undefined) => Lesson | null
  nextLessonId: (id: string) => string | null
  completedLessons: () => Promise<Set<string>>
  markLessonDone: (id: string) => Promise<void>
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
// Une leçon terminée = une ligne `learnSessions` { domain: 'course', itemId: '<slug>:<id>' },
// écrite une seule fois : déjà sauvegardée et restaurée avec le reste, sans changement de schéma.
export const COURSE_DOMAIN = 'course'

export function makeCourse(def: CourseDef, data: CourseData): Course {
  const lessonIds = data.chapters.flatMap((c) => c.lessons)
  const prefix = `${def.slug}:`
  const lessonById = (id: string | undefined) => (id && Object.hasOwn(data.lessons, id) ? data.lessons[id] : null)
  return {
    ...def,
    chapters: data.chapters,
    lessonIds,
    path: `/apprendre/${def.slug}`,
    lessonById,
    nextLessonId(id) {
      const i = lessonIds.indexOf(id)
      return i >= 0 && i + 1 < lessonIds.length ? lessonIds[i + 1] : null
    },
    async completedLessons() {
      const rows = await db.learnSessions.where('domain').equals(COURSE_DOMAIN).toArray()
      return new Set(rows.filter((r) => r.itemId.startsWith(prefix)).map((r) => r.itemId.slice(prefix.length)))
    },
    async markLessonDone(id) {
      const itemId = prefix + id
      await db.transaction('rw', db.learnSessions, async () => {
        const already = await db.learnSessions.where('domain').equals(COURSE_DOMAIN).filter((r) => r.itemId === itemId).count()
        if (!already) await db.learnSessions.add({ date: Date.now(), domain: COURSE_DOMAIN, itemId, success: 1, ratingAfter: null })
      })
    },
  }
}
