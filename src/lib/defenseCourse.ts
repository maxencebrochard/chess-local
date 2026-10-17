// Parcours « Tenir sous l'attaque » d'Apprendre (src/data/defenseCourse.json), pendant défensif de
// « Démolir le roque » et instance du moteur commun des cours (lessonCourse.ts). L'élève joue le camp
// qui défend. Chaque verdict (la défense tient, le coup perd, la menace de mat) est vérifié par
// Stockfish 18 hors ligne (scripts/verify-defense-course.py, qui tamponne le JSON) et le contrôle hors
// ligne scripts/check-defense-course.mjs (lancé par les E2E) refuse un contenu non tamponné.
import courseData from '../data/defenseCourse.json'
import { makeCourse, type CourseData, type LineResult } from './lessonCourse'

const KEPT: Record<LineResult, string> = {
  hold: 'tient aussi',
  edge: 'garde aussi une nette avance',
  win: 'garde aussi un avantage décisif',
  draw: 'tient aussi',
  plan: 'suit aussi un bon plan', // jamais utilisé ici : le contrôle refuse le résultat `plan`
}

export const DEFENSE = makeCourse(
  {
    slug: 'defense',
    title: "Tenir sous l'attaque",
    emoji: '🛡️',
    intro: "Échanger les attaquants, contre-attaquer au centre, ramener des défenseurs, rendre du matériel à temps. Chaque verdict est vérifié hors ligne par Stockfish 18, à profondeur fixe.",
    refusals: {
      alsoGood: (result) => `Selon Stockfish, ce coup ${KEPT[result]}, mais la leçon suit une autre idée. Cherche encore.`,
      bad: (result) =>
        result === 'hold' || result === 'draw'
          ? "Selon Stockfish, ce coup ne tient pas : l'attaque passe. Cherche encore."
          : "Selon Stockfish, ce coup laisse filer l'avantage de la défense. Cherche encore.",
      close: 'Selon Stockfish, ce coup se défend moins bien. Cherche encore.',
    },
  },
  courseData as unknown as CourseData,
)
