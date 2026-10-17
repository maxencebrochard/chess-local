// Parcours « Structures de pions » d'Apprendre (src/data/structuresCourse.json), instance du moteur
// commun des cours (lessonCourse.ts) : un chapitre par structure (id de src/lib/structures.ts),
// plans des deux camps, cases clés, ruptures. Chaque coup de ligne est vérifié par Stockfish 18 hors
// ligne (scripts/verify-structures-course.py, qui tamponne le JSON) et le contrôle hors ligne
// scripts/check-structures-course.mjs (lancé par les E2E) refuse un contenu non tamponné.
import courseData from '../data/structuresCourse.json'
import { makeCourse, type CourseData } from './lessonCourse'

export const STRUCTURES_COURSE = makeCourse(
  {
    slug: 'structures',
    title: 'Structures de pions',
    emoji: '♟️',
    intro: "Les pions décident du plan. Pour chaque structure typique : les plans des deux camps, les cases clés, les ruptures. Chaque coup des exercices est vérifié hors ligne par Stockfish 18.",
    refusals: {
      alsoGood: () => 'Selon Stockfish, ce coup se défend aussi, mais la leçon suit le plan de la structure. Cherche encore.',
      bad: () => 'Selon Stockfish, ce coup abîme ta position. Cherche le plan de la structure.',
      close: "Selon Stockfish, ce coup est un peu moins précis que le plan. Cherche encore.",
    },
  },
  courseData as unknown as CourseData,
)
