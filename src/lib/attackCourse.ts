// Parcours « Démolir le roque » d'Apprendre (src/data/attackCourse.json), instance du moteur commun
// des cours (lessonCourse.ts). Chaque évaluation affirmée est vérifiée par Stockfish 18 hors ligne
// (scripts/verify-attack-course.py, qui tamponne le JSON) et le contrôle hors ligne
// scripts/check-attack-course.mjs (lancé par les E2E) refuse un contenu non tamponné.
import courseData from '../data/attackCourse.json'
import { makeCourse, type CourseData } from './lessonCourse'

export const ROQUE = makeCourse(
  {
    slug: 'roque',
    title: 'Démolir le roque',
    emoji: '🔥',
    intro: "Ouvrir le roi adverse, sacrifier au bon moment, amener assez de pièces. Chaque verdict est vérifié hors ligne par Stockfish 18, à profondeur fixe.",
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
