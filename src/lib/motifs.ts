// Motifs tactiques détectés avec chess.js seul (aucun moteur) : pièce en prise, valeur
// réelle d'une capture, fourchette, clouage, enfilade, mat du couloir, pion passé, roque,
// mat en 1, pat. Partagé par le coach post-partie (coach.ts) et le coach live (liveCoach.ts).
// Règle d'or : chaque fonction ne renvoie que ce qu'elle a vérifié sur l'échiquier.
import { Chess, type Color, type Move, type PieceSymbol, type Square } from 'chess.js'

export const PIECE_VALUE: Record<PieceSymbol, number> = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 100 }

// Noms français avec article, et genre pour accorder les participes.
export const PIECE_FR: Record<PieceSymbol, { defini: string; indefini: string; ton: string; genre: 'm' | 'f' }> = {
  p: { defini: 'le pion', indefini: 'un pion', ton: 'ton pion', genre: 'm' },
  n: { defini: 'le cavalier', indefini: 'un cavalier', ton: 'ton cavalier', genre: 'm' },
  b: { defini: 'le fou', indefini: 'un fou', ton: 'ton fou', genre: 'm' },
  r: { defini: 'la tour', indefini: 'une tour', ton: 'ta tour', genre: 'f' },
  q: { defini: 'la dame', indefini: 'une dame', ton: 'ta dame', genre: 'f' },
  k: { defini: 'le roi', indefini: 'un roi', ton: 'ton roi', genre: 'm' },
}

export const other = (c: Color): Color => (c === 'w' ? 'b' : 'w')

function uciMove(c: Chess, uci: string): Move | null {
  try {
    return c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
  } catch {
    return null
  }
}

// SAN d'un coup UCI depuis une position, ou null s'il est illégal.
export function sanOf(fen: string, uci: string): string | null {
  return uciMove(new Chess(fen), uci)?.san ?? null
}

function pieces(c: Chess, color: Color) {
  return c.board().flat().filter((s): s is NonNullable<typeof s> => !!s && s.color === color)
}

// Échange statique par coups LÉGAUX (les clouages sont donc respectés) : ce que gagne le camp
// au trait s'il capture sur `sq` avec sa pièce la moins chère, puis échange jusqu'au bout.
export function see(fen: string, sq: Square): number {
  const c = new Chess(fen)
  if (!c.get(sq)) return 0
  // Seuls les coups des pièces qui attaquent la case : bien moins cher que tous les coups légaux.
  const caps = c
    .attackers(sq, c.turn())
    .flatMap((from) => c.moves({ square: from, verbose: true }))
    .filter((m) => m.to === sq && m.captured)
    .sort((a, b) => PIECE_VALUE[a.piece] - PIECE_VALUE[b.piece])
  if (caps.length === 0) return 0
  c.move(caps[0].san)
  return Math.max(0, PIECE_VALUE[caps[0].captured as PieceSymbol] - see(c.fen(), sq))
}

export type CaptureKind = 'reprise' | 'gain' | 'echange' | 'sacrifice'
export interface CaptureInfo {
  kind: CaptureKind
  captured: PieceSymbol
  by: PieceSymbol
  net: number
  square: Square
  clean: boolean // aucune pièce ne peut reprendre sur la case : la prise est vraiment gratuite
}

// D5 : valeur réelle d'une capture une fois les reprises terminées. « reprise » est testé en
// premier : le SEE d'une reprise est toujours positif alors que l'échange est équilibré.
export function captureInfo(fen: string, uci: string, lastCaptureSquare: string | null): CaptureInfo | null {
  const c = new Chess(fen)
  const mv = uciMove(c, uci)
  if (!mv || !mv.captured) return null
  const recapture = see(c.fen(), mv.to)
  const net = PIECE_VALUE[mv.captured] - recapture
  const kind: CaptureKind =
    lastCaptureSquare === mv.to ? 'reprise' : net >= 2 ? 'gain' : net >= -1 ? 'echange' : 'sacrifice'
  const clean = !c.attackers(mv.to, c.turn()).some((from) => c.moves({ square: from, verbose: true }).some((m) => m.to === mv.to))
  return { kind, captured: mv.captured, by: mv.piece, net, square: mv.to, clean }
}

// ------------------------------------------------------------------ outils de lichess-puzzler
// Portage de `util.py` de lichess-puzzler (github.com/ornicar/lichess-puzzler) : les mêmes
// définitions servent à étiqueter les puzzles lichess, et l'oracle python-chess de la suite
// E2E les réimplémente pour vérifier ces détecteurs sur des positions réelles.
const KING_VALUE: Record<PieceSymbol, number> = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 99 }
const RAY_TYPES: PieceSymbol[] = ['q', 'r', 'b']
const fileOf = (s: string) => s.charCodeAt(0) - 97
const rankOf = (s: string) => Number(s[1]) - 1

// Pièce défendue, y compris par rayon X : une pièce à longue portée qui l'attaque masque peut-être
// un défenseur placé derrière elle.
export function isDefended(c: Chess, sq: Square): boolean {
  const p = c.get(sq)
  if (!p) return false
  if (c.attackers(sq, p.color).length > 0) return true
  for (const a of c.attackers(sq, other(p.color))) {
    if (!RAY_TYPES.includes(c.get(a)!.type)) continue
    const copy = new Chess(c.fen(), { skipValidation: true })
    copy.remove(a)
    if (copy.attackers(sq, p.color).length > 0) return true
  }
  return false
}

// Pièce attaquée et (non défendue, ou prenable par une pièce adverse moins chère, roi exclu).
export function isInBadSpot(c: Chess, sq: Square): boolean {
  const p = c.get(sq)
  if (!p) return false
  const attackers = c.attackers(sq, other(p.color))
  if (attackers.length === 0) return false
  if (!isDefended(c, sq)) return true
  return attackers.some((a) => {
    const t = c.get(a)!.type
    return t !== 'k' && PIECE_VALUE[t] < PIECE_VALUE[p.type]
  })
}

const KNIGHT_STEPS: [number, number][] = [[1, 2], [2, 1], [2, -1], [1, -2], [-1, -2], [-2, -1], [-2, 1], [-1, 2]]
const KING_STEPS: [number, number][] = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]]
const sqAt = (f: number, r: number) => (String.fromCharCode(97 + f) + (r + 1)) as Square

// Cases attaquées par la pièce posée sur `from` (attaques brutes, clouages ignorés, comme
// `board.attacks` de python-chess). Calcul géométrique : 64 appels à `attackers` coûtaient cher.
function attacksFrom(c: Chess, from: Square): Square[] {
  const p = c.get(from)
  if (!p) return []
  const f0 = fileOf(from)
  const r0 = rankOf(from)
  const out: Square[] = []
  const inside = (f: number, r: number) => f >= 0 && f < 8 && r >= 0 && r < 8
  if (p.type === 'n' || p.type === 'k') {
    for (const [df, dr] of p.type === 'n' ? KNIGHT_STEPS : KING_STEPS) if (inside(f0 + df, r0 + dr)) out.push(sqAt(f0 + df, r0 + dr))
  } else if (p.type === 'p') {
    const dr = p.color === 'w' ? 1 : -1
    for (const df of [-1, 1]) if (inside(f0 + df, r0 + dr)) out.push(sqAt(f0 + df, r0 + dr))
  } else {
    for (const [df, dr] of DIRS[p.type]!) {
      for (let f = f0 + df, r = r0 + dr; inside(f, r); f += df, r += dr) {
        out.push(sqAt(f, r))
        if (c.get(sqAt(f, r))) break
      }
    }
  }
  return out
}

export interface Fork {
  by: PieceSymbol
  targets: PieceSymbol[] // les plus chères en premier
  squares: Square[]
  san: string
}

// D2 : fourchette, définition de `cook.fork` de lichess-puzzler. La pièce jouée (pas le roi)
// n'est pas en mauvaise case et attaque au moins deux pièces hors pions, chacune étant le roi,
// une pièce plus chère qu'elle, ou une pièce non défendue qui ne peut pas la prendre.
// Un coup qui mate n'est pas une fourchette : c'est un mat.
export function fork(fen: string, uci: string): Fork | null {
  const c = new Chess(fen)
  const mover = c.turn()
  const mv = uciMove(c, uci)
  if (!mv || mv.piece === 'k' || c.isCheckmate()) return null
  const me = c.get(mv.to)
  if (!me) return null
  const opp = other(mover)
  const attacked = attacksFrom(c, mv.to)
    .map((s) => ({ s, p: c.get(s) }))
    .filter((x) => x.p && x.p.color === opp && x.p.type !== 'p')
  // Tri bon marché d'abord : moins de deux pièces attaquées, pas de fourchette possible.
  if (attacked.length < 2 || isInBadSpot(c, mv.to)) return null
  const oppAttackers = c.attackers(mv.to, opp)
  const hits = attacked
    .filter((x) => KING_VALUE[x.p!.type] > KING_VALUE[me.type] || (!isDefended(c, x.s) && !oppAttackers.includes(x.s)))
    .sort((a, b) => KING_VALUE[b.p!.type] - KING_VALUE[a.p!.type])
  return hits.length >= 2 ? { by: me.type, targets: hits.map((x) => x.p!.type), squares: hits.map((x) => x.s), san: mv.san } : null
}

const DIRS: Partial<Record<PieceSymbol, [number, number][]>> = {
  b: [[1, 1], [1, -1], [-1, 1], [-1, -1]],
  r: [[1, 0], [-1, 0], [0, 1], [0, -1]],
}
DIRS.q = [...DIRS.b!, ...DIRS.r!]

export interface LineMotif {
  kind: 'clouage' | 'enfilade'
  by: PieceSymbol
  front: PieceSymbol
  rear: PieceSymbol
  frontSquare: Square
  rearSquare: Square
}

// D3 : clouage ou enfilade CRÉÉS par le coup d'une pièce à longue portée qui n'est pas en
// mauvaise case, sur deux pièces adverses alignées, la première ne pouvant pas la prendre.
// Clouage : derrière vaut plus que devant, et derrière est le roi, ou vaut plus que la pièce qui
// cloue, ou n'est pas défendue (sinon rien n'est gagné si devant s'écarte).
// Enfilade : devant (roi, ou pièce plus chère que l'attaquant, ou non défendue) vaut plus que
// derrière, et derrière (pas un pion) n'est pas défendue ou vaut plus que l'attaquant.
export function pinOrSkewer(fen: string, uci: string): LineMotif | null {
  const c = new Chess(fen)
  const mover = c.turn()
  const mv = uciMove(c, uci)
  if (!mv || c.isCheckmate()) return null
  const me = c.get(mv.to)
  const dirs = me && DIRS[me.type]
  if (!me || !dirs) return null
  const opp = other(mover)
  let safe: boolean | null = null // isInBadSpot, calculé seulement si un alignement se présente
  const f0 = fileOf(mv.to)
  const r0 = rankOf(mv.to)
  for (const [df, dr] of dirs) {
    // La pièce glisse le long de la même ligne (en avançant ou en reculant) : l'alignement
    // existait déjà avant le coup.
    const dfFrom = fileOf(mv.from) - f0
    const drFrom = rankOf(mv.from) - r0
    const k = Math.max(Math.abs(dfFrom), Math.abs(drFrom))
    if (Math.abs(dfFrom) === Math.abs(df) * k && Math.abs(drFrom) === Math.abs(dr) * k && dfFrom * dr === drFrom * df) continue
    const hit: { type: PieceSymbol; color: Color; square: Square }[] = []
    for (let f = f0 + df, r = r0 + dr; f >= 0 && f < 8 && r >= 0 && r < 8 && hit.length < 2; f += df, r += dr) {
      const sq = (String.fromCharCode(97 + f) + (r + 1)) as Square
      const p = c.get(sq)
      if (p) hit.push({ ...p, square: sq })
    }
    if (hit.length < 2 || hit[0].color !== opp || hit[1].color !== opp || hit[0].type === 'p') continue
    if (c.attackers(mv.to, opp).includes(hit[0].square)) continue // la pièce de devant peut prendre
    safe ??= !isInBadSpot(c, mv.to)
    if (!safe) return null
    const [front, rear] = hit
    const vFront = KING_VALUE[front.type]
    const vRear = KING_VALUE[rear.type]
    const vMe = KING_VALUE[me.type]
    const base = { by: me.type, front: front.type, rear: rear.type, frontSquare: front.square, rearSquare: rear.square }
    if (vRear > vFront && (rear.type === 'k' || vRear > vMe || !isDefended(c, rear.square))) return { kind: 'clouage', ...base }
    if (vFront > vRear && rear.type !== 'p' && (front.type === 'k' || vFront > vMe || !isDefended(c, front.square))
      && (vRear > vMe || !isDefended(c, rear.square))) return { kind: 'enfilade', ...base }
  }
  return null
}

// D4 : mat du couloir, définition de `cook.back_rank_mate` de lichess-puzzler : mat, roi sur sa
// dernière rangée, chaque case devant lui occupée par une de ses pièces et non attaquée, et une
// pièce qui donne échec depuis cette rangée.
export function backRankMate(fen: string, uci: string): boolean {
  const c = new Chess(fen)
  const mover = c.turn()
  const mv = uciMove(c, uci)
  if (!mv || !c.isCheckmate()) return false
  const opp = other(mover)
  const king = pieces(c, opp).find((p) => p.type === 'k')
  const back = opp === 'w' ? 0 : 7
  if (!king || rankOf(king.square) !== back) return false
  const front = back + (opp === 'w' ? 1 : -1)
  const kf = fileOf(king.square)
  for (const f of [kf - 1, kf, kf + 1]) {
    if (f < 0 || f > 7) continue
    const s = (String.fromCharCode(97 + f) + (front + 1)) as Square
    const p = c.get(s)
    if (!p || p.color !== opp || c.attackers(s, mover).length > 0) return false
  }
  return c.attackers(king.square, mover).some((s) => rankOf(s) === back)
}

function isPassed(c: Chess, sq: Square, color: Color): boolean {
  const f = fileOf(sq)
  const r = rankOf(sq)
  const dir = color === 'w' ? 1 : -1
  return !pieces(c, other(color)).some((e) => e.type === 'p' && Math.abs(fileOf(e.square) - f) <= 1 && (rankOf(e.square) - r) * dir > 0)
}

// D6 : pion passé CRÉÉ par le coup : le pion joué ne l'était pas sur sa case de départ, l'est
// sur sa case d'arrivée, et ne peut pas y être pris avec profit (sinon « pousse-le » tromperait).
export function passedPawn(fenBefore: string, uci: string): { square: Square; toGo: number } | null {
  const c = new Chess(fenBefore)
  const mover = c.turn()
  const from = uci.slice(0, 2) as Square
  const mv = uciMove(c, uci)
  if (!mv || mv.piece !== 'p' || mv.promotion) return null
  if (!isPassed(c, mv.to, mover) || see(c.fen(), mv.to) > 0) return null
  if (isPassed(new Chess(fenBefore), from, mover)) return null
  const r = rankOf(mv.to) + 1
  return { square: mv.to, toGo: mover === 'w' ? 8 - r : r - 1 }
}

// D7 : roque joué (tardif à partir du 13e coup) ou droits au roque perdus sans roquer.
export function castlingInfo(fenBefore: string, fenAfter: string, san: string, mover: Color): { kind: 'roque' | 'roque_tardif' | 'droit_perdu'; moveNo: number } | null {
  const moveNo = Number(fenBefore.split(' ')[5])
  const rightsBefore = fenBefore.split(' ')[2]
  const rightsAfter = fenAfter.split(' ')[2]
  const mine = mover === 'w' ? /[KQ]/ : /[kq]/
  if (san.startsWith('O-O')) return { kind: moveNo >= 13 ? 'roque_tardif' : 'roque', moveNo }
  // Roi en échec : perdre le roque n'était pas un choix, ce n'est pas la faute à pointer.
  if (mine.test(rightsBefore) && !mine.test(rightsAfter) && !new Chess(fenBefore).inCheck()) return { kind: 'droit_perdu', moveNo }
  return null
}

// SAN d'un mat en 1 disponible dans la position (le premier trouvé), sinon null.
export function mateInOne(fen: string): string | null {
  // chess.js marque déjà les coups qui matent d'un « # » dans leur SAN.
  return new Chess(fen).moves().find((san) => san.endsWith('#')) ?? null
}

export function isCheckmateFen(fen: string): boolean {
  return new Chess(fen).isCheckmate()
}

export function isStalemateFen(fen: string): boolean {
  return new Chess(fen).isStalemate()
}

// Bilan matériel du camp `color` (positif = avantage), hors rois.
export function materialBalance(fen: string, color: Color): number {
  let bal = 0
  for (const p of new Chess(fen).board().flat()) {
    if (!p || p.type === 'k') continue
    bal += (p.color === color ? 1 : -1) * PIECE_VALUE[p.type]
  }
  return bal
}
