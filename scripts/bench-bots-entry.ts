// Entrée du bundle Node de `scripts/bench-bots.mjs` (et de `e2e/bots_moves.mjs`) : la vraie
// logique des bots et la vraie classe Engine de l'app, servies au banc tel quel.
// Doit rester DANS le repo : hors de l'arbre, rolldown laisse `chess.js` en import externe.
export * from '../src/lib/bots'
export { Engine } from '../src/lib/engine'
export { Chess } from 'chess.js'
