// Valide les données d'Apprendre (src/data/endgames.json, courses.json, strategy.json) avec chess.js :
// positions légales, objectifs cohérents, flèches et coups cités jouables, textes en français.
// Lancé par e2e/test_endgames.py (donc par le gate) : `node scripts/check-learn-data.mjs`.
// N'imprime que les manquements ([KO]) et un bilan ; code de sortie 1 au moindre [KO].
import { readFileSync } from 'node:fs'
import { Chess } from 'chess.js'

const endgames = JSON.parse(readFileSync('src/data/endgames.json', 'utf8'))
const courses = JSON.parse(readFileSync('src/data/courses.json', 'utf8'))
const strategy = JSON.parse(readFileSync('src/data/strategy.json', 'utf8'))

let checks = 0
let failures = 0
function check(ok, label) {
  checks++
  if (!ok) {
    failures++
    console.log(`[KO] ${label}`)
  }
}

// ---------- Positions ----------
function load(fen) {
  try {
    return new Chess(fen)
  } catch {
    return null
  }
}

// Même position, trait à `color`, sans prise en passant : pour interroger l'autre camp.
function withTurn(fen, color) {
  const f = fen.split(' ')
  f[1] = color
  f[3] = '-'
  return f.join(' ')
}

// Le camp qui n'a pas le trait est-il en échec ? chess.js accepte ces FEN et propose alors la
// capture du roi (CONT-1) : on inverse le trait et on regarde si ce camp-là est en échec.
function oppositeCheck(fen) {
  const other = fen.split(' ')[1] === 'w' ? 'b' : 'w'
  const c = load(withTurn(fen, other))
  return c === null || c.isCheck()
}

// Notation française -> anglaise pour chess.js (R roi, D dame, T tour, F fou, C cavalier).
const FR_PIECE = { R: 'K', D: 'Q', T: 'R', F: 'B', C: 'N' }
function sanToEnglish(san) {
  return san.replace(/^[RDTFC]/, (p) => FR_PIECE[p]).replace(/=([DTFC])/, (_, p) => `=${FR_PIECE[p]}`)
}

// Le coup (SAN français) est-il légal dans la position pour l'un des deux camps ?
function sanPlayable(fen, sanFr) {
  const san = sanToEnglish(sanFr)
  for (const color of ['w', 'b']) {
    const c = load(withTurn(fen, color))
    if (!c) continue
    try {
      c.move(san)
      return true
    } catch {}
  }
  return false
}

const SQUARE = /^[a-h][1-8]$/
function coords(sq) {
  return [sq.charCodeAt(0) - 97, Number(sq[1]) - 1]
}

// La case `to` est-elle sur un rayon de la pièce en `from` (blocages ignorés) ? Pour les flèches
// de clouage ou de trajectoire, qui ne sont pas des coups.
function onRay(piece, from, to) {
  const [fx, fy] = coords(from)
  const [tx, ty] = coords(to)
  const dx = tx - fx
  const dy = ty - fy
  if (dx === 0 && dy === 0) return false
  const straight = dx === 0 || dy === 0
  const diagonal = Math.abs(dx) === Math.abs(dy)
  switch (piece.type) {
    case 'r': return straight
    case 'b': return diagonal
    case 'q': return straight || diagonal
    case 'n': return (Math.abs(dx) === 1 && Math.abs(dy) === 2) || (Math.abs(dx) === 2 && Math.abs(dy) === 1)
    case 'k': return Math.abs(dx) <= 1 && Math.abs(dy) <= 1
    case 'p': return dx === 0 && (piece.color === 'w' ? dy > 0 : dy < 0)
  }
  return false
}

// Une flèche part d'une case occupée et est soit un coup légal pour la couleur de la pièce, soit
// un rayon de cette pièce vers une case occupée (clouage), soit la colonne d'un pion dans son sens
// de marche (course à la promotion). Une flèche vers une case vide qui n'est pas un coup est refusée.
function arrowProblem(fen, arrow) {
  if (!Array.isArray(arrow) || arrow.length !== 2 || !SQUARE.test(arrow[0]) || !SQUARE.test(arrow[1])) return `flèche mal formée ${JSON.stringify(arrow)}`
  const [from, to] = arrow
  const c = load(fen)
  const piece = c.get(from)
  if (!piece) return `flèche ${from}→${to} : case de départ vide`
  const mover = load(withTurn(fen, piece.color))
  const legal = mover !== null && mover.moves({ square: from, verbose: true }).some((m) => m.to === to)
  if (legal) return null
  if (!onRay(piece, from, to)) return `flèche ${from}→${to} : ni un coup de ${piece.color}${piece.type}, ni sur son rayon`
  if (piece.type === 'p' || c.get(to)) return null
  return `flèche ${from}→${to} : n'est pas un coup légal et vise une case vide`
}

// ---------- Textes ----------
const SAN_FR = '[RDTFC]?[a-h]?[1-8]?x?[a-h][1-8](?:=[DTFC])?[+#]?'
// Coups cités que le script vérifie : celui qui ouvre le texte (précédé ou non de « 1. » ou « 1... »)
// et ceux qui portent une marque ! ou ?. Les autres coups de la prose (suites ultérieures) ne le sont pas.
const OPENING_SAN = new RegExp(`^(?:1\\.(?:\\.\\.)?\\s?)?(${SAN_FR})(?=[\\s!?,.:;)]|$)`)
const MARKED_SAN = new RegExp(`(?:^|[\\s(«])(${SAN_FR})\\s?[!?]{1,2}`, 'g')
function citedMoves(text) {
  const out = new Set()
  const opening = text.match(OPENING_SAN)
  if (opening) out.add(opening[1])
  for (const m of text.matchAll(MARKED_SAN)) out.add(m[1])
  return [...out]
}

const ENGLISH_SAN = /\b[KQNB][a-h][1-8]\b/
const BANNED = [
  [/boxe/i, '« boxe » (faux ami : la boîte)'],
  [/épingl/i, '« épinglé » (le terme est « cloué »)'],
  [/\bfourch(?!ette)/i, '« fourcher » (on dit « faire une fourchette »)'],
  [/\bluft\b/i, '« luft » (case de fuite)'],
  [/flashy/i, '« flashy »'],
  [/mat des arabes/i, '« mat des arabes » (mat arabe)'],
  [/nulle de salon/i, '« nulle de salon » (désigne une nulle arrangée)'],
  [/échecs croisés/i, '« échecs croisés » (contresens)'],
]
const SHOUTING = /\b[A-ZÀÂÉÈÊÎÔÙÛÇ]{2,}\b/

function checkText(text, label) {
  check(!text.includes('—'), `${label} : tiret cadratin`)
  check(!ENGLISH_SAN.test(text), `${label} : notation anglaise (${(text.match(ENGLISH_SAN) || [])[0]})`)
  for (const [re, why] of BANNED) check(!re.test(text), `${label} : ${why}`)
  check(!SHOUTING.test(text), `${label} : majuscules d'insistance (${(text.match(SHOUTING) || [])[0]})`)
}

function checkCitedMoves(text, fen, label) {
  for (const san of citedMoves(text)) check(sanPlayable(fen, san), `${label} : coup cité ${san} injouable dans ${fen}`)
}

// ---------- Exercices de finale ----------
// Exercices dont le diagramme de cours montre un motif plutôt que la position de départ.
const PATTERN_DIAGRAMS = new Set(['kq-mate', 'rr-mate', 'kr-mate', 'philidor'])
const GOALS = { mate: 'win', promote: 'win', capture: 'win', hold: 'draw' }
const ids = new Set()
for (const e of endgames) {
  const L = `endgames.json ${e.id}`
  check(!ids.has(e.id), `${L} : id en double`)
  ids.add(e.id)
  check(typeof e.title === 'string' && e.title.trim() && typeof e.lesson === 'string' && e.lesson.trim(), `${L} : titre ou leçon vide`)
  check(Number.isFinite(e.difficulty) && e.difficulty > 0, `${L} : difficulté invalide`)
  check(GOALS[e.goal] !== undefined, `${L} : goal manquant ou inconnu (${e.goal})`)
  check(GOALS[e.goal] === e.objective, `${L} : goal ${e.goal} incohérent avec objective ${e.objective}`)
  check(courses[e.id] !== undefined, `${L} : aucun cours pour cet id`)
  // LEARN-2 : le diagramme du cours montre la position de l'exercice, sauf ceux qui illustrent
  // le motif final (mats) ou le moment de la bascule (Philidor), assumés et listés dans PATTERN_DIAGRAMS.
  if (courses[e.id]?.diagram && !PATTERN_DIAGRAMS.has(e.id)) {
    check(courses[e.id].diagram.fen === e.fen, `${L} : le diagramme du cours (${courses[e.id].diagram.fen}) n'est pas la position de l'exercice`)
  }
  checkText(`${e.title} ${e.lesson}`, L)

  const c = load(e.fen)
  check(c !== null, `${L} : FEN refusée par chess.js`)
  if (!c) continue
  check(c.turn() === e.side, `${L} : trait ${c.turn()} mais side ${e.side}`)
  check(!oppositeCheck(e.fen), `${L} : le camp qui n'a pas le trait est en échec (position illégale)`)
  check(!c.isGameOver(), `${L} : partie déjà finie (mat, pat ou nulle)`)
  const mine = c.board().flat().filter((p) => p && p.color === e.side)
  const theirs = c.board().flat().filter((p) => p && p.color !== e.side)
  if (e.goal === 'promote') check(mine.some((p) => p.type === 'p'), `${L} : goal promote sans pion`)
  if (e.goal === 'mate') check(mine.some((p) => p.type !== 'p' && p.type !== 'k'), `${L} : goal mate sans pièce`)
  if (e.goal === 'capture') check(theirs.length > 1, `${L} : goal capture sans matériel adverse`)
  checkCitedMoves(e.lesson, e.fen, L)
}

// ---------- Cours ----------
for (const [id, course] of Object.entries(courses)) {
  const L = `courses.json ${id}`
  check(course.title?.trim() && course.intro?.trim(), `${L} : titre ou intro vide`)
  check(Array.isArray(course.sections) && course.sections.length > 0 && course.sections.every((s) => s.heading?.trim() && s.text?.trim()), `${L} : sections vides`)
  check(Array.isArray(course.keyPoints) && course.keyPoints.length > 0 && course.keyPoints.every((k) => k?.trim()), `${L} : points clés vides`)
  checkText([course.title, course.intro, ...(course.sections ?? []).flatMap((s) => [s.heading, s.text]), ...(course.keyPoints ?? [])].join('\n'), L)
  const d = course.diagram
  if (!d) continue
  check(typeof d.caption === 'string' && d.caption.trim(), `${L} : légende vide`)
  checkText(d.caption ?? '', `${L} légende`)
  const c = load(d.fen)
  check(c !== null, `${L} : FEN du diagramme refusée par chess.js`)
  if (!c) continue
  check(!oppositeCheck(d.fen), `${L} : diagramme illégal, le camp qui n'a pas le trait est en échec`)
  check(!c.isCheckmate(), `${L} : le diagramme est un mat`)
  check(!c.isStalemate(), `${L} : le diagramme est un pat`)
  for (const arrow of d.arrows ?? []) {
    const problem = arrowProblem(d.fen, arrow)
    check(problem === null, `${L} : ${problem}`)
  }
  checkCitedMoves(d.caption ?? '', d.fen, `${L} légende`)
}

// ---------- Cartes de stratégie ----------
for (const card of strategy) {
  const L = `strategy.json ${card.id}`
  check(card.title?.trim() && card.lesson?.trim(), `${L} : titre ou leçon vide`)
  check(Array.isArray(card.themes) && card.themes.length > 0, `${L} : aucun thème`)
  check((card.themes ?? []).some((t) => courses[t]) || courses[card.id] !== undefined, `${L} : aucun cours pour cette carte`)
  checkText(`${card.title} ${card.lesson}`, L)
}

console.log(`${checks} règles vérifiées, ${failures} manquement${failures > 1 ? 's' : ''}`)
process.exit(failures ? 1 : 0)
