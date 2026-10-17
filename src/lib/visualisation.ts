// Entraîneur « Calcul et visualisation » (/visualisation) : logique pure, chess.js seul.
// Une position montrée, une ligne de N demi-coups annoncée sans bouger les pièces, puis une question
// sur la position finale imaginée. La banque (src/data/visualisation.json) vient des puzzles lichess,
// générée et vérifiée par scripts/prepare-visualisation.py (meilleur coup confirmé par Stockfish 18).
// Les questions et leurs réponses se calculent ici, recoupées par l'oracle python-chess de
// e2e/test_visualisation.py.
import { Chess, type Color, type PieceSymbol, type Square } from 'chess.js'
import { db } from './db'
import { figurine } from './review'

export const VIS_DOMAIN = 'visualisation'
export const LEVELS = [2, 4, 6, 8] as const
export type Level = (typeof LEVELS)[number]
export type DisplayMode = 'visible' | 'flash'
export const DISPLAY_LABEL: Record<DisplayMode, string> = { visible: 'Ligne visible', flash: 'Un par un' }
export const MAX_ERRORS = 3

export interface VisItem {
  id: string // id du puzzle lichess
  fen: string // position montrée (après l'amorce), le camp du puzzle a le trait
  last: string // amorce (UCI), surlignée comme dernier coup
  line: string[] // N demi-coups (UCI)
  best: string // meilleur coup de la position finale (UCI), confirmé par Stockfish
  rating: number
}

export interface VisBank {
  version: 1
  levels: Record<string, VisItem[]>
}

// Chunk séparé : la banque ne se charge que sur la page.
export async function loadBank(): Promise<VisBank> {
  return (await import('../data/visualisation.json')).default as VisBank
}

export type QuestionKind = 'where' | 'hanging' | 'best' | 'mate'
export const KINDS: QuestionKind[] = ['where', 'hanging', 'best', 'mate']
export const KIND_LABEL: Record<QuestionKind, string> = {
  where: 'Où est la pièce',
  hanging: 'Pièce en prise',
  best: 'Meilleur coup',
  mate: 'Mat en un',
}

const NAMES: Record<PieceSymbol, string> = { p: 'pion', n: 'cavalier', b: 'fou', r: 'tour', q: 'dame', k: 'roi' }
// Genre du nom, pour accorder « blanc/blanche », « parti/partie ».
const FEMININE: Record<PieceSymbol, boolean> = { p: false, n: false, b: false, r: true, q: true, k: false }
const VALUE: Record<PieceSymbol, number> = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 100 }
export const SIDE_NAME: Record<Color, string> = { w: 'Blancs', b: 'Noirs' }

export function pieceName(type: PieceSymbol, color: Color): string {
  const f = FEMININE[type]
  return `${f ? 'la' : 'le'} ${NAMES[type]} ${color === 'w' ? (f ? 'blanche' : 'blanc') : (f ? 'noire' : 'noir')}`
}

function play(c: Chess, uci: string) {
  return c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
}

// ---------- Ligne ----------

export interface LineMove {
  ply: number // 1..N
  label: string // « 23. ♘xe5 », « 23… dxe5 » ou « dxe5 » (numéro omis après un coup blanc)
  numbered: string // toujours numéroté, pour l'affichage coup par coup
  san: string
  color: Color
}

// Notation numérotée depuis le compteur du FEN, en figurines (comme EngineLineRow).
export function lineMoves(item: Pick<VisItem, 'fen' | 'line'>): LineMove[] {
  const c = new Chess(item.fen)
  const out: LineMove[] = []
  item.line.forEach((uci, i) => {
    const color = c.turn()
    const num = c.moveNumber()
    const san = play(c, uci).san
    const fig = figurine(san, color)
    const numbered = color === 'w' ? `${num}. ${fig}` : `${num}… ${fig}`
    out.push({ ply: i + 1, san, color, numbered, label: color === 'w' || i === 0 ? numbered : fig })
  })
  return out
}

export function finalPosition(item: Pick<VisItem, 'fen' | 'line'>): Chess {
  const c = new Chess(item.fen)
  for (const uci of item.line) play(c, uci)
  return c
}

// ---------- Pièce suivie (where) ----------

export interface Tracked {
  start: Square // case dans la position montrée
  type: PieceSymbol
  color: Color
  end: Square // case finale
  moves: number
  lastPly: number // dernier demi-coup où elle a bougé (1..N)
}

// Pièces qui ont bougé pendant la ligne, encore là à la fin et non promues. Roque : roi et tour
// bougent ; prise en passant : le pion pris n'est pas sur la case d'arrivée.
export function trackPieces(item: Pick<VisItem, 'fen' | 'line'>): Tracked[] {
  const c = new Chess(item.fen)
  // Case actuelle -> identité (case de départ) de la pièce qui l'occupe.
  const at = new Map<Square, Square>()
  for (const row of c.board()) for (const p of row) if (p) at.set(p.square, p.square)
  const info = new Map<Square, { moves: number; lastPly: number; promoted: boolean }>()
  item.line.forEach((uci, i) => {
    const m = play(c, uci)
    const bump = (from: Square, to: Square, promoted = false) => {
      const id = at.get(from)!
      at.delete(from)
      at.set(to, id)
      const s = info.get(id) ?? { moves: 0, lastPly: 0, promoted: false }
      info.set(id, { moves: s.moves + 1, lastPly: i + 1, promoted: s.promoted || promoted })
    }
    if (m.isEnPassant()) at.delete(`${m.to[0]}${m.from[1]}` as Square)
    else if (m.captured) at.delete(m.to)
    bump(m.from, m.to, !!m.promotion)
    if (m.isKingsideCastle() || m.isQueensideCastle()) {
      const rank = m.from[1]
      const [rf, rt] = m.isKingsideCastle() ? ['h', 'f'] : ['a', 'd']
      bump(`${rf}${rank}` as Square, `${rt}${rank}` as Square)
    }
  })
  const start = new Chess(item.fen)
  const out: Tracked[] = []
  for (const [end, id] of at) {
    const s = info.get(id)
    if (!s || s.promoted) continue
    const p = start.get(id)!
    out.push({ start: id, type: p.type, color: p.color, end, moves: s.moves, lastPly: s.lastPly })
  }
  return out.sort((a, b) => a.start.localeCompare(b.start))
}

// Pièces qu'on peut demander : sa case finale ne doit pas se lire dans le dernier coup annoncé
// (ni l'avant-dernier dès 4 demi-coups). Les meilleures d'abord : plus de coups, puis dernier coup
// le plus ancien.
export function whereCandidates(item: Pick<VisItem, 'fen' | 'line'>): Tracked[] {
  const n = item.line.length
  const cutoff = n >= 4 ? n - 1 : n
  const ok = trackPieces(item).filter((t) => t.lastPly < cutoff)
  if (ok.length === 0) return []
  const score = (t: Tracked) => [t.moves, -t.lastPly]
  const [bm, bl] = ok.map(score).sort((a, b) => b[0] - a[0] || b[1] - a[1])[0]
  return ok.filter((t) => t.moves === bm && -t.lastPly === bl)
}

// ---------- Pièces en prise (hanging) ----------

// Pièces du camp qui n'a pas le trait (hors roi) que le camp au trait peut prendre avec profit : une
// prise légale sur leur case (prise en passant exclue) faite par une pièce de moindre valeur, ou
// après laquelle aucune reprise légale sur cette case n'existe.
export function hangingSquares(final: Chess): Square[] {
  const out = new Set<Square>()
  for (const m of final.moves({ verbose: true })) {
    if (!m.captured || m.isEnPassant() || m.captured === 'k') continue
    if (VALUE[m.piece] < VALUE[m.captured]) {
      out.add(m.to)
      continue
    }
    const after = new Chess(m.after)
    if (!after.moves({ verbose: true }).some((r) => r.to === m.to && !!r.captured)) out.add(m.to)
  }
  return [...out].sort()
}

// ---------- Mat en un ----------

export function mateMoves(final: Chess): string[] {
  return final.moves({ verbose: true }).filter((m) => m.san.endsWith('#')).map((m) => m.from + m.to + (m.promotion ?? ''))
}

// ---------- Questions ----------

export interface Question {
  kind: QuestionKind
  item: VisItem
  level: number
  side: Color // camp au trait dans la position finale (= camp du puzzle)
  text: string
  target?: Tracked // where
  answers: Square[] // where : [case finale] ; hanging : cases acceptées ; best : [départ, arrivée]
  mate?: string[] // mate : coups qui matent (vide = Non)
}

export function questionFor(item: VisItem, level: number, kind: QuestionKind, rng: () => number = Math.random): Question | null {
  const final = finalPosition(item)
  const side = final.turn()
  const base = { kind, item, level, side, answers: [] as Square[] }
  if (kind === 'where') {
    const c = whereCandidates(item)
    if (c.length === 0) return null
    const t = c[Math.floor(rng() * c.length)]
    const fem = FEMININE[t.type]
    return { ...base, target: t, answers: [t.end], text: `Où est maintenant ${pieceName(t.type, t.color)} ${fem ? 'partie' : 'parti'} de ${t.start} ?` }
  }
  if (kind === 'hanging') {
    const h = hangingSquares(final)
    if (h.length === 0) return null
    const other: Color = side === 'w' ? 'b' : 'w'
    return { ...base, answers: h, text: `Touche la case d'une pièce ${other === 'w' ? 'blanche' : 'noire'} en prise.` }
  }
  if (kind === 'best') {
    return { ...base, answers: [item.best.slice(0, 2) as Square, item.best.slice(2, 4) as Square], text: `Quel est le meilleur coup des ${SIDE_NAME[side]} ? Touche la case de départ, puis la case d'arrivée.` }
  }
  return { ...base, mate: mateMoves(final), text: `Les ${SIDE_NAME[side]} peuvent-ils mater en un coup ?` }
}

// Tirage d'une question : type d'abord (uniforme), puis priorité aux positions pas encore servies.
// Pour « mat en un », Oui et Non à 50 % : réutiliser une position si nécessaire pour préserver
// la réponse tirée, sinon « Non » serait juste neuf fois sur dix.
export function pickQuestion(items: VisItem[], level: number, used: Set<string>, rng: () => number = Math.random): Question | null {
  const fresh = items.filter((it) => !used.has(it.id))
  const pool = fresh.length > 0 ? fresh : items
  const order = shuffle(pool, rng)
  const kinds = shuffle(KINDS, rng)
  for (const kind of kinds) {
    if (kind === 'mate') {
      const wantYes = rng() < 0.5
      for (const candidates of [order, shuffle(items, rng)]) {
        const it = candidates.find((i) => (mateMoves(finalPosition(i)).length > 0) === wantYes)
        if (it) return questionFor(it, level, 'mate', rng)
      }
      continue
    }
    for (const it of order) {
      const q = questionFor(it, level, kind, rng)
      if (q) return q
    }
  }
  return null
}

// Fisher-Yates : un tri par comparateur aléatoire ne mélange pas uniformément.
function shuffle<T>(xs: readonly T[], rng: () => number): T[] {
  const a = [...xs]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

// Réponse par cases touchées (where, hanging : une case ; best : deux cases).
export function checkSquares(q: Question, squares: string[]): boolean {
  if (q.kind === 'where' || q.kind === 'hanging') return squares.length === 1 && q.answers.includes(squares[0] as Square)
  if (q.kind !== 'best' || squares.length !== 2) return false
  const [from, to] = squares
  if (from !== q.answers[0]) return false
  if (to === q.answers[1]) return true
  // Roque : roi puis tour accepté (convention chess.com).
  const final = finalPosition(q.item)
  const m = final.moves({ verbose: true }).find((x) => x.from + x.to === q.item.best.slice(0, 4))
  if (m && (m.isKingsideCastle() || m.isQueensideCastle())) {
    return to === `${m.isKingsideCastle() ? 'h' : 'a'}${m.from[1]}`
  }
  return false
}

export function checkMate(q: Question, yes: boolean): boolean {
  return (q.mate ?? []).length > 0 === yes
}

export function sanOf(fen: string, uci: string): string {
  const c = new Chess(fen)
  const color = c.turn()
  return figurine(play(c, uci).san, color)
}

// Texte de correction affiché à la révélation.
export function correction(q: Question): string {
  const final = finalPosition(q.item)
  const fen = final.fen()
  if (q.kind === 'where' && q.target) {
    const n = pieceName(q.target.type, q.target.color)
    return `${n[0].toUpperCase()}${n.slice(1)} est en ${q.target.end}.`
  }
  if (q.kind === 'hanging') {
    const names = q.answers.map((s) => {
      const p = final.get(s)!
      return `${NAMES[p.type]} en ${s}`
    })
    return `En prise : ${names.join(', ')}.`
  }
  if (q.kind === 'best') return `Meilleur coup : ${sanOf(fen, q.item.best)}.`
  const mates = q.mate ?? []
  return mates.length > 0 ? `Oui : ${mates.map((u) => sanOf(fen, u)).join(' ou ')}.` : 'Non : aucun coup ne mate.'
}

// ---------- Statistiques et séries (learnSessions, domaine `visualisation`) ----------

export function questionItemId(q: Question): string {
  return `q:${q.level}:${q.kind}:${q.item.id}`
}

export function seriesKey(level: number, mode: DisplayMode): string {
  return `serie:${level}:${mode}`
}

export async function recordQuestion(q: Question, success: boolean): Promise<void> {
  await db.learnSessions.add({ date: Date.now(), domain: VIS_DOMAIN, itemId: questionItemId(q), success: success ? 1 : 0, ratingAfter: null, fen: q.item.fen })
}

export interface VisStats {
  best: Record<string, number> // record par clé de série
  last: Record<string, number[]> // dix dernières séries par clé
  answered: number // questions répondues, toutes séries confondues
  recent: number // nombre de questions dans la fenêtre des taux (100 dernières au plus)
  rate: Partial<Record<QuestionKind, { ok: number; total: number }>>
}

export async function loadVisStats(): Promise<VisStats> {
  const rows = await db.learnSessions.where('domain').equals(VIS_DOMAIN).sortBy('date')
  const best: Record<string, number> = {}
  const last: Record<string, number[]> = {}
  const questions = rows.filter((r) => r.itemId.startsWith('q:'))
  for (const r of rows) {
    if (!r.itemId.startsWith('serie:')) continue
    const s = typeof r.score === 'number' ? r.score : 0
    best[r.itemId] = Math.max(best[r.itemId] ?? 0, s)
    last[r.itemId] = [...(last[r.itemId] ?? []), s].slice(-10)
  }
  const window = questions.slice(-100)
  const rate: VisStats['rate'] = {}
  for (const r of window) {
    const kind = r.itemId.split(':')[2] as QuestionKind
    if (!KINDS.includes(kind)) continue
    const k = (rate[kind] ??= { ok: 0, total: 0 })
    k.total += 1
    k.ok += r.success
  }
  return { best, last, answered: questions.length, recent: window.length, rate }
}

// ---------- Préférences (localStorage, clé propre, hors sauvegarde) ----------

const PREFS_KEY = 'chess-local-visualisation'

export interface VisPrefs {
  level: Level
  mode: DisplayMode
}

export function readVisPrefs(): VisPrefs {
  try {
    const raw = JSON.parse(localStorage.getItem(PREFS_KEY) ?? '{}') as Partial<VisPrefs>
    return {
      level: LEVELS.includes(raw.level as Level) ? (raw.level as Level) : 4,
      mode: raw.mode === 'flash' ? 'flash' : 'visible',
    }
  } catch {
    return { level: 4, mode: 'visible' }
  }
}

export function writeVisPrefs(p: VisPrefs) {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(p))
  } catch {
    // stockage indisponible (navigation privée) : préférence de session seulement
  }
}
