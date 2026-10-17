// Insights façon chess.com : ce que disent mes N dernières parties analysées. Pur (sans React,
// sans moteur, sans Dexie) : entrée = lignes `reviews` (bilans Stockfish mis en cache), sortie =
// chiffres, forces et faiblesses chiffrées, plan d'entraînement et résumé du coach généré par
// règles depuis les chiffres seuls. Exécuté aussi sous Node par la suite E2E (banc).
//
// Conventions :
// - seuls les coups du joueur comptent ; les précisions par phase et les comptes de fautes
//   excluent les coups théoriques (`book`), pour ne pas faire de la théorie une « force » ;
//   les précisions par partie reprennent celles du bilan `review.ts` ;
// - phases : `detectPhases` (coach.ts), ouverture étendue à au moins 20 demi-coups comme chez
//   chess.com (bornée par la finale) ;
// - une faiblesse coûte la part du win% perdu par le joueur dans ce qu'elle désigne : c'est
//   « là où je pèche ».
import { Chess, type PieceSymbol, type Square } from 'chess.js'
import type { ReviewRow } from './db'
import { figurine, moveAccuracy, type GameReview, type MoveClass, type ReviewedMove } from './review'
import { afterUci, colorAt, detectPhases, lostToReply, mateAgainst, moveNumber, stillAfterBest } from './coach'
import { timeClassLabel } from './chesscom'
import { attacksFrom, backRankMate, captureInfo, fork, isInBadSpot, mateInOne, other, pinOrSkewer, sanOf } from './motifs'
import { openingForMoves } from './openings'
import { openingFamilyFr } from './openingNames'
import { familyOfLine } from './openingFamilies'
import { DEFENSE_CLASSES, missedDefense } from './kingAttack'

export type Phase = 'opening' | 'middlegame' | 'endgame'
export const PHASES: Phase[] = ['opening', 'middlegame', 'endgame']
export const PHASE_FR: Record<Phase, string> = { opening: 'Ouverture', middlegame: 'Milieu de partie', endgame: 'Finale' }
const PHASE_LOW: Record<Phase, string> = { opening: "l'ouverture", middlegame: 'le milieu de partie', endgame: 'la finale' }

const START_FEN = new Chess().fen()
// Ouverture d'au moins 20 demi-coups (10 coups chacun), comme le découpage de chess.com Insights.
export const OPENING_MIN_PLIES = 20
// Moins de 10 % du temps de base à la pendule avant de jouer : « sous pression ».
export const PRESSURE_SHARE = 0.1
// ±3 pions : position gagnante / perdante (conversion, défense, défaite au temps gagnante).
export const DECISIVE_CP = 300
// Une partie de moins de 5 coups du joueur vaut 100 de précision par construction : hors moyenne.
export const MIN_OWN_MOVES = 5

const MISTAKE_CLASSES: MoveClass[] = ['mistake', 'miss', 'missedWin']
const FAULT_CLASSES: MoveClass[] = ['mistake', 'miss', 'missedWin', 'blunder']

const dropOf = (m: ReviewedMove) => Math.max(0, m.winPctBefore - m.winPctAfter)

// ------------------------------------------------------------------ lecture des parties

// Pendules `[%clk h:mm:ss(.d)]` d'un PGN chess.com, en secondes, une par demi-coup dans l'ordre
// (la pendule du camp qui vient de jouer). Null sans aucune pendule.
export function parseClocks(pgn: string): number[] | null {
  const movetext = pgn.replace(/^\[.*\]\s*$/gm, '')
  const out: number[] = []
  for (const m of movetext.matchAll(/\[%clk\s+(\d+):(\d{1,2}):(\d{1,2}(?:\.\d+)?)\]/g)) {
    out.push(Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3]))
  }
  return out.length ? out : null
}

// En-tête TimeControl chess.com : « 180 », « 180+2 » (secondes). Le différé (« 1/86400 ») et
// l'illimité (« - ») n'ont pas de pendule exploitable.
export function parseTimeControl(tc: string | undefined | null): { base: number; inc: number } | null {
  const m = tc?.trim().match(/^(\d+)(?:\+(\d+))?$/)
  if (!m) return null
  const base = Number(m[1])
  return base > 0 ? { base, inc: Number(m[2] ?? 0) } : null
}

function headerOf(pgn: string, name: string): string | null {
  return pgn.match(new RegExp(`^\\[${name} "([^"]*)"\\]`, 'm'))?.[1] ?? null
}

// ------------------------------------------------------------------ types du rapport

export type ErrorKind =
  | 'hanging' | 'ignoredThreat' | 'allowedMate' | 'allowedFork' | 'allowedPin'
  | 'missedMate' | 'missedBackRank' | 'missedFork' | 'missedPin' | 'missedFreePiece' | 'missedKingAttack'

export const ERROR_META: Record<ErrorKind, { label: string; plural: string; hint: string }> = {
  hanging: { label: 'Pièce laissée en prise', plural: 'pièces laissées en prise', hint: "Ton coup laisse une pièce que l'adversaire prend pour rien." },
  ignoredThreat: { label: 'Menace ignorée', plural: 'menaces ignorées', hint: "Une de tes pièces était déjà attaquée : tu as joué ailleurs et l'adversaire l'a prise." },
  allowedMate: { label: 'Mat en 1 autorisé', plural: 'mats en 1 autorisés', hint: "L'adversaire menaçait mat : ton coup ne l'empêchait pas, le meilleur coup si." },
  allowedFork: { label: 'Fourchette autorisée', plural: 'fourchettes autorisées', hint: "Ton coup permet une fourchette que le meilleur coup empêchait." },
  allowedPin: { label: 'Clouage autorisé', plural: 'clouages autorisés', hint: "Ton coup permet un clouage que le meilleur coup empêchait." },
  missedMate: { label: 'Mat manqué', plural: 'mats manqués', hint: 'Un mat était sur l\'échiquier et tu ne l\'as pas joué.' },
  missedBackRank: { label: 'Mat du couloir manqué', plural: 'mats du couloir manqués', hint: 'Le roi adverse était enfermé sur sa dernière rangée.' },
  missedFork: { label: 'Fourchette manquée', plural: 'fourchettes manquées', hint: 'Le meilleur coup attaquait deux pièces à la fois.' },
  missedPin: { label: 'Clouage manqué', plural: 'clouages manqués', hint: 'Le meilleur coup clouait une pièce adverse.' },
  missedFreePiece: { label: 'Pièce gratuite manquée', plural: 'pièces gratuites manquées', hint: 'Une pièce adverse se prenait sans reprise possible.' },
  missedKingAttack: { label: 'Attaque sur le roi manquée', plural: 'attaques sur le roi manquées', hint: 'Le meilleur coup amenait une pièce de plus contre le roi adverse.' },
}
export const ERROR_KINDS = Object.keys(ERROR_META) as ErrorKind[]

export interface Example {
  key: string // clé `reviews` de la partie
  index: number // index du coup fautif dans le bilan (0 = premier demi-coup)
  ply: number // index + 1
  moveNo: string // « 12. » ou « 12... »
  fen: string // position AVANT le coup
  san: string
  sanFig: string
  bestSan: string | null // meilleur coup en figurines
  drop: number // win% perdu
  color: 'w' | 'b'
  date: number
  label: string // libellé de la partie pour l'Analyse
}

export interface ErrorStat {
  kind: ErrorKind
  count: number
  drop: number // win% perdu cumulé
  examples: Example[] // les plus coûteux d'abord
  moves: Record<string, number> // `clé:index` du coup -> win% perdu : un coup à deux étiquettes ne compte qu'une fois dans un regroupement
}

export interface PhaseStat {
  moves: number // coups du joueur hors théorie
  accuracy: number | null
  mistakes: number // erreurs, occasions et gains manqués
  blunders: number
  mistakesPer100: number
  blundersPer100: number
  gamesEnded: number // parties terminées dans cette phase
  drop: number // win% perdu dans la phase
  dropShare: number // part du win% total perdu
}

export interface ColorStat {
  n: number
  wins: number
  draws: number
  losses: number
  score: number // %
  accuracy: number | null
}

export interface OpeningStat {
  key: string // famille lichess (clé de l'entraîneur)
  name: string // famille en français
  color: 'w' | 'b'
  n: number
  wins: number
  draws: number
  losses: number
  score: number
  accuracy: number | null
  exitEval: number | null // évaluation moyenne à la sortie de l'ouverture, point de vue du joueur (cp)
  costly: boolean
}

export interface TimeStat {
  gamesWithClocks: number
  pressureMoves: number
  pressureBlunders: number
  normalMoves: number
  normalBlunders: number
  pressureRate: number | null // gaffes pour 100 coups sous pression
  normalRate: number | null
  avgSecPerMove: Record<Phase, number | null>
  pressureDrop: number // win% perdu par les gaffes sous pression (toutes, pas seulement les exemples)
  examples: Example[] // gaffes sous pression
}

export interface PlanStep {
  label: string
  to?: string // route de l'app (avec sa requête), absente pour un simple conseil
  state?: Record<string, string> // state de navigation (séance Tactiques ciblée)
}

export interface Finding {
  id: string
  kind: 'faiblesse' | 'force'
  title: string
  detail: string // toujours chiffré
  severity: number // [0, 1]
  plan: PlanStep[]
  examples: Example[]
}

export interface Insights {
  games: {
    n: number
    wins: number
    draws: number
    losses: number
    score: number
    from: number | null
    to: number | null
    lostOnTime: number
    lostOnTimeWinning: number
    skipped: number // lignes illisibles ignorées
    timeClasses: ReviewRow['timeClass'][]
    byColor: Record<'w' | 'b', ColorStat>
  }
  accuracy: {
    mean: number | null
    games: number // parties comptées (au moins 5 coups du joueur)
    perGame: { key: string; date: number; acc: number; result: ReviewRow['result'] }[] // la plus ancienne d'abord
    firstHalf: number | null
    secondHalf: number | null
  }
  phases: Record<Phase, PhaseStat>
  openings: OpeningStat[]
  costlyOpenings: OpeningStat[]
  time: TimeStat | null
  errors: ErrorStat[] // dans l'ordre d'ERROR_KINDS, comptes nuls compris
  conversion: { winning: number; converted: number }
  defense: { losing: number; saved: number }
  kingDefense: { faults: number; games: number; drop: number; examples: Example[] }
  opportunism: { chances: number; punished: number }
  ratingBands: Record<'weaker' | 'equal' | 'stronger', { n: number; score: number | null }> | null
  tilt: { n: number; score: number; overall: number } | null
  ownMoves: number // coups du joueur hors théorie
  totalDrop: number
  // Les 3 plus sévères de chaque côté ; `candidates` garde toutes celles qui passent leur seuil.
  findings: { weaknesses: Finding[]; strengths: Finding[]; candidates: { weaknesses: Finding[]; strengths: Finding[] } }
  narrative: string[]
}

// ------------------------------------------------------------------ outils

const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0)
const mean = (xs: number[]) => (xs.length ? sum(xs) / xs.length : null)
const round1 = (n: number) => Math.round(n * 10) / 10
export const fr1 = (n: number) => n.toFixed(1).replace('.', ',')
export const pct = (n: number) => `${Math.round(n)} %`
const plural = (n: number, one: string, many: string) => `${n} ${n > 1 ? many : one}`
const resultScore = (r: ReviewRow['result']) => (r === 'win' ? 1 : r === 'draw' ? 0.5 : 0)
const scorePct = (rs: ReviewRow['result'][]) => (rs.length ? (sum(rs.map(resultScore)) / rs.length) * 100 : 0)
const clampCp = (cp: number) => Math.max(-1000, Math.min(1000, cp))
const povCp = (cp: number, color: 'w' | 'b') => (color === 'w' ? cp : -cp)

export function frDate(ms: number): string {
  return new Date(ms).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function gameLabel(row: Pick<ReviewRow, 'source' | 'opponent' | 'opponentRating' | 'date'>): string {
  const who = row.opponentRating ? `${row.opponent} (${row.opponentRating})` : row.opponent
  return `${row.source === 'chesscom' ? 'chess.com' : 'ChessLocal'} · contre ${who} · ${frDate(row.date)}`
}

// Ligne exploitable : bilan cohérent avec son PGN (chaque SAN se rejoue depuis le départ).
export function validRow(row: ReviewRow): boolean {
  const r = row?.review
  if (!r || !Array.isArray(r.moves) || typeof r.startFen !== 'string') return false
  if (row.playerColor !== 'w' && row.playerColor !== 'b') return false
  if (!['win', 'draw', 'loss'].includes(row.result)) return false
  if (!['bullet', 'blitz', 'rapid', 'unlimited'].includes(row.timeClass) || typeof row.opponent !== 'string') return false
  if (typeof row.key !== 'string' || typeof row.pgn !== 'string' || !Number.isFinite(row.date)) return false
  if (!Number.isFinite(r.accuracyWhite) || !Number.isFinite(r.accuracyBlack) || (r.startTurn !== 'w' && r.startTurn !== 'b')) return false
  try {
    const c = new Chess(r.startFen)
    // Trait initial du bilan = trait de la position : sinon les couleurs seraient inversées.
    if (c.turn() !== r.startTurn) return false
    for (const m of r.moves) {
      if (typeof m?.san !== 'string' || typeof m.uci !== 'string' || typeof m.bestMoveUci !== 'string' || typeof m.class !== 'string') return false
      if (!Number.isFinite(m.winPctBefore) || !Number.isFinite(m.winPctAfter)) return false
      if (m.evalAfterCp !== null && !Number.isFinite(m.evalAfterCp)) return false
      // Le coup UCI du bilan est bien celui que la SAN rejoue.
      if (c.move(m.san).lan !== m.uci) return false
    }
  } catch {
    return false
  }
  return true
}

// ------------------------------------------------------------------ attaque sur le roi

// Heuristique documentée (F12 pourra la remplacer par son diagnostic d'attaque) : un coup
// « offensif vers le roi » est un coup de pièce (pas du roi), pas un échange ni une reprise, qui
// donne échec, prend dans la zone 3x3 du roi adverse ou se met à attaquer une case de cette zone
// qu'il n'attaquait pas ; après lui, les pièces du joueur qui attaquent la zone (roi exclu, chacune
// comptée une fois) sont au moins 2 et au moins aussi nombreuses que les défenseurs (même règle
// côté adverse).
function kingZone(c: Chess, color: 'w' | 'b'): Set<Square> {
  const k = c.findPiece({ type: 'k', color })[0]
  const zone = new Set<Square>()
  if (!k) return zone
  const f0 = k.charCodeAt(0) - 97
  const r0 = Number(k[1]) - 1
  for (let df = -1; df <= 1; df++) {
    for (let dr = -1; dr <= 1; dr++) {
      const f = f0 + df
      const r = r0 + dr
      if (f >= 0 && f < 8 && r >= 0 && r < 8) zone.add((String.fromCharCode(97 + f) + (r + 1)) as Square)
    }
  }
  return zone
}

function zoneHitters(c: Chess, color: 'w' | 'b', zone: Set<Square>): number {
  let n = 0
  for (const row of c.board()) {
    for (const sq of row) {
      if (!sq || sq.color !== color || sq.type === 'k') continue
      if (attacksFrom(c, sq.square).some((s) => zone.has(s))) n++
    }
  }
  return n
}

export function isKingAttackMove(fen: string, uci: string, lastCaptureSquare: string | null): boolean {
  const c = new Chess(fen)
  const mover = c.turn()
  const opp = other(mover)
  const fromSq = uci.slice(0, 2) as Square
  const piece = c.get(fromSq)
  if (!piece || piece.type === 'k') return false
  const cap = captureInfo(fen, uci, lastCaptureSquare)
  if (cap && (cap.kind === 'echange' || cap.kind === 'reprise')) return false
  const zone = kingZone(c, opp)
  const before = new Set(attacksFrom(c, fromSq))
  let mv
  try {
    mv = c.move({ from: fromSq, to: uci.slice(2, 4), promotion: uci[4] })
  } catch {
    return false
  }
  const touches = c.inCheck() || (!!mv.captured && zone.has(mv.to)) || attacksFrom(c, mv.to).some((s) => zone.has(s) && !before.has(s))
  if (!touches) return false
  const attackers = zoneHitters(c, mover, zone)
  return attackers >= 2 && attackers >= zoneHitters(c, opp, zone)
}

const queensOn = (c: Chess) => c.findPiece({ type: 'q', color: 'w' }).length > 0 && c.findPiece({ type: 'q', color: 'b' }).length > 0

// ------------------------------------------------------------------ calcul

interface GameCtx {
  row: ReviewRow
  review: GameReview
  color: 'w' | 'b'
  oEnd: number
  eStart: number
  own: number[] // index des coups du joueur
  counted: boolean // au moins MIN_OWN_MOVES coups du joueur
  accuracy: number
}

function phaseOf(g: Pick<GameCtx, 'oEnd' | 'eStart'>, i: number): Phase {
  return i <= g.oEnd ? 'opening' : i < g.eStart ? 'middlegame' : 'endgame'
}

// Découpage d'une partie : ouverture étendue à OPENING_MIN_PLIES (bornée par la finale).
export function insightPhases(review: GameReview): { oEnd: number; eStart: number } {
  const ph = detectPhases(review)
  const eStart = ph.endgameStart
  const oEnd = review.startFen === START_FEN ? Math.min(Math.max(ph.openingEnd, OPENING_MIN_PLIES - 1), eStart - 1) : ph.openingEnd
  return { oEnd, eStart }
}

export function computeInsights(input: ReviewRow[]): Insights {
  const valid = input.filter(validRow)
  const skipped = input.length - valid.length
  // Ordre chronologique : série de précision, tilt, tendance.
  const rows = [...valid].sort((a, b) => a.date - b.date)
  const games: GameCtx[] = rows.map((row) => {
    const review = row.review
    const { oEnd, eStart } = insightPhases(review)
    const own = review.moves.map((_, i) => i).filter((i) => colorAt(review, i) === row.playerColor)
    return {
      row, review, color: row.playerColor, oEnd, eStart, own,
      counted: own.length >= MIN_OWN_MOVES,
      accuracy: row.playerColor === 'w' ? review.accuracyWhite : review.accuracyBlack,
    }
  })

  // ---------- parties ----------
  const results = games.map((g) => g.row.result)
  const colorStat = (c: 'w' | 'b'): ColorStat => {
    const gs = games.filter((g) => g.color === c)
    const rs = gs.map((g) => g.row.result)
    const acc = mean(gs.filter((g) => g.counted).map((g) => g.accuracy))
    return {
      n: gs.length, wins: rs.filter((r) => r === 'win').length, draws: rs.filter((r) => r === 'draw').length,
      losses: rs.filter((r) => r === 'loss').length, score: scorePct(rs), accuracy: acc === null ? null : round1(acc),
    }
  }
  const lastEvalPov = (g: GameCtx): number | null => {
    for (let i = g.review.moves.length - 1; i >= 0; i--) {
      const e = g.review.moves[i].evalAfterCp
      if (e !== null && e !== undefined) return povCp(e, g.color)
    }
    return null
  }
  const lostOnTime = games.filter((g) => g.row.lostOnTime && g.row.result === 'loss')
  const gamesBlock: Insights['games'] = {
    n: games.length,
    wins: results.filter((r) => r === 'win').length,
    draws: results.filter((r) => r === 'draw').length,
    losses: results.filter((r) => r === 'loss').length,
    score: scorePct(results),
    from: games.length ? games[0].row.date : null,
    to: games.length ? games[games.length - 1].row.date : null,
    lostOnTime: lostOnTime.length,
    lostOnTimeWinning: lostOnTime.filter((g) => (lastEvalPov(g) ?? 0) >= DECISIVE_CP).length,
    skipped,
    timeClasses: [...new Set(games.map((g) => g.row.timeClass))],
    byColor: { w: colorStat('w'), b: colorStat('b') },
  }

  // ---------- précision ----------
  const perGame = games.filter((g) => g.counted).map((g) => ({ key: g.row.key, date: g.row.date, acc: g.accuracy, result: g.row.result }))
  const accMean = mean(perGame.map((x) => x.acc))
  const half = Math.floor(perGame.length / 2)
  const accuracy: Insights['accuracy'] = {
    mean: accMean === null ? null : round1(accMean),
    games: perGame.length,
    perGame,
    firstHalf: half > 0 ? round1(mean(perGame.slice(0, half).map((x) => x.acc))!) : null,
    secondHalf: half > 0 ? round1(mean(perGame.slice(half).map((x) => x.acc))!) : null,
  }

  // ---------- phases ----------
  const phaseMoves: Record<Phase, ReviewedMove[]> = { opening: [], middlegame: [], endgame: [] }
  const ended: Record<Phase, number> = { opening: 0, middlegame: 0, endgame: 0 }
  for (const g of games) {
    for (const i of g.own) {
      const m = g.review.moves[i]
      if (m.class !== 'book') phaseMoves[phaseOf(g, i)].push(m)
    }
    if (g.review.moves.length > 0) ended[phaseOf(g, g.review.moves.length - 1)]++
  }
  const totalDrop = sum(PHASES.flatMap((p) => phaseMoves[p].map(dropOf)))
  const phases = Object.fromEntries(
    PHASES.map((p) => {
      const ms = phaseMoves[p]
      const acc = mean(ms.map(moveAccuracy))
      const mistakes = ms.filter((m) => MISTAKE_CLASSES.includes(m.class)).length
      const blunders = ms.filter((m) => m.class === 'blunder').length
      const drop = sum(ms.map(dropOf))
      const stat: PhaseStat = {
        moves: ms.length,
        accuracy: acc === null ? null : round1(acc),
        mistakes, blunders,
        mistakesPer100: ms.length ? round1((mistakes / ms.length) * 100) : 0,
        blundersPer100: ms.length ? round1((blunders / ms.length) * 100) : 0,
        gamesEnded: ended[p],
        drop,
        dropShare: totalDrop > 0 ? drop / totalDrop : 0,
      }
      return [p, stat]
    }),
  ) as Record<Phase, PhaseStat>
  const ownMoves = sum(PHASES.map((p) => phases[p].moves))

  // ---------- ouvertures ----------
  const openingGroups = new Map<string, { key: string; color: 'w' | 'b'; gs: GameCtx[]; exits: number[] }>()
  for (const g of games) {
    if (g.review.startFen !== START_FEN) continue
    const o = openingForMoves(g.review.moves.map((m) => m.uci))
    if (!o) continue
    const key = familyOfLine(o.name)
    const id = `${key}|${g.color}`
    if (!openingGroups.has(id)) openingGroups.set(id, { key, color: g.color, gs: [], exits: [] })
    const grp = openingGroups.get(id)!
    grp.gs.push(g)
    // Évaluation à la sortie de l'ouverture : seulement si la partie continue au-delà (une partie
    // finie en ouverture n'en sort pas, son évaluation finale n'en dit rien).
    const exit = g.oEnd >= 0 && g.oEnd < g.review.moves.length - 1 ? g.review.moves[g.oEnd].evalAfterCp : null
    if (exit !== null && exit !== undefined) grp.exits.push(clampCp(povCp(exit, g.color)))
  }
  const overall = gamesBlock.score
  const openings: OpeningStat[] = [...openingGroups.values()]
    .map(({ key, color, gs, exits }) => {
      const rs = gs.map((g) => g.row.result)
      const acc = mean(gs.filter((g) => g.counted).map((g) => g.accuracy))
      const exitEval = mean(exits)
      const score = scorePct(rs)
      const costly = gs.length >= 3 && ((score <= 33 && score <= overall - 20) || (exitEval !== null && exitEval <= -120))
      return {
        key, name: openingFamilyFr(key), color, n: gs.length,
        wins: rs.filter((r) => r === 'win').length, draws: rs.filter((r) => r === 'draw').length, losses: rs.filter((r) => r === 'loss').length,
        score, accuracy: acc === null ? null : round1(acc), exitEval: exitEval === null ? null : Math.round(exitEval), costly,
      }
    })
    .sort((a, b) => b.n - a.n || a.score - b.score || a.name.localeCompare(b.name, 'fr'))
  const costlyOpenings = openings.filter((o) => o.costly).sort((a, b) => a.score - b.score || b.n - a.n)

  // ---------- erreurs typiques, pendule, conversion, opportunisme ----------
  const errors = Object.fromEntries(ERROR_KINDS.map((k): [ErrorKind, ErrorStat] => [k, { kind: k, count: 0, drop: 0, examples: [], moves: {} }])) as Record<ErrorKind, ErrorStat>
  const time = { games: 0, pressureMoves: 0, pressureBlunders: 0, normalMoves: 0, normalBlunders: 0, pressureDrop: 0, examples: [] as Example[] }
  const secs: Record<Phase, number[]> = { opening: [], middlegame: [], endgame: [] }
  const kingDefense: Insights['kingDefense'] = { faults: 0, games: 0, drop: 0, examples: [] }
  const attackedGames = new Set<string>()
  let winning = 0
  let converted = 0
  let losing = 0
  let saved = 0
  let chances = 0
  let punished = 0

  for (const g of games) {
    const { review, row, color } = g
    const label = gameLabel(row)
    const example = (i: number, fen: string, bestSan: string | null): Example => ({
      key: row.key, index: i, ply: i + 1, moveNo: moveNumber(review, i), fen, san: review.moves[i].san,
      sanFig: figurine(review.moves[i].san, color), bestSan: bestSan ? figurine(bestSan, color) : null,
      drop: dropOf(review.moves[i]), color, date: row.date, label,
    })

    // Positions avant chaque coup et coups joués (cases, prises).
    const replay = new Chess(review.startFen)
    const fens: string[] = [replay.fen()]
    const played: { to: string; captured?: PieceSymbol }[] = []
    for (const m of review.moves) {
      const mv = replay.move(m.san)
      played.push({ to: mv.to, captured: mv.captured as PieceSymbol | undefined })
      fens.push(replay.fen())
    }

    // Pendule : une pendule par demi-coup, cadence lisible.
    const clocks = parseClocks(row.pgn)
    const tc = parseTimeControl(headerOf(row.pgn, 'TimeControl'))
    const withClocks = !!clocks && !!tc && clocks.length === review.moves.length && review.moves.length > 0
    if (withClocks) time.games++

    for (const i of g.own) {
      const m = review.moves[i]
      const phase = phaseOf(g, i)
      const fenBefore = fens[i]
      const fenAfter = fens[i + 1]

      if (withClocks) {
        const before = i >= 2 ? clocks![i - 2] : tc!.base
        secs[phase].push(Math.max(0, before - clocks![i] + tc!.inc))
        if (m.class !== 'book') {
          const pressure = before < PRESSURE_SHARE * tc!.base
          if (pressure) {
            time.pressureMoves++
            if (m.class === 'blunder') {
              time.pressureBlunders++
              time.pressureDrop += dropOf(m)
              time.examples.push(example(i, fenBefore, m.uci !== m.bestMoveUci ? sanOf(fenBefore, m.bestMoveUci) : null))
            }
          } else {
            time.normalMoves++
            if (m.class === 'blunder') time.normalBlunders++
          }
        }
      }

      // Même critère que « Mes défenses ratées », sur les seuls coups du joueur.
      const defense = DEFENSE_CLASSES.has(m.class) ? missedDefense(fenBefore, m.bestMoveUci) : null
      if (defense) {
        kingDefense.faults++
        kingDefense.drop += dropOf(m)
        attackedGames.add(row.key)
        kingDefense.examples.push(example(i, fenBefore, defense.bestSan))
      }

      if (!FAULT_CLASSES.includes(m.class)) continue
      const bestSan = m.uci !== m.bestMoveUci ? sanOf(fenBefore, m.bestMoveUci) : null
      const best = bestSan ? m.bestMoveUci : undefined
      const reply = review.moves[i + 1]?.bestMoveUci
      const prevMate = i > 0 ? review.moves[i - 1].mateAfter : null
      const against = mateAgainst(m.mateAfter, color)
      const wasFor = mateAgainst(prevMate, other(color))
      const forAfter = mateAgainst(m.mateAfter, other(color))
      const tags: ErrorKind[] = []

      if (best && bestSan!.endsWith('#')) tags.push(backRankMate(fenBefore, best) ? 'missedBackRank' : 'missedMate')
      else if (best && wasFor > 0 && forAfter === 0) tags.push('missedMate')
      if (against === 1 && best && mateInOne(afterUci(fenBefore, best)) === null) tags.push('allowedMate')

      const lost = lostToReply(fenAfter, reply, played[i])
      if (lost && !lost.capturer) {
        tags.push(lost.square === played[i].to || !isInBadSpot(new Chess(fenBefore), lost.square as Square) ? 'hanging' : 'ignoredThreat')
      }
      if (reply) {
        if (fork(fenAfter, reply) && !stillAfterBest(fenBefore, best, reply, fork)) tags.push('allowedFork')
        const l = pinOrSkewer(fenAfter, reply)
        if (l?.kind === 'clouage' && !stillAfterBest(fenBefore, best, reply, pinOrSkewer)) tags.push('allowedPin')
      }
      if (best) {
        if (fork(fenBefore, best)) tags.push('missedFork')
        if (pinOrSkewer(fenBefore, best)?.kind === 'clouage') tags.push('missedPin')
        const bc = captureInfo(fenBefore, best, null)
        if (bc && bc.clean && bc.net >= 2) tags.push('missedFreePiece')
      }
      if (tags.length === 0 && best && phase !== 'endgame' && queensOn(new Chess(fenBefore))) {
        const lastCap = i > 0 && played[i - 1].captured ? played[i - 1].to : null
        if (isKingAttackMove(fenBefore, best, lastCap) && !isKingAttackMove(fenBefore, m.uci, lastCap)) tags.push('missedKingAttack')
      }
      for (const t of tags) {
        errors[t].count++
        errors[t].drop += dropOf(m)
        errors[t].moves[`${row.key}:${i}`] = dropOf(m)
        errors[t].examples.push(example(i, fenBefore, bestSan))
      }
    }

    // Conversion et défense : l'évaluation a-t-elle franchi ±3 pions pour le joueur ?
    const evals = review.moves.map((m) => m.evalAfterCp).filter((e): e is number => e !== null && e !== undefined).map((e) => povCp(e, color))
    if (evals.some((e) => e >= DECISIVE_CP)) {
      winning++
      if (row.result === 'win') converted++
    }
    if (evals.some((e) => e <= -DECISIVE_CP)) {
      losing++
      if (row.result !== 'loss') saved++
    }

    // Opportunisme : gaffes adverses et réponse du joueur (une occasion manquée ou un gain manqué
    // n'est pas une punition).
    review.moves.forEach((m, i) => {
      if (colorAt(review, i) === color || (m.class !== 'blunder' && m.class !== 'missedWin')) return
      const next = review.moves[i + 1]
      if (!next) return
      chances++
      if (next.class !== 'miss' && next.class !== 'missedWin') punished++
    })
  }
  const errorList = ERROR_KINDS.map((k) => {
    const e = errors[k]
    e.examples.sort((a, b) => b.drop - a.drop || b.date - a.date)
    e.examples = e.examples.slice(0, 5)
    return e
  })
  time.examples.sort((a, b) => b.drop - a.drop)
  const timeStat: TimeStat | null = time.games
    ? {
        gamesWithClocks: time.games,
        pressureMoves: time.pressureMoves,
        pressureBlunders: time.pressureBlunders,
        normalMoves: time.normalMoves,
        normalBlunders: time.normalBlunders,
        pressureRate: time.pressureMoves ? round1((time.pressureBlunders / time.pressureMoves) * 100) : null,
        normalRate: time.normalMoves ? round1((time.normalBlunders / time.normalMoves) * 100) : null,
        avgSecPerMove: Object.fromEntries(PHASES.map((p) => [p, secs[p].length ? round1(mean(secs[p])!) : null])) as Record<Phase, number | null>,
        pressureDrop: time.pressureDrop,
        examples: time.examples.slice(0, 5),
      }
    : null

  // ---------- Elo adverse, tilt ----------
  const banded = games.filter((g) => typeof g.row.playerRating === 'number' && typeof g.row.opponentRating === 'number')
  let ratingBands: Insights['ratingBands'] = null
  if (banded.length) {
    const band = (f: (d: number) => boolean) => {
      const rs = banded.filter((g) => f(g.row.opponentRating! - g.row.playerRating!)).map((g) => g.row.result)
      return { n: rs.length, score: rs.length ? scorePct(rs) : null }
    }
    ratingBands = { weaker: band((d) => d <= -100), equal: band((d) => d > -100 && d < 100), stronger: band((d) => d >= 100) }
  }
  const afterLoss = games.filter((_, j) => j > 0 && games[j - 1].row.result === 'loss').map((g) => g.row.result)
  const tilt = afterLoss.length >= 3 ? { n: afterLoss.length, score: scorePct(afterLoss), overall } : null

  kingDefense.games = attackedGames.size
  kingDefense.examples.sort((a, b) => b.drop - a.drop)
  kingDefense.examples = kingDefense.examples.slice(0, 3)

  const base: Omit<Insights, 'findings' | 'narrative'> = {
    games: gamesBlock, accuracy, phases, openings, costlyOpenings, time: timeStat, errors: errorList,
    conversion: { winning, converted }, defense: { losing, saved }, opportunism: { chances, punished },
    ratingBands, tilt, ownMoves, totalDrop, kingDefense,
  }
  const findings = computeFindings(base)
  return { ...base, findings, narrative: narrate(base, findings) }
}

// ------------------------------------------------------------------ forces et faiblesses

export const BACK = { returnTo: '/insights', returnLabel: 'Retour aux Insights' }
const tactic = (theme: string, label: string): PlanStep => ({ label, to: '/apprendre', state: { tactic: theme, ...BACK } })
export const COLOR_FR = { w: 'Blancs', b: 'Noirs' } as const
const clamp01 = (x: number) => Math.max(0, Math.min(1, x))
// Dépassement relatif d'un seuil (rapporté au seuil) dans le sens du verdict : `over` au-dessus,
// `under` en dessous. Plancher 0,05 : une faiblesse retenue n'a jamais une sévérité nulle, et une
// valeur du bon côté du seuil ne pèse rien de plus.
const over = (value: number, threshold: number) => clamp01(Math.max(0.05, (value - threshold) / Math.max(1e-6, Math.abs(threshold))))
const under = (value: number, threshold: number) => over(-value, -threshold)

type Base = Omit<Insights, 'findings' | 'narrative'>

function errCount(b: Base, ...kinds: ErrorKind[]): number {
  return sum(kinds.map((k) => b.errors.find((e) => e.kind === k)!.count))
}
// Win% perdu par les coups portant au moins une de ces étiquettes, chaque coup compté une fois.
function errDrop(b: Base, ...kinds: ErrorKind[]): number {
  const moves: Record<string, number> = {}
  for (const k of kinds) Object.assign(moves, b.errors.find((e) => e.kind === k)!.moves)
  return sum(Object.values(moves))
}
function errExamples(b: Base, ...kinds: ErrorKind[]): Example[] {
  const seen = new Set<string>()
  return kinds
    .flatMap((k) => b.errors.find((e) => e.kind === k)!.examples)
    .sort((a, b2) => b2.drop - a.drop)
    .filter((e) => {
      const id = `${e.key}:${e.index}`
      if (seen.has(id)) return false
      seen.add(id)
      return true
    })
    .slice(0, 5)
}
const share = (b: Base, drop: number) => (b.totalDrop > 0 ? clamp01(drop / b.totalDrop) : 0)

// Thème de séance du motif manqué le plus fréquent.
function topMissedTheme(b: Base): { theme: string; label: string } {
  const cands: [ErrorKind, string, string][] = [
    ['missedFork', 'fork', 'Fourchettes'],
    ['missedPin', 'pin', 'Clouages'],
    ['missedFreePiece', 'hangingPiece', 'Pièces en prise'],
    ['missedMate', 'mateIn1', 'Mats en 1'],
  ]
  const top = cands.map(([k, theme, label]) => ({ n: errCount(b, k), theme, label })).sort((a, c) => c.n - a.n)[0]
  return top.n > 0 ? top : { theme: 'middlegame', label: 'Milieu de partie' }
}

function phasePlan(b: Base, p: Phase): PlanStep[] {
  if (p === 'opening') return [{ label: "Entraîneur d'ouvertures", to: '/ouvertures' }, tactic('opening', "Puzzles d'ouverture")]
  if (p === 'endgame') return [{ label: 'Finales à jouer contre Stockfish', to: '/finales' }, { label: 'Cours de finales', to: '/apprendre/finales' }]
  const t = topMissedTheme(b)
  return [tactic(t.theme, `Séance Tactiques : ${t.label.toLowerCase()}`), { label: 'Puzzle Rush (réflexes)', to: '/rush' }]
}

function computeFindings(b: Base): Insights['findings'] {
  const W: Finding[] = []
  const S: Finding[] = []
  const n = b.games.n
  const weak = (f: Omit<Finding, 'kind' | 'examples'> & { examples?: Example[] }) => W.push({ ...f, kind: 'faiblesse', examples: f.examples ?? [] })
  const strong = (f: Omit<Finding, 'kind' | 'examples' | 'plan'> & { plan?: PlanStep[] }) => S.push({ ...f, kind: 'force', plan: f.plan ?? [], examples: [] })

  // Phases.
  const eligible = PHASES.filter((p) => b.phases[p].moves >= 15 && b.phases[p].accuracy !== null)
  const bestPhase = [...eligible].sort((p, q) => b.phases[q].accuracy! - b.phases[p].accuracy!)[0]
  for (const p of eligible) {
    const st = b.phases[p]
    const acc = st.accuracy!
    const gap = bestPhase && bestPhase !== p ? b.phases[bestPhase].accuracy! - acc : 0
    const detail =
      `Précision ${fr1(acc)} sur ${st.moves} coups` +
      (gap > 0 ? ` (${fr1(b.phases[bestPhase].accuracy!)} en ${PHASE_FR[bestPhase].toLowerCase()})` : '') +
      ` · ${fr1(st.blundersPer100)} gaffes et ${fr1(st.mistakesPer100)} erreurs pour 100 coups · ${pct(st.dropShare * 100)} de l'avantage perdu`
    if (acc <= 65 || gap >= 8) {
      weak({ id: `phase-${p}`, title: `${PHASE_FR[p]} fragile`, detail, severity: share(b, st.drop), plan: phasePlan(b, p) })
    } else if (acc >= 80) {
      strong({ id: `phase-${p}`, title: `${PHASE_FR[p]} solide`, detail: `Précision ${fr1(acc)} sur ${st.moves} coups hors théorie`, severity: over(acc, 80) })
    }
  }

  // Gaffes.
  if (b.ownMoves >= 100) {
    const blunders = sum(PHASES.map((p) => b.phases[p].blunders))
    const rate = (blunders / b.ownMoves) * 100
    if (rate >= 5) weak({ id: 'gaffes', title: 'Trop de gaffes', detail: `${fr1(rate)} gaffes pour 100 coups (${blunders} sur ${b.ownMoves} coups)`, severity: over(rate, 5), plan: [tactic('hangingPiece', 'Séance Tactiques : pièces en prise'), { label: 'Puzzle Rush (réflexes)', to: '/rush' }] })
    else if (rate <= 2) strong({ id: 'gaffes', title: 'Peu de gaffes', detail: `${fr1(rate)} gaffes pour 100 coups (${blunders} sur ${b.ownMoves} coups)`, severity: under(rate, 2) })
  }

  if (n >= 5) {
    // Pièces en prise.
    const hang = errCount(b, 'hanging', 'ignoredThreat')
    const perGame = hang / n
    if (perGame >= 0.5) weak({ id: 'pieces-en-prise', title: 'Pièces laissées en prise', detail: `${plural(hang, 'pièce perdue', 'pièces perdues')} sans compensation en ${n} parties (${fr1(perGame)} par partie)`, severity: share(b, errDrop(b, 'hanging', 'ignoredThreat')), plan: [tactic('hangingPiece', 'Séance Tactiques : pièces en prise'), { label: 'Avant chaque coup : quelles pièces sont attaquées ?' }], examples: errExamples(b, 'hanging', 'ignoredThreat') })
    else if (perGame <= 0.1) strong({ id: 'pieces-en-prise', title: 'Pièces bien protégées', detail: `${plural(hang, 'pièce laissée', 'pièces laissées')} en prise en ${n} parties`, severity: under(perGame, 0.1) })

    // Menaces ignorées.
    const threats = errCount(b, 'ignoredThreat', 'allowedMate')
    if (threats / n >= 0.3) weak({ id: 'menaces-ignorees', title: 'Menaces adverses ignorées', detail: `${plural(threats, 'menace ignorée', 'menaces ignorées')} en ${n} parties (${fr1(threats / n)} par partie), dont ${plural(errCount(b, 'allowedMate'), 'mat en 1', 'mats en 1')}`, severity: share(b, errDrop(b, 'ignoredThreat', 'allowedMate')), plan: [tactic('defensiveMove', 'Séance Tactiques : coups défensifs'), tactic('hangingPiece', 'Séance Tactiques : pièces en prise')], examples: errExamples(b, 'ignoredThreat', 'allowedMate') })

    // Tactiques manquées.
    const missed = errCount(b, 'missedFork', 'missedPin', 'missedFreePiece')
    const parts = [
      [errCount(b, 'missedFork'), 'fourchette', 'fourchettes'],
      [errCount(b, 'missedPin'), 'clouage', 'clouages'],
      [errCount(b, 'missedFreePiece'), 'pièce gratuite', 'pièces gratuites'],
    ].filter(([c]) => (c as number) > 0).map(([c, one, many]) => plural(c as number, one as string, many as string))
    if (missed / n >= 0.4) {
      const t = topMissedTheme(b)
      weak({ id: 'tactiques-manquees', title: 'Tactiques manquées', detail: `${parts.join(', ')} manquées en ${n} parties (${fr1(missed / n)} par partie)`, severity: share(b, errDrop(b, 'missedFork', 'missedPin', 'missedFreePiece')), plan: [tactic(t.theme, `Séance Tactiques : ${t.label.toLowerCase()}`), { label: 'Problèmes', to: '/puzzles' }], examples: errExamples(b, 'missedFork', 'missedPin', 'missedFreePiece') })
    } else if (missed === 0) {
      strong({ id: 'tactiques-manquees', title: "Œil tactique", detail: `Aucune fourchette, aucun clouage ni aucune pièce gratuite manqués en ${n} parties`, severity: 0.5 })
    }

    // Mats manqués.
    const mates = errCount(b, 'missedMate', 'missedBackRank')
    if (mates >= 2 && mates / n >= 0.2) {
      const backRank = errCount(b, 'missedBackRank') > errCount(b, 'missedMate')
      weak({ id: 'mats-manques', title: 'Mats manqués', detail: `${plural(mates, 'mat manqué', 'mats manqués')} en ${n} parties${errCount(b, 'missedBackRank') ? `, dont ${plural(errCount(b, 'missedBackRank'), 'mat du couloir', 'mats du couloir')}` : ''}`, severity: share(b, errDrop(b, 'missedMate', 'missedBackRank')), plan: [{ label: backRank ? 'Mats éclair : mat du couloir' : 'Mats éclair : mat en 1', to: backRank ? '/mats?d=motif-backRankMate' : '/mats?d=mate-1' }, tactic('mateIn1', 'Séance Tactiques : mats en 1')], examples: errExamples(b, 'missedMate', 'missedBackRank') })
    }

    // Au moins deux parties concernées : ne pas généraliser depuis une seule défense ratée.
    const kd = b.kingDefense
    if (kd.faults >= 2 && kd.games >= 2) {
      weak({
        id: 'roi-attaque', title: 'Tu t’effondres quand ton roi est attaqué',
        detail: `${plural(kd.faults, 'faute', 'fautes')} sous attaque du roi dans ${kd.games} parties sur ${n} analysées · ${pct(share(b, kd.drop) * 100)} de l’avantage perdu`,
        severity: share(b, kd.drop),
        plan: [
          { label: 'Entraîneur de défense', to: '/defense' },
          { label: 'Mes défenses ratées', to: '/defenses-ratees' },
          { label: 'Pour remplir ta liste personnelle, lance un bilan dans Analyse depuis un exemple.' },
        ],
        examples: kd.examples,
      })
    }

    // Attaque sur le roi.
    const atk = errCount(b, 'missedKingAttack')
    if (atk / n >= 0.3) weak({ id: 'attaque', title: 'Attaques sur le roi manquées', detail: `${plural(atk, 'coup offensif', 'coups offensifs')} vers le roi adverse manqués en ${n} parties (${fr1(atk / n)} par partie)`, severity: share(b, errDrop(b, 'missedKingAttack')), plan: [{ label: "Entraîneur d’attaque", to: '/attaque' }, { label: 'Mes attaques manquées', to: '/attaques-manquees' }, tactic('kingsideAttack', "Séance Tactiques : attaque à l'aile roi"), { label: 'La liste personnelle utilise ses propres critères d’attaque. Un bilan dans Analyse depuis un exemple y ajoute les fautes qui correspondent.' }], examples: errExamples(b, 'missedKingAttack') })
  }

  // Pendule.
  const t = b.time
  if (t && t.pressureMoves >= 30 && t.pressureRate !== null && t.normalRate !== null) {
    if (t.pressureBlunders >= 3 && t.pressureRate >= 2 * t.normalRate) {
      weak({ id: 'temps-pression', title: 'Gaffes sous pression de la pendule', detail: `${fr1(t.pressureRate)} gaffes pour 100 coups sous pression contre ${fr1(t.normalRate)} hors pression (${t.pressureBlunders} gaffes sur ${t.pressureMoves} coups)`, severity: Math.max(share(b, t.pressureDrop), over(t.pressureRate, 2 * Math.max(t.normalRate, 0.5))), plan: [{ label: 'Puzzle Rush : décider vite', to: '/rush' }, { label: "Garde au moins 10 % de ta pendule pour la fin : joue plus vite les coups d'ouverture que tu connais." }], examples: t.examples })
    } else if (t.pressureRate <= t.normalRate) {
      strong({ id: 'temps-pression', title: 'Sang-froid à la pendule', detail: `${fr1(t.pressureRate)} gaffes pour 100 coups sous pression, pas plus qu'hors pression (${fr1(t.normalRate)})`, severity: 0.3 })
    }
  }
  if (b.games.losses >= 4 && b.games.lostOnTime >= 2 && b.games.lostOnTime / b.games.losses >= 0.25) {
    weak({ id: 'defaites-au-temps', title: 'Défaites au temps', detail: `${plural(b.games.lostOnTime, 'défaite', 'défaites')} au temps sur ${b.games.losses}${b.games.lostOnTimeWinning ? `, dont ${b.games.lostOnTimeWinning} en position gagnante` : ''}`, severity: over(b.games.lostOnTime / b.games.losses, 0.25), plan: [{ label: 'Puzzle Rush : décider vite', to: '/rush' }, { label: 'Fixe-toi un budget : en blitz, pas plus de 20 secondes sur un coup avant la finale.' }] })
  }

  // Conversion, défense, opportunisme.
  const { winning, converted } = b.conversion
  if (winning >= 5) {
    const r = converted / winning
    if (r < 0.6) weak({ id: 'conversion', title: 'Positions gagnantes non converties', detail: `${converted} victoires sur ${winning} positions gagnantes (+3 ou mieux), soit ${pct(r * 100)}`, severity: under(r, 0.6), plan: [{ label: 'Finales à jouer contre Stockfish', to: '/finales' }, { label: 'Cours de finales', to: '/apprendre/finales' }, { label: 'Avec de l\'avance : échange les pièces, pas les pions, et ne laisse aucun contre-jeu.' }] })
    else if (r >= 0.85) strong({ id: 'conversion', title: 'Tu conclus tes parties gagnantes', detail: `${converted} victoires sur ${winning} positions gagnantes, soit ${pct(r * 100)}`, severity: over(r, 0.85) })
  }
  const { losing, saved } = b.defense
  if (losing >= 5) {
    const r = saved / losing
    if (r < 0.1) weak({ id: 'defense', title: 'Défense des positions perdues', detail: `${saved} sauvée${saved > 1 ? 's' : ''} sur ${losing} positions perdantes (−3 ou pire), soit ${pct(r * 100)}`, severity: under(r, 0.1), plan: [{ label: 'Entraîneur de défense', to: '/defense' }, tactic('defensiveMove', 'Séance Tactiques : coups défensifs'), { label: 'Position perdue : cherche les échecs, les pièges et la nulle plutôt que d\'abandonner en jouant vite.' }] })
    else if (r >= 0.3) strong({ id: 'defense', title: 'Défenseur coriace', detail: `${saved} positions perdantes sauvées sur ${losing}, soit ${pct(r * 100)}`, severity: over(r, 0.3) })
  }
  const { chances, punished } = b.opportunism
  if (chances >= 5) {
    const r = punished / chances
    if (r < 0.5) weak({ id: 'opportunisme', title: 'Gaffes adverses non punies', detail: `${punished} gaffes adverses punies sur ${chances}, soit ${pct(r * 100)}`, severity: under(r, 0.5), plan: [tactic('hangingPiece', 'Séance Tactiques : pièces en prise'), { label: "Après chaque coup adverse : qu'est-ce qui vient de changer, qu'est-ce qui est attaqué ?" }] })
    else if (r >= 0.8) strong({ id: 'opportunisme', title: 'Opportuniste', detail: `${punished} gaffes adverses punies sur ${chances}, soit ${pct(r * 100)}`, severity: over(r, 0.8) })
  }

  // Ouvertures.
  for (const o of b.costlyOpenings) {
    const exit = o.exitEval !== null ? `, ${o.exitEval > 0 ? '+' : o.exitEval < 0 ? '−' : ''}${fr1(Math.abs(o.exitEval) / 100)} en moyenne à la sortie de l'ouverture` : ''
    weak({ id: `ouverture-${o.key}-${o.color}`, title: `${o.name} avec les ${COLOR_FR[o.color]}`, detail: `Score ${pct(o.score)} sur ${o.n} parties (${o.wins} V, ${o.draws} N, ${o.losses} D)${exit}`, severity: clamp01(Math.max(under(o.score, 33), o.exitEval !== null ? -o.exitEval / 300 : 0)), plan: [{ label: `Entraîneur : ${o.name}`, to: `/ouvertures?famille=${encodeURIComponent(o.key)}&camp=${o.color}` }] })
  }
  for (const o of b.openings) {
    if (o.n >= 5 && o.score >= 67 && !o.costly) strong({ id: `ouverture-${o.key}-${o.color}`, title: `${o.name} avec les ${COLOR_FR[o.color]}`, detail: `Score ${pct(o.score)} sur ${o.n} parties (${o.wins} V, ${o.draws} N, ${o.losses} D)`, severity: over(o.score, 67) })
  }

  // Couleur.
  const { w, b: bl } = b.games.byColor
  if (w.n >= 10 && bl.n >= 10) {
    const dScore = w.score - bl.score
    const dAcc = w.accuracy !== null && bl.accuracy !== null ? w.accuracy - bl.accuracy : 0
    if (Math.abs(dScore) >= 20 || Math.abs(dAcc) >= 6) {
      const weakC: 'w' | 'b' = Math.abs(dScore) >= 20 ? (dScore > 0 ? 'b' : 'w') : dAcc > 0 ? 'b' : 'w'
      weak({ id: 'couleur', title: `Plus fragile avec les ${COLOR_FR[weakC]}`, detail: `Score ${pct(w.score)} avec les Blancs, ${pct(bl.score)} avec les Noirs ; précision ${w.accuracy !== null ? fr1(w.accuracy) : '-'} contre ${bl.accuracy !== null ? fr1(bl.accuracy) : '-'}`, severity: clamp01(Math.max(Math.abs(dScore) / 40, Math.abs(dAcc) / 12)), plan: [{ label: `Répertoire des ${COLOR_FR[weakC]}`, to: `/ouvertures` }, { label: `Joue tes prochaines parties avec les ${COLOR_FR[weakC]}`, to: '/jouer' }] })
    }
  }

  // Tendance.
  const a = b.accuracy
  if (a.games >= 20 && a.firstHalf !== null && a.secondHalf !== null) {
    const d = a.secondHalf - a.firstHalf
    if (d <= -6) weak({ id: 'tendance', title: 'Précision en baisse', detail: `${fr1(a.firstHalf)} sur tes parties les plus anciennes, ${fr1(a.secondHalf)} sur les plus récentes`, severity: clamp01(-d / 15), plan: [{ label: 'Fatigue ou séries trop longues ? Fais une pause entre deux parties perdues.' }, { label: 'Problèmes pour te remettre en jambes', to: '/puzzles' }] })
    else if (d >= 6) strong({ id: 'tendance', title: 'En progrès', detail: `Précision ${fr1(a.firstHalf)} puis ${fr1(a.secondHalf)} sur tes parties les plus récentes`, severity: clamp01(d / 15) })
  }

  // Tilt.
  if (b.tilt && b.tilt.score <= b.tilt.overall - 20) {
    weak({ id: 'tilt', title: 'Série noire après une défaite', detail: `Score ${pct(b.tilt.score)} sur les ${b.tilt.n} parties jouées juste après une défaite, contre ${pct(b.tilt.overall)} en tout`, severity: clamp01((b.tilt.overall - b.tilt.score) / 40), plan: [{ label: 'Après une défaite : quelques problèmes avant de relancer une partie.', to: '/puzzles' }] })
  }

  const bySeverity = (x: Finding, y: Finding) => y.severity - x.severity || x.id.localeCompare(y.id)
  W.sort(bySeverity)
  S.sort(bySeverity)
  return { weaknesses: W.slice(0, 3), strengths: S.slice(0, 3), candidates: { weaknesses: W, strengths: S } }
}

// ------------------------------------------------------------------ résumé du coach

function narrate(b: Base, findings: Insights['findings']): string[] {
  const out: string[] = []
  const g = b.games
  if (g.n === 0) return ['Aucune partie analysée pour le moment.']
  const tcs = g.timeClasses.length === 1 ? ` de ${timeClassLabel(g.timeClasses[0])}` : ''
  const res = [plural(g.wins, 'victoire', 'victoires'), plural(g.draws, 'nulle', 'nulles'), plural(g.losses, 'défaite', 'défaites')]
  out.push(
    `Sur ces ${plural(g.n, 'partie', 'parties')}${tcs} : ${res[0]}, ${res[1]} et ${res[2]} (score ${pct(g.score)})` +
      (b.accuracy.mean !== null ? `, précision moyenne ${fr1(b.accuracy.mean)} %.` : '.'),
  )
  if (g.n < 5) {
    out.push("C'est trop peu pour un verdict fiable : analyse au moins 10 parties et je te dirai où tu pèches.")
    return out
  }

  // Phases.
  const eligible = PHASES.filter((p) => b.phases[p].moves >= 15 && b.phases[p].accuracy !== null)
  if (eligible.length >= 2) {
    const sorted = [...eligible].sort((p, q) => b.phases[p].accuracy! - b.phases[q].accuracy!)
    const worst = sorted[0]
    const best = sorted[sorted.length - 1]
    const w = b.phases[worst]
    out.push(
      `Ta phase la plus fragile est ${PHASE_LOW[worst]} : précision ${fr1(w.accuracy!)} et ${fr1(w.blundersPer100)} gaffes pour 100 coups, contre ${fr1(b.phases[best].accuracy!)} dans ${PHASE_LOW[best]}.`,
    )
  } else if (eligible.length === 1) {
    const p = eligible[0]
    out.push(`Hors théorie, ${PHASE_LOW[p]} est la seule phase assez jouée pour juger : précision ${fr1(b.phases[p].accuracy!)} sur ${b.phases[p].moves} coups.`)
  }

  // Gaffes et faute typique.
  if (b.ownMoves >= 30) {
    const blunders = sum(PHASES.map((p) => b.phases[p].blunders))
    out.push(`Tu commets ${fr1((blunders / b.ownMoves) * 100)} gaffes pour 100 coups joués hors théorie.`)
  }
  const top = [...b.errors].filter((e) => e.count > 0).sort((x, y) => y.count - x.count || y.drop - x.drop)[0]
  if (top) out.push(`Faute la plus fréquente : ${ERROR_META[top.kind].label.toLowerCase()} (${plural(top.count, 'fois', 'fois')}, ${fr1(top.count / g.n)} par partie).`)

  // Pendule.
  const t = b.time
  if (t && t.pressureMoves >= 5 && t.pressureRate !== null && t.normalRate !== null) {
    out.push(`Sous pression de la pendule (moins de 10 % du temps), tu fais ${fr1(t.pressureRate)} gaffes pour 100 coups, contre ${fr1(t.normalRate)} le reste du temps.`)
  }
  if (g.lostOnTime > 0) out.push(`${plural(g.lostOnTime, 'défaite', 'défaites')} au temps sur ${g.losses}${g.lostOnTimeWinning ? `, dont ${g.lostOnTimeWinning} en position gagnante` : ''}.`)

  // Conversion et défense.
  const conv = b.conversion
  const def = b.defense
  if (conv.winning > 0 || def.losing > 0) {
    const parts: string[] = []
    if (conv.winning > 0) parts.push(`converti ${conv.converted} ${conv.winning > 1 ? `des ${conv.winning} positions gagnantes` : 'position gagnante sur 1'}`)
    if (def.losing > 0) parts.push(`sauvé ${def.saved} ${def.losing > 1 ? `des ${def.losing} positions perdantes` : 'position perdante sur 1'}`)
    out.push(`Tu as ${parts.join(' et ')}.`)
  }

  // Ouverture coûteuse.
  const costly = b.costlyOpenings[0]
  if (costly) out.push(`L'ouverture qui te coûte le plus : ${costly.name} avec les ${COLOR_FR[costly.color]} (score ${pct(costly.score)} sur ${costly.n} parties).`)

  // Couleur.
  const { w, b: bl } = g.byColor
  if (w.n >= 5 && bl.n >= 5 && Math.abs(w.score - bl.score) >= 15) out.push(`Score ${pct(w.score)} avec les Blancs, ${pct(bl.score)} avec les Noirs.`)

  // Tendance.
  const a = b.accuracy
  if (a.games >= 20 && a.firstHalf !== null && a.secondHalf !== null && Math.abs(a.secondHalf - a.firstHalf) >= 3) {
    out.push(`Ta précision ${a.secondHalf > a.firstHalf ? 'monte' : 'baisse'} : ${fr1(a.firstHalf)} sur tes parties les plus anciennes, ${fr1(a.secondHalf)} sur les plus récentes.`)
  }

  const first = findings.weaknesses[0]
  out.push(first ? `À bosser en premier : ${first.title.charAt(0).toLowerCase()}${first.title.slice(1)}.` : 'Aucune faiblesse nette ne ressort de ces parties : continue comme ça.')
  return out
}
