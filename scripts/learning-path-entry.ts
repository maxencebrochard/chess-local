// Entrée du bundle Node de `scripts/check-learning-path.mjs` (et du contrôle de logique de
// e2e/test_parcours.py) : les vraies données et la vraie logique de l'app, sans duplication.
// Doit rester DANS le repo : hors de l'arbre, rolldown laisse `chess.js` en import externe.
export * from '../src/lib/learningPath'
export { getFamily, playerMoveCount } from '../src/lib/openingTrainer'
export { courseFor } from '../src/lib/courses'
export { ENDGAMES } from '../src/lib/learn'
export { PUZZLE_THEMES_FR } from '../src/lib/puzzleThemes'
