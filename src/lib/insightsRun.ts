// Série d'Insights : collecte des parties (chess.com + ChessLocal), bilans Stockfish en cache
// (table `reviews`), pause quand la page est masquée, annulation, reprise. Sans React : la page
// pilote, ce module fait le travail.
import { Chess } from 'chess.js'
import { db, type ReviewRow, type SavedGame } from './db'
import type { Engine } from './engine'
import { reviewGame } from './review'
import { botById } from './bots'
import {
  ChesscomNetworkError, extractGameId, fetchGamesByClass, normalizeUsername, outcomeFor, terminationLabel, type ChesscomGame,
} from './chesscom'
import type { InsightsConfig, InsightsTimeClass } from './insightsStore'

// Partie à analyser : tout ce que la ligne `reviews` portera, sauf le bilan.
export type Candidate = Omit<ReviewRow, 'review' | 'depth'>

// Profondeur adaptée au volume : un rapport n'a qu'une profondeur (une partie en cache n'est
// réutilisée qu'à profondeur égale, sinon la tendance mélangerait deux sensibilités aux gaffes).
export function depthFor(count: number): number {
  return count <= 10 ? 12 : count <= 25 ? 10 : count <= 50 ? 9 : 8
}

// Estimation sans réseau, pour un iPhone : demi-coups moyens par cadence × coût d'une position.
const PLIES_BY_CLASS: Record<InsightsTimeClass, number> = { bullet: 60, blitz: 70, rapid: 80, unlimited: 80 }
const SEC_PER_POSITION: Record<number, number> = { 8: 0.12, 9: 0.18, 10: 0.3, 12: 0.7 }
export function estimateSeconds(positions: number, depth: number): number {
  return positions * (SEC_PER_POSITION[depth] ?? 0.3)
}
export function estimateForConfig(config: InsightsConfig): number {
  return estimateSeconds(config.count * (PLIES_BY_CLASS[config.timeClass] + 1), depthFor(config.count))
}

export function formatDuration(sec: number): string {
  if (sec < 60) return 'moins d’une minute'
  const min = Math.round(sec / 60)
  if (min < 60) return `${min} min`
  const h = Math.floor(min / 60)
  const m = min % 60
  return m ? `${h} h ${String(m).padStart(2, '0')}` : `${h} h`
}

function chesscomCandidate(g: ChesscomGame, user: string, timeClass: InsightsTimeClass): Candidate | null {
  const id = extractGameId(g.url)
  if (!id) return null
  const me = g.playerColor === 'w' ? g.white : g.black
  const opp = g.playerColor === 'w' ? g.black : g.white
  return {
    key: `chesscom:${id}`,
    source: 'chesscom',
    username: user,
    date: g.endTime * 1000,
    timeClass,
    timeControl: g.timeControl,
    playerColor: g.playerColor,
    playerRating: typeof me.rating === 'number' ? me.rating : null,
    opponent: opp.username,
    opponentRating: typeof opp.rating === 'number' ? opp.rating : null,
    result: outcomeFor(g),
    termination: terminationLabel(g),
    lostOnTime: me.result === 'timeout',
    pgn: g.pgn,
  }
}

function localCandidate(g: SavedGame): Candidate | null {
  if (g.id === undefined) return null
  const bot = g.botId ? botById(g.botId) : undefined
  const won = (g.result === '1-0' && g.playerColor === 'w') || (g.result === '0-1' && g.playerColor === 'b')
  const result: ReviewRow['result'] = g.result === '1/2-1/2' ? 'draw' : won ? 'win' : 'loss'
  return {
    key: `local:${g.id}`,
    source: 'local',
    username: null,
    date: g.date,
    timeClass: g.timeClass,
    timeControl: g.timeControl,
    playerColor: g.playerColor,
    playerRating: g.playerRatingAfter ?? null,
    opponent: bot?.name ?? 'Bot',
    opponentRating: bot?.elo ?? null,
    result,
    termination: g.termination,
    lostOnTime: result === 'loss' && g.termination === 'au temps',
    pgn: g.pgn,
  }
}

export interface Collected {
  candidates: Candidate[] // les plus récentes d'abord, `count` au plus, PGN illisibles écartés
  failed: number // PGN illisibles (ou sans coup) parmi les `count` retenues
  offline: boolean // chess.com injoignable : seules ses parties déjà analysées servent
}

const pliesOf = (pgn: string) => {
  try {
    const c = new Chess()
    c.loadPgn(pgn)
    return c.history().length
  } catch {
    return 0
  }
}

// Liste des parties du rapport. Aucune requête pour la cadence « sans limite » (elle n'existe que
// dans l'app). chess.com injoignable : repli sur ses parties de ce pseudo déjà en cache, ou erreur
// réessayable s'il n'y en a pas. Les PGN illisibles sont écartés ici, une fois pour toutes : la
// progression, le bandeau d'interruption et le rapport comptent la même liste.
export async function collectGames(config: InsightsConfig, username: string, signal: AbortSignal): Promise<Collected> {
  signal.throwIfAborted()
  const out: Candidate[] = []
  let offline = false
  if (config.sources.includes('local')) {
    const games = await db.games.where('timeClass').equals(config.timeClass).toArray()
    for (const g of games.filter((x) => x.mode === 'bot').sort((a, b) => b.date - a.date).slice(0, config.count)) {
      const c = localCandidate(g)
      if (c) out.push(c)
    }
  }
  if (config.sources.includes('chesscom') && config.timeClass !== 'unlimited') {
    const user = normalizeUsername(username)
    try {
      for (const g of await fetchGamesByClass(user, config.timeClass, config.count, signal)) {
        const c = chesscomCandidate(g, user, config.timeClass)
        if (c) out.push(c)
      }
    } catch (e) {
      signal.throwIfAborted()
      if (!(e instanceof ChesscomNetworkError)) throw e
      const cached = await db.reviews.where('date').above(0).filter((r) => r.source === 'chesscom' && r.username === user && r.timeClass === config.timeClass).toArray()
      if (cached.length === 0) throw e
      offline = true
      for (const r of cached) {
        const { review: _review, depth: _depth, ...c } = r
        out.push(c)
      }
    }
  }
  signal.throwIfAborted()
  const picked = [...new Map(out.map((c) => [c.key, c])).values()].sort((a, b) => b.date - a.date).slice(0, config.count)
  const candidates = picked.filter((c) => pliesOf(c.pgn) > 0)
  const failed = picked.length - candidates.length
  if (failed) console.warn('[insights] parties ignorées (PGN illisible)', picked.filter((c) => !candidates.includes(c)).map((c) => c.key))
  return { candidates, failed, offline }
}

// Lignes en cache utilisables pour ces parties à cette profondeur et pour ce compte (undefined :
// à analyser). Deux comptes chess.com qui ont joué la même partie ne partagent pas sa ligne : la
// couleur et le résultat y sont ceux du joueur.
export async function cachedFor(candidates: Pick<Candidate, 'key' | 'username'>[], depth: number): Promise<(ReviewRow | undefined)[]> {
  const rows = await db.reviews.bulkGet(candidates.map((c) => c.key))
  return rows.map((r, i) => (r && r.depth === depth && r.username === candidates[i].username ? r : undefined))
}

// Résout quand la page est visible ; attend `visibilitychange` sinon. Rejette si la série est annulée.
export function whenVisible(signal: AbortSignal): Promise<void> {
  if (signal.aborted) return Promise.reject(new DOMException('Série annulée', 'AbortError'))
  if (!document.hidden) return Promise.resolve()
  return new Promise((resolve, reject) => {
    const done = () => {
      document.removeEventListener('visibilitychange', onVis)
      signal.removeEventListener('abort', onAbort)
    }
    const onVis = () => {
      if (document.hidden) return
      done()
      resolve()
    }
    const onAbort = () => {
      done()
      reject(new DOMException('Série annulée', 'AbortError'))
    }
    document.addEventListener('visibilitychange', onVis)
    signal.addEventListener('abort', onAbort)
  })
}

// Écran allumé pendant la série : iOS suspend la PWA dès que l'écran se verrouille. Le verrou
// tombe quand la page est masquée : il est redemandé au retour. Sans API (ou refus), rien.
function keepAwake(signal: AbortSignal): () => void {
  type Sentinel = { release: () => Promise<void> }
  const nav = navigator as Navigator & { wakeLock?: { request: (t: 'screen') => Promise<Sentinel> } }
  let sentinel: Sentinel | null = null
  let stopped = false
  const acquire = () => {
    if (stopped || document.hidden || !nav.wakeLock) return
    nav.wakeLock.request('screen').then(
      (s) => {
        if (stopped) void s.release().catch(() => {})
        else sentinel = s
      },
      () => {},
    )
  }
  const onVis = () => acquire()
  document.addEventListener('visibilitychange', onVis)
  acquire()
  const stop = () => {
    stopped = true
    document.removeEventListener('visibilitychange', onVis)
    void sentinel?.release().catch(() => {})
    sentinel = null
  }
  signal.addEventListener('abort', stop)
  return stop
}

export interface RunProgress {
  game: number // partie en cours (1-based)
  total: number
  analysed: number // parties déjà prêtes (cache compris)
  etaSec: number | null
}

// Analyse les candidats manquants du cache, séquentiellement, sur UN moteur, demandé à `engine()`
// seulement s'il reste une partie à analyser. Une annulation lève une AbortError à la granularité
// d'une recherche ; rien de partiel n'est écrit. Les candidats viennent de `collectGames`, PGN
// lisibles : toute erreur pendant l'analyse (moteur mort) remonte au lieu de faire passer les
// parties suivantes pour illisibles. Lignes rendues dans l'ordre des candidats.
export async function runSeries(
  candidates: Candidate[],
  depth: number,
  engine: () => Engine,
  signal: AbortSignal,
  onProgress: (p: RunProgress) => void,
): Promise<ReviewRow[]> {
  const stopAwake = keepAwake(signal)
  try {
    const cached = await cachedFor(candidates, depth)
    const rows: (ReviewRow | null)[] = cached.map((r) => r ?? null)
    const todo = candidates.map((c, i) => ({ c, i })).filter(({ i }) => !rows[i])
    const positions = todo.map(({ c }) => pliesOf(c.pgn) + 1)
    let remaining = positions.reduce((a, b) => a + b, 0)
    let analysed = rows.filter(Boolean).length
    let measured = 0 // positions réellement analysées
    let elapsed = 0 // ms
    const eta = () => (measured >= 5 ? (elapsed / measured / 1000) * remaining : estimateSeconds(remaining, depth))
    for (const { c, i } of todo) {
      if (signal.aborted) throw new DOMException('Série annulée', 'AbortError')
      onProgress({ game: analysed + 1, total: candidates.length, analysed, etaSec: eta() })
      let lastDone = 0
      let start = performance.now()
      const review = await reviewGame(
        c.pgn,
        engine(),
        depth,
        (pos) => {
          // `pos` : index de la position qui vient d'être évaluée, donc pos + 1 positions faites.
          const done = pos + 1
          const now = performance.now()
          elapsed += now - start
          measured += done - lastDone
          start = now
          remaining -= done - lastDone
          lastDone = done
          onProgress({ game: analysed + 1, total: candidates.length, analysed, etaSec: eta() })
        },
        signal,
        // Le temps passé en pause (page masquée) ne compte pas dans la vitesse mesurée.
        async () => {
          await whenVisible(signal)
          start = performance.now()
        },
      )
      if (signal.aborted) throw new DOMException('Série annulée', 'AbortError')
      const row: ReviewRow = { ...c, depth, review }
      await db.reviews.put(row)
      rows[i] = row
      analysed++
    }
    onProgress({ game: candidates.length, total: candidates.length, analysed, etaSec: 0 })
    return rows.filter((r): r is ReviewRow => r !== null)
  } finally {
    stopAwake()
  }
}
