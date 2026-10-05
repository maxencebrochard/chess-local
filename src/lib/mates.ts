// « Mats éclair » (/mats) : catalogue des exercices, viviers de positions, records.
// Contre la montre : positions vérifiées sur les tables de finales (src/data/mateDrills.json,
// scripts/prepare-mates.py). Mat en N, géométrie, motifs : puzzles lichess de public/puzzles.json
// (géométrie : index hors ligne src/data/mateIndex.json, scripts/prepare-mates-index.mjs).
// Records : une ligne `learnSessions` par série (domaine `mats`), sans nouvelle table.
import { Chess } from 'chess.js'
import drillsData from '../data/mateDrills.json'
import mateIndex from '../data/mateIndex.json'
import type { PuzzleData } from '../components/PuzzlePlayer'
import { db } from './db'
import type { GeoTag } from './mateNet'
import { puzzleThemeLabel } from './puzzleThemes'

export type Section = 'chrono' | 'mateIn' | 'geo' | 'motif'
export type ChronoPattern = 'kq' | 'kr' | 'krr' | 'kqr' | 'kbb' | 'kbn' | 'kqp' | 'kp'
export type Cadence = '15s' | '30s' | '60s' | '120s' | '3min' | '5min' | 'survie'

export interface Drill {
  id: string // clé stable des records : ne jamais renommer
  section: Section
  title: string
  glyph: string
  principle: string // le principe nommé, en une phrase
  text: string // méthode (contre la montre) ou définition (motif)
  lessonFen?: string // position de mat type (vérifiée par la suite E2E)
  pattern?: ChronoPattern | 'mix'
  mateIn?: 1 | 2 | 3 | 'mix'
  geo?: GeoTag
  theme?: string // thème lichess
  defaultCadence: Cadence
}

export const CHRONO_CADENCES: Cadence[] = ['15s', '30s', '60s', '120s']
export const RUSH_CADENCES: Cadence[] = ['3min', '5min', 'survie']
export const CADENCE_LABEL: Record<Cadence, string> = {
  '15s': '15 s', '30s': '30 s', '60s': '1 min', '120s': '2 min', '3min': '3 min', '5min': '5 min', survie: 'Survie',
}
export const CADENCE_MS: Record<Cadence, number | null> = {
  '15s': 15_000, '30s': 30_000, '60s': 60_000, '120s': 120_000, '3min': 180_000, '5min': 300_000, survie: null,
}

const chrono = (pattern: ChronoPattern | 'mix', title: string, glyph: string, principle: string, text: string, lessonFen: string | undefined, defaultCadence: Cadence): Drill => ({
  id: `chrono-${pattern}`, section: 'chrono', pattern, title, glyph, principle, text, lessonFen, defaultCadence,
})

export const DRILLS: Drill[] = [
  chrono('kq', 'Dame', '♕',
    'La dame enferme le roi sur le bord, ton roi vient en appui.',
    'Réduis la boîte du roi avec la dame placée à un saut de cavalier de lui. Quand il est sur la bande, rapproche ton roi : mat sur la rangée avec les rois face à face, ou mat au contact, la dame protégée par ton roi. Tant que tu ne donnes pas échec, laisse-lui toujours une case : sinon c\'est pat.',
    '1k1Q4/8/1K6/8/8/8/8/8 b - - 0 1', '30s'),
  chrono('kr', 'Tour', '♖',
    'La tour coupe le roi, les rois face à face, la tour donne l\'échec sur la bande.',
    'La tour coupe le roi adverse sur une rangée ou une colonne, ton roi monte en opposition. Échec de tour quand les rois se font face : le roi adverse recule d\'une ligne. S\'ils ne se font pas face, un coup d\'attente de la tour sur sa ligne force l\'opposition.',
    '3k3R/8/3K4/8/8/8/8/8 b - - 0 1', '60s'),
  chrono('krr', 'Deux tours', '♖♖',
    'Escalier : une tour tient la ligne voisine, l\'autre donne l\'échec sur la ligne du roi.',
    'Mat de l\'escalier : une tour coupe une rangée, l\'autre donne l\'échec sur la suivante, puis elles alternent jusqu\'au bord. Garde-les loin du roi adverse, sinon il les attaque. Ton roi n\'est pas nécessaire.',
    '1R4k1/R7/8/8/8/8/8/6K1 b - - 0 1', '15s'),
  chrono('kqr', 'Dame + tour', '♕♖',
    'Escalier : la dame et la tour sur deux lignes voisines, chacune garde la sienne.',
    'Le même escalier qu\'avec deux tours, en plus rapide : la dame et la tour alternent sur deux lignes voisines jusqu\'au bord. Garde la tour loin du roi adverse.',
    'Q5k1/1R6/8/8/8/8/8/6K1 b - - 0 1', '15s'),
  chrono('kbb', 'Deux fous', '♗♗',
    'Les deux fous côte à côte forment un mur en diagonale, ton roi pousse.',
    'Les deux fous sur des diagonales voisines forment un mur que le roi ne traverse pas. Rétrécis la zone avec ton roi en appui, pousse le roi adverse dans un coin, et les fous donnent les derniers échecs. Gare au pat dans le coin.',
    'k7/2B5/1K6/3B4/8/8/8/8 b - - 0 1', '60s'),
  chrono('kbn', 'Fou + cavalier', '♗♘',
    'Le mat n\'est forcé que dans un coin de la couleur du fou.',
    'Le cavalier et le roi ferment les cases que le fou ne voit pas. Pousse le roi adverse vers un coin de la couleur de ton fou ; s\'il file vers l\'autre coin, ramène-le le long du bord, le cavalier en W. Les positions de départ sont déjà avancées : le roi est près du bord.',
    'k7/3N4/1K6/3B4/8/8/8/8 b - - 0 1', '120s'),
  chrono('kqp', 'Dame + pion', '♕♙',
    'Avec une dame, mate d\'abord ; le pion peut tenir une case ou protéger la dame.',
    'Le pion change peu de chose : mate avec la dame et le roi, ou promeus si c\'est plus rapide. Un pion qui protège la dame au contact suffit à mater. Avant chaque coup, compte les cases du roi adverse : zéro case sans échec, c\'est pat.',
    'k7/1Q6/2P5/8/8/8/8/4K3 b - - 0 1', '30s'),
  chrono('kp', 'Promotion puis mat', '=♕',
    'Le roi devant le pion, promotion en dame, puis le mat dame + roi.',
    'Escorte le pion avec ton roi devant lui et prends l\'opposition pour écarter le roi adverse. Promeus en dame, puis mate comme avec dame + roi. Toutes les positions sont gagnantes (vérifiées sur les tables de finales).',
    '1k1Q4/8/1K6/8/8/8/8/8 b - - 0 1', '60s'),
  chrono('mix', 'Mélange', '🎲',
    'Un schéma différent à chaque mat : reconnais-le au premier coup d\'œil.',
    'Toutes les finales élémentaires mélangées, comme en partie : identifie le matériel, puis applique sa méthode sans réfléchir.',
    undefined, '60s'),

  ...([1, 2, 3] as const).map((n): Drill => ({
    id: `mate-${n}`, section: 'mateIn', mateIn: n, title: `Mat en ${n}`, glyph: `#${n}`,
    principle: n === 1 ? 'Un coup, le mat : cherche d\'abord les échecs.' : `La suite exacte en ${n} coups : échecs, captures, menaces, dans cet ordre.`,
    text: 'Puzzles lichess avec peu de matériel (12 pièces au plus, rois compris), comme en fin de partie de bullet. La difficulté monte avec ton score. Tout mat immédiat compte.',
    defaultCadence: '3min',
  })),
  {
    id: 'mate-mix', section: 'mateIn', mateIn: 'mix', title: 'Mélange', glyph: '#?', defaultCadence: '3min',
    principle: 'Mat en 1, 2 ou 3, sans savoir lequel : comme en partie.',
    text: 'Puzzles lichess avec peu de matériel (12 pièces au plus, rois compris). La difficulté monte avec ton score.',
  },

  geo('escalier', 'Escalier', '▤', '1R4k1/R7/8/8/8/8/8/6K1 b - - 0 1',
    'Deux pièces lourdes sur deux lignes voisines : l\'une coupe, l\'autre donne l\'échec.',
    'Tours ou dame + tour sur deux rangées (ou colonnes) qui se touchent : la pièce de derrière tient la ligne voisine, celle de devant donne l\'échec sur la ligne du roi. Mat sur le bord, ou là où ses pièces bloquent le reste.'),
  geo('batterie-diagonale', 'Batterie en diagonale', '⟋', '5rk1/5ppQ/8/8/8/3B4/8/6K1 b - - 0 1',
    'La dame et le fou alignés sur la même diagonale : la dame mate au contact, le fou la soutient.',
    'Dame et fou sur la même diagonale (b1-h7 vers le petit roque, par exemple) : la dame entre au contact du roi, le fou derrière elle la protège. Le roi ne peut pas la prendre.'),
  geo('batterie-ligne', 'Batterie en ligne', '⏐', '6k1/5pQp/8/8/8/8/8/6RK b - - 0 1',
    'La dame et la tour alignées sur la même colonne ou rangée : la dame mate au contact, la tour la soutient.',
    'Dame et tour sur la même colonne (ou rangée) : la dame avance au contact du roi, la tour derrière elle la protège. Deux tours doublées font le même travail.'),
  geo('diagonale-ligne', 'Diagonale + ligne', '✕', '7k/7p/8/4Q3/8/8/8/6RK b - - 0 1',
    'La tour coupe la colonne, la dame donne l\'échec en diagonale (ou l\'inverse).',
    'Les deux géométries se complètent : une pièce donne l\'échec par une diagonale, une autre ferme les cases de fuite par une colonne ou une rangée. Regarde quelles cases chaque ligne tient.'),
  geo('contact', 'Dame au contact', '♕', '6k1/5pQp/5Bp1/8/8/8/8/6K1 b - - 0 1',
    'La dame mate à côté du roi, protégée : le roi ne peut pas la prendre.',
    'Le mat le plus fréquent : la dame se colle au roi et couvre presque toutes ses cases. Il lui faut un soutien (roi, pion, fou, cavalier, tour) : sans lui, le roi la prend.'),

  motif('backRankMate', '♜', 'Le roi est maté sur sa première rangée, où ses propres pièces l\'enferment.'),
  motif('smotheredMate', '♞', 'Le cavalier mate un roi entouré de ses propres pièces.'),
  motif('anastasiaMate', '♞♜', 'Un cavalier et une tour (ou dame) piègent le roi entre le bord et une de ses propres pièces.'),
  motif('bodenMate', '♝♝', 'Deux fous sur des diagonales croisées matent un roi bloqué par ses propres pièces.'),
  motif('arabianMate', '♞♜', 'Un cavalier et une tour s\'associent pour piéger le roi dans un coin.'),
  {
    id: 'motif-damiano', section: 'motif', geo: 'damiano', title: 'Mat de Damiano', glyph: '♛♟', defaultCadence: '3min',
    lessonFen: '5rk1/7Q/6P1/8/8/8/8/6K1 b - - 0 1',
    principle: 'La dame mate au contact sur la colonne du bord, protégée par un pion.',
    text: 'Publié par Pedro Damiano en 1512 : le pion (en g6 contre un petit roque) soutient la dame qui entre en h7. Positions trouvées par la géométrie du mat final (pas de thème lichess pour ce mat).',
  },
  motif('epauletteMate', '♛', 'Deux cases de fuite parallèles, de part et d\'autre du roi, sont occupées par ses propres pièces.'),
  motif('hookMate', '♜♞♙', 'Une tour, un cavalier et un pion matent ensemble ; un pion du roi maté lui bloque une fuite.'),
  motif('dovetailMate', '♛', 'La dame mate au contact ; les deux seules cases de fuite sont occupées par les pièces du roi.'),
  motif('operaMate', '♜♝', 'La tour donne l\'échec, un fou la protège.'),
  motif('pillsburysMate', '♜♝', 'La tour donne le mat, le fou enferme le roi.'),
  motif('morphysMate', '♝♜', 'Le fou donne le mat, la tour enferme le roi.'),
  motif('doubleBishopMate', '♝♝', 'Deux fous sur des diagonales voisines matent un roi bloqué par ses propres pièces.'),
  motif('cornerMate', '♜♞', 'Le roi enfermé dans le coin par une tour ou une dame, un cavalier participe au mat.'),
]

function geo(tag: GeoTag, title: string, glyph: string, lessonFen: string, principle: string, text: string): Drill {
  return { id: `geo-${tag}`, section: 'geo', geo: tag, title, glyph, lessonFen, principle, text, defaultCadence: '3min' }
}

function motif(theme: string, glyph: string, principle: string): Drill {
  return {
    id: `motif-${theme}`, section: 'motif', theme, title: puzzleThemeLabel(theme), glyph, principle, defaultCadence: '3min',
    text: 'Puzzles lichess de ce motif, les plus épurés d\'abord (le moins de pièces possible).',
  }
}

export function drillById(id: string): Drill | undefined {
  return DRILLS.find((d) => d.id === id)
}

export const SECTIONS: { id: Section; title: string; subtitle: string }[] = [
  { id: 'chrono', title: 'Contre la montre', subtitle: 'Mate Stockfish avant la chute du drapeau.' },
  { id: 'mateIn', title: 'Mat en N', subtitle: 'Série chronométrée, trois erreurs et c\'est fini.' },
  { id: 'geo', title: 'Géométrie du mat', subtitle: 'Voir comment les pièces se complètent : lignes, colonnes, diagonales.' },
  { id: 'motif', title: 'Motifs de mat', subtitle: 'Un motif, des dizaines de positions : jusqu\'au réflexe.' },
]

// ---------- Viviers ----------

export interface ChronoPosition {
  fen: string
  mateIn: number // mat le plus court (tables de finales), camp fort au trait
  pattern: ChronoPattern
}

const DRILL_DATA = drillsData as { patterns: Record<ChronoPattern, { fen: string; mateIn: number }[]> }

export function chronoPool(pattern: ChronoPattern | 'mix'): ChronoPosition[] {
  const keys = pattern === 'mix' ? (Object.keys(DRILL_DATA.patterns) as ChronoPattern[]) : [pattern]
  return keys.flatMap((k) => (DRILL_DATA.patterns[k] ?? []).map((p) => ({ ...p, pattern: k })))
}

export function chronoTitle(pattern: ChronoPattern): string {
  return drillById(`chrono-${pattern}`)?.title ?? pattern
}

// Pièces sur l'échiquier, rois compris.
export function pieceCount(fen: string): number {
  return fen.split(' ')[0].replace(/[^a-zA-Z]/g, '').length
}

const LOW_MATERIAL = 12
const MOTIF_THRESHOLDS = [12, 16, 20, 24, 32]
const MIN_POOL = 40

const poolCache = new Map<string, PuzzleData[]>()

// Puzzles d'un exercice, triés par classement (la série monte en difficulté).
export function puzzlePool(drill: Drill, all: PuzzleData[]): PuzzleData[] {
  const cached = poolCache.get(drill.id)
  if (cached) return cached
  let pool: PuzzleData[] = []
  if (drill.section === 'mateIn') {
    const themes = drill.mateIn === 'mix' ? ['mateIn1', 'mateIn2', 'mateIn3'] : [`mateIn${drill.mateIn}`]
    pool = all.filter((p) => p.themes.some((t) => themes.includes(t)) && pieceCount(p.fen) <= LOW_MATERIAL)
  } else if (drill.geo) {
    const ids = new Set((mateIndex as Record<string, string[]>)[drill.geo] ?? [])
    pool = all.filter((p) => ids.has(p.id))
  } else if (drill.theme) {
    const withTheme = all.filter((p) => p.themes.includes(drill.theme!))
    const limit = MOTIF_THRESHOLDS.find((k) => withTheme.filter((p) => pieceCount(p.fen) <= k).length >= MIN_POOL) ?? 32
    pool = withTheme.filter((p) => pieceCount(p.fen) <= limit)
  }
  pool = [...pool].sort((a, b) => a.rating - b.rating)
  poolCache.set(drill.id, pool)
  return pool
}

// Puzzle suivant : la cible monte dans le vivier trié avec le score, au hasard autour d'elle.
export function pickPuzzle(pool: PuzzleData[], score: number, used: Set<string>): PuzzleData | undefined {
  const free = pool.filter((p) => !used.has(p.id))
  if (free.length === 0) return undefined
  const q = Math.min(0.9, score * 0.035)
  const center = Math.floor(q * (free.length - 1))
  const lo = Math.max(0, center - 8)
  const hi = Math.min(free.length, center + 9)
  return free[lo + Math.floor(Math.random() * (hi - lo))]
}

// Position finale de la ligne principale d'un puzzle (diagramme de la fiche d'un motif).
export function puzzleFinalFen(p: PuzzleData): string | null {
  try {
    const c = new Chess(p.fen)
    for (const m of p.moves) c.move({ from: m.slice(0, 2), to: m.slice(2, 4), promotion: m[4] })
    return c.isCheckmate() ? c.fen() : null
  } catch {
    return null
  }
}

// ---------- Records (learnSessions, domaine `mats`) ----------

export const MATS_DOMAIN = 'mats'

export function runKey(drillId: string, cadence: Cadence): string {
  return `${drillId}:${cadence}`
}

export interface RunStats {
  best: number
  runs: number
  last: number[] // scores des dernières séries, de la plus ancienne à la plus récente
}

export interface MatsStats {
  byKey: Record<string, RunStats>
  totalMates: number
  totalRuns: number
}

export async function loadMatsStats(): Promise<MatsStats> {
  const rows = await db.learnSessions.where('domain').equals(MATS_DOMAIN).sortBy('date')
  const byKey: Record<string, RunStats> = {}
  let totalMates = 0
  for (const r of rows) {
    const score = typeof r.score === 'number' ? r.score : 0
    totalMates += score
    const s = (byKey[r.itemId] ??= { best: 0, runs: 0, last: [] })
    s.best = Math.max(s.best, score)
    s.runs += 1
    s.last = [...s.last, score].slice(-10)
  }
  return { byKey, totalMates, totalRuns: rows.length }
}

// Meilleur score d'un exercice et sa cadence (affichés sur sa carte), null s'il n'a jamais été joué.
export function drillBest(stats: MatsStats | null, drillId: string): { best: number; cadence: Cadence } | null {
  if (!stats) return null
  let out: { best: number; cadence: Cadence } | null = null
  for (const [k, s] of Object.entries(stats.byKey)) {
    const [id, cadence] = k.split(':')
    if (id === drillId && (out === null || s.best > out.best) && cadence in CADENCE_MS) out = { best: s.best, cadence: cadence as Cadence }
  }
  return out
}

// Une ligne par série, écrite dès le premier mat puis mise à jour : une PWA tuée en arrière-plan
// ne perd pas sa série. Écritures chaînées, jamais deux `add` pour la même série.
export class RunRecorder {
  private id: number | null = null
  private chain: Promise<unknown> = Promise.resolve()
  private readonly itemId: string

  constructor(itemId: string) {
    this.itemId = itemId
  }

  save(score: number): Promise<unknown> {
    this.chain = this.chain.then(async () => {
      const row = { date: Date.now(), domain: MATS_DOMAIN, itemId: this.itemId, success: (score > 0 ? 1 : 0) as 0 | 1, ratingAfter: null, score }
      if (this.id === null) this.id = (await db.learnSessions.add(row)) as number
      else await db.learnSessions.update(this.id, { score, success: row.success })
    }).catch(() => {})
    return this.chain
  }

  // Fin de série : écrit le score (sauf série arrêtée à zéro par le joueur, qui n'en est pas une)
  // et dit s'il bat le record, relu en base au moment de la fin (jamais un record périmé).
  async finish(score: number, keepEmpty: boolean): Promise<boolean> {
    if (score === 0 && !keepEmpty && this.id === null) return false
    await this.save(score)
    const rows = await db.learnSessions.where('domain').equals(MATS_DOMAIN).toArray()
    const previous = rows.filter((r) => r.itemId === this.itemId && r.id !== this.id).map((r) => r.score ?? 0)
    return score > Math.max(0, ...previous)
  }
}

// ---------- Préférences (localStorage, clé propre, hors sauvegarde) ----------

const PREFS_KEY = 'chess-local-mats'

interface Prefs {
  cadence: Record<string, Cadence>
  showNet: boolean
}

export function readPrefs(): Prefs {
  try {
    const raw = JSON.parse(localStorage.getItem(PREFS_KEY) ?? '{}') as Partial<Prefs>
    return { cadence: raw.cadence ?? {}, showNet: raw.showNet ?? true }
  } catch {
    return { cadence: {}, showNet: true }
  }
}

export function writePrefs(p: Prefs) {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(p))
  } catch {}
}
