// Chargement lazy de la base de puzzles (public/puzzles.json, 120k entrées,
// format compact [id, fen, moves, rating, themes]). Hors bundle JS : fetch
// une fois, caché en mémoire pour la session.
import type { PuzzleData } from '../components/PuzzlePlayer'

type CompactPuzzle = [string, string, string, number, string]

let cache: PuzzleData[] | null = null
let pending: Promise<PuzzleData[]> | null = null

export function loadPuzzles(): Promise<PuzzleData[]> {
  if (cache) return Promise.resolve(cache)
  pending ??= fetch(`${import.meta.env.BASE_URL}puzzles.json`)
    .then((res) => {
      // Un 404 (page HTML) casserait res.json() comme une coupure réseau : même traitement.
      if (!res.ok) throw new Error(`puzzles.json : HTTP ${res.status}`)
      return res.json()
    })
    .then((raw: CompactPuzzle[]) => {
      cache = raw.map(([id, fen, moves, rating, themes]) => ({
        id,
        fen,
        moves: moves.split(' '),
        rating,
        themes: themes.split(' '),
      }))
      return cache
    })
    .catch((e: unknown) => {
      // L'échec n'est pas gardé en cache : le prochain appel retente le chargement.
      pending = null
      throw e
    })
  return pending
}
