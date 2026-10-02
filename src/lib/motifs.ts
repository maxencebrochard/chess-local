// Motifs tactiques détectés avec chess.js seul (aucun moteur) : pièce en prise, valeur
// réelle d'une capture, fourchette, clouage, enfilade, mat du couloir, pion passé, roque,
// mat en 1, pat. Partagé par le coach post-partie (coach.ts) et le coach live (liveCoach.ts).
// Règle d'or : chaque fonction ne renvoie que ce qu'elle a vérifié sur l'échiquier.
import { Chess, type Color, type Move, type PieceSymbol, type Square } from 'chess.js'

export const PIECE_VALUE: Record<PieceSymbol, number> = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 100 }

// Noms français avec article, et genre pour accorder les participes.
export const PIECE_FR: Record<PieceSymbol, { defini: string; indefini: string; genre: 'm' | 'f' }> = {
  p: { defini: 'le pion', indefini: 'un pion', genre: 'm' },
  n: { defini: 'le cavalier', indefini: 'un cavalier', genre: 'm' },
  b: { defini: 'le fou', indefini: 'un fou', genre: 'm' },
  r: { defini: 'la tour', indefini: 'une tour', genre: 'f' },
  q: { defini: 'la dame', indefini: 'une dame', genre: 'f' },
  k: { defini: 'le roi', indefini: 'un roi', genre: 'm' },
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

// Position identique avec le trait inversé (prise en passant effacée). Légal dès que le camp
// au trait n'est pas en échec : le camp qui n'a pas le trait ne l'est jamais.
function flipTurn(fen: string): string {
  const f = fen.split(' ')
  f[1] = other(f[1] as Color)
  f[3] = '-'
  return f.join(' ')
}

// Échange statique par coups LÉGAUX (les clouages sont donc respectés) : ce que gagne le camp
// au trait s'il capture sur `sq` avec sa pièce la moins chère, puis échange jusqu'au bout.
export function see(fen: string, sq: Square): number {
  const c = new Chess(fen)
  const caps = c
    .moves({ verbose: true })
    .filter((m) => m.to === sq && m.captured)
    .sort((a, b) => PIECE_VALUE[a.piece] - PIECE_VALUE[b.piece])
  if (caps.length === 0) return 0
  c.move(caps[0].san)
  return Math.max(0, PIECE_VALUE[caps[0].captured as PieceSymbol] - see(c.fen(), sq))
}

export interface Hanging {
  piece: PieceSymbol
  square: Square
  loss: number // perte nette au SEE
  defended: boolean
  attacker: PieceSymbol // attaquant adverse le moins cher
  capturer: boolean // la pièce vient de capturer : échange perdant plutôt que pièce en prise
}

// D1 : pièce du joueur en prise APRÈS son coup (perte nette ≥ 2), et qui ne perdait pas déjà
// autant avant. Pour la pièce qui vient de capturer, la perte nette retranche ce qu'elle a pris :
// ♝xd1 repris (fou contre dame) se tait, ♕xf7+ repris par le roi (dame contre pion) parle.
export function hangingAfter(fenBefore: string, fenAfter: string, mover: Color, moved?: { to: string; captured?: PieceSymbol }): Hanging | null {
  const after = new Chess(fenAfter)
  if (after.isGameOver()) return null
  const before = new Chess(fenBefore)
  const flipped = before.inCheck() ? null : flipTurn(fenBefore)
  const opp = other(mover)
  let worst: Hanging | null = null
  for (const p of pieces(after, mover)) {
    if (p.type === 'k') continue
    const attackers = after.attackers(p.square, opp)
    if (attackers.length === 0) continue
    const capturer = !!moved && moved.to === p.square && !!moved.captured
    const loss = see(fenAfter, p.square) - (capturer ? PIECE_VALUE[moved!.captured!] : 0)
    if (loss < 2) continue
    if (flipped && !capturer) {
      const b = before.get(p.square)
      if (b && b.type === p.type && b.color === mover && see(flipped, p.square) >= loss) continue // déjà en prise avant
    }
    const attacker = attackers
      .map((s) => after.get(s)!.type)
      .sort((a, b) => PIECE_VALUE[a] - PIECE_VALUE[b])[0]
    if (!worst || loss > worst.loss) {
      worst = { piece: p.type, square: p.square, loss, defended: after.attackers(p.square, mover).length > 0, attacker, capturer }
    }
  }
  return worst
}

export type CaptureKind = 'reprise' | 'gain' | 'echange' | 'sacrifice'
export interface CaptureInfo {
  kind: CaptureKind
  captured: PieceSymbol
  by: PieceSymbol
  net: number
  clean: boolean // aucune reprise possible : la prise est gratuite
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
  return { kind, captured: mv.captured, by: mv.piece, net, clean: recapture === 0 }
}

export interface Fork {
  by: PieceSymbol
  targets: PieceSymbol[] // les deux plus chères en premier
  san: string
}

// D2 : la pièce jouée attaque au moins deux cibles (roi, pièce plus chère qu'elle, ou pièce
// non défendue) sans être elle-même prenable.
export function fork(fen: string, uci: string): Fork | null {
  const c = new Chess(fen)
  const mover = c.turn()
  const mv = uciMove(c, uci)
  if (!mv || c.isCheckmate() || see(c.fen(), mv.to) > 0) return null
  const me = c.get(mv.to)
  if (!me) return null
  const opp = other(mover)
  const targets = pieces(c, opp)
    .filter((t) => t.type !== 'p' && c.attackers(t.square, mover).includes(mv.to))
    .filter((t) => t.type === 'k' || PIECE_VALUE[t.type] > PIECE_VALUE[me.type] || c.attackers(t.square, opp).length === 0)
    .map((t) => t.type)
    .sort((a, b) => PIECE_VALUE[b] - PIECE_VALUE[a])
  return targets.length >= 2 ? { by: me.type, targets, san: mv.san } : null
}

const DIRS: Partial<Record<PieceSymbol, [number, number][]>> = {
  b: [[1, 1], [1, -1], [-1, 1], [-1, -1]],
  r: [[1, 0], [-1, 0], [0, 1], [0, -1]],
}
DIRS.q = [...DIRS.b!, ...DIRS.r!]

export interface LineMotif {
  kind: 'clouage' | 'enfilade'
  front: PieceSymbol
  rear: PieceSymbol
}

// D3 : clouage (pièce moins chère devant une plus chère) ou enfilade (l'inverse) créés par une
// pièce à longue portée qui n'est pas prenable et que la pièce de devant ne peut pas capturer.
export function pinOrSkewer(fen: string, uci: string): LineMotif | null {
  const c = new Chess(fen)
  const mover = c.turn()
  const mv = uciMove(c, uci)
  if (!mv) return null
  const me = c.get(mv.to)
  const dirs = me && DIRS[me.type]
  if (!me || !dirs || see(c.fen(), mv.to) > 0) return null
  const f0 = mv.to.charCodeAt(0) - 97
  const r0 = Number(mv.to[1]) - 1
  for (const [df, dr] of dirs) {
    const hit: { type: PieceSymbol; color: Color; square: Square }[] = []
    for (let f = f0 + df, r = r0 + dr; f >= 0 && f < 8 && r >= 0 && r < 8 && hit.length < 2; f += df, r += dr) {
      const sq = (String.fromCharCode(97 + f) + (r + 1)) as Square
      const p = c.get(sq)
      if (p) hit.push({ ...p, square: sq })
    }
    if (hit.length < 2 || hit[0].color === mover || hit[1].color === mover || hit[0].type === 'p') continue
    if (c.attackers(mv.to, other(mover)).includes(hit[0].square)) continue // la pièce de devant peut prendre
    const front = PIECE_VALUE[hit[0].type]
    const rear = PIECE_VALUE[hit[1].type]
    if (rear > front && front >= PIECE_VALUE[me.type] - 2) return { kind: 'clouage', front: hit[0].type, rear: hit[1].type }
    if (front > rear && rear >= 3) return { kind: 'enfilade', front: hit[0].type, rear: hit[1].type }
  }
  return null
}

// D4 : mat du couloir, tour ou dame sur la dernière rangée, roi adverse muré par ses pièces.
export function backRankMate(fen: string, uci: string): boolean {
  const c = new Chess(fen)
  const mover = c.turn()
  const mv = uciMove(c, uci)
  if (!mv || !c.isCheckmate() || !'rq'.includes(mv.piece)) return false
  const opp = other(mover)
  const king = pieces(c, opp).find((p) => p.type === 'k')
  const rank = opp === 'w' ? '1' : '8'
  if (!king || king.square[1] !== rank || mv.to[1] !== rank) return false
  const front = opp === 'w' ? '2' : '7'
  return [-1, 0, 1]
    .map((d) => String.fromCharCode(king.square.charCodeAt(0) + d) + front)
    .filter((s) => /^[a-h]/.test(s))
    .every((s) => c.get(s as Square)?.color === opp)
}

// D6 : le pion joué n'a plus aucun pion adverse devant lui ni sur les colonnes voisines.
export function passedPawn(fenAfter: string, uci: string, mover: Color): { square: string; toGo: number } | null {
  const c = new Chess(fenAfter)
  const to = uci.slice(2, 4) as Square
  const p = c.get(to)
  if (!p || p.type !== 'p' || p.color !== mover) return null
  const f = to.charCodeAt(0) - 97
  const r = Number(to[1])
  const dir = mover === 'w' ? 1 : -1
  for (const e of pieces(c, other(mover))) {
    if (e.type !== 'p') continue
    const ef = e.square.charCodeAt(0) - 97
    const er = Number(e.square[1])
    if (Math.abs(ef - f) <= 1 && (er - r) * dir > 0) return null
  }
  return { square: to, toGo: mover === 'w' ? 8 - r : r - 1 }
}

// D7 : roque joué (tardif à partir du 13e coup) ou droits au roque perdus sans roquer.
export function castlingInfo(fenBefore: string, fenAfter: string, san: string, mover: Color): { kind: 'roque' | 'roque_tardif' | 'droit_perdu'; moveNo: number } | null {
  const moveNo = Number(fenBefore.split(' ')[5])
  const rightsBefore = fenBefore.split(' ')[2]
  const rightsAfter = fenAfter.split(' ')[2]
  const mine = mover === 'w' ? /[KQ]/ : /[kq]/
  if (san.startsWith('O-O')) return { kind: moveNo >= 13 ? 'roque_tardif' : 'roque', moveNo }
  if (mine.test(rightsBefore) && !mine.test(rightsAfter)) return { kind: 'droit_perdu', moveNo }
  return null
}

// SAN d'un mat en 1 disponible dans la position (le premier trouvé), sinon null.
export function mateInOne(fen: string): string | null {
  const c = new Chess(fen)
  for (const mv of c.moves({ verbose: true })) {
    c.move(mv.san)
    const mate = c.isCheckmate()
    c.undo()
    if (mate) return mv.san
  }
  return null
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
