// Partie contre Stockfish depuis une position (finales jouées jusqu'au bout, ou position
// quelconque venue de l'analyse) : thème d'une finale, fin de partie lue sur l'échiquier,
// verdict selon l'objectif, persistance de la partie pour survivre à un rechargement.
import { Chess } from 'chess.js'
import { db } from './db'
import type { EndgameGoal } from './learn'

export type Color = 'w' | 'b'
// Objectif du joueur : gagner, tenir la nulle, ou tenir face à une attaque (`hold`, entraîneur de
// défense : HOLD_MOVES coups sans que l'éval passe sous le plancher). `null` : partie libre.
export type Objective = 'win' | 'draw' | 'hold' | null
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

// `decisive` : partie conclue par le joueur sur un avantage décisif tenu (entraîneur d'attaque).
// `held` / `collapsed` : objectif « tenir » atteint ou perdu (entraîneur de défense), hors échiquier.
export type EndKind = 'mate' | 'stalemate' | 'repetition' | 'insufficient' | 'fifty' | 'resign' | 'agreed' | 'decisive' | 'held' | 'collapsed'

// Éval du joueur (de SON point de vue) qui a décidé d'une fin `held` ou `collapsed`.
export interface EndEval {
  cp: number | null
  mate: number | null
}

export interface GameEnd {
  result: GameResult
  kind: EndKind
  eval?: EndEval // `held` / `collapsed` seulement
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

export function decisiveEnd(player: Color): GameEnd {
  return { result: player === 'w' ? '1-0' : '0-1', kind: 'decisive' }
}

// Avantage décisif : éval du joueur (à son trait, donc de SON point de vue) au moins `thresholdCp`,
// ou mat en sa faveur. Retourne la série de tours consécutifs au-dessus du seuil.
export function decisiveStreak(prev: number, cp: number | null, mate: number | null, thresholdCp: number): number {
  const decisive = mate !== null ? mate > 0 : cp !== null && cp >= thresholdCp
  return decisive ? prev + 1 : 0
}
// Tours consécutifs au-dessus du seuil pour proposer de conclure : l'avantage doit tenir.
export const DECISIVE_TURNS = 2

// ---------- Objectif « tenir » (entraîneur de défense) ----------

// Réussite : HOLD_MOVES coups du joueur, éval de confirmation au moins au plancher sans mat contre
// lui. Échec : éval strictement sous le plancher (ou mat contre lui) DECISIVE_TURNS tours de suite.
export const HOLD_MOVES = 12
export const HOLD_FLOOR_CP = -300

export interface HoldRule {
  moves: number
  floorCp: number
}

// Série de tours où l'éval du joueur (à son trait, de son point de vue) est strictement sous le
// plancher, ou un mat contre lui : `decisiveStreak` vu de l'attaquant (éval inversée, seuil
// `-floorCp + 1` en centipions entiers, donc « strictement sous le plancher » pour le joueur).
export function holdStreak(prev: number, cp: number | null, mate: number | null, floorCp: number): number {
  return decisiveStreak(prev, cp === null ? null : -cp, mate === null ? null : -mate, -floorCp + 1)
}

// Éval de confirmation, du point de vue du joueur : tient s'il reste au plancher ou au-dessus, sans
// mat contre lui (un mat en sa faveur tient).
export function holdsAt(cp: number | null, mate: number | null, floorCp: number): boolean {
  if (mate !== null) return mate > 0
  return cp !== null && cp >= floorCp
}

// Fins hors échiquier de l'objectif « tenir ». `held` porte un résultat nul (le joueur n'a ni gagné
// ni perdu la partie, il a tenu) ; `collapsed` est une défaite.
export function heldEnd(evalAt: EndEval): GameEnd {
  return { result: '1/2-1/2', kind: 'held', eval: evalAt }
}

export function collapsedEnd(player: Color, evalAt: EndEval): GameEnd {
  return { result: player === 'w' ? '0-1' : '1-0', kind: 'collapsed', eval: evalAt }
}

// « -1,2 », « +0,4 », « mat en 3 contre toi » : éval lisible du joueur.
export function evalText(e: EndEval | undefined): string {
  if (!e) return 'éval inconnue'
  if (e.mate !== null) return e.mate > 0 ? `mat en ${e.mate} pour toi` : `mat en ${-e.mate} contre toi`
  const v = (e.cp ?? 0) / 100
  return `éval ${v > 0 ? '+' : v < 0 ? '-' : ''}${Math.abs(v).toFixed(1).replace('.', ',')}`
}

function scoreFor(result: GameResult, player: Color): 1 | 0.5 | 0 {
  if (result === '1/2-1/2') return 0.5
  return (result === '1-0') === (player === 'w') ? 1 : 0
}

// Objectif gain : il faut gagner. Objectif nulle : la nulle suffit, gagner aussi. Objectif tenir :
// `held`, une nulle de l'échiquier ou un gain ; `collapsed`, un mat subi ou un abandon échouent.
export function judge(end: GameEnd, player: Color, objective: Objective): 'success' | 'fail' | null {
  if (!objective) return null
  const score = scoreFor(end.result, player)
  if (objective === 'hold') {
    if (end.kind === 'held') return 'success'
    if (end.kind === 'collapsed' || end.kind === 'resign') return 'fail'
    return score >= 0.5 ? 'success' : 'fail'
  }
  return (objective === 'win' ? score === 1 : score >= 0.5) ? 'success' : 'fail'
}

// Titre et motif du verdict. `playerMoves` : nombre de coups joués par le joueur.
export function verdictText(end: GameEnd, player: Color, objective: Objective, playerMoves: number): { title: string; reason: string } {
  const verdict = judge(end, player, objective)
  const score = scoreFor(end.result, player)
  if (objective === 'hold') {
    const s = playerMoves > 1 ? 's' : ''
    const moves = `${playerMoves} coup${s}`
    const reason =
      end.kind === 'held' ? `Tu as tenu ${moves} : ${evalText(end.eval)}.`
      : end.kind === 'collapsed' ? `L'attaque a percé après ${moves} tenu${s} : ${evalText(end.eval)}.`
      : end.kind === 'mate' ? (score === 1 ? `Mat en ${moves} : la contre-attaque a gagné.` : `Tu es mat après ${moves}.`)
      : end.kind === 'resign' ? `Tu as abandonné après ${moves}.`
      : end.kind === 'stalemate' ? 'Nulle par pat.'
      : end.kind === 'repetition' ? 'Nulle par triple répétition.'
      : end.kind === 'insufficient' ? 'Nulle : plus assez de matériel pour mater.'
      : end.kind === 'fifty' ? 'Nulle par la règle des 50 coups.'
      : 'Nulle acceptée par Stockfish.'
    return { title: verdict === 'success' ? 'Défense réussie' : 'La défense a cédé', reason }
  }
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
    : end.kind === 'decisive' ? 'Avantage décisif : l\'attaque a porté.'
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

// Adversaire bridé (entraîneur d'attaque) : options UCI posées sur le moteur qui joue, libellé de
// la ligne moteur, Elo gardé avec la partie persistée (null = pleine force).
export interface Opponent {
  options: Record<string, string | number | boolean>
  label: string
  level: number | null
}

// ---------- Persistance ----------

// Une seule partie gardée : la dernière jouée, finale, position d'attaque ou position libre. localStorage et non
// sessionStorage : une PWA iOS tuée puis relancée ouvre une nouvelle session. Clé purgée par la
// réinitialisation (APP_LOCAL_KEYS de backup.ts).
export const POSITION_GAME_KEY = 'chess-local-position-game-v1'

export interface StoredGame {
  key: string // `finale:<id>`, `attaque:<id>`, `defense:<id>`, `defense-ratee:<id>` ou `position`
  startFen: string
  player: Color
  label: string | null
  uci: string[]
  end: GameEnd | null
  assisted: boolean // indice ou coup repris
  recorded?: boolean // résultat de la tentative déjà noté
  back?: unknown // partie libre : state de navigation qui rouvre l'analyse d'origine
  // Entraîneurs d'attaque, de défense et de conversion : Elo de l'adversaire bridé de cette partie
  // (le défenseur pour l'attaque et la conversion, l'attaquant pour la défense), null = pleine force.
  level?: number | null
  // Entraîneurs d'attaque et de conversion : avantage décisif atteint (`offered` : choix Continuer/Conclure affiché,
  // `continued` : le joueur poursuit, plus de proposition).
  decisive?: 'offered' | 'continued'
  // Entraîneur de défense : série de tours sous le plancher, et dernier demi-coup évalué. Rejouée
  // à la reprise : un rechargement n'efface pas un premier tour déjà sous le plancher.
  holdFall?: { count: number; ply: number }
}

// Partie en cours (non terminée, au moins un coup) de cette finale ou position d'attaque, telle que la liste l'annonce.
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

// Partie persistée que cette position reprend : même clé, même FEN de départ, et pas terminée
// sauf si `restoreFinished` (retour de l'analyse).
export function resumedGame(key: string, startFen: string, restoreFinished: boolean): StoredGame | null {
  const g = loadStoredGame()
  return g && g.key === key && g.startFen === startFen && (!g.end || restoreFinished) ? g : null
}

export function storeGame(g: StoredGame) {
  try {
    localStorage.setItem(POSITION_GAME_KEY, JSON.stringify(g))
    return true
  } catch {
    return false
  }
}
