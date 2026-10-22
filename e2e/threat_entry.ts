// Entrée du bundle Node de `test_menace.py` (`e2e/threat_cases.mjs`) : la vraie détection de
// menace et la vraie classe Engine, sur le WASM de l'app.
// Doit rester DANS le repo : hors de l'arbre, rolldown laisse `chess.js` en import externe.
export * from '../src/lib/threat'
export { Engine } from '../src/lib/engine'
export { Chess } from 'chess.js'
