// « Qu'est-ce qu'il menace ? » : la menace créée par le dernier coup adverse, par la technique du
// coup nul. P est la position courante (le joueur au trait, juste après le coup adverse), P_prev
// celle d'avant ce coup (l'adversaire au trait), N la position P où l'adversaire rejoue aussitôt
// (trait inversé, prise en passant effacée). Menace = ce que l'adversaire gagnerait en N :
// - réelle : un mat en 1 ou 2, ou au moins deux points de matériel gagnés sur la ligne principale
//   de N (une menace déjà parée ne gagne rien, un pion attaqué ou un tempo ne suffisent pas). Une
//   menace impossible à parer entièrement (fourchette) reste une question : il faut la voir pour
//   limiter la casse. Seul un mat imparable (mat annoncé dans P) n'en est plus une ;
// - créée par le dernier coup : jouée par la pièce qui vient de bouger ou ouverte par son départ
//   (découverte), sur une cible qui n'était pas déjà en prise ; à défaut, absente de P_prev (deux
//   pions d'éval de plus qu'avant le coup).
// Le jugement (`judgeThreat`) est pur, sans moteur : `e2e/test_menace.py` le revérifie contre un
// oracle python-chess sur les mêmes scores. `findThreat` y ajoute les recherches Stockfish.
// Règle d'or de motifs.ts : seule une menace vérifiée sur l'échiquier est annoncée.
import { Chess, type Color, type Move, type PieceSymbol, type Square } from 'chess.js'
import type { Engine, EngineLine } from './engine'
import { figurine } from './review'
import { PIECE_FR, PIECE_VALUE, attacksFrom, fork, isDefended, isInBadSpot, other, pinOrSkewer, see, uciMove } from './motifs'

// Profondeur du coach live : les scores comparés viennent de la même profondeur.
export const THREAT_DEPTH = 10
// Gain d'éval minimal face à P_prev d'une menace qui n'est pas liée au coup sur l'échiquier.
export const THREAT_MIN_CP = 200
// Matériel minimal gagné sur la ligne de N, en points (pion = 1), hors mat.
export const THREAT_MIN_MATERIAL = 2
// Scores bornés : au-delà, un écart de plus n'a pas de sens. Assez haut pour qu'une dame perdue
// compte encore quand le joueur écrase un bot faible.
export const CP_CAP = 3000
// Mats annoncés : en 1 ou en 2. Plus long, rien n'est annoncé (invérifiable sur l'échiquier seul).
export const MATE_MAX = 2
// Coups de la ligne de N examinés.
const LINE_PLIES = 5

// Score d'une recherche, du point de vue du camp au trait de la position cherchée.
export interface Score {
  cp: number | null
  mate: number | null // > 0 : le camp au trait mate ; 0 : il est mat sur l'échiquier
}

export function scoreOf(line: EngineLine | undefined): Score {
  if (!line) return { cp: 0, mate: null }
  return { cp: line.scoreCp, mate: line.scoreMate }
}

// Valeur ordonnée d'un score, pour le camp au trait : un mat rapide vaut plus qu'un mat lent.
export function scoreValue(s: Score): number {
  if (s.mate !== null) {
    if (s.mate > 0) return 10000 - 10 * s.mate
    return -10000 - 10 * s.mate // mat contre le camp au trait (0 : déjà mat)
  }
  return Math.max(-CP_CAP, Math.min(CP_CAP, s.cp ?? 0))
}

// Position du coup nul : même placement, l'autre camp au trait, sans prise en passant. Null si le
// camp au trait est en échec (le coup nul serait illégal) ou si la partie est finie.
export function nullMoveFen(fen: string): string | null {
  const c = new Chess(fen)
  if (c.isGameOver() || c.inCheck()) return null
  const parts = fen.split(' ')
  parts[1] = parts[1] === 'w' ? 'b' : 'w'
  parts[3] = '-'
  return parts.join(' ')
}

export type ThreatVeto = 'illegal' | 'over' | 'check' | 'recapture'

export interface ThreatSetup {
  fen: string // P
  nullFen: string // N
  last: Move // coup adverse
}

// Filtres sans moteur, avant toute recherche : coup adverse illisible, partie finie, joueur en
// échec (son coup est forcé, la menace est l'échec lui-même), échange en cours (le coup adverse
// est une prise que le joueur peut reprendre sur la même case sans perdre de matériel : le réflexe
// est de reprendre, et le coup nul y verrait à tort une pièce gagnée).
export function quickVeto(fenPrev: string, lastUci: string): ThreatVeto | ThreatSetup {
  let c: Chess
  try {
    c = new Chess(fenPrev)
  } catch {
    return 'illegal'
  }
  const last = uciMove(c, lastUci)
  if (!last) return 'illegal'
  if (c.isGameOver()) return 'over'
  if (c.inCheck()) return 'check'
  if (last.captured) {
    const fen = c.fen()
    const goodRecapture = c.moves({ verbose: true }).some((m) => {
      if (m.to !== last.to || !m.captured) return false
      const d = new Chess(fen)
      d.move(m.san)
      return PIECE_VALUE[m.captured] - see(d.fen(), last.to) >= 0
    })
    if (goodRecapture) return 'recapture'
  }
  const nullFen = nullMoveFen(c.fen())
  if (!nullFen) return 'over'
  return { fen: c.fen(), nullFen, last }
}

export type ThreatKind = 'mat' | 'fourchette' | 'clouage' | 'enfilade' | 'decouverte' | 'prise' | 'promotion' | 'gain'

export const THREAT_KINDS: ThreatKind[] = ['mat', 'fourchette', 'clouage', 'enfilade', 'decouverte', 'prise', 'promotion', 'gain']

// Détail des statistiques (« Mats 2/3 »).
export const THREAT_KIND_LABEL: Record<ThreatKind, string> = {
  mat: 'Mats',
  fourchette: 'Fourchettes',
  clouage: 'Clouages',
  enfilade: 'Enfilades',
  decouverte: 'Découvertes',
  prise: 'Pièces en prise',
  promotion: 'Promotions',
  gain: 'Gains de matériel',
}

export interface Threat {
  kind: ThreatKind
  uci: string // coup menaçant, joué en N
  san: string
  from: Square
  to: Square
  // Cases qui comptent comme bonne réponse : la case d'arrivée du coup menaçant, et selon le type
  // les pièces visées (telles qu'elles sont placées dans P), le roi et la case du mat.
  squares: Square[]
  mateIn: number | null
  gainCp: number // v(N) - v(P), du point de vue de l'adversaire (ce que la parade sauve)
  text: string
  fen: string // P
}

export interface ThreatInput {
  fenPrev: string
  lastUci: string
  prev: Score | null // P_prev, adversaire au trait ; null quand non cherché (menace liée au coup)
  now: Score // P, joueur au trait
  nul: Score // N, adversaire au trait
  pv: string[] // ligne principale de N
}

const SON: Record<PieceSymbol, string> = { p: 'son pion', n: 'son cavalier', b: 'son fou', r: 'sa tour', q: 'sa dame', k: 'son roi' }

// Case de la pièce prise par un coup (différente de l'arrivée pour une prise en passant).
function capturedSquare(m: Move): Square {
  return (m.flags.includes('e') ? m.to[0] + m.from[1] : m.to) as Square
}

function kingOf(c: Chess, color: Color): Square | null {
  return c.board().flat().find((p) => p && p.type === 'k' && p.color === color)?.square ?? null
}

// Coups de la ligne principale jouables depuis N (la ligne s'arrête au premier coup illisible).
export function playLine(nullFen: string, pv: string[], max = LINE_PLIES): Move[] {
  const c = new Chess(nullFen)
  const out: Move[] = []
  for (const uci of pv.slice(0, max)) {
    const m = uciMove(c, uci)
    if (!m) break
    out.push(m)
  }
  return out
}

// Matériel gagné par l'adversaire sur la ligne de N (pion = 1, promotion comprise) : le meilleur
// bilan après une réponse du joueur (2e ou 4e coup), ou après le dernier coup de la ligne quand
// c'est le sien, après déduction de la reprise légale que la coupure masquerait.
export function materialGain(line: Move[]): number {
  let bal = 0
  let best = -Infinity
  line.forEach((m, i) => {
    const sign = i % 2 === 0 ? 1 : -1
    if (m.captured) bal += sign * PIECE_VALUE[m.captured]
    if (m.promotion) bal += sign * (PIECE_VALUE[m.promotion] - 1)
    if (i % 2 === 1 || i === line.length - 1) {
      // Une prise au dernier demi-coup ne vaut pas son gain brut si le joueur peut reprendre.
      const recapture = i % 2 === 0 && (m.captured || m.promotion) ? see(m.after, m.to) : 0
      best = Math.max(best, bal - recapture)
    }
  })
  return line.length ? best : 0
}

// Case dans P de la pièce prise au coup `i` de la ligne : si le joueur l'a déplacée entre-temps
// (coups impairs), on remonte jusqu'à sa case de départ.
function squareInP(line: Move[], i: number): Square {
  let sq = capturedSquare(line[i])
  for (let j = i - 1; j >= 1; j -= 2) if (line[j].to === sq) sq = line[j].from
  return sq
}

// Cases d'arrivée des pièces que le coup adverse a déplacées (la tour aussi pour un roque).
function movedTo(last: Move): Square[] {
  const rank = last.to[1]
  if (last.flags.includes('k')) return [last.to, `f${rank}` as Square]
  if (last.flags.includes('q')) return [last.to, `d${rank}` as Square]
  return [last.to]
}

// Prise découverte : la pièce qui prend n'a pas bougé et ne visait pas la case avant le coup
// adverse. Seul ce coup a changé l'échiquier : son départ a ouvert la ligne.
function discovered(t: Move, last: Move, fenPrev: string): boolean {
  if (!t.captured || movedTo(last).includes(t.from)) return false
  const before = new Chess(fenPrev)
  return before.get(t.from)?.type === t.piece && !attacksFrom(before, t.from).includes(capturedSquare(t))
}

// Menace liée au coup adverse sans moteur : jouée par la pièce qui vient de bouger, prise
// découverte, ou mat donné par la pièce qui vient de bouger. Une prise d'une pièce qui était déjà
// en prise avant le coup (dame qui glisse en gardant la même cible) n'est pas liée : elle passe par
// la comparaison avec P_prev.
export function linkedToLast(line: Move[], last: Move, fenPrev: string, mateIn: number | null): boolean {
  const t = line[0]
  if (!t) return false
  const moved = movedTo(last)
  if (mateIn !== null) {
    const mating = line[2 * mateIn - 2]
    return moved.includes(t.from) || (!!mating && moved.includes(mating.from))
  }
  if (t.captured) {
    const before = new Chess(fenPrev)
    const target = capturedSquare(t)
    if (before.get(target)?.color === other(t.color) && isInBadSpot(before, target)) return false
  }
  return moved.includes(t.from) || discovered(t, last, fenPrev)
}

// Mat annoncé par le score de N, en 1 ou 2.
export function mateInOf(nul: Score): number | null {
  return nul.mate !== null && nul.mate > 0 && nul.mate <= MATE_MAX ? nul.mate : null
}

const tonList = (types: PieceSymbol[]) => types.map((p) => `de ${PIECE_FR[p].ton}`).join(' et ')

export function judgeThreat(input: ThreatInput): Threat | null {
  const setup = quickVeto(input.fenPrev, input.lastUci)
  if (typeof setup === 'string') return null
  const { fen, nullFen, last } = setup
  // Un mat dans P, pour l'un ou l'autre : le joueur a mieux à faire, ou la menace est imparable.
  if (input.now.mate !== null) return null
  // Mat en 3 ou plus : invérifiable sans moteur, rien n'est annoncé.
  if (input.nul.mate !== null && input.nul.mate > MATE_MAX) return null
  const vNull = scoreValue(input.nul)
  const gainCp = vNull + scoreValue(input.now)

  const line = playLine(nullFen, input.pv)
  const t = line[0]
  if (!t) return null
  const mateIn = mateInOf(input.nul)
  if (!linkedToLast(line, last, input.fenPrev, mateIn) && (input.prev === null || vNull - scoreValue(input.prev) < THREAT_MIN_CP)) return null

  const opp = t.color
  const player = other(opp)
  const pos = new Chess(fen)
  const prevPos = new Chess(input.fenPrev)
  const squares = new Set<Square>([t.to])
  const fig = (san: string) => figurine(san, opp)
  const base = { uci: t.lan, san: t.san, from: t.from, to: t.to, gainCp, fen }
  const done = (kind: ThreatKind, text: string): Threat => ({ kind, ...base, squares: [...squares], mateIn: kind === 'mat' ? mateIn : null, text })

  if (mateIn !== null) {
    // Le mat est rejoué sur l'échiquier : une ligne tronquée ne fait pas annoncer un mat.
    const mating = line[2 * mateIn - 2]
    const check = new Chess(nullFen)
    for (const m of line.slice(0, 2 * mateIn - 1)) check.move(m.san)
    if (!mating || !check.isCheckmate()) return null
    const king = kingOf(pos, player)
    if (king) squares.add(king)
    squares.add(mating.to)
    return done('mat', mateIn === 1 ? `Il menace ${fig(t.san)}, mat.` : `Il menace un mat en deux coups, à commencer par ${fig(t.san)}.`)
  }

  // Menace matérielle : au moins deux points gagnés sur la ligne de N.
  if (materialGain(line) < THREAT_MIN_MATERIAL) return null
  const playerPieceInP = (sq: Square) => pos.get(sq)?.color === player
  // Pièce la plus chère prise par l'adversaire dans ses trois premiers coups de la ligne.
  const caps = [0, 2, 4].filter((i) => line[i]?.captured).map((i) => ({ m: line[i], sq: squareInP(line, i) })).filter((c) => playerPieceInP(c.sq))
  const best = caps.sort((a, b) => PIECE_VALUE[b.m.captured!] - PIECE_VALUE[a.m.captured!])[0]
  if (best) squares.add(best.sq)
  // Pièces du joueur (cavalier et plus, roi exclu) que ce coup a mises en prise : une autre cible
  // que celle choisie par le moteur est aussi une bonne réponse.
  for (const p of pos.board().flat()) {
    if (!p || p.color !== player || p.type === 'p' || p.type === 'k') continue
    if (isInBadSpot(pos, p.square) && !isInBadSpot(prevPos, p.square)) squares.add(p.square)
  }
  const hits = (sqs: Square[]) => sqs.some((s) => s === t.to || s === best?.sq)

  // Fourchette, clouage ou enfilade : créés par le coup adverse lui-même (la menace en récolte le
  // fruit), ou par le coup menaçant.
  const lastFork = fork(input.fenPrev, last.lan)
  if (lastFork && hits(lastFork.squares)) {
    for (const s of lastFork.squares) squares.add(s)
    const tons = lastFork.targets.map((p) => PIECE_FR[p].ton).join(' et ')
    return done('fourchette', `Son coup ${fig(last.san)} fourchette ${tons} : il menace ${fig(t.san)}.`)
  }
  const fk = fork(nullFen, t.lan)
  if (fk) {
    for (const s of fk.squares) squares.add(s)
    return done('fourchette', `Il menace ${fig(t.san)} : fourchette ${tonList(fk.targets)}.`)
  }
  const lastLine = pinOrSkewer(input.fenPrev, last.lan)
  if (lastLine && hits([lastLine.frontSquare, lastLine.rearSquare])) {
    squares.add(lastLine.frontSquare)
    squares.add(lastLine.rearSquare)
    return done(lastLine.kind, lastLine.kind === 'clouage'
      ? `Son coup ${fig(last.san)} cloue ${PIECE_FR[lastLine.front].ton} devant ${PIECE_FR[lastLine.rear].ton} : il menace ${fig(t.san)}.`
      : `Son coup ${fig(last.san)} est une enfilade sur ${PIECE_FR[lastLine.front].ton} et ${PIECE_FR[lastLine.rear].ton} : il menace ${fig(t.san)}.`)
  }
  const ps = pinOrSkewer(nullFen, t.lan)
  if (ps) {
    squares.add(ps.frontSquare)
    squares.add(ps.rearSquare)
    return done(ps.kind, ps.kind === 'clouage'
      ? `Il menace ${fig(t.san)}, qui clouerait ${PIECE_FR[ps.front].ton} devant ${PIECE_FR[ps.rear].ton}.`
      : `Il menace ${fig(t.san)} : enfilade ${tonList([ps.front, ps.rear])}.`)
  }
  if (t.captured) {
    const target = PIECE_FR[t.captured]
    const sq = capturedSquare(t)
    if (discovered(t, last, input.fenPrev)) {
      return done('decouverte', `Son coup a ouvert une ligne : ${SON[t.piece]} menace ${target.ton} en ${sq} (${fig(t.san)}).`)
    }
    const note = isDefended(pos, sq) ? '' : target.genre === 'f' ? " Elle n'est pas défendue." : " Il n'est pas défendu."
    return done('prise', `Il menace de prendre ${target.ton} en ${sq} (${fig(t.san)}).${note}`)
  }
  const promo = [0, 2, 4].map((i) => line[i]).find((m) => m?.promotion)
  if (promo && !best) {
    squares.add(promo.to)
    // Le pion qui va à dame, tel qu'il est placé dans P.
    const pawn = line[0].piece === 'p' ? line[0].from : promo.from
    squares.add(pawn)
    return done('promotion', `Il menace d'aller à dame : ${fig(promo.san)}${promo === t ? '' : `, après ${fig(t.san)}`}.`)
  }
  if (!best) return null
  return done('gain', `Il menace ${fig(t.san)}, qui gagnerait ${PIECE_FR[best.m.captured!].ton}.`)
}

// Score et ligne principale d'une position (MultiPV 1, profondeur fixe).
export async function searchScore(engine: Engine, fen: string, depth = THREAT_DEPTH): Promise<{ score: Score; pv: string[] }> {
  const res = await engine.search({ fen, depth, multipv: 1 })
  const line = res.lines[0]
  return { score: scoreOf(line), pv: line?.pv ?? (res.bestMove && res.bestMove !== '(none)' ? [res.bestMove] : []) }
}

// Menace créée par le coup adverse `lastUci` joué depuis `fenPrev`, ou null. `known` reprend les
// scores déjà calculés (évals live du mode entraîneur) ; le reste est cherché ici, du moins cher au
// plus cher, et la recherche s'arrête dès qu'un critère tombe. `alive` est relu après chaque
// recherche : faux, plus rien n'est lancé (partie finie, coup joué, reprise).
export async function findThreat(
  engine: Engine,
  fenPrev: string,
  lastUci: string,
  known: { prev?: Score | null; now?: Score | null } = {},
  alive: () => boolean = () => true,
  depth = THREAT_DEPTH,
): Promise<Threat | null> {
  const setup = quickVeto(fenPrev, lastUci)
  if (typeof setup === 'string') return null
  const now = known.now ?? (await searchScore(engine, setup.fen, depth)).score
  if (!alive() || now.mate !== null) return null
  const nul = await searchScore(engine, setup.nullFen, depth)
  if (!alive()) return null
  // P_prev n'est cherchée que si la menace n'est pas liée au coup adverse sur l'échiquier.
  const linked = linkedToLast(playLine(setup.nullFen, nul.pv), setup.last, fenPrev, mateInOf(nul.score))
  const prev = known.prev ?? (linked ? null : (await searchScore(engine, fenPrev, depth)).score)
  if (!alive()) return null
  return judgeThreat({ fenPrev, lastUci, prev, now, nul: nul.score, pv: nul.pv })
}

// ---------------------------------------------------------------- réglage et statistiques

// Préférence hors persist Zustand et hors sauvegarde (simple confort, comme le niveau de
// l'entraîneur d'attaque). Entraîneur : activé par défaut ; bot : à activer.
export const THREAT_PREFS_KEY = 'chess-local-threat-check'
export interface ThreatPrefs {
  bot: boolean
  coach: boolean
}
export const DEFAULT_THREAT_PREFS: ThreatPrefs = { bot: false, coach: true }

export function loadThreatPrefs(): ThreatPrefs {
  try {
    const raw = JSON.parse(localStorage.getItem(THREAT_PREFS_KEY) ?? 'null') as Partial<ThreatPrefs> | null
    return {
      bot: typeof raw?.bot === 'boolean' ? raw.bot : DEFAULT_THREAT_PREFS.bot,
      coach: typeof raw?.coach === 'boolean' ? raw.coach : DEFAULT_THREAT_PREFS.coach,
    }
  } catch {
    return { ...DEFAULT_THREAT_PREFS }
  }
}

export function saveThreatPrefs(prefs: ThreatPrefs) {
  try {
    localStorage.setItem(THREAT_PREFS_KEY, JSON.stringify(prefs))
  } catch {
    // stockage indisponible : le choix vaut pour la visite
  }
}

export const THREAT_DOMAIN = 'threat-check'
export const threatItemId = (t: Pick<Threat, 'kind' | 'uci'>) => `${t.kind}:${t.uci}`

export interface ThreatStats {
  total: number
  seen: number
  byKind: { kind: ThreatKind; total: number; seen: number }[]
}

export function threatStatsOf(rows: { itemId: string; success: 0 | 1 }[]): ThreatStats {
  const by = new Map<ThreatKind, { total: number; seen: number }>()
  let seen = 0
  for (const r of rows) {
    const kind = r.itemId.split(':')[0] as ThreatKind
    if (!THREAT_KINDS.includes(kind)) continue
    const k = by.get(kind) ?? { total: 0, seen: 0 }
    k.total++
    k.seen += r.success
    seen += r.success
    by.set(kind, k)
  }
  const byKind = THREAT_KINDS.filter((k) => by.has(k)).map((kind) => ({ kind, ...by.get(kind)! }))
  return { total: byKind.reduce((s, k) => s + k.total, 0), seen, byKind }
}
