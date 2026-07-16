// Coach post-partie : commentaires en français générés par règles depuis le
// Game Review (classe du coup, delta d'éval, matériel, mat, meilleur coup).
import { Chess, type Square } from 'chess.js'
import type { GameReview, ReviewedMove } from './review'

export interface CoachComment {
  moveIndex: number
  text: string
  // Coup meilleur suggéré, en SAN, quand le coup joué n'était pas le bon.
  betterMove?: string
  severity: 'praise' | 'neutral' | 'warn' | 'alarm'
}

const PIECE_NAMES: Record<string, string> = {
  p: 'le pion', n: 'le cavalier', b: 'le fou', r: 'la tour', q: 'la dame', k: 'le roi',
}
const PIECE_VALUE: Record<string, number> = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 }

function fmtEval(m: ReviewedMove): string {
  if (m.mateAfter !== null && m.mateAfter !== 0) {
    const side = m.mateAfter > 0 ? 'les Blancs' : 'les Noirs'
    return `mat en ${Math.abs(m.mateAfter)} pour ${side}`
  }
  if (m.evalAfterCp === null) return ''
  const v = m.evalAfterCp / 100
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}`
}

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
    const point = better ? bestMovePoint(fenBefore, m.bestMoveUci) : ''
    const evalTxt = fmtEval(m)
    let text: string
    let severity: CoachComment['severity'] = 'neutral'

    switch (m.class) {
      case 'brilliant':
        text = `${m.san} est brillant ! Un sacrifice que la tactique justifie entièrement. Superbe vision.`
        severity = 'praise'
        break
      case 'great':
        text = `${m.san} était le seul bon coup dans cette position. Bien vu.`
        severity = 'praise'
        break
      case 'best':
        text = `${m.san} est exactement ce que le moteur aurait joué.`
        severity = 'praise'
        break
      case 'excellent':
        text = `${m.san} est un excellent coup, quasiment optimal.`
        severity = 'praise'
        break
      case 'good':
        text = `${m.san} est correct${better ? `, même si ${better} était un peu plus précis` : ''}.`
        break
      case 'book':
        text = `${m.san} suit la théorie.`
        break
      case 'inaccuracy':
        text = `${m.san} est une imprécision. ${better ? `${better}${point} gardait un meilleur contrôle.` : ''} (${evalTxt})`
        severity = 'warn'
        break
      case 'mistake': {
        const hung = hungPiece(fenAfter, moverColor)
        text = `${m.san} est une erreur${hung ? ` : ${hung} peut être capturé` : ''}. ${better ? `Il fallait jouer ${better}${point}.` : ''} (${evalTxt})`
        severity = 'warn'
        break
      }
      case 'blunder': {
        const hung = hungPiece(fenAfter, moverColor)
        const missedMate = m.mateAfter !== null && (moverColor === 'w' ? m.mateAfter < 0 : m.mateAfter > 0)
        text = `${m.san} est une gaffe${hung ? ` qui abandonne ${hung}` : ''}${missedMate ? ' et laisse un mat forcé' : ''}. ${better ? `${better}${point} était nécessaire.` : ''} (${evalTxt})`
        severity = 'alarm'
        break
      }
    }

    comments.push({ moveIndex: i, text, betterMove: better, severity })
  })

  return comments
}

// Résumé d'ouverture de session du coach.
export function coachSummary(review: GameReview, playerColor: 'w' | 'b' | null): string {
  const color = playerColor ?? 'w'
  const acc = color === 'w' ? review.accuracyWhite : review.accuracyBlack
  const counts = review.counts[color]
  const mistakes = counts.mistake + counts.blunder
  const parts: string[] = []

  if (acc >= 90) parts.push(`Très belle partie : ${acc} % de précision.`)
  else if (acc >= 75) parts.push(`Partie solide, ${acc} % de précision.`)
  else if (acc >= 55) parts.push(`Partie correcte à ${acc} % de précision, avec des occasions manquées.`)
  else parts.push(`Partie difficile (${acc} % de précision), mais chaque erreur est une leçon.`)

  if (counts.brilliant > 0) parts.push(`Tu as trouvé ${counts.brilliant} coup${counts.brilliant > 1 ? 's' : ''} brillant${counts.brilliant > 1 ? 's' : ''} !`)
  if (counts.blunder > 0) parts.push(`${counts.blunder} gaffe${counts.blunder > 1 ? 's' : ''} à revoir en priorité.`)
  else if (mistakes === 0) parts.push('Aucune erreur grave, très propre.')

  parts.push('Navigue avec les flèches, je commente chaque coup.')
  return parts.join(' ')
}
