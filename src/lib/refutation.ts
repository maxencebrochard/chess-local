// Réfutation expliquée (« Pourquoi ? » sur une faute) : logique pure, sans moteur ni React.
// Le composant RefutationPlayer fournit la ligne principale du moteur après le coup fautif et
// les deux évaluations ; ce module en tire, demi-coup par demi-coup, des FAITS vérifiés sur
// l'échiquier (motifs.ts) puis des phrases qui ne disent rien d'autre que ces faits.
// Règle d'or, comme motifs.ts : aucune phrase sans fait calculé. Le gain matériel se lit sur la
// ligne réellement jouée (bilan cumulé), jamais sur une estimation statique d'échange.
// Testé sous Node contre un oracle python-chess indépendant (e2e/test_refutation.py).
import { Chess, type Color, type PieceSymbol, type Square } from 'chess.js'
import {
  backRankMate, captureInfo, fork, mateInOne, materialBalance, passedPawn, pinOrSkewer,
  PIECE_FR, uciMove, type CaptureInfo, type Fork, type LineMotif,
} from './motifs'
import { figurine, winPct, type MoveClass } from './review'

// Espace insécable avant « : », « ! », « ? » (typographie française, comme le coach).
const NB = ' '

// Fautes expliquées : celles que le bilan range dans « Mes erreurs » (une imprécision a
// rarement une réfutation parlante).
export const EXPLAINED_CLASSES: readonly MoveClass[] = ['mistake', 'miss', 'missedWin', 'blunder']

// Longueur de la ligne montrée : 4 à 8 demi-coups (moins si la ligne du moteur est plus courte
// ou finit sur un mat), prolongée d'au plus 2 reprises pour montrer les reprises immédiates.
export const MIN_PLIES = 4
export const MAX_PLIES = 8
const MAX_RECAPTURES = 2

// Sous cet écart de win%, le moteur juge le coup joué presque aussi bon que le meilleur : la carte
// « bon coup » ne présente alors pas le meilleur coup comme nettement supérieur.
export const CLOSE_WINPCT = 5

// Évaluation du point de vue du joueur fautif : cp > 0 ou mate > 0 = bon pour lui.
export interface Score {
  cp: number | null
  mate: number | null
}

// Score d'une ligne moteur calculée dans une position où l'ADVERSAIRE du joueur a le trait
// (après le coup fautif, ou après le bon coup) : les scores UCI sont du point de vue du trait,
// on les retourne donc pour le joueur.
export function scoreForPlayer(line: { scoreCp: number | null; scoreMate: number | null } | undefined): Score | null {
  if (!line) return null
  if (line.scoreMate !== null) return { cp: null, mate: -line.scoreMate }
  if (line.scoreCp === null) return null
  return { cp: -line.scoreCp, mate: null }
}

function scoreWinPct(s: Score): number {
  if (s.mate !== null) return s.mate > 0 ? 100 : 0
  return winPct(s.cp ?? 0)
}

// Évaluation lisible, signe explicite, virgule décimale, insécables (« mat en 2 » ne se coupe pas).
export function scoreText(s: Score): string {
  if (s.mate !== null) {
    const n = Math.abs(s.mate)
    return s.mate > 0 ? `mat${NB}en${NB}${n} pour toi` : `mat${NB}en${NB}${n} contre toi`
  }
  const v = (s.cp ?? 0) / 100
  const txt = Math.abs(v).toFixed(1).replace('.', ',')
  return v >= 0.05 ? `+${txt}` : v <= -0.05 ? `-${txt}` : '0,0'
}

export interface MoveFacts {
  uci: string
  san: string
  color: Color
  piece: PieceSymbol // pièce jouée (avant une éventuelle promotion)
  forced: boolean // seul coup légal
  mate: boolean
  backRank: boolean
  stalemate: boolean
  check: boolean // échec sans mat
  capture: CaptureInfo | null
  fork: Fork | null
  line: LineMotif | null
  passed: { square: Square; toGo: number } | null
  promotion: PieceSymbol | null
  // Nouvelle menace de mat en 1 : le camp qui vient de jouer materait s'il rejouait tout de suite,
  // ce qu'il ne pouvait pas faire avant son coup. SAN du mat.
  threat: string | null
}

// Mat en 1 du camp qui n'a PAS le trait s'il rejouait (l'autre passant son tour). Seulement
// quand le camp au trait n'est pas en échec : la position inversée serait illégale.
function mateIfMovedAgain(fen: string): string | null {
  const c = new Chess(fen)
  if (c.inCheck() || c.isGameOver()) return null
  const parts = fen.split(' ')
  parts[1] = parts[1] === 'w' ? 'b' : 'w'
  parts[3] = '-'
  try {
    return mateInOne(parts.join(' '))
  } catch {
    return null
  }
}

// Faits d'un coup UCI joué depuis `fen`, ou null s'il est illégal. `lastCaptureSquare` : case de
// la prise du demi-coup précédent (une prise sur la même case est une reprise).
export function moveFacts(fen: string, uci: string, lastCaptureSquare: string | null): MoveFacts | null {
  const c = new Chess(fen)
  const forced = c.moves().length === 1
  const mv = uciMove(c, uci)
  if (!mv) return null
  const mate = c.isCheckmate()
  const check = !mate && c.inCheck()
  let threat: string | null = null
  if (!mate && !check) {
    const t = mateIfMovedAgain(c.fen())
    // Menace déjà là avant le coup (le camp avait déjà ce mat au trait) : rien de nouveau.
    if (t && !mateInOne(fen)) threat = t
  }
  return {
    uci,
    san: mv.san,
    color: mv.color,
    piece: mv.piece,
    forced,
    mate,
    backRank: mate && backRankMate(fen, uci),
    stalemate: c.isStalemate(),
    check,
    capture: captureInfo(fen, uci, lastCaptureSquare),
    fork: fork(fen, uci),
    line: pinOrSkewer(fen, uci),
    passed: passedPawn(fen, uci),
    promotion: (mv.promotion as PieceSymbol | undefined) ?? null,
    threat,
  }
}

const def = (p: PieceSymbol) => PIECE_FR[p].defini
const PROMO_FR: Record<string, string> = { q: 'dame', r: 'tour', b: 'fou', n: 'cavalier' }

function list(items: string[]): string {
  return items.length <= 1 ? (items[0] ?? '') : `${items.slice(0, -1).join(', ')} et ${items[items.length - 1]}`
}

// Genre des faits phrasés, dans leur ordre de priorité : le test oracle les recalcule.
export type FactKind = 'capture' | 'mate' | 'check' | 'stalemate' | 'backRank' | 'fork' | 'line' | 'promotion' | 'passed' | 'threat'

export function factKinds(f: MoveFacts): FactKind[] {
  const out: FactKind[] = []
  // Un mat passe avant tout le reste (et le mat du couloir juste derrière lui).
  if (f.mate) out.push('mate')
  if (f.backRank) out.push('backRank')
  if (f.promotion) out.push('promotion')
  if (f.capture) out.push('capture')
  if (!f.mate && f.check) out.push('check')
  else if (f.stalemate) out.push('stalemate')
  if (f.fork) out.push('fork')
  if (f.line) out.push('line')
  if (f.passed) out.push('passed')
  if (f.threat) out.push('threat')
  return out
}

// Phrases d'un coup, une par fait, dans l'ordre de `factKinds`, au plus `max`. Le sujet est le
// coup lui-même (« ♞xd5 prend le fou en d5 ») : la même phrase vaut pour les deux camps.
// Une prise ne dit que ce qui est sûr sur l'échiquier : reprise, ou aucune reprise légale.
export function factSentences(f: MoveFacts, max = 2): string[] {
  const fig = figurine(f.san, f.color)
  const cap = f.capture
  const out = factKinds(f).map((k, i): string => {
    switch (k) {
      case 'capture': {
        // Après « ♕xf7# : échec et mat. », le coup est déjà nommé : « Il prend… ».
        const what = `${i > 0 ? 'Il' : fig} ${cap!.kind === 'reprise' ? 'reprend' : 'prend'} ${def(cap!.captured)} en ${cap!.square}`
        return cap!.kind !== 'reprise' && cap!.clean ? `${what}, et rien ne peut reprendre.` : `${what}.`
      }
      case 'mate': return `${fig}${NB}: échec et mat.`
      case 'check': return cap ? 'Échec.' : `${fig} donne échec.`
      case 'stalemate': return 'Pat, la partie est nulle.'
      case 'backRank': return 'Mat du couloir, le roi est enfermé derrière ses propres pièces.'
      case 'fork': return `Fourchette${NB}: ${def(f.fork!.by)} attaque ${list(f.fork!.targets.map(def))} à la fois.`
      case 'line': return f.line!.kind === 'clouage'
        ? `Clouage${NB}: ${def(f.line!.by)} cloue ${def(f.line!.front)} devant ${def(f.line!.rear)}.`
        : `Enfilade${NB}: ${def(f.line!.by)} attaque ${def(f.line!.front)}, ${def(f.line!.rear)} est derrière.`
      case 'promotion': return `Promotion en ${PROMO_FR[f.promotion!]}.`
      case 'passed': return `Le pion ${f.passed!.square} devient passé, à ${f.passed!.toGo} case${f.passed!.toGo > 1 ? 's' : ''} de la promotion.`
      case 'threat': return `Nouvelle menace${NB}: ${figurine(f.threat!.replace('#', ''), f.color)} et mat.`
    }
  })
  return out.slice(0, max)
}

// Nombre de demi-coups de la ligne à montrer : arrêt au mat (ou à la fin de partie) ; sinon
// jusqu'au dernier changement de matériel dans les 8 premiers, au moins 4 ; puis tant que le coup
// suivant reprend sur la case de la dernière prise (au plus 2 fois), pour montrer les reprises immédiates.
export function refutationLength(fenAfterPlayed: string, pv: string[]): number {
  const c = new Chess(fenAfterPlayed)
  const moves: { captured: boolean; to: string }[] = []
  for (let i = 0; i < Math.min(MAX_PLIES + MAX_RECAPTURES, pv.length); i++) {
    if (c.isGameOver()) break
    const mv = uciMove(c, pv[i])
    if (!mv) break
    moves.push({ captured: !!mv.captured, to: mv.to })
    if (c.isCheckmate() && i < MAX_PLIES) return i + 1
  }
  let lastChange = 0
  const replay = new Chess(fenAfterPlayed)
  for (let i = 0; i < Math.min(MAX_PLIES, moves.length); i++) {
    const mv = uciMove(replay, pv[i])!
    if (mv.captured || mv.promotion) lastChange = i + 1
  }
  let n = Math.min(Math.min(MAX_PLIES, moves.length), Math.max(MIN_PLIES, lastChange))
  while (n > 0 && n < moves.length && n < MAX_PLIES + MAX_RECAPTURES && moves[n - 1].captured && moves[n].captured && moves[n].to === moves[n - 1].to) n++
  return n
}

export type Actor = 'player' | 'opponent'

export interface RefStep {
  uci: string
  san: string
  color: Color
  actor: Actor
  fenBefore: string
  fenAfter: string
  facts: MoveFacts
  text: string
  material: number // bilan matériel du joueur depuis la position avant sa faute
}

export interface RefutationInput {
  fenBefore: string
  playedUci: string
  bestUci?: string | null
  pv: string[] // ligne du moteur depuis la position après le coup fautif
  evalAfterPlayed: Score | null // point de vue du joueur
  evalAfterBest?: Score | null
}

export interface BestCard {
  uci: string
  san: string
  fenAfter: string
  facts: MoveFacts
  prevention: Prevention | null
  close: boolean // le moteur juge le coup joué presque aussi bon
  text: string
}

export interface Refutation {
  player: Color
  intro: string
  played: RefStep
  line: RefStep[]
  summary: string
  best: BestCard | null
}

// null si le coup joué est illégal ou s'il mate (rien à réfuter).
export function buildRefutation(input: RefutationInput): Refutation | null {
  const { fenBefore, playedUci } = input
  const player = new Chess(fenBefore).turn()
  const base = materialBalance(fenBefore, player)
  const playedFacts = moveFacts(fenBefore, playedUci, null)
  if (!playedFacts || playedFacts.mate) return null
  const playedFig = figurine(playedFacts.san, player)
  const afterPlayed = new Chess(fenBefore)
  uciMove(afterPlayed, playedUci)
  const fenAfterPlayed = afterPlayed.fen()
  const evalPlayed = afterPlayed.isGameOver() ? null : input.evalAfterPlayed

  const playedText = [
    ...factSentences(playedFacts),
    evalPlayed ? `Après ${playedFig}, le moteur évalue la position à ${scoreText(evalPlayed)}.` : null,
  ].filter((s): s is string => !!s)
  const played: RefStep = {
    uci: playedUci, san: playedFacts.san, color: player, actor: 'player',
    fenBefore, fenAfter: fenAfterPlayed, facts: playedFacts,
    text: playedText.length ? playedText.join(' ') : `Tu joues ${playedFig}.`,
    material: materialBalance(fenAfterPlayed, player) - base,
  }

  const n = refutationLength(fenAfterPlayed, input.pv)
  const line: RefStep[] = []
  let fen = fenAfterPlayed
  let lastCap: string | null = playedFacts.capture ? playedFacts.capture.square : null
  for (let i = 0; i < n; i++) {
    const facts = moveFacts(fen, input.pv[i], lastCap)
    if (!facts) break
    const c = new Chess(fen)
    uciMove(c, input.pv[i])
    const actor: Actor = facts.color === player ? 'player' : 'opponent'
    const sentences = factSentences(facts)
    const fig = figurine(facts.san, facts.color)
    const text = sentences.length
      ? sentences.join(' ')
      : actor === 'opponent' ? `${fig}${NB}: la suite la plus forte selon le moteur.`
      : facts.forced ? `${fig}${NB}: ton seul coup légal.` : `${fig}${NB}: ta meilleure défense selon le moteur.`
    line.push({
      uci: input.pv[i], san: facts.san, color: facts.color, actor, fenBefore: fen, fenAfter: c.fen(),
      facts, text, material: materialBalance(c.fen(), player) - base,
    })
    lastCap = facts.capture ? facts.capture.square : null
    fen = c.fen()
  }

  const summary = summaryText(played, line, evalPlayed)
  const best = input.bestUci && input.bestUci !== playedUci
    ? bestCard(fenBefore, input.bestUci, playedFig, line[0] ?? null, input.evalAfterBest ?? null, evalPlayed)
    : null
  const span = line.length ? ` en ${line.length} demi-coup${line.length > 1 ? 's' : ''}` : ''
  const intro = line.length
    ? `Tu as joué ${playedFig}. Voici la réponse du moteur${span}.`
    : `Tu as joué ${playedFig}.`
  return { player, intro, played, line, summary, best }
}

function summaryText(played: RefStep, line: RefStep[], evalPlayed: Score | null): string {
  const last = line[line.length - 1] ?? played
  const end = new Chess(last.fenAfter)
  if (end.isCheckmate()) return end.turn() === played.color ? `Bilan${NB}: ton roi est mat.` : `Bilan${NB}: le roi adverse est mat.`
  if (end.isStalemate()) return `Bilan${NB}: pat, la partie est nulle.`
  const parts: string[] = []
  if (line.length === 0) {
    parts.push(`Le moteur n'a pas donné de suite après ${figurine(played.san, played.color)}.`)
    if (evalPlayed) parts.push(`Il évalue la position à ${scoreText(evalPlayed)}.`)
    return parts.join(' ')
  }
  const d = last.material
  const plies = line.length + 1
  const span = `sur la suite de ${plies} demi-coup${plies > 1 ? 's' : ''}`
  const pts = (n: number) => `${n} point${n > 1 ? 's' : ''}`
  if (d < 0) parts.push(`Bilan${NB}: tu perds ${pts(-d)} de matériel ${span}.`)
  else if (d > 0) parts.push(`Bilan${NB}: tu gagnes ${pts(d)} de matériel ${span}.`)
  else parts.push(`Bilan${NB}: le matériel reste inchangé ${span}.`)
  if (evalPlayed) parts.push(`Le moteur évalue la position après ton coup à ${scoreText(evalPlayed)}.`)
  return parts.join(' ')
}

function bestCard(fenBefore: string, bestUci: string, playedFig: string, ref1: RefStep | null, evalBest: Score | null, evalPlayed: Score | null): BestCard | null {
  const facts = moveFacts(fenBefore, bestUci, null)
  if (!facts) return null
  const c = new Chess(fenBefore)
  uciMove(c, bestUci)
  const fenAfter = c.fen()
  const fig = figurine(facts.san, facts.color)
  // Le bon coup mate ou pate : pas d'évaluation moteur à comparer (aucune recherche).
  const terminal = c.isGameOver()
  const close = !terminal && !!evalBest && !!evalPlayed && scoreWinPct(evalBest) - scoreWinPct(evalPlayed) < CLOSE_WINPCT
  const prevention = ref1 && !close ? preventionKind(fenAfter, ref1.facts) : null
  const parts = close
    ? [`À cette profondeur, le moteur juge ${playedFig} presque aussi bon que ${fig}, ou meilleur (${scoreText(evalPlayed!)} contre ${scoreText(evalBest!)}).`]
    : factSentences(facts) // le titre de la carte nomme déjà le bon coup
  if (prevention) parts.push(preventionText(prevention, ref1!))
  if (!close && !terminal && evalBest && evalPlayed) parts.push(`Moteur${NB}: ${scoreText(evalBest)}, contre ${scoreText(evalPlayed)}.`)
  if (parts.length === 0) parts.push(`Le meilleur coup selon le moteur était ${fig}.`)
  return { uci: bestUci, san: facts.san, fenAfter, facts, prevention, close, text: parts.join(' ') }
}

// Ce que le bon coup change au premier coup de la réfutation, vérifié dans la position après lui.
// illegal : le coup n'existe plus (case de départ vide, autre pièce, ou coup illégal) ;
// no_mate : il matait, il ne mate plus ; no_take : il prenait une pièce sans reprise possible,
// il ne le peut plus ; no_fork : c'était une fourchette, ce n'en est plus une.
export type Prevention = 'illegal' | 'no_mate' | 'no_take' | 'no_fork'
export function preventionKind(fenAfterBest: string, ref1: MoveFacts): Prevention | null {
  if (new Chess(fenAfterBest).isGameOver()) return null
  const piece = new Chess(fenAfterBest).get(ref1.uci.slice(0, 2) as Square)
  const f = moveFacts(fenAfterBest, ref1.uci, null)
  if (!f || !piece || piece.color !== ref1.color || piece.type !== ref1.piece) return 'illegal'
  if (ref1.mate && !f.mate) return 'no_mate'
  if (ref1.capture?.clean && !(f.capture?.clean)) return 'no_take'
  if (ref1.fork && !f.fork) return 'no_fork'
  return null
}

function preventionText(kind: Prevention, ref1: RefStep): string {
  const fig = figurine(ref1.san, ref1.color)
  const bare = fig.replace(/[+#]/g, '')
  switch (kind) {
    case 'illegal': return `Il empêche ${fig}.`
    case 'no_mate': return `Après lui, ${bare} ne serait plus mat.`
    case 'no_take': return `Après lui, ${bare} ne prendrait plus de pièce sans reprise possible.`
    case 'no_fork': return `Après lui, ${bare} ne serait plus une fourchette.`
  }
}
