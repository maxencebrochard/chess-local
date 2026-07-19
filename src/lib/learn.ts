// Moteur de séance « Apprendre » : choix du domaine, sélection d'items à la
// bonne difficulté, scoring Elo par domaine (table ratings existante).
import { db, eloUpdate, getRating, type Mistake } from './db'
import { loadPuzzles } from './puzzles'
import { buildDrillLines, type DrillLine } from './repertoire'
import { TACTIC_THEMES } from './themes'
import type { PuzzleData } from '../components/PuzzlePlayer'
import endgamesData from '../data/endgames.json'
import strategyData from '../data/strategy.json'

export type LearnDomain = 'endgame' | 'tactic' | 'opening' | 'strategy' | 'mistakes'

export const DOMAIN_META: Record<LearnDomain, { label: string; emoji: string; ratingKey: string | null }> = {
  endgame: { label: 'Finales', emoji: '🏁', ratingKey: 'learn-endgame' },
  tactic: { label: 'Tactiques', emoji: '⚔️', ratingKey: 'learn-tactic' },
  opening: { label: 'Ouvertures', emoji: '📖', ratingKey: 'learn-opening' },
  strategy: { label: 'Stratégie', emoji: '🧠', ratingKey: 'learn-strategy' },
  mistakes: { label: 'Mes erreurs', emoji: '🩹', ratingKey: null },
}

export interface EndgameItem {
  id: string
  title: string
  fen: string
  side: 'w' | 'b'
  objective: 'win' | 'draw'
  lesson: string
  difficulty: number
}

export interface StrategyCard {
  id: string
  title: string
  lesson: string
  themes: string[]
  difficulty: number
}

export const ENDGAMES = endgamesData as EndgameItem[]
export const STRATEGY_CARDS = strategyData as StrategyCard[]

// Un item de séance, typé par domaine.
export type SessionItem =
  | { kind: 'endgame'; endgame: EndgameItem; difficulty: number }
  | { kind: 'tactic'; theme: string; themeLabel: string; puzzle: PuzzleData; difficulty: number }
  | { kind: 'strategy'; card: StrategyCard; puzzle: PuzzleData; difficulty: number }
  | { kind: 'opening'; line: DrillLine; depth: number; difficulty: number }
  | { kind: 'mistake'; mistake: Mistake; difficulty: number }

export interface Session {
  domain: LearnDomain
  items: SessionItem[]
}

function near<T>(items: T[], diff: (t: T) => number, elo: number, span = 200): T[] {
  const close = items.filter((i) => Math.abs(diff(i) - elo) <= span)
  return close.length ? close : items
}

function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)]
}

// Domaine suivant : le moins travaillé récemment, avec « Mes erreurs » glissé
// une fois sur trois quand il y a du stock.
export async function pickNextDomain(): Promise<LearnDomain> {
  const pending = await db.mistakes.where('solved').equals(0).count()
  const sessions = await db.learnSessions.orderBy('date').reverse().limit(30).toArray()
  if (pending > 0) {
    const sinceMistakes = sessions.findIndex((s) => s.domain === 'mistakes')
    if (sinceMistakes === -1 || sinceMistakes >= 3) return 'mistakes'
  }
  const domains: LearnDomain[] = ['endgame', 'tactic', 'opening', 'strategy']
  const lastIndex = (d: LearnDomain) => {
    const i = sessions.findIndex((s) => s.domain === d)
    return i === -1 ? Infinity : i
  }
  // Le plus ancien dans l'historique récent = le moins travaillé.
  return domains.sort((a, b) => lastIndex(b) - lastIndex(a))[0]
}

export async function domainRating(domain: LearnDomain): Promise<number | null> {
  const key = DOMAIN_META[domain].ratingKey
  if (!key) return null
  return (await getRating(key)).value
}

// Construit une séance de 1 à 3 items pour un domaine.
export async function buildSession(domain: LearnDomain): Promise<Session> {
  const elo = (await domainRating(domain)) ?? 800

  if (domain === 'endgame') {
    const item = pick(near(ENDGAMES, (e) => e.difficulty, elo, 300))
    return { domain, items: [{ kind: 'endgame', endgame: item, difficulty: item.difficulty }] }
  }

  if (domain === 'tactic') {
    const theme = pick(TACTIC_THEMES)
    const all = await loadPuzzles()
    const themed = all.filter((p) => p.themes.includes(theme.tag))
    const pool = near(themed, (p) => p.rating, elo, 150)
    const items: SessionItem[] = []
    const used = new Set<string>()
    for (let i = 0; i < 3 && pool.length > used.size; i++) {
      let puzzle = pick(pool)
      let guard = 0
      while (used.has(puzzle.id) && guard++ < 20) puzzle = pick(pool)
      used.add(puzzle.id)
      items.push({ kind: 'tactic', theme: theme.tag, themeLabel: theme.label, puzzle, difficulty: puzzle.rating })
    }
    return { domain, items }
  }

  if (domain === 'strategy') {
    const card = pick(near(STRATEGY_CARDS, (c) => c.difficulty, elo, 300))
    const all = await loadPuzzles()
    const themed = all.filter((p) => card.themes.some((t) => p.themes.includes(t)))
    const pool = near(themed.length ? themed : all, (p) => p.rating, elo, 200)
    const items: SessionItem[] = []
    const used = new Set<string>()
    for (let i = 0; i < 2 && pool.length > used.size; i++) {
      let puzzle = pick(pool)
      let guard = 0
      while (used.has(puzzle.id) && guard++ < 20) puzzle = pick(pool)
      used.add(puzzle.id)
      items.push({ kind: 'strategy', card, puzzle, difficulty: puzzle.rating })
    }
    return { domain, items }
  }

  if (domain === 'opening') {
    const lines = await buildDrillLines()
    const line = pick(lines.slice(0, 6))
    // Profondeur du drill : plus l'Elo monte, plus la ligne est longue.
    const depth = Math.min(line.uci.length, elo < 900 ? 6 : elo < 1300 ? 8 : elo < 1700 ? 10 : 14)
    return { domain, items: [{ kind: 'opening', line, depth, difficulty: 700 + depth * 60 }] }
  }

  // mistakes
  const pendings = await db.mistakes.where('solved').equals(0).reverse().sortBy('date')
  const items: SessionItem[] = pendings.slice(0, 2).map((m) => ({
    kind: 'mistake' as const,
    mistake: m,
    difficulty: 0,
  }))
  return { domain, items }
}

// Enregistre le résultat d'un item et met à jour l'Elo du domaine.
export async function scoreItem(domain: LearnDomain, itemId: string, success: boolean, difficulty: number): Promise<number | null> {
  const key = DOMAIN_META[domain].ratingKey
  let after: number | null = null
  if (key && difficulty > 0) {
    const r = await getRating(key)
    after = eloUpdate(r.value, difficulty, success ? 1 : 0, r.games)
    await db.ratings.put({ key, value: after, games: r.games + 1 })
  }
  await db.learnSessions.add({ date: Date.now(), domain, itemId, success: success ? 1 : 0, ratingAfter: after })
  return after
}
