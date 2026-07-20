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
  // Position de départ (FEN) et trait initial — départ custom possible (puzzle).
  startFen: string
  startTurn: 'w' | 'b'
  accuracyWhite: number
  accuracyBlack: number
  counts: { w: Record<MoveClass, number>; b: Record<MoveClass, number> }
  // Elo estimé de la performance sur cette partie (par couleur).
  gameRatingWhite: number
  gameRatingBlack: number
  // Win% blanc après chaque demi-coup ; index 0 = position initiale. Longueur = coups + 1.
  winPctSeries: number[]
}

// label : tallies et listes. headline : « {san} est {headline} » dans la bulle coach.
export const CLASS_META: Record<
  MoveClass,
  { label: string; headline: string; symbol: string; color: string }
> = {
  brilliant: { label: 'Brillant', headline: 'brillant', symbol: '!!', color: '#1baca6' },
  great: { label: 'Très bon', headline: 'un très bon coup', symbol: '!', color: '#5b8bb0' },
  best: { label: 'Meilleur', headline: 'le meilleur', symbol: '★', color: '#81b64c' },
  excellent: { label: 'Excellent', headline: 'excellent', symbol: '👍', color: '#81b64c' },
  good: { label: 'Bon', headline: 'un bon coup', symbol: '✓', color: '#95b776' },
  book: { label: 'Théorique', headline: 'un coup théorique', symbol: '📖', color: '#a88865' },
  inaccuracy: { label: 'Imprécision', headline: 'une imprécision', symbol: '?!', color: '#f7c631' },
  mistake: { label: 'Erreur', headline: 'une erreur', symbol: '?', color: '#ffa459' },
  miss: { label: 'Coup manqué', headline: 'une occasion manquée', symbol: '✗', color: '#ff7769' },
  missedWin: { label: 'Gain manqué', headline: 'un gain manqué', symbol: '−', color: '#ff7769' },
  blunder: { label: 'Gaffe', headline: 'une gaffe', symbol: '??', color: '#fa412d' },
}

// SAN avec figurines (Nf3 -> ♘f3 / ♞f3 selon le camp), plus lisible partout.
const FIGURINES: Record<'w' | 'b', Record<string, string>> = {
  w: { K: '♔', Q: '♕', R: '♖', B: '♗', N: '♘' },
  b: { K: '♚', Q: '♛', R: '♜', B: '♝', N: '♞' },
}
export function figurine(san: string, color: 'w' | 'b' = 'b'): string {
  return san.replace(/[KQRBN]/g, (c) => FIGURINES[color][c])
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
  // Position de départ custom (puzzle, FEN importé) : header FEN du PGN.
  const customStart = game.header().FEN ?? undefined

  // Évaluations de chaque position (avant coup 1, après coup 1, ...).
  const chess = new Chess(customStart)
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
  const replay = new Chess(customStart)
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
    if (!customStart && isBookPosition(uciSoFar)) {
      cls = 'book'
    } else if (mv.lan !== bestMoveUci && wBefore >= 85 && wAfter < 55) {
      // Position gagnante jetée : Gain manqué (prioritaire sur l'échelle standard).
      cls = 'missedWin'
    } else if (mv.lan !== bestMoveUci && opponentJustBlundered && drop >= 5) {
      // L'adversaire venait d'offrir l'avantage, non puni : Occasion manquée.
      cls = 'miss'
    } else if (mv.lan === bestMoveUci) {
      // Brillant (critères chess.com) : sacrifice réel d'au moins une pièce
      // mineure, sur une case effectivement prenable par l'adversaire, dans
      // une position pas déjà largement gagnante sans ce coup, et qui reste
      // au moins égale ensuite.
      const balBefore = materialBalance(replay, mover)
      const balAfter2 = -materialBalance(replayAfter, replayAfter.turn())
      const sacrifice = balBefore - balAfter2 >= 2 && !replayAfter.isCheckmate()
      const destAttacked = sacrifice && replayAfter.isAttacked(mv.to, replayAfter.turn())
      const secondBestWinPct = before[1] ? winPct(lineCp(before[1])) : 0
      const secondGap = wBefore - secondBestWinPct
      if (sacrifice && destAttacked && secondBestWinPct < 85 && wAfter >= 50) {
        cls = 'brilliant'
      } else if (
        secondGap > 20 || // seul bon coup de la position
        (wBefore < 45 && wAfter >= 50) || // renverse : perdant -> au moins égal
        (wBefore >= 45 && wBefore < 55 && wAfter >= 70) // renverse : égal -> nettement gagnant
      ) {
        cls = 'great'
      } else cls = 'best'
    } else if (drop < 3.5) cls = 'excellent'
    else if (drop < 7) cls = 'good'
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

  const startTurn = new Chess(customStart).turn()
  const colorAt = (i: number): 'w' | 'b' =>
    (i % 2 === 0) === (startTurn === 'w') ? 'w' : 'b'

  const emptyCounts = () =>
    Object.fromEntries(Object.keys(CLASS_META).map((k) => [k, 0])) as Record<MoveClass, number>
  const counts = { w: emptyCounts(), b: emptyCounts() }

  // Win% blanc après chaque demi-coup (index 0 = départ).
  const startPct = moves.length
    ? startTurn === 'w'
      ? moves[0].winPctBefore
      : 100 - moves[0].winPctBefore
    : 50
  const winPctSeries: number[] = [startPct]
  moves.forEach((m) => {
    winPctSeries.push(m.evalAfterCp !== null ? winPct(m.evalAfterCp) : winPctSeries[winPctSeries.length - 1])
  })

  // Accuracy par coup (formule Lichess) + poids de volatilité : écart-type du
  // win% dans une fenêtre glissante autour du coup (~10 plis, comme Lichess).
  // Un coup joué en pleine bagarre tactique pèse plus qu'un coup dans une
  // position calme déjà décidée.
  const windowSize = Math.min(8, Math.max(2, Math.round(moves.length / 10)))
  const accs: { w: number[]; b: number[] } = { w: [], b: [] }
  const weights: { w: number[]; b: number[] } = { w: [], b: [] }
  moves.forEach((m, i) => {
    const color = colorAt(i)
    counts[color][m.class]++
    const drop = Math.max(0, m.winPctBefore - m.winPctAfter)
    const acc = Math.max(0, Math.min(100, 103.1668 * Math.exp(-0.04354 * drop) - 3.1669))
    accs[color].push(acc)

    const half = Math.floor(windowSize / 2)
    const lo = Math.max(0, i + 1 - half)
    const hi = Math.min(winPctSeries.length - 1, i + 1 + half)
    const window = winPctSeries.slice(lo, hi + 1)
    const windowMean = window.reduce((a, b) => a + b, 0) / window.length
    const variance = window.reduce((a, b) => a + (b - windowMean) ** 2, 0) / window.length
    weights[color].push(Math.min(12, Math.max(0.5, Math.sqrt(variance))))
  })

  const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 100)
  const harmonicMean = (xs: number[]) =>
    xs.length ? xs.length / xs.reduce((a, x) => a + 1 / Math.max(x, 1), 0) : 100
  const weightedMean = (xs: number[], ws: number[]) => {
    const sumW = ws.reduce((a, b) => a + b, 0)
    return sumW ? xs.reduce((a, x, i) => a + x * ws[i], 0) / sumW : mean(xs)
  }
  // Précision finale façon Lichess : moyenne de la moyenne harmonique (pénalise
  // les gaffes isolées) et de la moyenne pondérée par volatilité (pénalise les
  // fautes dans les moments critiques). Plus fidèle qu'une moyenne arithmétique
  // simple, trop indulgente pour une partie propre avec une seule grosse gaffe.
  const accuracy = (color: 'w' | 'b') =>
    Math.round(((harmonicMean(accs[color]) + weightedMean(accs[color], weights[color])) / 2) * 10) / 10

  return {
    moves,
    startFen: new Chess(customStart).fen(),
    startTurn,
    accuracyWhite: accuracy('w'),
    accuracyBlack: accuracy('b'),
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
