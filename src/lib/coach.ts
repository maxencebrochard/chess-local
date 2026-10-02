// Coach post-partie : commentaires en français générés par règles depuis le
// Game Review (classe du coup, mat, matériel, pièce en prise, meilleur coup).
// Les phrases vivent dans coachPhrases.ts, les détections dans motifs.ts : ici, on
// choisit la situation la plus grave constatée sur l'échiquier, puis une variante.
import { Chess, type PieceSymbol } from 'chess.js'
import { CLASS_META, figurine, type GameReview, type MoveClass } from './review'
import { Picker, type Vars } from './coachPhrases'
import {
  PIECE_FR, captureInfo, hangingAfter, isCheckmateFen, isStalemateFen, mateInOne, other, sanOf,
} from './motifs'

export interface CoachComment {
  moveIndex: number
  // « ♗xa7 est une gaffe » : affiché en gras avec la pastille de classe.
  headline: string
  // Explication en langage naturel, sans répéter le coup.
  body: string
  // Coup meilleur suggéré, en SAN, quand le coup joué n'était pas le bon.
  betterMove?: string
  // praise / warn / alarm sont les « moments clés » du bilan guidé ; neutral n'en est pas un.
  severity: 'praise' | 'neutral' | 'warn' | 'alarm'
  mood: 'happy' | 'thinking' | 'worried'
}

const FAULTS: MoveClass[] = ['inaccuracy', 'mistake', 'miss', 'missedWin', 'blunder']
const BAD_CLASSES: MoveClass[] = ['blunder', 'missedWin', 'miss', 'mistake']

// Mat annoncé par le moteur contre le camp qui vient de jouer (nombre de coups), sinon 0.
function mateAgainst(mateAfter: number | null, mover: 'w' | 'b'): number {
  if (mateAfter === null || mateAfter === 0) return 0
  return (mover === 'w' ? mateAfter < 0 : mateAfter > 0) ? Math.abs(mateAfter) : 0
}

// Numéro du coup au demi-coup i, depuis le compteur du FEN de départ : « 5. » ou « 5... ».
function moveNumber(review: GameReview, i: number): string {
  const full = parseInt(review.startFen.split(' ')[5] ?? '1', 10) || 1
  const offset = review.startTurn === 'b' ? 1 : 0
  const no = full + Math.floor((i + offset) / 2)
  return colorAt(review, i) === 'w' ? `${no}.` : `${no}...`
}

export function coachComments(review: GameReview, playerColor: 'w' | 'b' | null): CoachComment[] {
  const comments: CoachComment[] = []
  const replay = new Chess(review.startFen)
  const pick = new Picker(review.moves.length)
  let lastCaptureSquare: string | null = null
  let prevMateAgainst = 0

  review.moves.forEach((m, i) => {
    const mover = replay.turn()
    const fenBefore = replay.fen()
    const played = replay.move(m.san)
    const fenAfter = replay.fen()
    const headline = `${figurine(m.san, mover)} est ${CLASS_META[m.class].headline}`
    const mated = isCheckmateFen(fenAfter)
    const pat = isStalemateFen(fenAfter)
    const against = mateAgainst(m.mateAfter, mover)
    const wasAgainst = prevMateAgainst
    prevMateAgainst = mateAgainst(m.mateAfter, other(mover))
    const cap = captureInfo(fenBefore, m.uci, lastCaptureSquare)
    lastCaptureSquare = played.captured ? played.to : null

    // Coup de l'adversaire : une bulle courte et neutre, jamais vide (ANA-36).
    if (playerColor && mover !== playerColor) {
      const key = mated ? 'post.adverse.mat' : pat ? 'post.adverse.pat' : BAD_CLASSES.includes(m.class) ? 'post.adverse.erreur' : 'post.adverse.generique'
      comments.push({ moveIndex: i, headline, body: pick.say(key, i), severity: 'neutral', mood: key === 'post.adverse.erreur' ? 'happy' : 'thinking' })
      return
    }

    const better = m.uci !== m.bestMoveUci ? sanOf(fenBefore, m.bestMoveUci) ?? undefined : undefined
    const betterFig = better ? figurine(better, mover) : undefined
    const bestMates = !!better && better.endsWith('#')
    // {meilleur} n'existe que si un meilleur coup existe : le Picker écarte alors les variantes qui le citent.
    const vars: Vars = { coup: figurine(m.san, mover) }
    if (betterFig) vars.meilleur = betterFig
    let key: string
    let gender: 'm' | 'f' = 'm'
    let severity: CoachComment['severity'] = 'neutral'
    let mood: CoachComment['mood'] = 'thinking'

    if (m.class === 'book') {
      key = 'post.book.generique'
    } else if (FAULTS.includes(m.class)) {
      // Fautes : le plus grave d'abord (pat, mat autorisé, mat raté, pièce en prise), sinon la classe.
      const hang = hangingAfter(fenBefore, fenAfter, mover, { to: played.to, captured: played.captured as PieceSymbol | undefined })
      if (pat) key = 'faute.pat'
      else if (against === 1) {
        const reply = mateInOne(fenAfter)
        vars.reponse = reply ? figurine(reply, other(mover)) : 'le prochain coup'
        // « Déjà perdu » seulement si le meilleur coup n'évitait pas non plus le mat en 1.
        const stillMated = !better || mateInOne(afterUci(fenBefore, m.bestMoveUci)) !== null
        key = wasAgainst === 1 && stillMated ? 'faute.mat_en_1_deja' : 'faute.mat_en_1'
      } else if (against > 1) {
        vars.n = against
        key = wasAgainst > 0 ? 'faute.mat_en_n_deja' : 'faute.mat_en_n'
      } else if (bestMates) { key = 'faute.mat_manque'; vars.n = 1 }
      else if (hang?.capturer && played.captured) {
        gender = PIECE_FR[played.captured as PieceSymbol].genre
        vars.cible = PIECE_FR[played.captured as PieceSymbol].defini
        key = 'faute.mauvais_echange'
      } else if (hang) {
        gender = PIECE_FR[hang.piece].genre
        Object.assign(vars, { piece: PIECE_FR[hang.piece].defini, case: hang.square, attaquant: PIECE_FR[hang.attacker].defini })
        key = hang.defended ? 'faute.mal_defendue' : 'faute.piece_en_prise'
      } else key = better ? `post.${m.class}.generique` : 'post.secours.generique'
      severity = m.class === 'blunder' || m.class === 'missedWin' ? 'alarm' : 'warn'
      mood = severity === 'alarm' ? 'worried' : 'thinking'
    } else {
      // Bons coups : mat, mat en 1 raté, prise, sinon la classe. best et excellent ne sont
      // plus des moments clés (ANA-15) : seuls brillant et très bon restent en praise.
      mood = 'happy'
      if (mated) key = 'post.best.mat'
      else if (bestMates) { key = 'faute.mat_manque'; vars.n = 1; mood = 'thinking' }
      else if (cap && (cap.kind === 'gain' || cap.kind === 'reprise')) {
        gender = PIECE_FR[cap.captured].genre
        vars.cible = PIECE_FR[cap.captured].defini
        key = cap.kind === 'reprise' ? 'post.best.reprise' : cap.clean ? 'post.best.gain_materiel' : 'post.best.gain_echange'
      } else if (m.class === 'brilliant') {
        gender = PIECE_FR[played.piece].genre
        vars.piece = PIECE_FR[played.piece].defini
        key = 'post.brilliant.sacrifice'
      }
      else if (m.class === 'great') key = 'post.great.seul_coup'
      else if (m.class === 'good') key = better ? 'post.good.generique' : 'post.excellent.generique'
      else if (m.class === 'excellent') key = 'post.excellent.generique'
      else key = 'post.best.generique'
      if (m.class === 'brilliant' || m.class === 'great') severity = 'praise'
    }

    comments.push({ moveIndex: i, headline, body: pick.say(key, i, vars, gender), betterMove: better, severity, mood })
  })

  return comments
}

// Position après un coup UCI (le coup est supposé légal : il vient du moteur).
function afterUci(fen: string, uci: string): string {
  const c = new Chess(fen)
  try {
    c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
  } catch {
    return fen
  }
  return c.fen()
}

// Couleur du joueur au demi-coup i, en tenant compte du trait initial.
function colorAt(review: GameReview, i: number): 'w' | 'b' {
  return (i % 2 === 0) === (review.startTurn === 'w') ? 'w' : 'b'
}

// Précision en français : virgule décimale, une décimale au plus.
const fr = (n: number) => String(Math.round(n * 10) / 10).replace('.', ',')

// Punchline courte du coach pour l'écran de résumé, façon chess.com.
export function coachQuip(review: GameReview, playerColor: 'w' | 'b' | null): string {
  const color = playerColor ?? 'w'
  const report = phaseReport(review)
  const o = report.opening[color]
  const m = report.middlegame[color]
  const e = report.endgame[color]
  const pick = new Picker(review.moves.length + 1)
  const acc = color === 'w' ? review.accuracyWhite : review.accuracyBlack
  if (o === 'good' && (m === 'bad' || m === 'meh')) return pick.say('punchline.milieu_rate', 0)
  if (o !== 'good' && m === 'good') return pick.say('punchline.remontee', 0)
  if (e === 'bad') return pick.say('punchline.finale_ratee', 0)
  if (o === 'bad') return pick.say('punchline.ouverture_ratee', 0)
  if (acc >= 90) return pick.say('punchline.generique.excellent', 0)
  if (acc >= 75) return pick.say('punchline.generique.solide', 0)
  if (acc >= 55) return pick.say('punchline.generique.moyen', 0)
  return pick.say('punchline.generique.difficile', 0)
}

// Verdict par phase et par couleur, pour l'écran de résumé.
export type PhaseVerdict = 'good' | 'meh' | 'bad' | 'none'

export interface PhaseReport {
  opening: { w: PhaseVerdict; b: PhaseVerdict }
  middlegame: { w: PhaseVerdict; b: PhaseVerdict }
  endgame: { w: PhaseVerdict; b: PhaseVerdict }
}

function verdictOf(acc: number | null): PhaseVerdict {
  if (acc === null) return 'none'
  if (acc >= 80) return 'good'
  if (acc >= 60) return 'meh'
  return 'bad'
}

export function phaseReport(review: GameReview): PhaseReport {
  const phases = detectPhases(review)
  const range = (from: number, to: number) => ({
    w: verdictOf(accuracyOnRange(review, 'w', from, to)),
    b: verdictOf(accuracyOnRange(review, 'b', from, to)),
  })
  return {
    opening: range(0, phases.openingEnd + 1),
    middlegame: range(phases.openingEnd + 1, phases.endgameStart),
    endgame: range(phases.endgameStart, review.moves.length),
  }
}

// Découpage en phases : ouverture = jusqu'au dernier coup de théorie (fallback
// 16 demi-coups) ; finale = quand il reste ≤ 6 pièces hors pions et rois.
export interface GamePhases {
  openingEnd: number // index du dernier demi-coup d'ouverture (-1 si aucun)
  endgameStart: number // index du premier demi-coup de finale (moves.length si jamais atteinte)
}

export function detectPhases(review: GameReview): GamePhases {
  let openingEnd = -1
  review.moves.forEach((m, i) => {
    if (m.class === 'book') openingEnd = i
  })
  if (openingEnd === -1) openingEnd = Math.min(15, review.moves.length - 1)

  const replay = new Chess(review.startFen)
  let endgameStart = review.moves.length
  for (let i = 0; i < review.moves.length; i++) {
    replay.move(review.moves[i].san)
    let pieces = 0
    for (const row of replay.board()) {
      for (const sq of row) {
        if (sq && sq.type !== 'p' && sq.type !== 'k') pieces++
      }
    }
    if (pieces <= 6) {
      endgameStart = i + 1
      break
    }
  }
  return { openingEnd, endgameStart: Math.max(endgameStart, openingEnd + 1) }
}

// Précision d'une couleur sur une tranche de demi-coups.
function accuracyOnRange(review: GameReview, color: 'w' | 'b', from: number, to: number): number | null {
  const accs: number[] = []
  for (let i = Math.max(0, from); i < Math.min(to, review.moves.length); i++) {
    if (colorAt(review, i) !== color) continue
    const m = review.moves[i]
    const drop = Math.max(0, m.winPctBefore - m.winPctAfter)
    accs.push(Math.max(0, Math.min(100, 103.1668 * Math.exp(-0.04354 * drop) - 3.1669)))
  }
  if (accs.length === 0) return null
  return Math.round((accs.reduce((a, b) => a + b, 0) / accs.length) * 10) / 10
}

// Adjectifs invariables : ils qualifient « ouverture », « milieu de partie » et « finale ».
function phaseVerdict(acc: number): string {
  if (acc >= 92) return 'impeccable'
  if (acc >= 80) return 'solide'
  if (acc >= 65) return 'en dents de scie'
  return 'difficile'
}

// Résumé narratif d'ouverture de session du coach.
export function coachSummary(review: GameReview, playerColor: 'w' | 'b' | null): string {
  const color = playerColor ?? 'w'
  const acc = color === 'w' ? review.accuracyWhite : review.accuracyBlack
  const rating = color === 'w' ? review.gameRatingWhite : review.gameRatingBlack
  const counts = review.counts[color]
  const phases = detectPhases(review)
  const pick = new Picker(review.moves.length + 2)
  const parts: string[] = []
  const own = review.moves.filter((_, i) => colorAt(review, i) === color).length

  // Verdict global + classement de la partie (pas de chiffres sous 5 coups, REV-15).
  const vars: Vars = { precision: fr(acc), elo: rating }
  if (own < 5) parts.push(pick.say('resume.verdict.courte', 0))
  else if (acc >= 90) parts.push(pick.say('resume.verdict.excellent', 0, vars))
  else if (acc >= 75) parts.push(pick.say('resume.verdict.solide', 0, vars))
  else if (acc >= 55) parts.push(pick.say('resume.verdict.moyen', 0, vars))
  else parts.push(pick.say('resume.verdict.difficile', 0, vars))

  // Fin de partie prouvée par la position finale : mat ou pat.
  const replay = new Chess(review.startFen)
  review.moves.forEach((m) => replay.move(m.san))
  const last = review.moves.length - 1
  if (last >= 0 && replay.isCheckmate()) parts.push(pick.say(colorAt(review, last) === color ? 'resume.resultat.victoire_mat' : 'resume.resultat.defaite_mat', 1))
  else if (last >= 0 && replay.isStalemate()) parts.push(pick.say('resume.resultat.pat', 1))

  // Compte des fautes, mis en avant.
  const faults: string[] = []
  // « une erreur » plutôt que « 1 erreur » : le chiffre ne sert qu'au pluriel.
  const plural = (n: number, s: string, p: string) => (n > 1 ? `${n} ${p}` : s)
  if (counts.blunder > 0) faults.push(plural(counts.blunder, 'une gaffe', 'gaffes'))
  if (counts.missedWin > 0) faults.push(plural(counts.missedWin, 'un gain manqué', 'gains manqués'))
  if (counts.miss > 0) faults.push(plural(counts.miss, 'une occasion manquée', 'occasions manquées'))
  if (counts.mistake > 0) faults.push(plural(counts.mistake, 'une erreur', 'erreurs'))
  const nFaults = counts.blunder + counts.missedWin + counts.miss + counts.mistake
  if (nFaults === 0) parts.push(pick.say('resume.fautes.aucune', 2))
  else parts.push(pick.say(nFaults === 1 ? 'resume.fautes.une' : 'resume.fautes.liste', 2, { fautes: faults.join(', ') }))
  if (counts.brilliant === 1) parts.push(pick.say('resume.brillant.un', 3))
  else if (counts.brilliant > 1) parts.push(pick.say('resume.brillant.plusieurs', 3, { n: counts.brilliant }))

  // Récit par phases.
  const accOpen = accuracyOnRange(review, color, 0, phases.openingEnd + 1)
  const accMid = accuracyOnRange(review, color, phases.openingEnd + 1, phases.endgameStart)
  const accEnd = accuracyOnRange(review, color, phases.endgameStart, review.moves.length)
  if (accOpen !== null && accMid !== null) {
    const v: Vars = { v_ouverture: phaseVerdict(accOpen), v_milieu: phaseVerdict(accMid), v_finale: accEnd === null ? '' : phaseVerdict(accEnd) }
    parts.push(pick.say(accEnd === null ? 'resume.phases.deux' : 'resume.phases.trois', 4, v))
  }

  // Le moment où la partie a basculé (plus gros drop du joueur), en figurines et numéroté.
  let pivotIdx = -1
  let pivotDrop = 12
  review.moves.forEach((m, i) => {
    if (colorAt(review, i) !== color) return
    if (!BAD_CLASSES.includes(m.class)) return
    const drop = m.winPctBefore - m.winPctAfter
    if (drop > pivotDrop) {
      pivotDrop = drop
      pivotIdx = i
    }
  })
  if (pivotIdx >= 0) {
    parts.push(pick.say('resume.pivot.coup', 5, { numero: moveNumber(review, pivotIdx), coup: figurine(review.moves[pivotIdx].san, color) }))
  }

  return parts.join(' ')
}
