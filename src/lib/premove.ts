import { type Chess, type Square, SQUARES } from 'chess.js'

// Géométrie anticipée : occupation et attaques peuvent changer au coup adverse.
// Les pions peuvent anticiper une prise sur une case vide ; la légalité complète attend l'exécution.
export function premoveTargets(chess: Chess, from: Square): Set<string> {
  const piece = chess.get(from)
  if (!piece) return new Set()
  const file = from.charCodeAt(0)
  const rank = Number(from[1])
  return new Set(SQUARES.filter((to) => {
    const dx = Math.abs(to.charCodeAt(0) - file)
    const dy = Number(to[1]) - rank
    const y = Math.abs(dy)
    if (!dx && !y) return false
    switch (piece.type) {
      case 'n': return dx * y === 2
      case 'b': return dx === y
      case 'r': return dx === 0 || y === 0
      case 'q': return dx === y || dx === 0 || y === 0
      case 'k': {
        const home = piece.color === 'w' ? '1' : '8'
        const rights = chess.getCastlingRights(piece.color)
        return (dx <= 1 && y <= 1) || (from === `e${home}` &&
          ((to === `g${home}` && rights.k) || (to === `c${home}` && rights.q)))
      }
      case 'p': {
        const forward = piece.color === 'w' ? 1 : -1
        return (dy === forward && dx <= 1) ||
          (dx === 0 && dy === 2 * forward && rank === (piece.color === 'w' ? 2 : 7))
      }
    }
  }))
}
