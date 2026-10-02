// Entraîneur d'ouvertures (/ouvertures) : familles, arbre des variantes et progression.
// Sans React. Les lignes viennent de src/data/openings.json (lichess) ; une « variante » est
// une feuille de l'arbre préfixe de sa famille. Limite connue : un arbre préfixe ignore les
// transpositions (un autre ordre de coups vers la même position n'est pas reconnu).
import openingsData from '../data/openings.json'
import { db } from './db'
import type { EngineLine } from './engine'
import { openingFamilyFr, openingFr } from './openingNames'

export interface OpeningLine {
  eco: string
  name: string
  uci: string
}

export type Color = 'w' | 'b'
export type DrillMode = 'next' | 'suite' | 'full'

export const MODE_LABEL: Record<DrillMode, string> = {
  next: 'Prochain coup',
  suite: 'Suite',
  full: 'Variante complète',
}

export interface Variant {
  line: OpeningLine
  moves: string[] // UCI
  label: string // nom FR sans le préfixe de famille
}

export interface Family {
  key: string // nom lichess de la famille, ex. "Scotch Game"
  label: string // nom FR, ex. "Partie écossaise"
  lines: OpeningLine[]
  variants: Variant[]
  mainLine: OpeningLine // la plus courte ligne : « ligne mère » affichée sur la fiche
  defaultColor: Color
  named: Set<string> // UCI des lignes nommées de la famille
  index: { text: string; label: string }[] // noms normalisés (EN + FR) des lignes, pour la recherche
}

const ALL = openingsData as OpeningLine[]

// Les lignes « London System » sont rangées par lichess sous plusieurs familles
// (Queen's Pawn Game, Indian Defense...) : la famille Londres les regroupe par le nom.
const BY_NAME: Record<string, (name: string) => boolean> = {
  'London System': (n) => n.includes('London System'),
}

// Ordre d'affichage des « plus courantes ».
export const POPULAR_KEYS = [
  'Sicilian Defense', 'French Defense', 'Caro-Kann Defense', 'Scandinavian Defense', 'Ruy Lopez',
  'Italian Game', 'Scotch Game', "Queen's Gambit", "King's Indian Defense", 'Slav Defense',
  'Nimzo-Indian Defense', 'London System', 'English Opening', "Petrov's Defense", 'Pirc Defense',
  'Alekhine Defense', 'Vienna Game', "King's Gambit", 'Grünfeld Defense', 'Dutch Defense', 'Catalan Opening',
]

// Famille d'un nom lichess : avant « : » et « , », suffixes Accepted/Declined retirés
// (« Queen's Gambit Declined » rejoint « Queen's Gambit »).
export function familyKey(name: string): string {
  return name.split(':')[0].split(',')[0].trim().replace(/ (Accepted|Declined)$/, '')
}

export function normalize(s: string): string {
  return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
}

export function uciMoves(uci: string): string[] {
  return uci ? uci.split(' ') : []
}

// Camp qui « choisit » l'ouverture : une défense se joue avec les Noirs, un système, une partie,
// une attaque ou un début avec les Blancs ; sinon (gambits, noms propres) la parité de la ligne
// mère dit qui a joué le dernier coup (Benko, letton, Englund : Noirs).
function defaultColorOf(key: string, mainLine: OpeningLine): Color {
  if (/Defen[cs]e/.test(key)) return 'b'
  if (/System|Game|Attack|Opening/.test(key)) return 'w'
  return uciMoves(mainLine.uci).length % 2 === 1 ? 'w' : 'b'
}

function buildFamily(key: string, lines: OpeningLine[]): Family {
  const label = openingFamilyFr(key)
  const ucis = lines.map((l) => l.uci)
  const variants = lines
    .filter((l) => !ucis.some((u) => u !== l.uci && u.startsWith(l.uci + ' ')))
    .map((line) => ({ line, moves: uciMoves(line.uci), label: variantLabel(line.name, label) }))
    .sort((a, b) => a.label.localeCompare(b.label, 'fr') || a.moves.length - b.moves.length)
  // À longueur égale, l'ordre lichess (par code ECO) départage.
  const mainLine = lines.reduce((best, l) => (uciMoves(l.uci).length < uciMoves(best.uci).length ? l : best))
  const names = [...new Set(lines.map((l) => l.name))]
  return {
    key,
    label,
    lines,
    variants,
    mainLine,
    defaultColor: defaultColorOf(key, mainLine),
    named: new Set(ucis),
    index: names.map((n) => ({ text: normalize(`${n} | ${openingFr(n)}`), label: openingFr(n) })),
  }
}

// Nom de variante sans la famille : « Partie écossaise · Gambit Göring » -> « Gambit Göring ».
export function variantLabel(name: string, familyLabel: string): string {
  const fr = openingFr(name)
  if (fr.startsWith(familyLabel + ' · ')) return fr.slice(familyLabel.length + 3)
  return fr
}

let cache: Map<string, Family> | null = null

export function families(): Map<string, Family> {
  if (cache) return cache
  const groups = new Map<string, OpeningLine[]>()
  for (const l of ALL) {
    const k = familyKey(l.name)
    if (!groups.has(k)) groups.set(k, [])
    groups.get(k)!.push(l)
  }
  for (const [k, match] of Object.entries(BY_NAME)) {
    groups.set(k, ALL.filter((l) => match(l.name)))
  }
  cache = new Map([...groups].map(([k, lines]) => [k, buildFamily(k, lines)]))
  return cache
}

export function getFamily(key: string): Family | null {
  return families().get(key) ?? null
}

export function popularFamilies(): Family[] {
  return POPULAR_KEYS.map((k) => getFamily(k)).filter((f): f is Family => f !== null)
}

export interface SearchHit {
  family: Family
  via: string | null // variante qui a fait remonter la famille (null : le nom de famille correspond)
}

// Familles dont le nom correspond d'abord, puis celles dont une variante correspond.
export function searchFamilies(query: string): SearchHit[] {
  const q = normalize(query.trim())
  if (!q) return []
  const all = [...families().values()]
  const size = (a: SearchHit, b: SearchHit) => b.family.variants.length - a.family.variants.length
  const byName: SearchHit[] = []
  const byLine: SearchHit[] = []
  for (const family of all) {
    if (normalize(`${family.label} | ${family.key}`).includes(q)) {
      byName.push({ family, via: null })
      continue
    }
    const hit = family.index.find((e) => e.text.includes(q))
    if (hit) byLine.push({ family, via: hit.label })
  }
  return [...byName.sort(size), ...byLine.sort(size)]
}

// ---------- Arbre ----------

// Coups théoriques de la famille après `prefix`, du plus fourni au moins fourni (nombre de
// lignes de la branche), avec la ligne nommée la plus courte de chaque branche (pour annoncer
// « Cf3 (Variante X) »).
export function familyContinuations(fam: Family, prefix: string[]): { move: string; line: OpeningLine; count: number }[] {
  const n = prefix.length
  const key = prefix.join(' ')
  const best = new Map<string, { line: OpeningLine; count: number }>()
  for (const l of fam.lines) {
    const mv = uciMoves(l.uci)
    if (mv.length <= n || (n > 0 && !l.uci.startsWith(key + ' '))) continue
    const cur = best.get(mv[n])
    if (!cur) best.set(mv[n], { line: l, count: 1 })
    else {
      cur.count++
      if (l.uci.length < cur.line.uci.length) cur.line = l
    }
  }
  return [...best].map(([move, b]) => ({ move, ...b })).sort((a, b) => b.count - a.count)
}

// Nom de la position : la plus longue ligne de la famille qui en est un préfixe.
export function positionName(fam: Family, moves: string[]): OpeningLine | null {
  for (let n = moves.length; n > 0; n--) {
    const key = moves.slice(0, n).join(' ')
    if (fam.named.has(key)) return fam.lines.find((l) => l.uci === key) ?? null
  }
  return null
}

// Premier demi-coup où la ligne est « dans » l'ouverture (préfixe nommé de la famille), ou -1.
function entryPly(fam: Family, moves: string[]): number {
  for (let n = 1; n <= moves.length; n++) if (fam.named.has(moves.slice(0, n).join(' '))) return n
  return -1
}

const isPlayerTurn = (ply: number, color: Color) => (ply % 2 === 0) === (color === 'w')

// Positions de « Prochain coup » : déjà dans l'ouverture (une ligne nommée de la famille en est
// le préfixe), trait au joueur, au moins un coup théorique de la famille ensuite.
export function nextMovePositions(fam: Family, color: Color): string[][] {
  const seen = new Set<string>()
  const out: string[][] = []
  for (const l of fam.lines) {
    const mv = uciMoves(l.uci)
    const entry = entryPly(fam, mv)
    if (entry < 0) continue
    for (let n = entry; n < mv.length; n++) {
      const key = mv.slice(0, n).join(' ')
      if (!isPlayerTurn(n, color) || seen.has(key)) continue
      seen.add(key)
      out.push(mv.slice(0, n))
    }
  }
  return out
}

// Coups du joueur dans une variante.
export function playerMoveCount(v: Variant, color: Color): number {
  return v.moves.filter((_, i) => isPlayerTurn(i, color)).length
}

// Départs possibles de « Suite » dans `moves` (limité à `limit` demi-coups) : trait au joueur,
// dans l'ouverture, avec `count` coups du joueur encore dans la ligne.
function suiteStarts(fam: Family, moves: string[], color: Color, count: number, limit: number): number[] {
  const entry = entryPly(fam, moves)
  if (entry < 0) return []
  const out: number[] = []
  for (let n = entry; n < limit; n++) {
    // Le dernier coup demandé (index n + 2 * (count - 1)) doit exister dans la ligne.
    if (isPlayerTurn(n, color) && n + 2 * count - 1 <= limit) out.push(n)
  }
  return out
}

// Tirage de « Suite » : une variante qui contient `count` coups du joueur après l'entrée dans
// l'ouverture si la famille en a, sinon départ au plus tôt dans l'ouverture.
export function pickSuite(
  fam: Family, color: Color, count: number, limit: number | null, progress: Progress, exclude?: Variant,
): { variant: Variant; start: number } {
  const lim = (v: Variant) => Math.min(v.moves.length, limit ?? Infinity)
  const ok = fam.variants.filter((v) => v !== exclude && suiteStarts(fam, v.moves, color, count, lim(v)).length > 0)
  if (ok.length) {
    const variant = pickFrom(ok, color, progress)
    const starts = suiteStarts(fam, variant.moves, color, count, lim(variant))
    return { variant, start: starts[Math.floor(Math.random() * starts.length)] }
  }
  const variant = pickVariant(fam, color, progress, exclude)
  const entry = Math.max(0, entryPly(fam, variant.moves))
  const start = isPlayerTurn(entry, color) ? entry : entry + 1
  // Aucun coup du joueur après l'entrée : la suite part du début de la ligne.
  return { variant, start: start < variant.moves.length ? start : color === 'w' ? 0 : 1 }
}

// ---------- Stockfish ----------

// Score d'une ligne pour le camp au trait : un mat pour lui bat tout score en centipawns.
export function lineScore(l: EngineLine): number {
  if (l.scoreMate !== null) return l.scoreMate > 0 ? 100000 - l.scoreMate : -100000 - l.scoreMate
  return l.scoreCp ?? 0
}

// Tolérance pour un « autre bon coup » selon Stockfish (même recherche, même trait).
export const ENGINE_TOLERANCE_CP = 30

// ---------- Progression (table learnSessions, domaine 'opening-drill') ----------

export const DRILL_DOMAIN = 'opening-drill'

export function drillItemId(mode: DrillMode, color: Color, moves: string[]): string {
  return `${mode}:${color}:${moves.join(' ')}`
}

export interface Progress {
  last: Map<string, 0 | 1> // itemId -> dernier résultat
  rows: { itemId: string; success: 0 | 1 }[] // toutes les tentatives, dans l'ordre
}

export type VariantStatus = 'mastered' | 'review' | 'new'

export async function loadProgress(): Promise<Progress> {
  const rows = await db.learnSessions.where('domain').equals(DRILL_DOMAIN).sortBy('date')
  const last = new Map<string, 0 | 1>()
  for (const r of rows) last.set(r.itemId, r.success)
  return { last, rows: rows.map((r) => ({ itemId: r.itemId, success: r.success })) }
}

export const EMPTY_PROGRESS: Progress = { last: new Map(), rows: [] }

export function variantStatus(progress: Progress, color: Color, v: Variant): VariantStatus {
  const s = progress.last.get(drillItemId('full', color, v.moves))
  return s === undefined ? 'new' : s === 1 ? 'mastered' : 'review'
}

// Réussites d'un mode pour une famille et un camp (toutes tentatives).
export function modeStats(progress: Progress, fam: Family, color: Color, mode: DrillMode): { ok: number; total: number } {
  const prefix = `${mode}:${color}:`
  let ok = 0
  let total = 0
  const lines = fam.lines
  for (const r of progress.rows) {
    if (!r.itemId.startsWith(prefix)) continue
    const uci = r.itemId.slice(prefix.length)
    // Une position `next` appartient à la famille si une ligne de la famille la prolonge.
    const inFamily = mode === 'next'
      ? lines.some((l) => l.uci.startsWith(uci + ' '))
      : fam.variants.some((v) => v.line.uci === uci)
    if (!inFamily) continue
    total++
    ok += r.success
  }
  return { ok, total }
}

export async function recordDrill(mode: DrillMode, color: Color, moves: string[], success: boolean): Promise<void> {
  await db.learnSessions.add({
    date: Date.now(),
    domain: DRILL_DOMAIN,
    itemId: drillItemId(mode, color, moves),
    success: success ? 1 : 0,
    ratingAfter: null,
  })
}

// Tirage pondéré : priorité aux variantes à revoir et nouvelles, et à celles où le joueur a au
// moins 3 coups à jouer (1.e4 c5 2.b3 n'apprend rien aux Noirs).
function pickFrom(pool: Variant[], color: Color, progress: Progress): Variant {
  const meaty = pool.filter((v) => playerMoveCount(v, color) >= 3)
  const base = meaty.length ? meaty : pool
  const todo = base.filter((v) => variantStatus(progress, color, v) !== 'mastered')
  const from = todo.length && Math.random() < 0.85 ? todo : base
  return from[Math.floor(Math.random() * from.length)]
}

// Variante suivante, jamais la même (ni une homonyme) deux fois de suite quand il y a le choix.
export function pickVariant(fam: Family, color: Color, progress: Progress, exclude?: Variant): Variant {
  const pool = fam.variants.filter((v) => v !== exclude && v.label !== exclude?.label)
  return pickFrom(pool.length ? pool : fam.variants, color, progress)
}
