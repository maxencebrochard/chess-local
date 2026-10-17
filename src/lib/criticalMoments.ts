// « Moments critiques » : parcours utilisateur décrit dans README.md, section Features → Analyse.
// La sélection et les réponses se déduisent du bilan (`GameReview`) et de l'échiquier
// (chess.js et motifs.ts), sans nouvelle recherche moteur.
// Testée sous Node par la suite `moments` (e2e/test_moments.py).
import { Chess, type Color, type PieceSymbol, type Square } from 'chess.js'
import { db } from './db'
import { mateInOne, other, PIECE_FR, sanOf, see } from './motifs'
import { figurine, type GameReview, type MoveClass } from './review'

// Une bascule : le coup joué fait perdre au moins 10 points de win% (seuil de l'« Erreur »), depuis
// une position pas déjà perdue, vers une position qui n'est plus largement gagnante.
export const DROP_MIN = 10
export const LOST_BEFORE = 15
export const STILL_WINNING_AFTER = 85
// Coup unique : le 2e coup de Stockfish fait perdre plus de 20 points (seuil du « Très bon » de review.ts).
export const FORCED_GAP = 20
// Prise menacée : au moins 2 points de matériel gagnés après échanges (une pièce contre un pion, la qualité).
export const THREAT_GAIN = 2
export const MAX_MOMENTS = 3

export type MomentAnswer = 'forced' | 'threat' | 'plan'

export const ANSWER_LABEL: Record<MomentAnswer, string> = {
  plan: 'Plan',
  threat: 'Menace',
  forced: 'Coup forcé',
}
export const ANSWERS: MomentAnswer[] = ['plan', 'threat', 'forced']

// Menace adverse vérifiée sur l'échiquier, le trait donné à l'adversaire (« coup nul »).
export type Threat =
  | { kind: 'check' }
  | { kind: 'mate'; san: string }
  | { kind: 'capture'; san: string; piece: PieceSymbol; square: Square; gain: number }
  | { kind: 'promotion'; san: string; square: Square }

export interface CriticalMoment {
  index: number // demi-coup du bilan
  color: Color // camp au trait (celui qui a joué le coup)
  moveNo: string // « 14 » ou « 14... »
  fen: string // position avant le coup
  playedSan: string
  playedUci: string
  cls: MoveClass
  bestUci: string
  bestSan: string
  found: boolean // le coup joué est celui de Stockfish
  drop: number // chute de win% du coup joué (point de vue du trait)
  winBefore: number // win% avec le meilleur coup
  winSecond: number | null // win% avec le 2e coup de Stockfish, null si inconnu
  bestMates: boolean // le meilleur coup mate : coup forcé quel que soit l'écart
  answer: MomentAnswer
  threat: Threat | null
}

// Menace de l'adversaire dans `fen` (trait au joueur) : roi en échec, sinon ce que l'adversaire
// ferait s'il jouait maintenant : mat en 1, puis la prise qui gagne le plus de matériel (≥ 2), puis
// une promotion en dame que rien ne peut reprendre. Fourchettes et mats en 2 ne sont pas cherchés.
export function threatIn(fen: string): Threat | null {
  const c = new Chess(fen)
  if (c.inCheck()) return { kind: 'check' }
  const me = c.turn()
  const parts = fen.split(' ')
  parts[1] = other(me)
  parts[3] = '-' // la prise en passant n'appartient qu'au coup qui vient d'être joué
  const flipped = parts.join(' ')
  let nul: Chess
  try {
    nul = new Chess(flipped)
  } catch {
    return null
  }
  const mate = mateInOne(flipped)
  if (mate) return { kind: 'mate', san: mate }
  let best: Extract<Threat, { kind: 'capture' }> | null = null
  for (const sq of nul.board().flat()) {
    if (!sq || sq.color !== me || sq.type === 'k') continue
    if (nul.attackers(sq.square, other(me)).length === 0) continue
    const gain = see(flipped, sq.square)
    if (gain < THREAT_GAIN || (best && gain <= best.gain)) continue
    // La prise la moins chère sur la case, celle que `see` a jouée.
    const capture = nul
      .moves({ verbose: true })
      .filter((m) => m.to === sq.square && m.captured)
      .sort((a, b) => valueOf(a.piece) - valueOf(b.piece))[0]
    if (capture) best = { kind: 'capture', san: capture.san, piece: sq.type, square: sq.square, gain }
  }
  if (best) return best
  for (const mv of nul.moves({ verbose: true })) {
    if (mv.promotion !== 'q') continue
    const after = new Chess(flipped)
    after.move(mv.san)
    if (!after.moves({ verbose: true }).some((r) => r.to === mv.to)) return { kind: 'promotion', san: mv.san, square: mv.to }
  }
  return null
}

const valueOf = (p: PieceSymbol) => ({ p: 1, n: 3, b: 3, r: 5, q: 9, k: 100 })[p]

// Réponse attendue, par priorité : un seul coup tient ou le meilleur coup mate (coup forcé), sinon l'adversaire menace
// quelque chose (menace), sinon la position demande un plan.
export function expectedAnswer(winBefore: number, winSecond: number | null, threat: Threat | null, bestMates = false): MomentAnswer {
  if (bestMates || (winSecond !== null && winBefore - winSecond > FORCED_GAP)) return 'forced'
  if (threat) return 'threat'
  return 'plan'
}

interface Candidate {
  index: number
  score: number
}

export function criticalMoments(review: GameReview, playerColor: Color | null): CriticalMoment[] {
  const replay = new Chess(review.startFen)
  const fens: string[] = []
  const legalCounts: number[] = []
  for (const m of review.moves) {
    fens.push(replay.fen())
    legalCounts.push(replay.moves().length)
    try {
      replay.move(m.san)
    } catch {
      break // bilan incohérent avec sa position de départ : on s'arrête là
    }
  }

  const candidates: Candidate[] = []
  for (let i = 0; i < fens.length; i++) {
    const m = review.moves[i]
    const color = new Chess(fens[i]).turn()
    if (playerColor && color !== playerColor) continue
    if (m.class === 'book' || legalCounts[i] < 2) continue
    const drop = Math.max(0, m.winPctBefore - m.winPctAfter)
    const gap = m.winPctSecond != null ? m.winPctBefore - m.winPctSecond : null
    // Le coup joué compte, pas le bruit d'une recherche à profondeur fixe : une bascule est un
    // autre coup que celui de Stockfish, un coup unique trouvé est le sien.
    const found = m.uci === m.bestMoveUci
    if (!found && drop >= DROP_MIN && m.winPctBefore > LOST_BEFORE && m.winPctAfter < STILL_WINNING_AFTER) {
      candidates.push({ index: i, score: drop })
    } else if (found && drop < DROP_MIN && gap !== null && gap > FORCED_GAP) {
      candidates.push({ index: i, score: gap / 2 })
    }
  }

  // Chaque coup est jugé contre le meilleur coup de SA position : deux coups voisins sont deux
  // décisions distinctes, tous deux gardés s'ils comptent parmi les plus lourds.
  candidates.sort((a, b) => b.score - a.score || a.index - b.index)
  return candidates
    .slice(0, MAX_MOMENTS)
    .map((c) => c.index)
    .sort((a, b) => a - b)
    .map((i) => {
      const m = review.moves[i]
      const fen = fens[i]
      const color = new Chess(fen).turn()
      const threat = threatIn(fen)
      const winSecond = m.winPctSecond ?? null
      const fullMove = Number(fen.split(' ')[5])
      const bestSan = sanOf(fen, m.bestMoveUci) ?? m.san
      return {
        index: i,
        color,
        moveNo: color === 'w' ? `${fullMove}` : `${fullMove}...`,
        fen,
        playedSan: m.san,
        playedUci: m.uci,
        cls: m.class,
        bestUci: m.bestMoveUci,
        bestSan,
        found: m.uci === m.bestMoveUci,
        drop: Math.max(0, m.winPctBefore - m.winPctAfter),
        winBefore: m.winPctBefore,
        winSecond,
        bestMates: bestSan.endsWith('#'),
        answer: expectedAnswer(m.winPctBefore, winSecond, threat, bestSan.endsWith('#')),
        threat,
      }
    })
}

const pct = (x: number) => `${Math.round(x)} %`

// Phrase qui décrit la menace, adversaire au sujet (« Les Noirs menaçaient ... »).
function threatText(t: Threat, fig: (san: string) => string): string {
  if (t.kind === 'check') return "le roi était en échec : il fallait d'abord y répondre"
  if (t.kind === 'mate') return `l'adversaire menaçait de mater en un coup par ${fig(t.san)}`
  if (t.kind === 'promotion') return `l'adversaire menaçait d'aller à dame en ${t.square} (${fig(t.san)})`
  return `l'adversaire menaçait de prendre ${PIECE_FR[t.piece].defini} en ${t.square} (${fig(t.san)})`
}

// Justification de la bonne réponse, déduite des faits du moment.
export function momentExplanation(m: CriticalMoment): string {
  const theirs = (san: string) => figurine(san, other(m.color))
  if (m.answer === 'forced') {
    const second = m.winSecond ?? 0
    // Le coup lui-même n'est jamais nommé : il reste à trouver en rejouant la position.
    if (m.bestMates) return "Un mat en un coup était sur l'échiquier : quand il existe, il passe avant tout le reste."
    const base = `Un seul coup tenait : avec le deuxième choix de Stockfish, les chances de gain passaient déjà de ${pct(m.winBefore)} à ${pct(second)}.`
    return m.threat ? `${base} Ici, ${threatText(m.threat, theirs)}.` : base
  }
  if (m.answer === 'threat') {
    return `Plusieurs coups tenaient, mais ${threatText(m.threat!, theirs)}. Avant tout projet, on regarde ce que veut l'adversaire.`
  }
  return "Aucun coup unique ne s'imposait et aucune menace immédiate (mat, prise, promotion) : la position demandait un plan, c'est-à-dire améliorer ses pièces ou viser une faiblesse."
}

// Règle affichée sous la justification : l'ordre dans lequel se pose la question.
export const ANSWER_RULE =
  "La règle : coup forcé si un seul coup tient (ou si un mat est là), sinon menace si l'adversaire menace quelque chose, sinon plan."

// ---------- Résultats (learnSessions, domaine 'critical-moment', hors Elo) ----------

export const MOMENT_DOMAIN = 'critical-moment'

export async function recordMomentAnswer(fen: string, expected: MomentAnswer, chosen: MomentAnswer): Promise<void> {
  await db.learnSessions.add({
    date: Date.now(), domain: MOMENT_DOMAIN, itemId: `question:${expected}:${chosen}`, fen,
    success: expected === chosen ? 1 : 0, ratingAfter: null,
  })
}

export async function recordMomentMove(fen: string, expected: MomentAnswer, found: boolean): Promise<void> {
  await db.learnSessions.add({
    date: Date.now(), domain: MOMENT_DOMAIN, itemId: `coup:${expected}`, fen, success: found ? 1 : 0, ratingAfter: null,
  })
}

export interface MomentHistory {
  chosen: MomentAnswer | null // dernière réponse donnée pour cette position
  move: 'found' | 'missed' | null // dernière tentative notée
}

// Dernière réponse et dernière tentative pour chaque position (clé : FEN).
export async function momentHistory(fens: string[]): Promise<Map<string, MomentHistory>> {
  const wanted = new Set(fens)
  const rows = await db.learnSessions.where('domain').equals(MOMENT_DOMAIN).sortBy('date')
  const out = new Map<string, MomentHistory>()
  for (const r of rows) {
    if (!r.fen || !wanted.has(r.fen)) continue
    const h = out.get(r.fen) ?? { chosen: null, move: null }
    const [kind, , chosen] = r.itemId.split(':')
    if (kind === 'question' && (ANSWERS as string[]).includes(chosen)) h.chosen = chosen as MomentAnswer
    else if (kind === 'coup') h.move = r.success ? 'found' : 'missed'
    out.set(r.fen, h)
  }
  return out
}

// ---------- Retour au bilan ----------

// Bilan rapporté par le retour d'un moment critique (`state.bilan` de l'analyse), accepté seulement
// s'il correspond coup pour coup à la partie rechargée : un state abîmé relance un bilan normal.
export function restorableBilan(raw: unknown, pgn: string): { review: GameReview; gameKey: string | null } | null {
  const b = raw as { review?: GameReview; gameKey?: unknown } | null | undefined
  const review = b?.review
  if (!review || !Array.isArray(review.moves) || typeof review.startFen !== 'string') return null
  try {
    const c = new Chess()
    c.loadPgn(pgn)
    const sans = c.history()
    const start = c.header().FEN ? new Chess(c.header().FEN!).fen() : new Chess().fen()
    if (start !== review.startFen || sans.length !== review.moves.length) return null
    if (sans.some((san, i) => review.moves[i]?.san !== san)) return null
  } catch {
    return null
  }
  return { review, gameKey: typeof b.gameKey === 'string' ? b.gameKey : null }
}
