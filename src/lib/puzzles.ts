// Chargement lazy de la base de puzzles (public/puzzles.json, 120k entrées,
// format compact [id, fen, moves, rating, themes]). Hors bundle JS : fetch
// une fois, caché en mémoire pour la session.
import type { PuzzleData } from '../components/PuzzlePlayer'
import { assetResponseOk } from './assetResponse'
import { applyRating, db } from './db'

type CompactPuzzle = [string, string, string, number, string]

let cache: PuzzleData[] | null = null
let pending: Promise<PuzzleData[]> | null = null

export function loadPuzzles(): Promise<PuzzleData[]> {
  if (cache) return Promise.resolve(cache)
  pending ??= fetch(`${import.meta.env.BASE_URL}puzzles.json`)
    .then((res) => {
      // Un 404 (page HTML) casserait res.json() comme une coupure réseau : même traitement.
      if (!assetResponseOk(res)) throw new Error(`puzzles.json : HTTP ${res.status}`)
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

// ---------- Puzzles classés (/puzzles, séance du jour) ----------

// Puzzle classé en cours sur /puzzles (localStorage) : la séance du jour ne le note pas à sa place,
// et la réinitialisation l'efface.
export const PUZZLE_SESSION_KEY = 'chess-local-puzzle-session'

export function pendingPuzzleId(): string | null {
  try {
    const id = (JSON.parse(localStorage.getItem(PUZZLE_SESSION_KEY) ?? 'null') as { puzzle?: { id?: unknown } } | null)?.puzzle?.id
    return typeof id === 'string' ? id : null
  } catch {
    return null
  }
}

// Ids des 2000 dernières tentatives classées : un puzzle récent ne revient pas.
export async function recentPuzzleIds(): Promise<Set<string>> {
  return new Set((await db.puzzleAttempts.orderBy('date').reverse().limit(2000).toArray()).map((a) => a.puzzleId))
}

// Puzzle à portée du classement : à moins de 120 points et pas récent, sinon à moins de 300 (pas
// récent d'abord), sinon le premier. `theme` (séance du jour) restreint d'abord aux puzzles portant ce thème lichess, et
// retombe sur tous les puzzles s'il n'en reste aucun hors des exclusions.
export function pickRatedPuzzle(
  all: PuzzleData[],
  rating: number,
  exclude: Set<string>,
  opts: { theme?: string; rng?: () => number } = {},
): PuzzleData {
  const rng = opts.rng ?? Math.random
  const pickIn = (base: PuzzleData[], fresh: boolean): PuzzleData | null => {
    const near = (span: number) => base.filter((p) => Math.abs(p.rating - rating) < span)
    const wide = near(300)
    const pools = [near(120).filter((p) => !exclude.has(p.id)), wide.filter((p) => !exclude.has(p.id)), ...(fresh ? [] : [wide])]
    const pool = pools.find((x) => x.length > 0)
    return pool ? pool[Math.floor(rng() * pool.length)] : null
  }
  const theme = opts.theme
  return (theme ? pickIn(all.filter((p) => p.themes.includes(theme)), true) : null) ?? pickIn(all, false) ?? all[0]
}

// Note un puzzle classé : Elo `puzzle` puis ligne `puzzleAttempts`, comme /puzzles. Renvoie le
// nouveau classement.
export async function recordRatedPuzzle(puzzle: PuzzleData, success: boolean): Promise<number> {
  const after = await applyRating('puzzle', puzzle.rating, success ? 1 : 0)
  await db.puzzleAttempts.add({ puzzleId: puzzle.id, date: Date.now(), success, puzzleRating: puzzle.rating, ratingAfter: after })
  return after
}
