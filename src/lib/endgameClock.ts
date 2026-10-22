// « Finales au chrono » (/finales/chrono) : finales théoriques à gagner ou à tenir nulle contre
// Stockfish pleine force, avec très peu de temps, pour la fin de partie de bullet.
// Banque : src/data/endgameClock.json (scripts/prepare-endgame-clock.py, verdicts des tables de
// finales lichess). Logique pure ici : cadences, ordre des séries, verdicts.
// Séries : une ligne `learnSessions` par série (domaine `endgame-clock`, RunRecorder de mates.ts).
import { Chess } from 'chess.js'
import data from '../data/endgameClock.json'
import type { EndgameGoal } from './learn'
import { boardEnd, verdictText, type Color, type GameEnd } from './positionGame'

export const ENDGAME_CLOCK_DOMAIN = 'endgame-clock'
// Cadence choisie : convenance locale, hors sauvegarde, purgée par la réinitialisation.
export const ENDGAME_CLOCK_PREFS_KEY = 'chess-local-endgame-clock'

export interface ClockPosition {
  id: string
  fen: string
  line: string[] // ligne optimale des tables (contrôle des seuils par la suite E2E)
}

export interface ClockFamily {
  id: string // clé stable des records : ne jamais renommer
  title: string
  objective: 'win' | 'draw'
  goal: EndgameGoal
  difficulty: number
  principle: string
  positions: ClockPosition[]
}

export const FAMILIES = (data as { families: ClockFamily[] }).families

export function familyById(id: string): ClockFamily | undefined {
  return FAMILIES.find((f) => f.id === id)
}

export function familyOf(positionId: string): ClockFamily | undefined {
  return FAMILIES.find((f) => f.positions.some((p) => p.id === positionId))
}

// ---------- Cadences ----------

export const BASES_S = [15, 30, 60] as const
export const INCREMENTS_S = [0, 1, 2] as const
export type BaseS = (typeof BASES_S)[number]
export type IncrementS = (typeof INCREMENTS_S)[number]

export interface ClockCadence {
  baseS: BaseS
  incS: IncrementS
}

export const DEFAULT_CADENCE: ClockCadence = { baseS: 30, incS: 0 }

// Clé des records : `15+0`, `30+1`, `60+2`.
export function cadenceKey(c: ClockCadence): string {
  return `${c.baseS}+${c.incS}`
}

export function parseCadence(key: string): ClockCadence | null {
  const m = /^(\d+)\+(\d+)$/.exec(key)
  if (!m) return null
  const baseS = Number(m[1]) as BaseS
  const incS = Number(m[2]) as IncrementS
  return BASES_S.includes(baseS) && INCREMENTS_S.includes(incS) ? { baseS, incS } : null
}

export function baseLabel(s: number): string {
  return s >= 60 ? `${s / 60} min` : `${s} s`
}

// « 15 s », « 30 s | 1 », « 1 min | 2 » : la notation des cadences de Jouer.
export function cadenceLabel(c: ClockCadence): string {
  return c.incS ? `${baseLabel(c.baseS)} | ${c.incS}` : baseLabel(c.baseS)
}

// Série : une famille, ou toutes mélangées.
export const MIX = 'mix'

export function recordKey(serie: string, c: ClockCadence): string {
  return `${serie}:${cadenceKey(c)}`
}

// ---------- Ordre des séries ----------

function shuffle<T>(arr: T[], random: () => number): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

// Tour de série : une famille, ses variantes mélangées ; le mélange, toutes les positions par
// difficulté croissante, mélangées à difficulté égale. Rejoué quand il est épuisé.
export function seriesRound(serie: string, random: () => number = Math.random): ClockPosition[] {
  if (serie !== MIX) return shuffle(familyById(serie)?.positions ?? [], random)
  const tiers = [...new Set(FAMILIES.map((f) => f.difficulty))].sort((a, b) => a - b)
  return tiers.flatMap((d) => shuffle(FAMILIES.filter((f) => f.difficulty === d).flatMap((f) => f.positions), random))
}

// ---------- Verdicts ----------

// Coups du joueur à tenir pour réussir une nulle sans fin de partie par les règles.
export const HOLD_MOVES = 15
// Nulle tenue : la recherche du moteur (camp fort, à son trait) ne voit ni mat ni plus de +1,50.
export const HOLD_MAX_CP = 150
// Gain devenu nul : le moteur (défenseur, à son trait) ne s'estime pas plus bas que -0,50 pendant
// WIN_DRAWN_TURNS réponses de suite.
export const WIN_DRAWN_CP = 50
export const WIN_DRAWN_TURNS = 3
// Les verdicts moteur (tenue, gain envolé) viennent d'une recherche distincte du coup joué, à
// nœuds fixes et table de hachage vidée : même score sur iPhone, sous charge et dans la suite E2E,
// qui la rejoue sur toutes les lignes optimales de la banque (pire nulle +63, pire gain +170).
export const VERDICT_NODES = 100_000

// Score d'une recherche du moteur, de SON point de vue (camp au trait de la position cherchée).
export interface EngineScore {
  cp: number | null
  mate: number | null
}

const VALUE: Record<string, number> = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 }

interface Material {
  total: number
  pieces: number // hors pions
  heavy: boolean // dame ou tour
  queen: boolean
  bare: boolean // roi seul
}

function material(fen: string, color: Color): Material {
  let total = 0
  let pieces = 0
  let heavy = false
  let queen = false
  let count = 0
  for (const ch of fen.split(' ')[0]) {
    if (!/[a-z]/i.test(ch)) continue
    const mine = color === 'w' ? ch === ch.toUpperCase() : ch === ch.toLowerCase()
    const t = ch.toLowerCase()
    if (!mine || t === 'k') continue
    count++
    total += VALUE[t]
    if (t !== 'p') pieces += VALUE[t]
    if (t === 'q' || t === 'r') heavy = true
    if (t === 'q') queen = true
  }
  return { total, pieces, heavy, queen, bare: count === 0 }
}

export type Verdict = { success: boolean; reason: string; end: GameEnd | null }

// Verdict lu sur l'échiquier après un coup (du joueur ou du moteur), ou null si la série continue
// sur cette position. Les fins par les règles passent d'abord ; la conversion d'un gain ne se lit
// qu'au trait du joueur, une fois la réponse du moteur jouée (la pièce promue a survécu).
// `playerMoves` : coups du joueur sur la position (texte du mat).
export function judgeBoard(c: Chess, player: Color, objective: 'win' | 'draw', startFen: string, playerMoves: number): Verdict | null {
  const end = boardEnd(c)
  if (end) {
    const { reason } = verdictText(end, player, objective, playerMoves)
    const won = end.kind === 'mate' && c.turn() !== player
    const success = objective === 'win' ? won : end.kind !== 'mate' || won
    return { success, reason: success || end.kind === 'mate' ? reason : `${reason} Il fallait gagner.`, end }
  }
  if (objective !== 'win' || c.turn() !== player) return null
  const opp: Color = player === 'w' ? 'b' : 'w'
  const mine = material(c.fen(), player)
  const theirs = material(c.fen(), opp)
  // Promotion en dame d'abord (roi et pion contre roi : le roi adverse est nu dès le départ).
  const start = material(startFen, player)
  const promoted = mine.queen && mine.pieces > start.pieces
  if (promoted && mine.total - theirs.total >= 3) return { success: true, reason: 'Promotion réussie : la dame tient, le gain est acquis.', end: null }
  if (theirs.bare && mine.heavy) return { success: true, reason: 'Matériel adverse raflé : le mat est une formalité.', end: null }
  return null
}

// Nulle tenue : assez de coups joués et le moteur, à son trait, ne voit rien de décisif.
export function holdReached(playerMoves: number, engine: EngineScore | null): boolean {
  if (playerMoves < HOLD_MOVES || !engine) return false
  if (engine.mate !== null) return engine.mate < 0
  return (engine.cp ?? 0) < HOLD_MAX_CP
}

// Réponses de suite où le gain semble envolé (le défenseur, à son trait, tient l'équilibre).
export function drawnStreak(prev: number, engine: EngineScore | null): number {
  if (!engine || engine.mate !== null || engine.cp === null) return 0
  return engine.cp >= -WIN_DRAWN_CP ? prev + 1 : 0
}

// « 12,3 s »
export function secondsLabel(ms: number): string {
  return `${(Math.max(0, ms) / 1000).toFixed(1).replace('.', ',')} s`
}

// Ce qui conclut la position, affiché sous la pendule.
export const CLOCK_HINT: Record<EndgameGoal, string> = {
  mate: 'Mate le roi adverse.',
  promote: 'Promeus ton pion en dame : elle doit survivre à la réponse.',
  capture: 'Rafle le matériel adverse en gardant ta dame ou ta tour.',
  hold: `Obtiens la nulle, ou tiens ${HOLD_MOVES} coups sans rien lâcher.`,
}
