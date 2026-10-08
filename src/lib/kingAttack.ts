// Attaque sur le roi, avec chess.js seul (aucun moteur) : zone du roi, compte des attaquants et
// des défenseurs (calque « Compte les attaquants »), et repérage d'une attaque manquée dans une
// faute du bilan (table `mistakes` : position avant le coup + meilleur coup du moteur).
// Règle d'or de motifs.ts : chaque fonction ne renvoie que ce qu'elle a vérifié sur l'échiquier.
import { Chess, type Color, type Square } from 'chess.js'
import { db, type Mistake } from './db'
import { figurine } from './review'
import { PIECE_VALUE, fork, isPassed, other, see, uciMove } from './motifs'
import { validFen } from './positionGame'

const fileOf = (s: string) => s.charCodeAt(0) - 97
const rankOf = (s: string) => Number(s[1]) - 1
const sqAt = (f: number, r: number) => (String.fromCharCode(97 + f) + (r + 1)) as Square
const clamp = (v: number) => Math.min(6, Math.max(1, v))

// ------------------------------------------------------------------ zone et compte

// Anneau du roi, définition de Stockfish : 3x3 centré sur le roi ramené dans les colonnes b-g et
// les rangées 2-7. Toujours 9 cases : un roi roqué sur sa première rangée a aussi la rangée devant
// son bouclier dans sa zone (f1-h3 pour un roi en g1 ou h1).
function kingZone(king: Square): Square[] {
  const f0 = clamp(fileOf(king))
  const r0 = clamp(rankOf(king))
  const out: Square[] = []
  for (let f = f0 - 1; f <= f0 + 1; f++) for (let r = r0 - 1; r <= r0 + 1; r++) out.push(sqAt(f, r))
  return out
}

export function kingSquare(c: Chess, color: Color): Square {
  const k = c.board().flat().find((p) => p && p.type === 'k' && p.color === color)
  if (!k) throw new Error(`roi ${color} absent`)
  return k.square
}

export interface ZoneCounts {
  king: Square
  zone: Square[]
  attackers: Square[] // pièces adverses (cavalier, fou, tour, dame) qui visent une case de la zone
  defenders: Square[] // pièces du camp du roi (cavalier, fou, tour, dame) qui visent une case de la zone
}

// Pièces seulement : les pions du bouclier et de la tempête sont hors compte (la tempête a son type
// d'attaque manquée), les rois aussi. Attaques brutes de `chess.attackers` (clouages ignorés, pas
// de rayon X) ; une pièce compte une fois, même si elle vise plusieurs cases.
export function zoneCounts(c: Chess, kingColor: Color): ZoneCounts {
  const king = kingSquare(c, kingColor)
  const zone = kingZone(king)
  const opp = other(kingColor)
  const attackers = new Set<Square>()
  const defenders = new Set<Square>()
  const isPiece = (sq: Square) => {
    const t = c.get(sq)?.type
    return t !== undefined && t !== 'k' && t !== 'p'
  }
  for (const sq of zone) {
    for (const from of c.attackers(sq, opp)) if (isPiece(from)) attackers.add(from)
    for (const from of c.attackers(sq, kingColor)) if (isPiece(from)) defenders.add(from)
  }
  return { king, zone, attackers: [...attackers], defenders: [...defenders] }
}

// Les deux rois d'une position : `w` décrit la zone du roi blanc (attaquée par les Noirs).
export function attackCounts(fen: string): Record<Color, ZoneCounts> {
  const c = new Chess(fen)
  return { w: zoneCounts(c, 'w'), b: zoneCounts(c, 'b') }
}

// Principe du calque, affiché tel quel sous l'échiquier : un repère, pas une règle absolue.
export const ATTACK_PRINCIPLE = 'Attaque quand tes attaquants dépassent les défenseurs.'

// ------------------------------------------------------------------ attaque manquée

export type AttackKind = 'mat' | 'sacrifice' | 'poussee' | 'piece'

export const ATTACK_KINDS: AttackKind[] = ['mat', 'sacrifice', 'poussee', 'piece']

// `one` : « 1 attaque manquée : un mat manqué » ; `plural` : « surtout des mats manqués ».
export const ATTACK_KIND_META: Record<AttackKind, { label: string; one: string; plural: string; emoji: string; lesson: string }> = {
  mat: {
    label: 'Mat manqué', one: 'un mat manqué', plural: 'des mats manqués', emoji: '♚',
    lesson: "Avant de jouer, cherche le mat : un échec que l'adversaire ne peut pas parer vaut toute la partie.",
  },
  sacrifice: {
    label: 'Sacrifice près du roi', one: 'un sacrifice près du roi', plural: 'des sacrifices près du roi', emoji: '💥',
    lesson: "Un sacrifice près du roi ouvre son abri : il paie quand tes pièces arrivent plus vite que les défenseurs. Compte-les avant d'offrir la pièce.",
  },
  poussee: {
    label: 'Pion contre le roque', one: 'un pion à lancer contre le roque', plural: 'des pions lancés contre le roque', emoji: '🪖',
    lesson: "Un pion lancé sur le roque adverse ouvre une colonne ou chasse un défenseur : la partie se joue devant son roi, pas devant le tien.",
  },
  piece: {
    label: 'Pièce vers le roi', one: 'une pièce à amener vers le roi', plural: 'des pièces à amener vers le roi', emoji: '🎯',
    lesson: "Une pièce de plus qui vise la zone du roi adverse fait pencher le compte : amène tes pièces avant de frapper.",
  },
}

export interface MissedAttack {
  kind: AttackKind
  bestSan: string // meilleur coup du bilan, en SAN
  to: Square
  king: Square // roi adverse visé
  attackers: number // comptes après le meilleur coup
  defenders: number
}

// Roi « roqué » : sur une aile (colonnes a-c ou g-h) et sur ses deux premières rangées.
function castledKing(king: Square, color: Color): boolean {
  const f = fileOf(king)
  const r = rankOf(king)
  const home = color === 'w' ? r <= 1 : r >= 6
  return home && (f <= 2 || f >= 6)
}

// Rangée du point de vue du camp qui joue : 1 = sa première rangée.
function relRank(sq: Square, color: Color): number {
  return color === 'w' ? rankOf(sq) + 1 : 8 - rankOf(sq)
}

// La pièce posée sur `from` vise-t-elle une case de la zone ? (attaques brutes)
function attacksZone(c: Chess, from: Square, zone: Square[], color: Color): boolean {
  return zone.some((sq) => c.attackers(sq, color).includes(from))
}

// Assez de pièces pour attaquer : au moins trois pièces hors pions et roi. Écarte les finales, où
// une poussée ou une pièce active n'ont rien d'une attaque sur le roi.
function hasAttackingForce(c: Chess, color: Color): boolean {
  return c.board().flat().filter((p) => p && p.color === color && p.type !== 'p' && p.type !== 'k').length >= 3
}

// Le meilleur coup du bilan était-il une attaque sur le roi adverse ? Un seul type, dans l'ordre :
// mat sur l'échiquier ; pion (prise comprise, pas passé) lancé sur le roque adverse ; sacrifice
// d'une pièce près du roi (reprises comptées) ; pièce qui devient une nouvelle attaquante de la
// zone, quand les attaquants sont au moins deux et au moins aussi nombreux que les défenseurs.
// Hors mat, il faut au moins trois pièces pour parler d'attaque, et un coup qui fourchette ou
// gagne du matériel (pion compris) est une tactique, pas une attaque sur le roi : déjà dans « Mes erreurs ».
// Les mats plus longs qu'un coup ne sont pas vérifiables sans moteur : ils ne sont pas revendiqués.
export function missedAttack(fenBefore: string, bestUci: string): MissedAttack | null {
  let before: Chess
  try {
    before = new Chess(fenBefore)
  } catch {
    return null
  }
  const mover = before.turn()
  const opp = other(mover)
  const c = new Chess(fenBefore)
  const mv = uciMove(c, bestUci)
  if (!mv) return null
  const { king, zone, attackers, defenders } = zoneCounts(c, opp)
  const base = { bestSan: mv.san, to: mv.to, king, attackers: attackers.length, defenders: defenders.length }
  if (c.isCheckmate()) return { kind: 'mat', ...base }
  if (mv.piece === 'k' || !hasAttackingForce(before, mover) || fork(fenBefore, bestUci)) return null
  // Bilan matériel du coup une fois les reprises terminées : l'adversaire a le trait sur `c`.
  const net = (mv.captured ? PIECE_VALUE[mv.captured] : 0) - see(c.fen(), mv.to)
  if (net >= 2) return null
  if (mv.piece === 'p') {
    if (mv.promotion || !castledKing(king, opp) || isPassed(c, mv.to, mover)) return null
    if (Math.abs(fileOf(mv.to) - fileOf(king)) > 1 || relRank(mv.to, mover) < 5) return null
    return { kind: 'poussee', ...base }
  }
  const near = zone.includes(mv.to) || attacksZone(c, mv.to, zone, mover)
  if (!near) return null
  if (net <= -2) return { kind: 'sacrifice', ...base }
  if (attacksZone(before, mv.from, zone, mover)) return null // elle visait déjà la zone
  if (attackers.length < 2 || attackers.length < defenders.length) return null
  return { kind: 'piece', ...base }
}

export interface MissedAttackItem extends MissedAttack {
  mistake: Mistake
  playedFig: string // coup joué, en figurine du camp qui l'a joué
}

export interface AttackDiagnostic {
  games: number // parties distinctes (`gameKey`) parmi les fautes du joueur
  faults: number // fautes du joueur (camp connu et au trait)
  items: MissedAttackItem[] // du plus récent au plus ancien
  byKind: Record<AttackKind, number>
  topKind: AttackKind | null // type le plus fréquent ; null sans attaque ou en cas d'égalité
}

// Seules les fautes dont le bilan connaissait le camp du joueur sont les siennes : les parties
// locales, les PGN collés et les exercices analysés enregistrent les deux camps, sans `color`.
// Une ligne incomplète (sauvegarde ancienne ou retouchée) est ignorée, jamais fatale à la liste.
function playerMistakes(rows: Mistake[]): Mistake[] {
  return rows.filter((r) => {
    if (!r.color || typeof r.playedSan !== 'string' || typeof r.bestUci !== 'string') return false
    return validFen(r.fenBefore) && new Chess(r.fenBefore).turn() === r.color
  })
}

export function diagnoseMissedAttacks(rows: Mistake[]): AttackDiagnostic {
  const mine = playerMistakes(rows).sort((a, b) => b.date - a.date)
  const games = new Set(mine.map((r) => r.gameKey)).size
  const items: MissedAttackItem[] = []
  for (const mistake of mine) {
    try {
      const found = missedAttack(mistake.fenBefore, mistake.bestUci)
      if (found) items.push({ ...found, mistake, playedFig: figurine(mistake.playedSan, mistake.color!) })
    } catch {
      // Coup illisible dans cette position : ligne ignorée.
    }
  }
  const byKind = { mat: 0, sacrifice: 0, poussee: 0, piece: 0 }
  for (const it of items) byKind[it.kind]++
  const max = Math.max(...ATTACK_KINDS.map((k) => byKind[k]))
  const tops = ATTACK_KINDS.filter((k) => byKind[k] === max && max > 0)
  return { games, faults: mine.length, items, byKind, topKind: tops.length === 1 ? tops[0] : null }
}

export async function loadAttackDiagnostic(): Promise<AttackDiagnostic> {
  return diagnoseMissedAttacks(await db.mistakes.toArray())
}

const plural = (n: number, word: string) => `${n} ${word}${n > 1 ? 's' : ''}`

// « Dans tes fautes relevées sur 2 parties, 5 attaques manquées, surtout des sacrifices près du roi. »
// Chaque mot est exact : les parties comptées sont celles où un bilan a relevé une faute du joueur,
// « surtout » n'apparaît que si un type domine seul, une attaque unique est nommée.
export function attackSummary(d: AttackDiagnostic): string {
  if (d.faults === 0) return "Aucune faute à ton nom pour l'instant : fais le bilan d'une partie contre un bot ou importée de chess.com."
  const scope = `Dans tes fautes relevées sur ${plural(d.games, 'partie')}`
  const n = d.items.length
  if (n === 0) return `${scope}, aucune attaque manquée.`
  if (n === 1) return `${scope}, 1 attaque manquée : ${ATTACK_KIND_META[d.items[0].kind].one}.`
  const attacks = `${n} attaques manquées`
  return d.topKind ? `${scope}, ${attacks}, surtout ${ATTACK_KIND_META[d.topKind].plural}.` : `${scope}, ${attacks}.`
}

// « 3 attaquants contre 2 défenseurs »
export function countsText(attackers: number, defenders: number): string {
  return `${plural(attackers, 'attaquant')} contre ${plural(defenders, 'défenseur')}`
}

// Empreinte courte et stable d'une partie sans identifiant (FNV-1a sur la position de départ et
// les coups) : deux bilans de la même partie partagent la même clé.
export function pgnKey(startFen: string, sans: string[]): string {
  let h = 0x811c9dc5
  for (const ch of `${startFen}|${sans.join(' ')}`) {
    h ^= ch.charCodeAt(0)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return `pgn:${h.toString(16).padStart(8, '0')}`
}

// ------------------------------------------------------------------ progression

// Une ligne `learnSessions` par tentative : domaine à part, hors de la rotation d'Apprendre
// (`pickNextDomain` filtre sur les clés de `DOMAIN_META`). `success` = coup du bilan retrouvé.
const MISSED_ATTACK_DOMAIN = 'missed-attack'

export async function recordMissedAttack(id: number, fen: string, success: boolean): Promise<void> {
  await db.learnSessions.add({ date: Date.now(), domain: MISSED_ATTACK_DOMAIN, itemId: String(id), fen, success: success ? 1 : 0, ratingAfter: null })
}

// Clés `id|fen` des attaques dont le coup a déjà été retrouvé sans aide.
export async function solvedMissedAttacks(): Promise<Set<string>> {
  const rows = await db.learnSessions.where('domain').equals(MISSED_ATTACK_DOMAIN).toArray()
  return new Set(rows.filter((r) => r.success === 1).map((r) => `${r.itemId}|${r.fen ?? ''}`))
}
