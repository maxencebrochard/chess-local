// « Dans mes parties » (/structures) : structures de pions des parties du joueur, sans réseau.
// Parties lues : celles jouées ici contre un bot (`games`, couleur connue) et les parties chess.com
// déjà passées au bilan par Insights (`reviews`, source chesscom, tous pseudos confondus).
// Les tentatives depuis une position de ces parties vont dans `learnSessions`, domaine
// `structure-play` (contrat dans db.ts), sans aucun Elo.
import { botById } from './bots'
import { db, type LearnSession } from './db'
import type { Level } from './attack'
import { structuresInGame, structureStats, type Sighting, type StructureGame, type StructureStat } from './structures'

export interface MyGame extends StructureGame {
  source: 'local' | 'chesscom'
  date: number
  opponent: string
  timeControl: string
  pgn: string
}

export const STRUCTURE_PLAY_DOMAIN = 'structure-play'

// Position proposée : `<clé de partie>@<demi-coup>@<structure>`, ex. `local:12@14@iqp`, `chesscom:1234@21@carlsbad`.
export const positionKey = (game: Pick<MyGame, 'key'>, s: Pick<Sighting, 'ply' | 'id'>) => `${game.key}@${s.ply}@${s.id}`
export const playKey = (key: string) => `structure:${key}`
export const structurePath = (key: string) => `/structures/${encodeURIComponent(key)}`

function localGame(g: { id?: number; date: number; botId?: string; playerColor: 'w' | 'b'; result: string; timeControl: string; pgn: string }): MyGame | null {
  if (g.id === undefined) return null
  const won = (g.result === '1-0' && g.playerColor === 'w') || (g.result === '0-1' && g.playerColor === 'b')
  return {
    key: `local:${g.id}`,
    source: 'local',
    playerColor: g.playerColor,
    result: g.result === '1/2-1/2' ? 'draw' : won ? 'win' : 'loss',
    date: g.date,
    opponent: (g.botId && botById(g.botId)?.name) || 'Bot',
    timeControl: g.timeControl,
    pgn: g.pgn,
  }
}

// Parties du joueur, les plus récentes d'abord. Les bilans `local:` d'Insights doublent `games` : ignorés.
export async function loadMyGames(): Promise<MyGame[]> {
  const [games, reviews] = await Promise.all([db.games.where('mode').equals('bot').toArray(), db.reviews.toArray()])
  const out: MyGame[] = []
  for (const g of games) {
    const m = localGame(g)
    if (m) out.push(m)
  }
  for (const r of reviews) {
    if (r.source !== 'chesscom' || typeof r.pgn !== 'string') continue
    out.push({ key: r.key, source: 'chesscom', playerColor: r.playerColor, result: r.result, date: r.date, opponent: r.opponent, timeControl: r.timeControl, pgn: r.pgn })
  }
  return [...new Map(out.map((g) => [g.key, g])).values()].sort((a, b) => b.date - a.date)
}

async function gameByKey(key: string): Promise<MyGame | null> {
  if (key.startsWith('local:')) {
    const id = Number(key.slice('local:'.length))
    const g = Number.isInteger(id) ? await db.games.get(id) : undefined
    return g && g.mode === 'bot' ? localGame(g) : null
  }
  const r = await db.reviews.get(key)
  return r && r.source === 'chesscom' ? { key: r.key, source: 'chesscom', playerColor: r.playerColor, result: r.result, date: r.date, opponent: r.opponent, timeControl: r.timeControl, pgn: r.pgn } : null
}

export interface MyStructures {
  games: number // parties lues (PGN lisibles ou non)
  stats: StructureStat<MyGame>[]
}

// Repérage partie par partie, en rendant la main au navigateur entre deux paquets : quelques
// centaines de parties ne figent pas l'écran.
export async function loadMyStructures(): Promise<MyStructures> {
  const games = await loadMyGames()
  const scanned: { game: MyGame; sightings: Sighting[] }[] = []
  for (let i = 0; i < games.length; i++) {
    if (i > 0 && i % 10 === 0) await new Promise((r) => setTimeout(r, 0))
    scanned.push({ game: games[i], sightings: structuresInGame(games[i].pgn, games[i].playerColor) })
  }
  return { games: games.length, stats: structureStats(scanned) }
}

// Position d'une clé `<partie>@<demi-coup>@<structure>` : la partie est relue et la structure recalculée (une
// partie supprimée, ou une règle de structure changée, ne rouvre rien).
export async function sightingByKey(key: string): Promise<{ game: MyGame; sighting: Sighting } | null> {
  const match = /^(.+)@\d+@[^@]+$/.exec(key)
  if (!match) return null
  const game = await gameByKey(match[1])
  const sighting = game ? structuresInGame(game.pgn, game.playerColor).find((s) => positionKey(game, s) === key) : undefined
  return game && sighting ? { game, sighting } : null
}

export type PlayOutcome = NonNullable<LearnSession['outcome']>

// Une ligne par tentative : succès = gain (mat ou avantage décisif tenu) sans aide. Une nulle, une
// défaite, un abandon ou un Recommencer (`abandon`) restent des tentatives.
export async function recordStructurePlay(key: string, fen: string, outcome: PlayOutcome, level: Level, assisted: boolean): Promise<void> {
  const success = (outcome === 'mate' || outcome === 'decisive') && !assisted
  await db.learnSessions.add({
    date: Date.now(),
    domain: STRUCTURE_PLAY_DOMAIN,
    itemId: key,
    fen,
    success: success ? 1 : 0,
    ratingAfter: null,
    outcome,
    defenderElo: level,
    assisted,
  })
}

export interface PlayStats {
  attempts: number
  successes: number
}

// Tentatives par `clé|fen` : une position recalculée autrement sous la même clé repart de zéro.
export async function structurePlayStats(): Promise<Map<string, PlayStats>> {
  const rows = await db.learnSessions.where('domain').equals(STRUCTURE_PLAY_DOMAIN).toArray()
  const out = new Map<string, PlayStats>()
  for (const r of rows) {
    const k = `${r.itemId}|${r.fen ?? ''}`
    const s = out.get(k) ?? { attempts: 0, successes: 0 }
    s.attempts++
    if (r.success) s.successes++
    out.set(k, s)
  }
  return out
}
