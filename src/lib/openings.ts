import openingsData from '../data/openings.json'

interface OpeningEntry {
  eco: string
  name: string
  uci: string
}

const openings = openingsData as OpeningEntry[]
// Index par séquence UCI pour lookup exact.
const byUci = new Map(openings.map((o) => [o.uci, o]))

// Nom de l'ouverture correspondant au plus long préfixe connu de la partie.
export function openingForMoves(uciMoves: string[]): OpeningEntry | null {
  let best: OpeningEntry | null = null
  for (let n = 1; n <= Math.min(uciMoves.length, 24); n++) {
    const hit = byUci.get(uciMoves.slice(0, n).join(' '))
    if (hit) best = hit
  }
  return best
}

// Positions théoriques : la séquence complète est un préfixe d'une ouverture connue.
const knownPrefixes = new Set<string>()
for (const o of openings) {
  const moves = o.uci.split(' ')
  for (let n = 1; n <= moves.length; n++) {
    knownPrefixes.add(moves.slice(0, n).join(' '))
  }
}

export function isBookPosition(uciMoves: string[]): boolean {
  return knownPrefixes.has(uciMoves.join(' '))
}

// Coups théoriques possibles depuis une séquence donnée (explorer d'ouvertures).
export function bookContinuations(uciMoves: string[]): { move: string; openings: OpeningEntry[] }[] {
  const prefix = uciMoves.join(' ')
  const map = new Map<string, OpeningEntry[]>()
  for (const o of openings) {
    const moves = o.uci.split(' ')
    if (moves.length <= uciMoves.length) continue
    if (moves.slice(0, uciMoves.length).join(' ') !== prefix) continue
    const next = moves[uciMoves.length]
    if (!map.has(next)) map.set(next, [])
    map.get(next)!.push(o)
  }
  return [...map.entries()]
    .map(([move, list]) => ({ move, openings: list }))
    .sort((a, b) => b.openings.length - a.openings.length)
}
