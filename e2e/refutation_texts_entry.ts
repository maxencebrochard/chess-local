// Entrée du bundle Node de `test_refutation.py` : réexporte ce que `refutation_texts.mjs` exerce.
// Doit rester DANS le repo : hors de l'arbre, rolldown laisse `chess.js` en import externe.
export * from '../src/lib/refutation'
export { Chess } from 'chess.js'
