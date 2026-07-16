// Game Review façon chess.com : classification de chaque coup + accuracy.
// Méthode : pour chaque position, éval multipv=2 à profondeur fixe ; le delta
// de win% entre le meilleur coup et le coup joué détermine la classe.
import { Chess } from 'chess.js'
import { Engine, type EngineLine } from './engine'
import { isBookPosition } from './openings'

export type MoveClass =
  | 'brilliant' | 'great' | 'best' | 'excellent' | 'good'
  | 'book' | 'inaccuracy' | 'mistake' | 'miss' | 'missedWin' | 'blunder'

export interface ReviewedMove {
  san: string
  uci: string
  class: MoveClass
  evalAfterCp: number | null // point de vue blanc
  mateAfter: number | null
  bestMoveUci: string
  winPctBefore: number // point de vue du joueur au trait
  winPctAfter: number
}

export interface GameReview {
  moves: ReviewedMove[]
  accuracyWhite: number
  accuracyBlack: number
  counts: { w: Record<MoveClass, number>; b: Record<MoveClass, number> }
  // Elo estimé de la performance sur cette partie (par couleur).
  gameRatingWhite: number
  gameRatingBlack: number
  // Win% blanc après chaque demi-coup ; index 0 = position initiale. Longueur = coups + 1.
  winPctSeries: number[]
}

export const CLASS_META: Record<MoveClass, { label: string; symbol: string; color: string }> = {
  brilliant: { label: 'Brillant', symbol: '!!', color: '#26c2a3' },
  great: { label: 'Excellent coup', symbol: '!', color: '#5b8bb0' },
  best: { label: 'Meilleur', symbol: '★', color: '#95bb4a' },
  excellent: { label: 'Excellent', symbol: '✓', color: '#95bb4a' },
  good: { label: 'Bon', symbol: '✓', color: '#77915f' },
  book: { label: 'Théorie', symbol: '📖', color: '#a88865' },
  inaccuracy: { label: 'Imprécision', symbol: '?!', color: '#f0c15c' },
  mistake: { label: 'Erreur', symbol: '?', color: '#e58f2a' },
  miss: { label: 'Occasion manquée', symbol: '✗', color: '#e58f2a' },
  missedWin: { label: 'Gain manqué', symbol: '−', color: '#ca6431' },
  blunder: { label: 'Gaffe', symbol: '??', color: '#ca3431' },
}

// Win% depuis des centipawns, formule lichess.
export function winPct(cp: number): number {
  return 50 + 50 * (2 / (1 + Math.exp(-0.00368208 * cp)) - 1)
}

function lineCp(line: EngineLine): number {
  if (line.scoreMate !== null) return line.scoreMate > 0 ? 10000 : -10000
  return line.scoreCp ?? 0
}

const PIECE_VALUE: Record<string, number> = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 }

function materialBalance(chess: Chess, color: 'w' | 'b'): number {
  let bal = 0
  for (const row of chess.board()) {
    for (const sq of row) {
      if (!sq) continue
      bal += (sq.color === color ? 1 : -1) * PIECE_VALUE[sq.type]
    }
  }
  return bal
}

export async function reviewGame(
  pgn: string,
  engine: Engine,
  depth: number,
  onProgress: (done: number, total: number) => void,
): Promise<GameReview> {
  const game = new Chess()
  game.loadPgn(pgn)
  const verbose = game.history({ verbose: true })
  const total = verbose.length

  // Évaluations de chaque position (avant coup 1, après coup 1, ...).
  const chess = new Chess()
  const evals: { lines: EngineLine[] }[] = []
  for (let i = 0; i <= total; i++) {
    if (i > 0) chess.move(verbose[i - 1].san)
    if (chess.isGameOver()) {
      evals.push({ lines: [] })
    } else {
      const res = await engine.search({ fen: chess.fen(), depth, multipv: 2 })
      evals.push({ lines: res.lines })
    }
    onProgress(i, total + 1)
  }

  const moves: ReviewedMove[] = []
  const replay = new Chess()
  const uciSoFar: string[] = []
  const cpLosses: { w: number[]; b: number[] } = { w: [], b: [] }

  for (let i = 0; i < total; i++) {
    const mv = verbose[i]
    const mover = replay.turn()
    const before = evals[i].lines
    const after = evals[i + 1].lines
    const bestLine = before[0]
    const bestMoveUci = bestLine ? bestLine.pv[0] : mv.lan

    // cp point de vue du joueur au trait.
    const cpBefore = bestLine ? lineCp(bestLine) : 0
    let cpAfterMover: number
    const replayAfter = new Chess(replay.fen())
    replayAfter.move(mv.san)
    if (replayAfter.isCheckmate()) cpAfterMover = 10000
    else if (replayAfter.isGameOver()) cpAfterMover = 0
    else cpAfterMover = after[0] ? -lineCp(after[0]) : cpBefore

    const wBefore = winPct(cpBefore)
    const wAfter = winPct(cpAfterMover)
    const drop = Math.max(0, wBefore - wAfter)

    uciSoFar.push(mv.lan)
    // Le coup précédent (adverse) était-il une grosse faute non punie ?
    const prevMove = moves[i - 1]
    const opponentJustBlundered =
      prevMove !== undefined && Math.max(0, prevMove.winPctBefore - prevMove.winPctAfter) >= 10

    let cls: MoveClass
    if (isBookPosition(uciSoFar)) {
      cls = 'book'
    } else if (mv.lan !== bestMoveUci && wBefore >= 85 && wAfter < 55) {
      // Position gagnante jetée : Gain manqué (prioritaire sur l'échelle standard).
      cls = 'missedWin'
    } else if (mv.lan !== bestMoveUci && opponentJustBlundered && drop >= 5) {
      // L'adversaire venait d'offrir l'avantage, non puni : Occasion manquée.
      cls = 'miss'
    } else if (mv.lan === bestMoveUci) {
      // Brillant : meilleur coup qui sacrifie du matériel en restant gagnant/égal.
      const balBefore = materialBalance(replay, mover)
      const balAfter2 = -materialBalance(replayAfter, replayAfter.turn())
      const sacrifice = balAfter2 < balBefore - 1 && !replayAfter.isCheckmate()
      const secondGap = before[1] ? winPct(cpBefore) - winPct(lineCp(before[1])) : 0
      if (sacrifice && wAfter > 45) cls = 'brilliant'
      else if (secondGap > 12 && wBefore > 40 && wBefore < 90) cls = 'great'
      else cls = 'best'
    } else if (drop < 2) cls = 'excellent'
    else if (drop < 5) cls = 'good'
    else if (drop < 10) cls = 'inaccuracy'
    else if (drop < 20) cls = 'mistake'
    else cls = 'blunder'

    // Eval affichée : point de vue blanc.
    const afterLine = after[0] ?? null
    let evalAfterCp: number | null = null
    let mateAfter: number | null = null
    if (replayAfter.isCheckmate()) {
      mateAfter = 0
      evalAfterCp = mover === 'w' ? 10000 : -10000
    } else if (afterLine) {
      const sign = replayAfter.turn() === 'w' ? 1 : -1
      if (afterLine.scoreMate !== null) mateAfter = sign * afterLine.scoreMate
      evalAfterCp = sign * lineCp(afterLine)
    }

    moves.push({
      san: mv.san, uci: mv.lan, class: cls,
      evalAfterCp, mateAfter, bestMoveUci,
      winPctBefore: wBefore, winPctAfter: wAfter,
    })
    cpLosses[mover].push(Math.min(1000, Math.max(0, cpBefore - cpAfterMover)))
    replay.move(mv.san)
  }

  const emptyCounts = () =>
    Object.fromEntries(Object.keys(CLASS_META).map((k) => [k, 0])) as Record<MoveClass, number>
  const counts = { w: emptyCounts(), b: emptyCounts() }
  const accs: { w: number[]; b: number[] } = { w: [], b: [] }
  moves.forEach((m, i) => {
    const color = i % 2 === 0 ? 'w' : 'b'
    counts[color][m.class]++
    // Accuracy par coup, formule lichess.
    const drop = Math.max(0, m.winPctBefore - m.winPctAfter)
    const acc = Math.max(0, Math.min(100, 103.1668 * Math.exp(-0.04354 * drop) - 3.1669))
    accs[color].push(acc)
  })
  const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 100)

  // Win% blanc après chaque demi-coup (index 0 = départ).
  const winPctSeries: number[] = [50]
  moves.forEach((m) => {
    winPctSeries.push(m.evalAfterCp !== null ? winPct(m.evalAfterCp) : winPctSeries[winPctSeries.length - 1])
  })

  return {
    moves,
    accuracyWhite: Math.round(mean(accs.w) * 10) / 10,
    accuracyBlack: Math.round(mean(accs.b) * 10) / 10,
    counts,
    gameRatingWhite: ratingFromAcpl(mean(cpLosses.w.length ? cpLosses.w : [0])),
    gameRatingBlack: ratingFromAcpl(mean(cpLosses.b.length ? cpLosses.b : [0])),
    winPctSeries,
  }
}

// Elo estimé depuis l'ACPL (centipawn loss moyen) : table empirique interpolée.
const ACPL_RATING: [number, number][] = [
  [5, 2800], [15, 2350], [25, 1900], [40, 1500], [60, 1150], [90, 850], [140, 600], [200, 400],
]

export function ratingFromAcpl(acpl: number): number {
  if (acpl <= ACPL_RATING[0][0]) return ACPL_RATING[0][1]
  for (let i = 1; i < ACPL_RATING.length; i++) {
    const [x1, y1] = ACPL_RATING[i - 1]
    const [x2, y2] = ACPL_RATING[i]
    if (acpl <= x2) {
      const t = (acpl - x1) / (x2 - x1)
      return Math.round((y1 + t * (y2 - y1)) / 50) * 50
    }
  }
  return ACPL_RATING[ACPL_RATING.length - 1][1]
}
