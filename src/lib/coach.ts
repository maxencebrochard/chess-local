// Coach post-partie : commentaires en français générés par règles depuis le
// Game Review (classe du coup, mat, matériel, motifs tactiques, meilleur coup).
// Les phrases vivent dans coachPhrases.ts, les détections dans motifs.ts : ici, on
// choisit la situation la plus grave constatée sur l'échiquier, puis une variante.
// Un motif n'est nommé que si un détecteur l'a vérifié sur la position : sinon, le
// générique de la classe parle.
import { Chess, type PieceSymbol } from 'chess.js'
import { CLASS_META, figurine, type GameReview, type MoveClass } from './review'
import { openingForMoves } from './openings'
import { openingFamilyFr } from './openingNames'
import { Picker, type Gender, type Vars } from './coachPhrases'
import {
  PIECE_FR, PIECE_VALUE, backRankMate, captureInfo, castlingInfo, fork, isCheckmateFen, isStalemateFen,
  mateInOne, materialBalance, other, passedPawn, pinOrSkewer, sanOf, type Fork, type LineMotif,
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
const START_FEN = new Chess().fen()

// Mat annoncé par le moteur contre le camp `side` (nombre de coups), sinon 0.
function mateAgainst(mateAfter: number | null, side: 'w' | 'b'): number {
  if (mateAfter === null || mateAfter === 0) return 0
  return (side === 'w' ? mateAfter < 0 : mateAfter > 0) ? Math.abs(mateAfter) : 0
}

// Numéro du coup au demi-coup i, depuis le compteur du FEN de départ : « 5. » ou « 5... ».
function moveNumber(review: GameReview, i: number): string {
  const full = parseInt(review.startFen.split(' ')[5] ?? '1', 10) || 1
  const offset = review.startTurn === 'b' ? 1 : 0
  const no = full + Math.floor((i + offset) / 2)
  return colorAt(review, i) === 'w' ? `${no}.` : `${no}...`
}

// Deux pièces nommées ensemble : participe au féminin seulement si les deux le sont.
const pairGender = (a: PieceSymbol, b: PieceSymbol): Gender => (PIECE_FR[a].genre === 'f' && PIECE_FR[b].genre === 'f' ? 'f' : 'm')

// Le coup de réponse `reply` fait-il encore ce motif après le meilleur coup ? Un coup devenu
// illégal compte comme empêché. Sert à n'accuser un coup que d'un motif qu'il a permis.
function stillAfterBest<T>(fenBefore: string, best: string | undefined, reply: string, detect: (fen: string, uci: string) => T | null): boolean {
  if (!best) return true
  const fen = afterUci(fenBefore, best)
  return fen !== fenBefore && detect(fen, reply) !== null
}

// Pièce du joueur que la meilleure réponse adverse gagne vraiment (prise nette ≥ 2 une fois
// les reprises comptées ; pour la pièce qui vient de capturer, ce qu'elle a pris est déduit).
function lostToReply(fenAfter: string, reply: string | undefined, moved: { to: string; captured?: PieceSymbol }) {
  if (!reply) return null
  const cap = captureInfo(fenAfter, reply, null)
  if (!cap) return null
  const capturer = moved.to === cap.square && !!moved.captured
  const loss = cap.net - (capturer ? PIECE_VALUE[moved.captured!] : 0)
  if (loss < 2) return null
  const c = new Chess(fenAfter)
  const mover = other(c.turn())
  return {
    piece: cap.captured, square: cap.square, attacker: cap.by, capturer,
    defended: c.attackers(cap.square, mover).length > 0,
    cheaper: PIECE_VALUE[cap.by] < PIECE_VALUE[cap.captured],
  }
}

function forkVars(f: Fork, own: boolean): { vars: Vars; gender: Gender } {
  const name = (p: PieceSymbol) => (own ? PIECE_FR[p].ton : PIECE_FR[p].defini)
  return { vars: { cible: name(f.targets[0]), cible2: name(f.targets[1]) }, gender: pairGender(f.targets[0], f.targets[1]) }
}

function lineVars(l: LineMotif, own: boolean): { vars: Vars; gender: Gender } {
  const name = (p: PieceSymbol) => (own ? PIECE_FR[p].ton : PIECE_FR[p].defini)
  return { vars: { cible: name(l.front), cible2: name(l.rear) }, gender: PIECE_FR[l.front].genre }
}

export function coachComments(review: GameReview, playerColor: 'w' | 'b' | null): CoachComment[] {
  const comments: CoachComment[] = []
  const replay = new Chess(review.startFen)
  const pick = new Picker(review.moves.length)
  const book = review.startFen === START_FEN
  const ucis: string[] = []
  const passedFiles = new Set<string>()
  let lastCaptureSquare: string | null = null
  let lastFamily: string | null = null

  review.moves.forEach((m, i) => {
    const mover = replay.turn()
    const fenBefore = replay.fen()
    const played = replay.move(m.san)
    const fenAfter = replay.fen()
    ucis.push(m.uci)
    const headline = `${figurine(m.san, mover)} est ${CLASS_META[m.class].headline}`
    const mated = isCheckmateFen(fenAfter)
    const pat = isStalemateFen(fenAfter)
    const prevMate = i > 0 ? review.moves[i - 1].mateAfter : null
    // Mat contre le joueur après son coup / avant son coup ; mat pour lui avant / après.
    const against = mateAgainst(m.mateAfter, mover)
    const wasAgainst = mateAgainst(prevMate, mover)
    const wasFor = mateAgainst(prevMate, other(mover))
    const forAfter = mateAgainst(m.mateAfter, other(mover))
    const cap = captureInfo(fenBefore, m.uci, lastCaptureSquare)
    lastCaptureSquare = played.captured ? played.to : null
    const fam = book && m.class === 'book' ? familyFr(ucis) : null

    // Coup de l'adversaire : une bulle courte et neutre, jamais vide (ANA-36).
    if (playerColor && mover !== playerColor) {
      if (fam) lastFamily = fam
      const key = mated ? 'post.adverse.mat' : pat ? 'post.adverse.pat' : BAD_CLASSES.includes(m.class) ? 'post.adverse.erreur' : 'post.adverse.generique'
      comments.push({ moveIndex: i, headline, body: pick.say(key, i), severity: 'neutral', mood: key === 'post.adverse.erreur' ? 'happy' : 'thinking' })
      return
    }

    const bestUci = m.uci !== m.bestMoveUci ? m.bestMoveUci : undefined
    const better = bestUci ? sanOf(fenBefore, bestUci) ?? undefined : undefined
    const best = better ? bestUci : undefined
    const betterFig = better ? figurine(better, mover) : undefined
    const bestMates = !!better && better.endsWith('#')
    // Meilleure réponse adverse vue par le moteur (pv[0] de la position après le coup).
    const reply = review.moves[i + 1]?.bestMoveUci
    // {meilleur} n'existe que si un meilleur coup existe : le Picker écarte alors les variantes qui le citent.
    const vars: Vars = { coup: figurine(m.san, mover) }
    if (betterFig) vars.meilleur = betterFig
    let key: string
    let gender: Gender = 'm'
    let severity: CoachComment['severity'] = 'neutral'
    let mood: CoachComment['mood'] = 'thinking'
    // Situation à motif : ses marqueurs et son genre rejoignent ceux du coup.
    const withMotif = (k: string, extra: { vars: Vars; gender: Gender }): string => {
      Object.assign(vars, extra.vars)
      gender = extra.gender
      return k
    }

    if (m.class === 'book') {
      // Ouverture nommée quand sa famille change ; sortie de théorie sur le dernier coup
      // théorique du joueur (son coup suivant n'est plus dans les livres).
      const nextOwn = review.moves[i + 2]
      if (fam && fam !== lastFamily) {
        vars.ouverture = fam
        key = 'post.book.nommee'
      } else if (nextOwn && nextOwn.class !== 'book') key = 'post.book.sortie'
      else key = 'post.book.generique'
      if (fam) lastFamily = fam
    } else if (FAULTS.includes(m.class)) {
      key = faultKey()
      severity = m.class === 'blunder' || m.class === 'missedWin' ? 'alarm' : 'warn'
      mood = severity === 'alarm' ? 'worried' : 'thinking'
    } else {
      mood = 'happy'
      key = goodKey()
      if (key.startsWith('faute.')) mood = 'thinking'
      if (m.class === 'brilliant' || m.class === 'great') severity = 'praise'
    }

    comments.push({ moveIndex: i, headline, body: pick.say(key, i, vars, gender), betterMove: better, severity, mood })

    // Fautes : le plus grave d'abord, le motif vérifié ensuite, le générique de la classe en dernier.
    function faultKey(): string {
      if (pat) return 'faute.pat'
      if (against === 1) {
        // La réponse du moteur si elle mate, sinon le premier mat en 1 trouvé.
        const replyMates = !!reply && isCheckmateFen(afterUci(fenAfter, reply))
        const mateUci = replyMates ? reply! : null
        const mateSan = mateUci ? sanOf(fenAfter, mateUci) : mateInOne(fenAfter)
        vars.reponse = mateSan ? figurine(mateSan, other(mover)) : 'le prochain coup'
        // « {meilleur} empêchait le mat » seulement si c'est vérifié ; « déjà perdu » seulement
        // si le meilleur coup laissait aussi un mat en 1.
        const prevented = !!best && mateInOne(afterUci(fenBefore, best)) === null
        if (!prevented) delete vars.meilleur
        if (mateUci && backRankMate(fenAfter, mateUci)) return 'faute.mat_du_couloir_subi'
        return wasAgainst === 1 && !prevented ? 'faute.mat_en_1_deja' : 'faute.mat_en_1'
      }
      if (against > 1) {
        vars.n = against
        return wasAgainst > 0 ? 'faute.mat_en_n_deja' : 'faute.mat_en_n'
      }
      if (bestMates) {
        vars.n = 1
        return backRankMate(fenBefore, best!) ? 'faute.mat_du_couloir_manque' : 'faute.mat_manque'
      }
      if (wasFor > 0 && forAfter === 0 && best) {
        vars.n = wasFor
        return 'faute.mat_manque'
      }
      const lost = lostToReply(fenAfter, reply, { to: played.to, captured: played.captured as PieceSymbol | undefined })
      if (lost?.capturer) {
        gender = PIECE_FR[played.captured as PieceSymbol].genre
        vars.cible = PIECE_FR[played.captured as PieceSymbol].defini
        return 'faute.mauvais_echange'
      }
      if (reply) {
        const f = fork(fenAfter, reply)
        if (f && !stillAfterBest(fenBefore, best, reply, fork)) {
          vars.reponse = figurine(sanOf(fenAfter, reply)!, other(mover))
          return withMotif('faute.autorise_fourchette', forkVars(f, true))
        }
      }
      if (lost) {
        gender = PIECE_FR[lost.piece].genre
        Object.assign(vars, { piece: PIECE_FR[lost.piece].ton, case: lost.square, attaquant: PIECE_FR[lost.attacker].defini })
        return !lost.defended ? 'faute.piece_en_prise' : lost.cheaper ? 'faute.mal_defendue' : 'faute.sous_defendue'
      }
      if (reply) {
        const l = pinOrSkewer(fenAfter, reply)
        if (l?.kind === 'clouage' && !stillAfterBest(fenBefore, best, reply, pinOrSkewer)) {
          vars.reponse = figurine(sanOf(fenAfter, reply)!, other(mover))
          return withMotif('faute.autorise_clouage', lineVars(l, true))
        }
      }
      if (best) {
        const f = fork(fenBefore, best)
        if (f) {
          return withMotif('faute.fourchette_manquee', forkVars(f, false))
        }
        const bc = captureInfo(fenBefore, best, null)
        if (bc && bc.clean && bc.net >= 2) {
          gender = PIECE_FR[bc.captured].genre
          vars.cible = PIECE_FR[bc.captured].defini
          return 'faute.prise_gratuite'
        }
        const l = pinOrSkewer(fenBefore, best)
        if (l?.kind === 'clouage') {
          return withMotif('faute.clouage_manque', lineVars(l, false))
        }
        if (better!.startsWith('O-O')) return 'faute.roque_tardif'
      }
      const castle = castlingInfo(fenBefore, fenAfter, m.san, mover)
      if (castle?.kind === 'droit_perdu') return 'faute.droit_au_roque_perdu'
      if (best && !played.captured && materialBalance(fenBefore, mover) >= 3) {
        const bc = captureInfo(fenBefore, best, null)
        if (bc && bc.kind === 'echange' && bc.captured !== 'p') {
          vars.cible = PIECE_FR[bc.captured].defini
          return 'faute.simplification'
        }
      }
      return better ? `post.${m.class}.generique` : 'post.secours.generique'
    }

    // Bons coups : mat, mat raté, mat forcé, motif joué, prise, roque, pion passé, sinon la classe.
    // best et excellent ne sont plus des moments clés (ANA-15) : seuls brillant et très bon le restent.
    function goodKey(): string {
      if (mated) return backRankMate(fenBefore, m.uci) ? 'post.best.mat_du_couloir' : 'post.best.mat'
      if (bestMates) {
        vars.n = 1
        return backRankMate(fenBefore, best!) ? 'faute.mat_du_couloir_manque' : 'faute.mat_manque'
      }
      if (wasFor > 0 && best && (forAfter === 0 || forAfter >= wasFor) && (forAfter > 0 || m.winPctAfter >= 90)) {
        vars.n = wasFor
        return 'post.excellent.mat_plus_rapide'
      }
      if (!best && forAfter > 0) {
        vars.n = forAfter
        return 'post.best.mat_en_n'
      }
      if (m.class === 'brilliant') {
        gender = PIECE_FR[played.piece].genre
        vars.piece = PIECE_FR[played.piece].defini
        return 'post.brilliant.sacrifice'
      }
      const f = fork(fenBefore, m.uci)
      if (f) {
        return withMotif('post.best.fourchette', forkVars(f, false))
      }
      const l = pinOrSkewer(fenBefore, m.uci)
      if (l) {
        return withMotif(l.kind === 'enfilade' ? 'post.best.enfilade' : l.rear === 'k' ? 'post.best.clouage_absolu' : 'post.best.clouage', lineVars(l, false))
      }
      if (m.class === 'great') {
        if (cap?.kind === 'reprise') {
          gender = PIECE_FR[cap.captured].genre
          Object.assign(vars, { cible: PIECE_FR[cap.captured].defini, case: cap.square })
          return 'post.great.reprise'
        }
        const wb = m.winPctBefore
        const wa = m.winPctAfter
        if ((wb < 45 && wa >= 50) || (wb >= 45 && wb < 55 && wa >= 70)) return 'post.great.retournement'
        return 'post.great.seul_coup'
      }
      if (cap && (cap.kind === 'gain' || cap.kind === 'reprise')) {
        gender = PIECE_FR[cap.captured].genre
        vars.cible = PIECE_FR[cap.captured].defini
        return cap.kind === 'reprise' ? 'post.best.reprise' : cap.clean ? 'post.best.gain_materiel' : 'post.best.gain_echange'
      }
      if (m.san.startsWith('O-O')) return 'post.best.roque'
      const pp = passedPawn(fenBefore, m.uci)
      if (pp && !passedFiles.has(pp.square[0])) {
        passedFiles.add(pp.square[0])
        vars.case = pp.square
        return 'post.best.pion_passe'
      }
      if (m.class === 'good') return better ? 'post.good.generique' : 'post.excellent.generique'
      if (m.class === 'excellent') return 'post.excellent.generique'
      return 'post.best.generique'
    }
  })

  return comments
}

// Famille d'ouverture en français après ces coups, ou null si inconnue ou non traduite
// (une famille sans traduction resterait en anglais : on ne la nomme pas).
function familyFr(ucis: string[]): string | null {
  const o = openingForMoves(ucis)
  if (!o) return null
  const fam = openingFamilyFr(o.name)
  return fam !== o.name.split(':')[0].trim() ? fam : null
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

// Découpage en phases : ouverture = jusqu'au dernier coup de théorie (fallback 16 demi-coups),
// aucune sur un départ custom (position de puzzle, FEN importé) ; finale = dès qu'il reste
// ≤ 6 pièces hors pions et rois, d'emblée si la position de départ en a déjà ≤ 6, et
// seulement si elle dure au moins 8 demi-coups (sinon ces coups restent au milieu de partie).
export interface GamePhases {
  openingEnd: number // index du dernier demi-coup d'ouverture (-1 si aucun)
  endgameStart: number // index du premier demi-coup de finale (moves.length si jamais atteinte)
}

const MIN_ENDGAME_PLIES = 8

function minorAndMajor(c: Chess): number {
  let n = 0
  for (const row of c.board()) for (const sq of row) if (sq && sq.type !== 'p' && sq.type !== 'k') n++
  return n
}

export function detectPhases(review: GameReview): GamePhases {
  const total = review.moves.length
  const replay = new Chess(review.startFen)
  if (minorAndMajor(replay) <= 6) return { openingEnd: -1, endgameStart: 0 }

  let openingEnd = -1
  if (review.startFen === START_FEN) {
    review.moves.forEach((m, i) => {
      if (m.class === 'book') openingEnd = i
    })
    if (openingEnd === -1) openingEnd = Math.min(15, total - 1)
  }

  let endgameStart = total
  for (let i = 0; i < total; i++) {
    replay.move(review.moves[i].san)
    if (minorAndMajor(replay) <= 6) {
      endgameStart = i + 1
      break
    }
  }
  endgameStart = Math.max(endgameStart, openingEnd + 1)
  if (total - endgameStart < MIN_ENDGAME_PLIES) endgameStart = total
  return { openingEnd, endgameStart }
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

  // Récit par phases : seulement sur une vraie partie (30 demi-coups et plus).
  const accOpen = accuracyOnRange(review, color, 0, phases.openingEnd + 1)
  const accMid = accuracyOnRange(review, color, phases.openingEnd + 1, phases.endgameStart)
  const accEnd = accuracyOnRange(review, color, phases.endgameStart, review.moves.length)
  if (review.moves.length >= 30 && accOpen !== null && accMid !== null) {
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
