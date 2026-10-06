// Parcours « Cours de finales » d'Apprendre (src/data/endgameCourse.json), instance du moteur
// commun des cours (lessonCourse.ts). Contenu vérifié par scripts/verify-endgame-course.py
// (tables de finales) et scripts/check-endgame-course.mjs (contrôle hors ligne lancé par les E2E).
import courseData from '../data/endgameCourse.json'
import { makeCourse, type CourseData } from './lessonCourse'

export {
  COURSE_DOMAIN, lineUci,
  type Chapter, type CourseArrow, type CourseStep, type DiagramStep, type Lesson, type LineMove, type LineStep, type MarkColor,
} from './lessonCourse'

export const FINALES = makeCourse(
  {
    slug: 'finales',
    title: 'Cours de finales',
    emoji: '📚',
    intro: "Les finales à connaître, de la plus simple à la plus fine. Chaque leçon se lit et se joue sur l'échiquier.",
    refusals: {
      alsoGood: (result) => `Ce coup ${result === 'win' ? 'gagne' : 'tient'} aussi, mais la leçon suit une autre méthode. Cherche encore.`,
      bad: (result) => (result === 'win' ? 'Ce coup laisse échapper le gain. Cherche encore.' : 'Ce coup perd. Cherche encore.'),
    },
  },
  courseData as unknown as CourseData,
)

export const CHAPTERS = FINALES.chapters
export const LESSON_IDS = FINALES.lessonIds
export const lessonById = FINALES.lessonById
export const nextLessonId = FINALES.nextLessonId
export const completedLessons = FINALES.completedLessons
export const markLessonDone = FINALES.markLessonDone

// Leçon qui enseigne un exercice de finale donné (lien « Voir la leçon »).
export function lessonForExercise(endgameId: string): string | null {
  return LESSON_IDS.find((id) => lessonById(id)?.exercise === endgameId) ?? null
}
