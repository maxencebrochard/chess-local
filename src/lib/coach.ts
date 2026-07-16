// Coach post-partie : commentaires en français générés par règles depuis le
// Game Review (classe du coup, delta d'éval, matériel, mat, meilleur coup).
import { Chess, type Square } from 'chess.js'
import { CLASS_META, figurine, type GameReview, type MoveClass } from './review'

export interface CoachComment {
  moveIndex: number
  // « ♗xa7 est une gaffe » — affiché en gras avec la pastille de classe.
  headline: string
  // Explication en langage naturel, sans répéter le coup.
  body: string
  // Coup meilleur suggéré, en SAN, quand le coup joué n'était pas le bon.
  betterMove?: string
  severity: 'praise' | 'neutral' | 'warn' | 'alarm'
}

const PIECE_NAMES: Record<string, string> = {
  p: 'le pion', n: 'le cavalier', b: 'le fou', r: 'la tour', q: 'la dame', k: 'le roi',
}
const PIECE_VALUE: Record<string, number> = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 }

// SAN du meilleur coup depuis la position avant le coup joué.
function bestMoveSan(fenBefore: string, uci: string): string | undefined {
  try {
    const c = new Chess(fenBefore)
    return c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] }).san
  } catch {
    return undefined
  }
}

// Ce que le meilleur coup accomplissait : mat, gain de matériel, ou rien de spécial.
function bestMovePoint(fenBefore: string, bestUci: string): string {
  try {
    const c = new Chess(fenBefore)
    const target = c.get(bestUci.slice(2, 4) as Square)
    const mv = c.move({ from: bestUci.slice(0, 2), to: bestUci.slice(2, 4), promotion: bestUci[4] })
    if (c.isCheckmate()) return ' qui matait immédiatement'
    if (mv.san.includes('#')) return ' qui matait immédiatement'
    if (target && PIECE_VALUE[target.type] >= 3) return ` qui gagnait ${PIECE_NAMES[target.type]}`
    if (mv.san.includes('+')) return ' avec échec'
    return ''
  } catch {
    return ''
  }
}

// Ce que le coup joué a coûté : pièce pendue ?
function hungPiece(fenAfter: string, moverColor: 'w' | 'b'): string | null {
  // Détection simple : la meilleure réponse adverse capture une pièce non défendue de valeur ≥ 3.
  // On approxime avec les captures disponibles gagnantes au SEE naïf (valeur cible > valeur attaquant si défendu, sinon valeur cible).
  const c = new Chess(fenAfter)
  let bestGain = 0
  let bestPiece: string | null = null
  for (const mv of c.moves({ verbose: true })) {
    if (!mv.captured) continue
    const victim = PIECE_VALUE[mv.captured]
    if (victim < 3) continue
    // Défendu ? On regarde si la case de capture est reprise possible.
    const c2 = new Chess(fenAfter)
    c2.move(mv.san)
    const recaptures = c2.moves({ verbose: true }).filter((r) => r.to === mv.to && r.captured)
    const gain = recaptures.length > 0 ? victim - PIECE_VALUE[mv.piece] : victim
    if (gain > bestGain) {
      bestGain = gain
      bestPiece = mv.captured
    }
  }
  if (bestGain >= 3 && bestPiece) return PIECE_NAMES[bestPiece]
  void moverColor
  return null
}

export function coachComments(review: GameReview, playerColor: 'w' | 'b' | null): CoachComment[] {
  const comments: CoachComment[] = []
  const replay = new Chess()

  review.moves.forEach((m, i) => {
    const moverColor: 'w' | 'b' = i % 2 === 0 ? 'w' : 'b'
    const fenBefore = replay.fen()
    replay.move(m.san)
    const fenAfter = replay.fen()

    // Le coach ne commente que les coups du joueur (les deux couleurs en partie locale).
    if (playerColor && moverColor !== playerColor) return

    const better = m.uci !== m.bestMoveUci ? bestMoveSan(fenBefore, m.bestMoveUci) : undefined
    const betterFig = better ? figurine(better, moverColor) : undefined
    const point = better ? bestMovePoint(fenBefore, m.bestMoveUci) : ''
    const headline = `${figurine(m.san, moverColor)} est ${CLASS_META[m.class].headline}`
    let body: string
    let severity: CoachComment['severity'] = 'neutral'

    switch (m.class) {
      case 'brilliant':
        body = 'Un sacrifice que la tactique justifie entièrement. Superbe vision !'
        severity = 'praise'
        break
      case 'great':
        body = "C'était le seul bon coup dans cette position. Bien vu."
        severity = 'praise'
        break
      case 'best':
        body = "Exactement ce que le moteur aurait joué. Rien à redire."
        severity = 'praise'
        break
      case 'excellent':
        body = 'Quasiment optimal. Ça tient la route.'
        severity = 'praise'
        break
      case 'good':
        body = better ? `Correct, même si ${betterFig} était un peu plus précis.` : 'Correct, la position reste saine.'
        break
      case 'book':
        body = 'La théorie approuve. Terrain connu.'
        break
      case 'inaccuracy':
        body = better ? `${betterFig}${point} gardait un meilleur contrôle de la position.` : 'La position glisse doucement.'
        severity = 'warn'
        break
      case 'mistake': {
        const hung = hungPiece(fenAfter, moverColor)
        body = `${hung ? `${hung[0].toUpperCase()}${hung.slice(1)} peut maintenant être capturé. ` : ''}${better ? `Il fallait jouer ${betterFig}${point}.` : ''}`
        severity = 'warn'
        break
      }
      case 'miss': {
        body = `L'adversaire venait de faire une faute et ça reste impuni. ${better ? `${betterFig}${point} punissait immédiatement.` : ''}`
        severity = 'warn'
        break
      }
      case 'missedWin': {
        body = `Une position gagnante vient d'être jetée. ${better ? `${betterFig}${point} gardait la victoire en main.` : ''}`
        severity = 'alarm'
        break
      }
      case 'blunder': {
        const hung = hungPiece(fenAfter, moverColor)
        const missedMate = m.mateAfter !== null && (moverColor === 'w' ? m.mateAfter < 0 : m.mateAfter > 0)
        body = `${hung ? `Ça abandonne ${hung}. ` : ''}${missedMate ? 'Et un mat forcé est maintenant au tableau. ' : ''}${better ? `${betterFig}${point} était nécessaire.` : ''}`
        severity = 'alarm'
        break
      }
    }

    comments.push({ moveIndex: i, headline, body: body.trim() || 'Voyons la suite.', betterMove: better, severity })
  })

  return comments
}

// Punchline courte du coach pour l'écran de résumé, façon chess.com.
export function coachQuip(review: GameReview, playerColor: 'w' | 'b' | null): string {
  const color = playerColor ?? 'w'
  const report = phaseReport(review)
  const o = report.opening[color]
  const m = report.middlegame[color]
  const e = report.endgame[color]
  if (o === 'good' && (m === 'bad' || m === 'meh')) return "Le milieu de partie a dérapé, mais au moins l'ouverture était solide."
  if (o !== 'good' && m === 'good') return "L'ouverture a piqué, mais tu t'es bien rattrapé au milieu de partie."
  if (e === 'bad') return 'Tout se jouait dans la finale… et elle a glissé. Ça se travaille.'
  if (e === 'good' && (m === 'bad' || o === 'bad')) return 'Belle finale ! Le début de partie mérite encore du travail.'
  const acc = color === 'w' ? review.accuracyWhite : review.accuracyBlack
  if (acc >= 90) return 'Une partie très propre. Continue comme ça.'
  if (acc >= 75) return 'Une partie solide, avec quelques occasions à ne plus laisser filer.'
  if (acc >= 55) return 'Des hauts et des bas — on regarde les moments clés ensemble ?'
  return 'Partie compliquée, mais chaque erreur est une leçon. Au travail.'
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

  const replay = new Chess()
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
    if ((i % 2 === 0 ? 'w' : 'b') !== color) continue
    const m = review.moves[i]
    const drop = Math.max(0, m.winPctBefore - m.winPctAfter)
    accs.push(Math.max(0, Math.min(100, 103.1668 * Math.exp(-0.04354 * drop) - 3.1669)))
  }
  if (accs.length === 0) return null
  return Math.round((accs.reduce((a, b) => a + b, 0) / accs.length) * 10) / 10
}

function phaseVerdict(acc: number | null): string {
  if (acc === null) return 'pas de coup à évaluer'
  if (acc >= 92) return 'impeccable'
  if (acc >= 80) return 'solide'
  if (acc >= 65) return 'irrégulière'
  return 'difficile'
}

const BAD_CLASSES: MoveClass[] = ['blunder', 'missedWin', 'miss', 'mistake']

// Résumé narratif d'ouverture de session du coach.
export function coachSummary(review: GameReview, playerColor: 'w' | 'b' | null): string {
  const color = playerColor ?? 'w'
  const acc = color === 'w' ? review.accuracyWhite : review.accuracyBlack
  const rating = color === 'w' ? review.gameRatingWhite : review.gameRatingBlack
  const counts = review.counts[color]
  const phases = detectPhases(review)
  const parts: string[] = []

  // Verdict global + game rating.
  if (acc >= 90) parts.push(`Très belle partie : ${acc} % de précision — tu as joué comme un ~${rating}.`)
  else if (acc >= 75) parts.push(`Partie solide (${acc} % de précision), niveau de jeu estimé ~${rating}.`)
  else if (acc >= 55) parts.push(`${acc} % de précision, un niveau de jeu autour de ${rating} sur cette partie.`)
  else parts.push(`Partie compliquée (${acc} % de précision, ~${rating}), mais on va en tirer les leçons.`)

  // Compte des fautes, mis en avant.
  const faults: string[] = []
  if (counts.blunder > 0) faults.push(`${counts.blunder} gaffe${counts.blunder > 1 ? 's' : ''}`)
  if (counts.missedWin > 0) faults.push(`${counts.missedWin} gain${counts.missedWin > 1 ? 's' : ''} manqué${counts.missedWin > 1 ? 's' : ''}`)
  if (counts.miss > 0) faults.push(`${counts.miss} occasion${counts.miss > 1 ? 's' : ''} manquée${counts.miss > 1 ? 's' : ''}`)
  if (counts.mistake > 0) faults.push(`${counts.mistake} erreur${counts.mistake > 1 ? 's' : ''}`)
  if (faults.length > 0) parts.push(`Au tableau : ${faults.join(', ')} — je te les montre une par une avec « Moment clé ».`)
  else parts.push('Aucune faute sérieuse, très propre.')
  if (counts.brilliant > 0) parts.push(`Et ${counts.brilliant === 1 ? 'un coup brillant' : `${counts.brilliant} coups brillants`} !`)

  // Récit par phases.
  const accOpen = accuracyOnRange(review, color, 0, phases.openingEnd + 1)
  const accMid = accuracyOnRange(review, color, phases.openingEnd + 1, phases.endgameStart)
  const accEnd = accuracyOnRange(review, color, phases.endgameStart, review.moves.length)
  const phraseParts: string[] = []
  if (accOpen !== null) phraseParts.push(`ouverture ${phaseVerdict(accOpen)} (${accOpen} %)`)
  if (accMid !== null) phraseParts.push(`milieu de partie ${phaseVerdict(accMid)} (${accMid} %)`)
  if (accEnd !== null) phraseParts.push(`finale ${phaseVerdict(accEnd)} (${accEnd} %)`)
  if (phraseParts.length > 1) parts.push(`Le film : ${phraseParts.join(', ')}.`)

  // Le moment où la partie a basculé (plus gros drop du joueur).
  let pivotIdx = -1
  let pivotDrop = 12
  review.moves.forEach((m, i) => {
    if ((i % 2 === 0 ? 'w' : 'b') !== color) return
    if (!BAD_CLASSES.includes(m.class)) return
    const drop = m.winPctBefore - m.winPctAfter
    if (drop > pivotDrop) {
      pivotDrop = drop
      pivotIdx = i
    }
  })
  if (pivotIdx >= 0) {
    const moveNo = Math.floor(pivotIdx / 2) + 1
    parts.push(`La partie a basculé au ${moveNo}e coup : ${review.moves[pivotIdx].san}.`)
  }

  return parts.join(' ')
}
