// Configuration et dernier rapport d'Insights, mémorisés dans localStorage : au retour sur
// /insights (depuis l'Analyse, app relancée, hors ligne), le rapport se reconstruit depuis la
// table `reviews` sans réseau ni moteur. Clé effacée par la réinitialisation (backup.ts).

export const INSIGHTS_KEY = 'chess-local-insights-v1'

export type InsightsTimeClass = 'bullet' | 'blitz' | 'rapid' | 'unlimited'
export type InsightsSource = 'chesscom' | 'local'
export const INSIGHTS_COUNTS = [10, 25, 50, 100] as const
export type InsightsCount = (typeof INSIGHTS_COUNTS)[number]

export interface InsightsConfig {
  timeClass: InsightsTimeClass
  count: InsightsCount
  sources: InsightsSource[]
}

export interface InsightsLastRun {
  keys: string[] // clés `reviews` du rapport, dans l'ordre
  at: number
  depth?: number
  // Pseudo chess.com normalisé de la série (null : parties ChessLocal seules). Une même partie
  // chess.com analysée depuis l'autre compte réécrit la ligne : le rapport n'est alors plus restauré.
  username?: string | null
  partial?: boolean // série interrompue : le rapport ne couvre qu'une partie de la liste
  total?: number // parties de la liste de la série (PGN illisibles exclus)
  failed?: number // parties au PGN illisible, ignorées
}

export interface InsightsSaved {
  config: InsightsConfig
  lastRun: InsightsLastRun | null
}

export const DEFAULT_INSIGHTS_CONFIG: InsightsConfig = { timeClass: 'blitz', count: 25, sources: ['chesscom', 'local'] }

const TIME_CLASSES: InsightsTimeClass[] = ['bullet', 'blitz', 'rapid', 'unlimited']

// Lecture tolérante : une valeur abîmée ou d'une autre forme revient aux défauts, jamais d'exception.
export function readInsights(): InsightsSaved {
  let raw: unknown = null
  try {
    raw = JSON.parse(localStorage.getItem(INSIGHTS_KEY) ?? 'null')
  } catch {
    raw = null
  }
  const obj = (v: unknown): Record<string, unknown> | null => (typeof v === 'object' && v !== null && !Array.isArray(v) ? (v as Record<string, unknown>) : null)
  const root = obj(raw)
  const c = obj(root?.config)
  const config: InsightsConfig = { ...DEFAULT_INSIGHTS_CONFIG }
  if (c) {
    if (TIME_CLASSES.includes(c.timeClass as InsightsTimeClass)) config.timeClass = c.timeClass as InsightsTimeClass
    if (INSIGHTS_COUNTS.includes(c.count as InsightsCount)) config.count = c.count as InsightsCount
    if (Array.isArray(c.sources)) {
      const s = c.sources.filter((x): x is InsightsSource => x === 'chesscom' || x === 'local')
      if (s.length) config.sources = [...new Set(s)]
    }
  }
  const l = obj(root?.lastRun)
  let lastRun: InsightsLastRun | null = null
  if (l && Array.isArray(l.keys) && l.keys.every((k) => typeof k === 'string') && typeof l.at === 'number') {
    lastRun = {
      keys: l.keys as string[],
      at: l.at,
      depth: typeof l.depth === 'number' ? l.depth : undefined,
      username: typeof l.username === 'string' || l.username === null ? l.username : undefined,
      partial: l.partial === true,
      total: typeof l.total === 'number' ? l.total : undefined,
      failed: typeof l.failed === 'number' ? l.failed : undefined,
    }
  }
  return { config, lastRun }
}

export function writeInsights(saved: InsightsSaved): void {
  try {
    localStorage.setItem(INSIGHTS_KEY, JSON.stringify(saved))
  } catch {
    // Stockage saturé : le rapport reste affiché, il ne sera simplement pas restauré au retour.
  }
}
