// Cours « Les bases » d'Apprendre (src/data/basicsCourse.json), instance du moteur commun des cours
// (lessonCourse.ts) : les leçons qui manquaient au parcours d'apprentissage (valeur des pièces,
// menaces, développement, colonne ouverte). Chaque verdict est vérifié hors ligne par Stockfish 18
// (scripts/verify-basics-course.py, qui tamponne le JSON) et contrôlé par
// scripts/check-basics-course.mjs (lancé par les E2E).
import courseData from '../data/basicsCourse.json'
import { makeCourse, type CourseData } from './lessonCourse'

export const BASES = makeCourse(
  {
    slug: 'bases',
    title: 'Les bases',
    emoji: '🧱',
    intro: "Valeur des pièces, menaces, développement, colonnes ouvertes : les réflexes de base. Chaque verdict est vérifié hors ligne par Stockfish 18.",
    refusals: {
      alsoGood: (result) =>
        result === 'edge'
          ? 'Ce coup garde aussi une nette avance, mais la leçon suit une autre idée. Cherche encore.'
          : 'Ce coup garde aussi un avantage décisif, mais la leçon suit une autre idée. Cherche encore.',
      bad: (result) =>
        result === 'edge'
          ? "Selon Stockfish, ce coup laisse filer l'avance. Cherche encore."
          : "Selon Stockfish, ce coup laisse échapper l'avantage décisif. Cherche encore.",
      close: 'Selon Stockfish, ce coup garde un avantage, mais moins net. Cherche encore.',
    },
  },
  courseData as unknown as CourseData,
)
