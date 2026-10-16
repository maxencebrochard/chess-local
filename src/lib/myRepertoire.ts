// « Mon répertoire » (/repertoire) : dans les parties chess.com du joueur, le demi-coup où la partie
// sort de la théorie d'openings.json, qui en sort le premier, les coups théoriques attendus et ce
// que la sortie coûte (bilan Stockfish d'Insights s'il existe, sinon fréquence et résultats).
// Calcul pur, sans Dexie ni React : testé sous Node par e2e/test_repertoire.py.
//
// La théorie est un ensemble de POSITIONS (placement, trait, roques ; la prise en passant est
// ignorée), pas un arbre de coups : un ordre de coups différent vers une position théorique reste
// dans la théorie (1.d4 d5 2.Bf4 Nf6 rejoint 1.d4 Nf6 2.Bf4 d5). La séance d'entraînement rejoue les
// lignes lichess depuis les coups réels de la partie (`drillLines`).
import { Chess } from 'chess.js'
import openingsData from '../data/openings.json'
import type { GameReview } from './review'
import { familyOfLine } from './openingFamilies'

export type Color = 'w' | 'b'
export type Outcome = 'win' | 'draw' | 'loss'

export interface OpeningLine {
  eco: string
  name: string
  uci: string
}

export interface RepGame {
  key: string // 'chesscom:<id>'
  pgn: string
  playerColor: Color
  result: Outcome
  timeClass: string // code chess.com : bullet, blitz, rapid, daily
  date: number // ms
  opponent: string
  review: GameReview | null
}

// Seuil de coût d'une sortie : chute de win% du coup à partir de laquelle review.ts parle
// d'imprécision (en dessous de 7, le coup est « bon »).
export const COSTLY_DROP = 7
// Coups théoriques montrés pour une déviation.
const EXPECTED_MAX = 3

export type Verdict = 'costly' | 'unknown' | 'ok'

export interface ExpectedMove {
  uci: string
  san: string
  lines: number // lignes lichess qui passent par la position et continuent par ce coup
  name: string // nom de la plus courte de ces lignes
}

export interface PlayedMove {
  uci: string
  san: string
  games: number
}

// Une sortie = une position théorique où le joueur a quitté la théorie (quel que soit le coup
// joué, quel que soit l'ordre de coups qui y a mené) : une séance « Prochain coup » par sortie.
export interface Deviation {
  id: string // `<couleur>|<clé de position>`
  color: Color
  family: string // famille lichess de l'ouverture de la partie la plus récente
  opening: string // nom lichess de l'ouverture de la partie la plus récente
  prefix: string[] // coups de la partie la plus récente jusqu'à la position (trait au joueur)
  prefixes: string[] // tous les ordres de coups (UCI joints par des espaces) qui y ont mené
  played: PlayedMove[] // coups joués à la place de la théorie, du plus fréquent au moins fréquent
  ply: number // index du coup de sortie dans la partie la plus récente (0 = 1er coup des Blancs)
  moveNumber: number
  expected: ExpectedMove[]
  games: number
  wins: number
  draws: number
  losses: number
  reviewed: number // parties dont le bilan correspond à la partie
  avgDrop: number | null // chute moyenne de win% du coup de sortie (point de vue du joueur), null sans bilan
  verdict: Verdict
  last: { key: string; date: number; opponent: string; moves: string[] } // partie la plus récente
}

export interface OpeningReport {
  family: string
  games: number
  wins: number
  draws: number
  losses: number
  mine: number // parties où le joueur sort le premier de la théorie
  theirs: number // l'adversaire sort le premier
  end: number // fin de la théorie connue sans sortie
  inBook: number // partie finie dans la théorie
  typicalMove: number | null // médiane basse des coups de sortie du joueur (une valeur par partie)
  deviations: Deviation[]
}

export interface ColorReport {
  games: number
  mine: number
  typicalMove: number | null
  openings: OpeningReport[]
  deviations: Deviation[] // toutes les sorties du joueur, par priorité (file de la séance)
}

export interface RepertoireReport {
  games: number // parties retenues (cadence comprise)
  skipped: number // PGN illisibles, départ non standard, sans coup
  reviewed: number // parties retenues avec un bilan
  byColor: Record<Color, ColorReport>
}

export type ExitKind = 'mine' | 'theirs' | 'end' | 'inBook'

export interface GameExit {
  kind: ExitKind
  ply: number | null // demi-coup de sortie (mine, theirs), null sinon
  position: string | null // clé de la position avant la sortie (mine, theirs)
  family: string
  opening: string
}

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
const ALL = openingsData as OpeningLine[]

// Clé de position : placement, trait et roques (sans prise en passant ni compteurs).
export function positionKey(fen: string): string {
  return fen.split(' ').slice(0, 3).join(' ')
}

const play = (c: Chess, uci: string) => c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })

interface Through {
  line: OpeningLine
  at: number // demi-coups de la ligne jusqu'à la position
}

interface BookIndex {
  // Lignes qui passent par chaque position théorique (y compris celles qui s'y arrêtent).
  through: Map<string, Through[]>
  // Ligne nommée qui se termine sur la position (la première d'openings.json).
  named: Map<string, OpeningLine>
}

let index: BookIndex | null = null

// Index des positions d'openings.json, construit une fois : arbre préfixe parcouru en profondeur
// avec un seul échiquier (environ 8 600 coups joués puis repris).
export function bookIndex(): BookIndex {
  if (index) return index
  interface Node { kids: Map<string, Node>; ends: OpeningLine[]; lines: OpeningLine[] }
  const node = (): Node => ({ kids: new Map(), ends: [], lines: [] })
  const root = node()
  for (const line of ALL) {
    let n = root
    n.lines.push(line)
    for (const mv of line.uci.split(' ')) {
      let k = n.kids.get(mv)
      if (!k) n.kids.set(mv, (k = node()))
      n = k
      n.lines.push(line)
    }
    n.ends.push(line)
  }
  const through = new Map<string, Through[]>()
  const named = new Map<string, OpeningLine>()
  const c = new Chess()
  const visit = (n: Node, depth: number) => {
    const key = positionKey(c.fen())
    let list = through.get(key)
    if (!list) through.set(key, (list = []))
    for (const line of n.lines) list.push({ line, at: depth })
    if (n.ends.length && !named.has(key)) named.set(key, n.ends[0])
    for (const [mv, kid] of n.kids) {
      play(c, mv)
      visit(kid, depth + 1)
      c.undo()
    }
  }
  visit(root, 0)
  index = { through, named }
  return index
}

// Coups théoriques d'une position : nombre de lignes qui continuent par chacun, et la plus courte.
export function bookMovesAt(key: string): { uci: string; lines: number; line: OpeningLine }[] {
  const out = new Map<string, { uci: string; lines: number; line: OpeningLine }>()
  for (const { line, at } of bookIndex().through.get(key) ?? []) {
    const mv = line.uci.split(' ')[at]
    if (!mv) continue
    const cur = out.get(mv)
    if (!cur) out.set(mv, { uci: mv, lines: 1, line })
    else {
      cur.lines++
      if (line.uci.length < cur.line.uci.length) cur.line = line
    }
  }
  return [...out.values()].sort((a, b) => b.lines - a.lines || (a.uci < b.uci ? -1 : 1))
}

// Coups UCI d'un PGN de partie standard, ou null (illisible, départ non standard, aucun coup).
// Mémorisés par PGN : changer de camp ou de cadence ne relit pas 200 parties.
const movesCache = new Map<string, string[] | null>()
export function pgnMoves(pgn: string): string[] | null {
  let moves = movesCache.get(pgn)
  if (moves === undefined) {
    moves = parseMoves(pgn)
    if (movesCache.size > 2000) movesCache.clear()
    movesCache.set(pgn, moves)
  }
  return moves
}

function parseMoves(pgn: string): string[] | null {
  try {
    const c = new Chess()
    c.loadPgn(pgn)
    const fen = c.header().FEN
    if (fen && fen !== START_FEN) return null
    const moves = c.history({ verbose: true }).map((m) => m.lan)
    return moves.length ? moves : null
  } catch {
    return null
  }
}

const isPlayerMove = (ply: number, color: Color) => (ply % 2 === 0) === (color === 'w')

// Clés de position de la partie : index 0 = départ, index n = après n demi-coups.
function positionsOf(moves: string[], upTo: number): string[] {
  const c = new Chess()
  const keys = [positionKey(c.fen())]
  for (let i = 0; i < Math.min(upTo, moves.length); i++) {
    play(c, moves[i])
    keys.push(positionKey(c.fen()))
  }
  return keys
}

// Sortie de théorie : premier demi-coup qui mène à une position absente d'openings.json. Une
// position théorique sans coup théorique ensuite est la fin de la théorie connue : aucune sortie.
export function gameExit(moves: string[], color: Color): GameExit {
  const { through, named } = bookIndex()
  const keys = positionsOf(moves, 40)
  let d = 0
  while (d < moves.length && d + 1 < keys.length && through.has(keys[d + 1])) d++
  // Ouverture : la plus profonde position de la partie (jusqu'à la sortie) qui termine une ligne nommée.
  let opening: OpeningLine | null = null
  for (let n = Math.min(d, keys.length - 1); n > 0 && !opening; n--) opening = named.get(keys[n]) ?? null
  const name = opening?.name ?? '?'
  const base = { family: opening ? familyOfLine(name) : '?', opening: name }
  if (d >= moves.length || d + 1 >= keys.length) return { ...base, kind: 'inBook', ply: null, position: null }
  if (bookMovesAt(keys[d]).length === 0) return { ...base, kind: 'end', ply: null, position: null }
  return { ...base, kind: isPlayerMove(d, color) ? 'mine' : 'theirs', ply: d, position: keys[d] }
}

// Lignes lichess d'une séance « Prochain coup » sur la position atteinte par `prefix` : chaque ligne
// qui passe par cette position est réécrite depuis les coups réels (`prefix` + sa suite), et la
// ligne nommée de la position devient `prefix` lui-même (nom affiché par l'entraîneur).
export function drillLines(prefix: string[], opening: string): OpeningLine[] {
  const key = positionsOf(prefix, prefix.length)[prefix.length]
  const head = prefix.join(' ')
  const out = new Map<string, OpeningLine>()
  const name = bookIndex().named.get(key) ?? ALL.find((l) => l.name === opening) ?? null
  if (name) out.set(head, { ...name, uci: head })
  for (const { line, at } of bookIndex().through.get(key) ?? []) {
    const tail = line.uci.split(' ').slice(at)
    if (!tail.length) continue
    const uci = [head, ...tail].filter(Boolean).join(' ')
    if (!out.has(uci)) out.set(uci, { ...line, uci })
  }
  return [...out.values()].filter((l) => l.uci !== '')
}

function sanAt(prefix: string[], uci: string): string {
  const c = new Chess()
  for (const m of prefix) play(c, m)
  return play(c, uci).san
}

// Chute de win% du coup `ply` selon le bilan, si le bilan correspond bien à la partie.
export function reviewDrop(review: GameReview | null, moves: string[], ply: number): number | null {
  if (!review || typeof review !== 'object' || !Array.isArray(review.moves)) return null
  if (review.startFen !== undefined && review.startFen !== START_FEN) return null
  const m = review.moves[ply]
  if (!m || m.uci !== moves[ply]) return null
  const before = Number(m.winPctBefore)
  const after = Number(m.winPctAfter)
  if (!Number.isFinite(before) || !Number.isFinite(after)) return null
  return Math.max(0, before - after)
}

const lowMedian = (xs: number[]): number | null => {
  if (!xs.length) return null
  const s = [...xs].sort((a, b) => a - b)
  return s[Math.floor((s.length - 1) / 2)]
}

const VERDICT_RANK: Record<Verdict, number> = { costly: 0, unknown: 1, ok: 2 }

// Ordre de priorité : coûteuses (chute × parties), puis sans bilan (parties, défaites), puis sans
// dommage (parties) ; à égalité, la sortie la plus précoce, puis l'identifiant.
export function byPriority(a: Deviation, b: Deviation): number {
  const r = VERDICT_RANK[a.verdict] - VERDICT_RANK[b.verdict]
  if (r) return r
  if (a.verdict === 'costly') {
    const k = b.avgDrop! * b.games - a.avgDrop! * a.games
    if (k) return k
  } else {
    if (b.games !== a.games) return b.games - a.games
    if (a.verdict === 'unknown' && b.losses !== a.losses) return b.losses - a.losses
  }
  return a.ply - b.ply || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)
}

function emptyColor(): ColorReport {
  return { games: 0, mine: 0, typicalMove: null, openings: [], deviations: [] }
}

function tally(t: { wins: number; draws: number; losses: number }, r: Outcome) {
  if (r === 'win') t.wins++
  else if (r === 'draw') t.draws++
  else t.losses++
}

// Rapport du répertoire. `timeClass` : 'all' ou un code de cadence chess.com. Une clé de partie en
// double ne compte qu'une fois (la première).
export function computeRepertoire(input: RepGame[], timeClass = 'all'): RepertoireReport {
  const report: RepertoireReport = { games: 0, skipped: 0, reviewed: 0, byColor: { w: emptyColor(), b: emptyColor() } }
  const openings = { w: new Map<string, OpeningReport>(), b: new Map<string, OpeningReport>() }
  const devs = new Map<string, Deviation & { drops: number[]; moves: number[]; families: Set<string> }>()
  const exitByFamily = new Map<string, number[]>()

  const seen = new Set<string>()
  for (const g of input) {
    if (!g || seen.has(g.key)) continue
    seen.add(g.key)
    if (timeClass !== 'all' && g.timeClass !== timeClass) continue
    const color: Color = g.playerColor === 'b' ? 'b' : 'w'
    const moves = typeof g.pgn === 'string' ? pgnMoves(g.pgn) : null
    if (!moves) {
      report.skipped++
      continue
    }
    const exit = gameExit(moves, color)
    report.games++
    if (g.review) report.reviewed++
    report.byColor[color].games++
    let op = openings[color].get(exit.family)
    if (!op) {
      op = { family: exit.family, games: 0, wins: 0, draws: 0, losses: 0, mine: 0, theirs: 0, end: 0, inBook: 0, typicalMove: null, deviations: [] }
      openings[color].set(exit.family, op)
    }
    op.games++
    tally(op, g.result)
    op[exit.kind]++
    if (exit.kind !== 'mine') continue
    const ply = exit.ply!
    const prefix = moves.slice(0, ply)
    const played = moves[ply]
    const id = `${color}|${exit.position}`
    const last = { key: g.key, date: g.date, opponent: g.opponent, moves }
    let d = devs.get(id)
    if (!d) {
      d = {
        id, color, family: exit.family, opening: exit.opening, prefix, prefixes: [], played: [],
        ply, moveNumber: Math.floor(ply / 2) + 1,
        expected: bookMovesAt(exit.position!).slice(0, EXPECTED_MAX).map((m) => ({ uci: m.uci, san: '', lines: m.lines, name: m.line.name })),
        games: 0, wins: 0, draws: 0, losses: 0, reviewed: 0, avgDrop: null, verdict: 'unknown',
        last, drops: [], moves: [], families: new Set(),
      }
      devs.set(id, d)
    } else if (g.date > d.last.date) {
      // La partie la plus récente fournit les coups de la séance et le lien « Partie ».
      Object.assign(d, { family: exit.family, opening: exit.opening, prefix, ply, moveNumber: Math.floor(ply / 2) + 1, last })
    }
    if (!d.prefixes.includes(prefix.join(' '))) d.prefixes.push(prefix.join(' '))
    const pm = d.played.find((m) => m.uci === played)
    if (pm) pm.games++
    else d.played.push({ uci: played, san: '', games: 1 })
    d.games++
    tally(d, g.result)
    d.moves.push(Math.floor(ply / 2) + 1)
    d.families.add(exit.family)
    const fk = `${color}|${exit.family}`
    exitByFamily.set(fk, [...(exitByFamily.get(fk) ?? []), Math.floor(ply / 2) + 1])
    const drop = reviewDrop(g.review, moves, ply)
    if (drop !== null) d.drops.push(drop)
  }

  const all: Deviation[] = []
  const exitMoves = { w: [] as number[], b: [] as number[] }
  const familiesOf = new Map<string, Set<string>>()
  for (const { drops, moves, families, ...d } of devs.values()) {
    d.reviewed = drops.length
    d.avgDrop = drops.length ? drops.reduce((a, b) => a + b, 0) / drops.length : null
    d.verdict = d.avgDrop === null ? 'unknown' : d.avgDrop >= COSTLY_DROP ? 'costly' : 'ok'
    // SAN dans la position de la partie la plus récente (même position, donc mêmes coups légaux).
    d.played = d.played.map((m) => ({ ...m, san: sanAt(d.prefix, m.uci) })).sort((a, b) => b.games - a.games || (a.uci < b.uci ? -1 : 1))
    d.expected = d.expected.map((e) => ({ ...e, san: sanAt(d.prefix, e.uci) }))
    exitMoves[d.color].push(...moves)
    familiesOf.set(d.id, families)
    all.push(d)
  }
  all.sort(byPriority)
  for (const color of ['w', 'b'] as const) {
    const cr = report.byColor[color]
    cr.deviations = all.filter((d) => d.color === color)
    cr.mine = exitMoves[color].length
    cr.typicalMove = lowMedian(exitMoves[color])
    for (const op of openings[color].values()) {
      op.deviations = cr.deviations.filter((d) => familiesOf.get(d.id)!.has(op.family))
      op.typicalMove = lowMedian(exitByFamily.get(`${color}|${op.family}`) ?? [])
    }
    cr.openings = [...openings[color].values()].sort((a, b) => b.games - a.games || (a.family < b.family ? -1 : a.family > b.family ? 1 : 0))
  }
  return report
}
