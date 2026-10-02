// Partie contre Stockfish depuis une position (finales jouées jusqu'au bout, ou position
// quelconque venue de l'analyse) : thème d'une finale, fin de partie lue sur l'échiquier,
// verdict selon l'objectif, persistance de la partie pour survivre à un rechargement.
import { Chess } from 'chess.js'
import { db } from './db'
import type { EndgameGoal } from './learn'

export type Color = 'w' | 'b'
// Objectif du joueur : gagner, ou tenir la nulle. `null` : partie libre, sans objectif.
export type Objective = 'win' | 'draw' | null
export type GameResult = '1-0' | '0-1' | '1/2-1/2'

// ---------- Finales ----------

// Ce qu'il faut faire pour conclure, la partie n'ayant pas de plafond de coups.
export const GOAL_HINT: Record<EndgameGoal, string> = {
  mate: 'Mate le roi adverse.',
  promote: 'Promeus ton pion, puis mate.',
  capture: 'Gagne le matériel adverse, puis mate.',
  hold: 'Pat, répétition, 50 coups : toute nulle te va.',
}

export type EndgameTheme = 'mates' | 'pawns' | 'rooks' | 'queen' | 'other'

export const THEME_LABEL: Record<EndgameTheme, string> = {
  mates: 'Mats de base',
  pawns: 'Pions',
  rooks: 'Tours',
  queen: 'Dame',
  other: 'Autres',
}

// Thème déduit du matériel : une finale ajoutée aux données est classée sans champ en plus.
export function endgameTheme(fen: string): EndgameTheme {
  const pieces = fen.split(' ')[0].replace(/[^a-zA-Z]/g, '')
  const white = pieces.replace(/[a-z]/g, '')
  const black = pieces.replace(/[A-Z]/g, '')
  if (!/p/i.test(pieces) && (white === 'K' || black === 'k')) return 'mates'
  if (/^[kp]+$/i.test(pieces)) return 'pawns'
  if (/q/i.test(pieces)) return 'queen'
  if (/r/i.test(pieces)) return 'rooks'
  return 'other'
}

// Résultats des finales jouées jusqu'au bout : une ligne `learnSessions` par tentative, domaine
// à part (aucune incidence sur l'Elo d'Apprendre ni sur le choix des séances). La FEN rattache
// le résultat à la position : une finale corrigée sous le même id repart de zéro.
export const ENDGAME_PLAY_DOMAIN = 'endgame-play'

export async function recordEndgamePlay(id: string, fen: string, success: boolean): Promise<void> {
  await db.learnSessions.add({ date: Date.now(), domain: ENDGAME_PLAY_DOMAIN, itemId: id, fen, success: success ? 1 : 0, ratingAfter: null })
}

// Clés `id|fen` des finales déjà gagnées (objectif atteint sans aide).
export async function solvedEndgames(): Promise<Set<string>> {
  const rows = await db.learnSessions.where('domain').equals(ENDGAME_PLAY_DOMAIN).toArray()
  return new Set(rows.filter((r) => r.success === 1).map((r) => `${r.itemId}|${r.fen ?? ''}`))
}

// ---------- Fin de partie ----------

export type EndKind = 'mate' | 'stalemate' | 'repetition' | 'insufficient' | 'fifty' | 'resign' | 'agreed'

export interface GameEnd {
  result: GameResult
  kind: EndKind
}

// Fin lue sur l'échiquier, ou null si la partie continue. Aucun plafond de coups : seules les
// règles du jeu arrêtent la partie.
export function boardEnd(c: Chess): GameEnd | null {
  if (c.isCheckmate()) return { result: c.turn() === 'w' ? '0-1' : '1-0', kind: 'mate' }
  if (c.isStalemate()) return { result: '1/2-1/2', kind: 'stalemate' }
  if (c.isThreefoldRepetition()) return { result: '1/2-1/2', kind: 'repetition' }
  if (c.isInsufficientMaterial()) return { result: '1/2-1/2', kind: 'insufficient' }
  if (c.isDrawByFiftyMoves()) return { result: '1/2-1/2', kind: 'fifty' }
  return null
}

export function resignEnd(player: Color): GameEnd {
  return { result: player === 'w' ? '0-1' : '1-0', kind: 'resign' }
}

function scoreFor(result: GameResult, player: Color): 1 | 0.5 | 0 {
  if (result === '1/2-1/2') return 0.5
  return (result === '1-0') === (player === 'w') ? 1 : 0
}

// Objectif gain : il faut gagner. Objectif nulle : la nulle suffit, gagner aussi.
export function judge(end: GameEnd, player: Color, objective: Objective): 'success' | 'fail' | null {
  if (!objective) return null
  const score = scoreFor(end.result, player)
  return (objective === 'win' ? score === 1 : score >= 0.5) ? 'success' : 'fail'
}

// Titre et motif du verdict. `playerMoves` : nombre de coups joués par le joueur.
export function verdictText(end: GameEnd, player: Color, objective: Objective, playerMoves: number): { title: string; reason: string } {
  const verdict = judge(end, player, objective)
  const score = scoreFor(end.result, player)
  const title =
    verdict === 'success' ? 'Objectif atteint'
    : verdict === 'fail' ? 'Objectif manqué'
    : score === 1 ? 'Victoire' : score === 0 ? 'Défaite' : 'Nulle'
  const reason =
    end.kind === 'mate' ? (score === 1 ? `Mat en ${playerMoves} coup${playerMoves > 1 ? 's' : ''}.` : 'Tu es mat.')
    : end.kind === 'stalemate' ? 'Nulle par pat.'
    : end.kind === 'repetition' ? 'Nulle par triple répétition.'
    : end.kind === 'insufficient' ? 'Nulle : plus assez de matériel pour mater.'
    : end.kind === 'fifty' ? 'Nulle par la règle des 50 coups.'
    : end.kind === 'resign' ? 'Tu as abandonné.'
    : 'Nulle acceptée par Stockfish.'
  return { title, reason }
}

// Proposition de nulle, jouée au trait du joueur : `cp`/`mate` sont donc de SON point de vue.
// Stockfish accepte s'il ne s'estime pas mieux que +0,30 : joueur à -0,30 ou mieux, ou mat
// en faveur du joueur.
export function engineAcceptsDraw(cp: number | null, mate: number | null): boolean {
  if (mate !== null) return mate > 0
  return (cp ?? 0) >= -30
}

// Demi-coups sans prise ni coup de pion (règle des 50 coups : nulle à 100).
export function halfmoveClock(fen: string): number {
  return +(fen.split(' ')[4] ?? 0) || 0
}

// Rejoue les coups sur la position de départ : l'historique reste complet, la triple
// répétition et la règle des 50 coups restent justes après une restauration.
export function replay(startFen: string, uci: string[]): Chess {
  const c = new Chess(startFen)
  for (const m of uci) {
    try {
      c.move({ from: m.slice(0, 2), to: m.slice(2, 4), promotion: m[4] })
    } catch {
      break
    }
  }
  return c
}

// Nombre d'occurrences de la position courante dans la partie (pièces, trait, roques, prise en
// passant : les quatre premiers champs de la FEN). 3 = nulle par répétition.
export function repetitions(c: Chess): number {
  const key = (fen: string) => fen.split(' ').slice(0, 4).join(' ')
  const history = c.history({ verbose: true })
  const fens = history.length ? [history[0].before, ...history.map((m) => m.after)] : [c.fen()]
  const now = key(c.fen())
  return fens.filter((f) => key(f) === now).length
}

// FEN jouable contre le moteur : acceptée par chess.js, et camp qui n'est pas au trait hors
// d'échec (chess.js ne le vérifie pas ; Stockfish répond alors « bestmove (none) »).
export function validFen(fen: string): boolean {
  try {
    const f = new Chess(fen).fen().split(' ')
    const flipped = [f[0], f[1] === 'w' ? 'b' : 'w', f[2], '-', f[4], f[5]].join(' ')
    return !new Chess(flipped).inCheck()
  } catch {
    return false
  }
}

// ---------- Persistance ----------

// Une seule partie gardée : la dernière jouée, finale ou position libre. localStorage et non
// sessionStorage : une PWA iOS tuée puis relancée ouvre une nouvelle session. Clé purgée par la
// réinitialisation (APP_LOCAL_KEYS de backup.ts).
export const POSITION_GAME_KEY = 'chess-local-position-game-v1'

export interface StoredGame {
  key: string // `finale:<id>` ou `position`
  startFen: string
  player: Color
  label: string | null
  uci: string[]
  end: GameEnd | null
  assisted: boolean // indice ou coup repris
  recorded?: boolean // résultat de la tentative déjà noté
  back?: unknown // partie libre : state de navigation qui rouvre l'analyse d'origine
}

// Partie en cours (non terminée, au moins un coup) de cette finale, telle que la liste l'annonce.
export function inProgressKey(): string | null {
  const g = loadStoredGame()
  return g && !g.end && g.uci.length > 0 ? `${g.key}|${g.startFen}` : null
}

export function loadStoredGame(): StoredGame | null {
  try {
    const raw = localStorage.getItem(POSITION_GAME_KEY)
    if (!raw) return null
    const g = JSON.parse(raw) as StoredGame
    if (typeof g?.key !== 'string' || !validFen(g.startFen) || !Array.isArray(g.uci)) return null
    return g
  } catch {
    return null
  }
}

export function storeGame(g: StoredGame) {
  try {
    localStorage.setItem(POSITION_GAME_KEY, JSON.stringify(g))
  } catch {}
}
