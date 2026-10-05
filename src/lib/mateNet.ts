// Réseau de mat : géométrie exacte d'une position de mat, calculée sur l'échiquier.
// Qui donne l'échec et par quelle ligne, quelles cases de fuite du roi sont couvertes (par quelle
// pièce, par quelle rangée, colonne ou diagonale) ou bloquées par ses propres pièces, qui protège
// la pièce au contact. Les phrases et les étiquettes de coordination (escalier, batteries...) sont
// déduites de ces faits seulement : elles ne peuvent pas affirmer ce que l'échiquier ne montre pas.
import { Chess, type Square } from 'chess.js'
import type { BoardArrow } from '../components/Board'

type Color = 'w' | 'b'
type PieceType = 'p' | 'n' | 'b' | 'r' | 'q' | 'k'
export type LineKind = 'rangée' | 'colonne' | 'diagonale' | 'cavalier' | 'pion' | 'roi'

export interface Cover {
  from: Square
  type: PieceType
  kind: LineKind
}

export interface Flight {
  square: Square
  blockedBy: PieceType | null // pièce du roi maté qui occupe la case
  covers: Cover[] // pièces du camp qui mate qui contrôlent la case (roi maté retiré de l'échiquier)
}

export type GeoTag = 'escalier' | 'batterie-diagonale' | 'batterie-ligne' | 'diagonale-ligne' | 'contact' | 'damiano'

export interface MateNet {
  king: Square
  mated: Color
  checks: Cover[]
  flights: Flight[]
  tags: GeoTag[]
}

const FILES = 'abcdefgh'
const sq = (f: number, r: number) => `${FILES[f]}${r + 1}` as Square
const fileOf = (s: string) => s.charCodeAt(0) - 97
const rankOf = (s: string) => Number(s[1]) - 1

type Grid = (({ type: PieceType; color: Color }) | null)[][] // [file][rank]

function gridOf(chess: Chess): Grid {
  const g: Grid = Array.from({ length: 8 }, () => Array<null>(8).fill(null))
  for (const row of chess.board()) {
    for (const p of row) if (p) g[fileOf(p.square)][rankOf(p.square)] = { type: p.type, color: p.color }
  }
  return g
}

// La pièce en `from` attaque-t-elle `to` ? `empty` : case traitée comme vide (le roi maté, pour
// voir la case derrière lui sur la ligne d'échec). Retourne la ligne d'attaque ou null.
function attackKind(g: Grid, from: string, to: string, empty: string | null): LineKind | null {
  const p = g[fileOf(from)][rankOf(from)]
  if (!p || from === to) return null
  const df = fileOf(to) - fileOf(from)
  const dr = rankOf(to) - rankOf(from)
  const adf = Math.abs(df)
  const adr = Math.abs(dr)
  switch (p.type) {
    case 'k':
      return adf <= 1 && adr <= 1 ? 'roi' : null
    case 'n':
      return (adf === 1 && adr === 2) || (adf === 2 && adr === 1) ? 'cavalier' : null
    case 'p':
      return adf === 1 && dr === (p.color === 'w' ? 1 : -1) ? 'pion' : null
  }
  const straight = df === 0 || dr === 0
  const diagonal = adf === adr
  if (straight && p.type === 'b') return null
  if (diagonal && p.type === 'r') return null
  if (!straight && !diagonal) return null
  const sf = Math.sign(df)
  const sr = Math.sign(dr)
  for (let f = fileOf(from) + sf, r = rankOf(from) + sr; f !== fileOf(to) || r !== rankOf(to); f += sf, r += sr) {
    if (g[f][r] && sq(f, r) !== empty) return null
  }
  return diagonal ? 'diagonale' : dr === 0 ? 'rangée' : 'colonne'
}

function attackersOf(g: Grid, target: string, color: Color, empty: string | null): Cover[] {
  const out: Cover[] = []
  for (let f = 0; f < 8; f++) {
    for (let r = 0; r < 8; r++) {
      const p = g[f][r]
      if (!p || p.color !== color) continue
      const kind = attackKind(g, sq(f, r), target, empty)
      if (kind) out.push({ from: sq(f, r), type: p.type, kind })
    }
  }
  return out
}

// Null si la position n'est pas un mat.
export function analyseMate(fen: string): MateNet | null {
  let chess: Chess
  try {
    chess = new Chess(fen)
  } catch {
    return null
  }
  if (!chess.isCheckmate()) return null
  const mated = chess.turn()
  const mater: Color = mated === 'w' ? 'b' : 'w'
  const g = gridOf(chess)
  let king = 'a1' as Square
  for (let f = 0; f < 8; f++) for (let r = 0; r < 8; r++) {
    const p = g[f][r]
    if (p && p.type === 'k' && p.color === mated) king = sq(f, r)
  }
  const checks = attackersOf(g, king, mater, null)
  const flights: Flight[] = []
  for (let df = -1; df <= 1; df++) {
    for (let dr = -1; dr <= 1; dr++) {
      const f = fileOf(king) + df
      const r = rankOf(king) + dr
      if ((df === 0 && dr === 0) || f < 0 || f > 7 || r < 0 || r > 7) continue
      const p = g[f][r]
      const s = sq(f, r)
      if (p && p.color === mated) flights.push({ square: s, blockedBy: p.type, covers: [] })
      else flights.push({ square: s, blockedBy: null, covers: attackersOf(g, s, mater, king) })
    }
  }
  return { king, mated, checks, flights, tags: tagsOf(g, king, mated, checks, flights) }
}

const HEAVY = (t: PieceType) => t === 'r' || t === 'q'
const LINE = (k: LineKind) => k === 'rangée' || k === 'colonne'
const adjacent = (a: string, b: string) => Math.abs(fileOf(a) - fileOf(b)) <= 1 && Math.abs(rankOf(a) - rankOf(b)) <= 1

function tagsOf(g: Grid, king: Square, mated: Color, checks: Cover[], flights: Flight[]): GeoTag[] {
  const tags: GeoTag[] = []
  // Cases de fuite vides seulement : protéger la pièce au contact n'est pas fermer une ligne.
  const covers = flights
    .filter((fl) => !g[fileOf(fl.square)][rankOf(fl.square)])
    .flatMap((fl) => fl.covers.map((c) => ({ ...c, target: fl.square })))

  // Escalier : une pièce lourde donne l'échec sur une rangée (ou colonne), une autre pièce lourde
  // tient la rangée (ou colonne) voisine, depuis cette ligne même.
  const ladder = checks.some((c) =>
    HEAVY(c.type) && LINE(c.kind) && covers.some((v) => {
      if (v.from === c.from || !HEAVY(v.type) || v.kind !== c.kind) return false
      return c.kind === 'rangée'
        ? Math.abs(rankOf(v.from) - rankOf(king)) === 1 && rankOf(v.target) === rankOf(v.from)
        : Math.abs(fileOf(v.from) - fileOf(king)) === 1 && fileOf(v.target) === fileOf(v.from)
    }),
  )
  if (ladder) tags.push('escalier')

  // Batterie : la pièce qui mate au contact est soutenue par une pièce alignée avec elle sur une
  // ligne qu'elles parcourent toutes les deux (dame en h7 soutenue par le fou d3 : batterie de la
  // diagonale b1-h7). Sans ce soutien, le roi la prendrait : la batterie fait le mat.
  for (const c of checks) {
    if (!adjacent(c.from, king)) continue
    for (const v of attackersOf(g, c.from, mated === 'w' ? 'b' : 'w', null)) {
      if (v.kind === 'diagonale' && (v.type === 'b' || v.type === 'q') && (c.type === 'b' || c.type === 'q')) tags.push('batterie-diagonale')
      if (LINE(v.kind) && HEAVY(v.type) && HEAVY(c.type)) tags.push('batterie-ligne')
    }
  }

  // Diagonale + ligne : l'échec par une diagonale et une case de fuite tenue par une rangée ou
  // colonne (ou l'inverse), par une autre pièce.
  const crossed = checks.some((c) =>
    covers.some((v) => v.from !== c.from && (
      (c.kind === 'diagonale' && HEAVY(v.type) && LINE(v.kind))
      || (LINE(c.kind) && (v.type === 'b' || v.type === 'q') && v.kind === 'diagonale')
    )),
  )
  if (crossed) tags.push('diagonale-ligne')

  // Dame au contact : elle mate à côté du roi, protégée (sinon il la prendrait).
  const contact = checks.find((c) => c.type === 'q' && adjacent(c.from, king))
  if (contact) {
    tags.push('contact')
    // Damiano, géométrie exacte : roi sur sa 1re rangée, dame sur la colonne du bord (a ou h) en
    // 7e rangée relative, protégée par un pion sur la colonne voisine (b ou g) en 6e.
    const guards = flights.find((fl) => fl.square === contact.from)?.covers ?? []
    const rel = (s: string) => (mated === 'b' ? rankOf(s) : 7 - rankOf(s)) // 7 = 1re rangée du roi maté
    const qf = fileOf(contact.from)
    const edge = qf === 0 || qf === 7
    const pawn = guards.find((v) => v.type === 'p' && Math.abs(fileOf(v.from) - qf) === 1 && rel(v.from) === 5)
    if (rel(king) === 7 && edge && rel(contact.from) === 6 && pawn) tags.push('damiano')
  }
  return [...new Set(tags)]
}

// ---------- Rendu : phrases et dessin ----------

const NAME: Record<PieceType, [string, string]> = {
  q: ['La', 'dame'], r: ['La', 'tour'], b: ['Le', 'fou'], n: ['Le', 'cavalier'], p: ['Le', 'pion'], k: ['Le', 'roi'],
}
const NAME_OBJ: Record<PieceType, string> = { q: 'la dame', r: 'la tour', b: 'le fou', n: 'le cavalier', p: 'le pion', k: 'le roi' }

export function pieceLabel(type: PieceType, square: string): string {
  const [art, noun] = NAME[type]
  return `${art} ${noun} ${square}`
}

function listFr(items: string[]): string {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} et ${items[items.length - 1]}`
}

function ordinal(rank: number): string {
  return rank === 1 ? '1re' : `${rank}e`
}

// Diagonale nommée par ses deux extrémités (« la diagonale b1-h7 »).
function diagonalName(a: string, b: string): string {
  const sf = Math.sign(fileOf(b) - fileOf(a))
  const sr = Math.sign(rankOf(b) - rankOf(a))
  const end = (s: number) => {
    let f = fileOf(a)
    let r = rankOf(a)
    while (f + s * sf >= 0 && f + s * sf < 8 && r + s * sr >= 0 && r + s * sr < 8) {
      f += s * sf
      r += s * sr
    }
    return { f, r }
  }
  const [p, q] = [end(-1), end(1)].sort((x, y) => x.f - y.f)
  return `la diagonale ${sq(p.f, p.r)}-${sq(q.f, q.r)}`
}

function lineName(from: string, to: string, kind: LineKind): string {
  if (kind === 'rangée') return `la ${ordinal(rankOf(from) + 1)} rangée`
  if (kind === 'colonne') return `la colonne ${from[0]}`
  return diagonalName(from, to)
}

const CHECK_PHRASE: Record<LineKind, string> = {
  rangée: 'sur la rangée', colonne: 'sur la colonne', diagonale: 'en diagonale', cavalier: '', pion: '', roi: '',
}

export interface NetPiece {
  square: Square
  type: PieceType
  color: string // couleur du dessin et de la légende
  checking: boolean
  sentence: string
}

export interface NetView {
  pieces: NetPiece[]
  blocked: string | null // phrase sur les cases bloquées par les pièces du roi maté
  arrows: BoardArrow[]
  marks: Record<string, string>
}

const CHECK_COLOR = 'rgba(220, 38, 38, 0.9)'
const PALETTE = ['#3b82f6', '#f59e0b', '#a855f7', '#06b6d4', '#ec4899', '#84cc16']
const BLOCKED_MARK = 'rgba(0, 0, 0, 0.42)'

function withAlpha(hex: string, a: number): string {
  const n = parseInt(hex.slice(1), 16)
  return `rgba(${n >> 16}, ${(n >> 8) & 255}, ${n & 255}, ${a})`
}

export function netView(net: MateNet, fen: string): NetView {
  const chess = new Chess(fen)
  const occupant = (s: string) => chess.get(s as Square)
  // Pièces du camp qui mate impliquées : celles qui donnent l'échec d'abord, puis par case.
  const order: Square[] = []
  for (const c of net.checks) if (!order.includes(c.from)) order.push(c.from)
  for (const fl of net.flights) for (const c of fl.covers) if (!order.includes(c.from)) order.push(c.from)

  const pieces: NetPiece[] = []
  const arrows: BoardArrow[] = []
  const marks: Record<string, string> = {}
  order.forEach((from, i) => {
    const color = PALETTE[i % PALETTE.length]
    const check = net.checks.find((c) => c.from === from)
    const type = (check?.type ?? net.flights.flatMap((f) => f.covers).find((c) => c.from === from)!.type)
    const parts: string[] = []
    if (check) {
      const slider = check.kind === 'rangée' || check.kind === 'colonne' || check.kind === 'diagonale'
      const how = adjacent(from, net.king) && slider ? 'au contact' : slider ? `sur ${lineName(from, net.king, check.kind)}` : CHECK_PHRASE[check.kind]
      parts.push(`donne l'échec${how ? ` ${how}` : ''}`)
      arrows.push({ startSquare: from, endSquare: net.king, color: CHECK_COLOR })
    }
    // Cases tenues, groupées par ligne ; une case occupée par une pièce amie est « protégée ».
    const covered = net.flights.flatMap((fl) => fl.covers.filter((c) => c.from === from).map((c) => ({ ...c, target: fl.square })))
    const free = covered.filter((c) => !occupant(c.target))
    const guarded = covered.filter((c) => occupant(c.target))
    const groups = new Map<string, string[]>()
    for (const c of free) {
      const key = c.kind === 'rangée' || c.kind === 'colonne' || c.kind === 'diagonale' ? lineName(from, c.target, c.kind) : ''
      groups.set(key, [...(groups.get(key) ?? []), c.target])
    }
    // Ligne de l'échec à distance : déjà nommée, seules ses cases sont citées.
    const checkLine = check && (check.kind === 'rangée' || check.kind === 'colonne' || check.kind === 'diagonale') && !adjacent(from, net.king)
      ? lineName(from, net.king, check.kind)
      : null
    const coverTexts = [...groups.entries()].map(([line, squares]) =>
      line === checkLine ? `${listFr(squares)} sur cette ligne` : line ? `${line} (${listFr(squares)})` : listFr(squares))
    // Groupes séparés par « , plus » : un seul « et » par liste de cases.
    if (coverTexts.length) parts.push(`${check ? 'couvre aussi' : 'couvre'} ${coverTexts.join(', plus ')}`)
    for (const c of guarded) {
      const target = occupant(c.target)!
      parts.push(`protège ${NAME_OBJ[target.type as PieceType]} ${c.target}`)
    }
    // Flèches : une par ligne tenue, jusqu'à la case la plus lointaine de cette ligne.
    const far = new Map<string, string>()
    for (const c of covered) {
      if (c.kind !== 'rangée' && c.kind !== 'colonne' && c.kind !== 'diagonale') continue
      const key = `${Math.sign(fileOf(c.target) - fileOf(from))},${Math.sign(rankOf(c.target) - rankOf(from))}`
      const prev = far.get(key)
      const dist = (s: string) => Math.max(Math.abs(fileOf(s) - fileOf(from)), Math.abs(rankOf(s) - rankOf(from)))
      if (!prev || dist(c.target) > dist(prev)) far.set(key, c.target)
    }
    for (const target of far.values()) {
      const onCheckLine = check && arrows.some((a) => a.startSquare === from && sameRay(from, a.endSquare, target))
      if (!onCheckLine) arrows.push({ startSquare: from, endSquare: target, color: withAlpha(color, 0.8) })
    }
    for (const c of free) marks[c.target] ??= withAlpha(color, 0.5)
    pieces.push({ square: from, type, color, checking: !!check, sentence: `${pieceLabel(type, from)} ${listFr(parts)}.` })
  })

  const blockedSquares = net.flights.filter((fl) => fl.blockedBy).map((fl) => fl.square)
  for (const s of blockedSquares) marks[s] = BLOCKED_MARK
  const blocked = blockedSquares.length
    ? `${blockedSquares.length > 1 ? 'Ses propres pièces bloquent' : 'Une de ses propres pièces bloque'} ${listFr(blockedSquares)}.`
    : null
  return { pieces, blocked, arrows, marks }
}

// `b` et `c` sont-elles sur le même rayon partant de `a` ?
function sameRay(a: string, b: string, c: string): boolean {
  const s = (x: string) => `${Math.sign(fileOf(x) - fileOf(a))},${Math.sign(rankOf(x) - rankOf(a))}`
  return s(b) === s(c)
}

// Principe en une ligne, à partir des étiquettes et des échecs.
export const TAG_PRINCIPLE: Record<GeoTag, string> = {
  escalier: 'Escalier : une pièce lourde tient la ligne voisine, l\'autre donne l\'échec sur la ligne du roi.',
  'batterie-diagonale': 'Batterie en diagonale : la pièce qui mate et un fou ou une dame alignés sur la même diagonale, celle de derrière soutient celle de devant.',
  'batterie-ligne': 'Batterie en ligne : la pièce qui mate et une tour ou une dame alignées sur la même colonne ou rangée, celle de derrière soutient celle de devant.',
  'diagonale-ligne': 'Diagonale + ligne : l\'échec vient d\'une diagonale, une autre pièce ferme les cases par une ligne droite (ou l\'inverse).',
  contact: 'Dame au contact : elle mate à côté du roi parce qu\'une autre pièce la protège.',
  damiano: 'Mat de Damiano : la dame mate au contact sur la colonne du bord, protégée par un pion.',
}

export function principleOf(net: MateNet): string {
  for (const t of ['escalier', 'damiano', 'batterie-diagonale', 'batterie-ligne', 'diagonale-ligne', 'contact'] as GeoTag[]) {
    if (net.tags.includes(t)) return TAG_PRINCIPLE[t]
  }
  const c = net.checks[0]
  if (!c) return ''
  const blocked = net.flights.filter((f) => f.blockedBy).length
  const pieces = new Set([...net.checks, ...net.flights.flatMap((f) => f.covers)].map((v) => v.from)).size
  if (blocked > 0 && blocked * 2 >= net.flights.length) {
    return `Le roi est enfermé par ses propres pièces : ${NAME_OBJ[c.type]} n'a plus qu'à donner l'échec.`
  }
  return pieces > 1
    ? `Réseau à ${pieces} pièces : chaque case de fuite est tenue${blocked ? ' ou bloquée' : ''}.`
    : blocked
      ? 'Une seule pièce tient l\'échec et les cases de fuite libres.'
      : 'Une seule pièce tient l\'échec et toutes les cases de fuite.'
}
