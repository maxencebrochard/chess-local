import Dexie, { type EntityTable } from 'dexie'

export interface SavedGame {
  id?: number
  date: number
  mode: 'bot' | 'local'
  botId?: string
  playerColor: 'w' | 'b'
  timeControl: string // ex "5+0", "illimité"
  timeClass: 'bullet' | 'blitz' | 'rapid' | 'unlimited'
  pgn: string
  result: '1-0' | '0-1' | '1/2-1/2'
  termination: string
  playerRatingAfter?: number
}

export interface Rating {
  key: string // 'bullet' | 'blitz' | 'rapid' | 'unlimited' | 'puzzle'
  value: number
  games: number
}

export interface PuzzleAttempt {
  id?: number
  puzzleId: string
  date: number
  success: boolean
  puzzleRating: number
  ratingAfter: number
}

export interface RushScore {
  id?: number
  mode: '3min' | '5min' | 'survival'
  score: number
  date: number
}

export const db = new Dexie('chess-local') as Dexie & {
  games: EntityTable<SavedGame, 'id'>
  ratings: EntityTable<Rating, 'key'>
  puzzleAttempts: EntityTable<PuzzleAttempt, 'id'>
  rushScores: EntityTable<RushScore, 'id'>
}

db.version(1).stores({
  games: '++id, date, mode, timeClass',
  ratings: 'key',
  puzzleAttempts: '++id, date, puzzleId',
  rushScores: '++id, mode, score, date',
})

export const DEFAULT_RATING = 800

export async function getRating(key: string): Promise<Rating> {
  return (await db.ratings.get(key)) ?? { key, value: DEFAULT_RATING, games: 0 }
}

// Elo classique, K décroissant avec l'expérience.
export function eloUpdate(rating: number, opponent: number, score: 0 | 0.5 | 1, games: number): number {
  const k = games < 20 ? 40 : 20
  const expected = 1 / (1 + 10 ** ((opponent - rating) / 400))
  return Math.round(rating + k * (score - expected))
}

export async function applyRating(key: string, opponent: number, score: 0 | 0.5 | 1): Promise<number> {
  const r = await getRating(key)
  const value = eloUpdate(r.value, opponent, score, r.games)
  await db.ratings.put({ key, value, games: r.games + 1 })
  return value
}
