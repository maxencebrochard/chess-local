// Entrée du bundle Node de `test_coach.py` : réexporte ce que `coach_texts.mjs` exerce.
// Doit rester DANS le repo : hors de l'arbre, rolldown laisse `chess.js` en import externe.
export * from '../src/lib/coach'
export * from '../src/lib/liveCoach'
export { figurine, CLASS_META, winPct } from '../src/lib/review'
export { Chess } from 'chess.js'
export * from '../src/lib/motifs'
export { PHRASES, Picker } from '../src/lib/coachPhrases'
