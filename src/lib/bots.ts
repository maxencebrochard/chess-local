// Adversaires façon chess.com : personnalités avec force cible.
//
// Deux familles :
// - à partir de 1320 Elo (plancher de `UCI_Elo`), Stockfish bridé par UCI_LimitStrength, au
//   movetime du bot ;
// - sous 1320, un « style » : Stockfish pleine force mais à horizon court (profondeur fixe),
//   qui examine plusieurs candidats et en tire un au sort, pondéré par la perte par rapport au
//   meilleur coup qu'il voit. Les fautes ressemblent à celles d'un humain : tactique trop
//   profonde pour son horizon, pièce laissée en prise, coup passif. Jamais de coup absurde
//   quand un coup s'impose (mat, dame gratuite, reprise obligatoire).
// L'échelle est mesurée par `scripts/bench-bots.mjs` (Iris, inchangée, sert d'ancre à 1600).
import type { EngineLine, SearchResult } from './engine'

export interface WeakStyle {
  // Horizon de calcul. Fixe (et non un temps) : même force sur iPhone et sur ordinateur.
  depth: number
  // Nombre de coups candidats examinés.
  multipv: number
  // Tolérance aux coups moins bons : un candidat pèse exp(-perte / température).
  temperatureCp: number
  // Perte maximale acceptée par rapport au meilleur coup vu.
  maxLossCp: number
  // Seuil où un coup s'impose : les candidats sont triés, et dès qu'un écart entre deux voisins
  // atteint ce seuil, tout ce qui suit est écarté (mat, dame gratuite, reprise de dame, parade unique).
  // Une pièce mineure gratuite (~300 cp) reste sous la falaise des bots les plus faibles : ils peuvent la rater.
  forcedGapCp: number
}

export interface Bot {
  id: string
  name: string
  elo: number
  emoji: string
  description: string
  // Temps de réflexion des bots bridés par UCI_Elo. Un bot à `style` cherche à profondeur fixe :
  // ce temps ne sert plus qu'à réduire sa latence artificielle quand la pendule presse (botThinkBudget).
  movetimeMs: number
  // Bots faibles uniquement (sous le plancher UCI_Elo de 1320).
  style?: WeakStyle
}

export const BOTS: Bot[] = [
  {
    id: 'noa', name: 'Noa', elo: 400, emoji: '🐣', description: 'Débute à peine, laisse des pièces en prise.', movetimeMs: 150,
    style: { depth: 2, multipv: 21, temperatureCp: 150, maxLossCp: 435, forcedGapCp: 415 },
  },
  {
    id: 'marty', name: 'Marty', elo: 700, emoji: '🤓', description: 'Connaît les règles, pas encore les plans.', movetimeMs: 200,
    style: { depth: 2, multipv: 18, temperatureCp: 105, maxLossCp: 355, forcedGapCp: 380 },
  },
  {
    id: 'lea', name: 'Léa', elo: 1000, emoji: '🎒', description: 'Joueuse de club junior, tactique irrégulière.', movetimeMs: 250,
    style: { depth: 2, multipv: 15, temperatureCp: 76, maxLossCp: 290, forcedGapCp: 340 },
  },
  {
    id: 'nina', name: 'Nina', elo: 1300, emoji: '☕', description: 'Habituée du club, solide en ouverture.', movetimeMs: 300,
    style: { depth: 3, multipv: 12, temperatureCp: 60, maxLossCp: 275, forcedGapCp: 300 },
  },
  { id: 'iris', name: 'Iris', elo: 1600, emoji: '📚', description: 'Compétitrice sérieuse, punit les erreurs simples.', movetimeMs: 350 },
  { id: 'viktor', name: 'Viktor', elo: 1900, emoji: '🧊', description: 'Positionnel et froid, rarement pressé.', movetimeMs: 400 },
  { id: 'sofia', name: 'Sofia', elo: 2200, emoji: '🔥', description: 'Attaquante candidate maître.', movetimeMs: 500 },
  { id: 'arun', name: 'Arun', elo: 2500, emoji: '🎯', description: 'Grand-maître, précision chirurgicale.', movetimeMs: 700 },
  { id: 'maximus', name: 'Maximus', elo: 3200, emoji: '🤖', description: 'Stockfish pleine puissance. Bonne chance.', movetimeMs: 1000 },
]

const MATE_CP = 100_000

export function botById(id: string): Bot | undefined {
  return BOTS.find((b) => b.id === id)
}

// Options UCI pour un bot donné.
export function botEngineOptions(bot: Bot): Record<string, string | number | boolean> {
  if (bot.style || bot.elo >= 3190) return { UCI_LimitStrength: false }
  return {
    UCI_LimitStrength: true,
    UCI_Elo: Math.max(1320, Math.min(3190, bot.elo)),
  }
}

// Budget de réflexion selon la pendule du bot : min(movetime, reste / 40 + 0,8 x incrément).
// La latence artificielle (rythme naturel) est réduite dans la même proportion, et
// supprimée sous 10 s. En illimité (null), le bot prend son movetime.
export function botThinkBudget(bot: Bot, remainingMs: number | null, incMs: number): { movetimeMs: number; latencyScale: number } {
  if (remainingMs === null) return { movetimeMs: bot.movetimeMs, latencyScale: 1 }
  const movetimeMs = Math.max(20, Math.min(bot.movetimeMs, Math.floor(remainingMs / 40 + 0.8 * incMs)))
  return { movetimeMs, latencyScale: remainingMs < 10_000 ? 0 : movetimeMs / bot.movetimeMs }
}

// Ce dont `chooseBotMove` a besoin d'un moteur (la classe Engine de l'app, ou le banc).
export interface BotEngine {
  setOptions(options: Record<string, string | number | boolean>): Promise<void>
  search(opts: { fen: string; depth?: number; movetimeMs?: number; multipv?: number }): Promise<SearchResult>
}

// Coup UCI du bot dans la position `fen`. Règle ses options moteur à chaque appel : le même
// moteur peut servir des bots différents d'une partie à l'autre.
// `movetimeMs` remplace le temps de réflexion des bots bridés (pendule) ; `rng` sert aux tests.
export async function chooseBotMove(
  engine: BotEngine,
  bot: Bot,
  fen: string,
  opts: { movetimeMs?: number; rng?: () => number } = {},
): Promise<string> {
  await engine.setOptions(botEngineOptions(bot))
  if (!bot.style) {
    const res = await engine.search({ fen, movetimeMs: opts.movetimeMs ?? bot.movetimeMs, multipv: 1 })
    return res.bestMove
  }
  const res = await engine.search({ fen, depth: bot.style.depth, multipv: bot.style.multipv })
  return pickWeakMove(res.lines, bot.style, opts.rng ?? Math.random) ?? res.bestMove
}

// Valeur d'une ligne du point de vue du trait, mats compris (mat rapide > mat lent).
function lineValue(line: EngineLine): number {
  if (line.scoreMate !== null) return line.scoreMate > 0 ? MATE_CP - line.scoreMate : -MATE_CP - line.scoreMate
  return line.scoreCp ?? 0
}

// Probabilité de chaque coup candidat d'un bot faible, d'après ses lignes MultiPV
// (vide sans ligne exploitable). Exportée pour que les tests vérifient la loi exacte.
export function weakMoveDistribution(lines: EngineLine[], style: WeakStyle): { uci: string; p: number }[] {
  const seen = new Set<string>()
  const cands: { uci: string; value: number }[] = []
  for (const line of lines) {
    const uci = line.pv[0]
    if (!uci || seen.has(uci) || (line.scoreCp === null && line.scoreMate === null)) continue
    seen.add(uci)
    cands.push({ uci, value: lineValue(line) })
  }
  if (cands.length === 0) return []
  cands.sort((a, b) => b.value - a.value)
  const best = cands[0]
  // Un mat trouvé n'est jamais laissé passer.
  if (best.value >= MATE_CP / 2) return [{ uci: best.uci, p: 1 }]
  const pool = [best]
  for (let i = 1; i < cands.length; i++) {
    if (cands[i - 1].value - cands[i].value >= style.forcedGapCp || best.value - cands[i].value > style.maxLossCp) break
    pool.push(cands[i])
  }
  const weights = pool.map((c) => Math.exp(-(best.value - c.value) / style.temperatureCp))
  const total = weights.reduce((s, w) => s + w, 0)
  return pool.map((c, i) => ({ uci: c.uci, p: weights[i] / total }))
}

// Tirage d'un bot faible parmi les lignes MultiPV. Renvoie null sans ligne exploitable.
export function pickWeakMove(lines: EngineLine[], style: WeakStyle, rng: () => number): string | null {
  const dist = weakMoveDistribution(lines, style)
  if (dist.length === 0) return null
  let r = rng()
  for (const { uci, p } of dist) {
    r -= p
    if (r < 0) return uci
  }
  return dist[0].uci
}
