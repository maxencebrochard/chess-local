// Contrôle hors ligne du cours de finales (src/data/endgameCourse.json) avec chess.js : structure,
// positions légales, lignes jouables, flèches, textes en français, et tampon de vérification.
// Le verdict des positions (gain, nulle, « seul coup ») est prouvé par scripts/verify-endgame-course.py
// contre les tables de finales ; ce contrôle exige que le JSON soit exactement celui qu'il a tamponné.
// Lancé par e2e/test_endgame_course.py (donc par le gate) : `node scripts/check-endgame-course.mjs`.
// Règles de texte reprises de scripts/check-learn-data.mjs (lot L4) : à fusionner en un module commun.
// N'imprime que les manquements ([KO]) et un bilan ; code de sortie 1 au moindre [KO].
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { Chess } from 'chess.js'

const RAW = readFileSync('src/data/endgameCourse.json', 'utf8')
const course = JSON.parse(RAW)
const endgames = JSON.parse(readFileSync('src/data/endgames.json', 'utf8'))

// Ids publiés : la progression des élèves est stockée par id (learnSessions `finales:<id>`).
// Un id ne se renomme ni ne se supprime jamais ; on peut seulement en ajouter.
const FROZEN_IDS = [
  'mat-deux-tours', 'mat-dame', 'mat-tour',
  'carre-du-pion', 'opposition', 'cases-cles', 'pion-de-tour', 'manoeuvre-de-reti',
  'lucena', 'philidor', 'tour-derriere-le-pion',
  'dame-contre-pion',
  'roi-actif', 'pion-passe',
]

let checks = 0
let failures = 0
function check(ok, label) {
  checks++
  if (!ok) {
    failures++
    console.log(`[KO] ${label}`)
  }
}

// ---------- Tampon ----------
const stamp = readFileSync('scripts/endgame-course.verified', 'utf8').trim()
const digest = createHash('sha256').update(RAW).digest('hex')
check(stamp === digest, 'endgameCourse.json a changé depuis sa vérification par les tables : lance python3 scripts/verify-endgame-course.py')

// ---------- Positions ----------
function load(fen) {
  try {
    return new Chess(fen)
  } catch {
    return null
  }
}

function withTurn(fen, color) {
  const f = fen.split(' ')
  f[1] = color
  f[3] = '-'
  return f.join(' ')
}

// Le camp qui n'a pas le trait est-il en échec ? (chess.js accepte ces FEN illégales)
function oppositeCheck(fen) {
  const other = fen.split(' ')[1] === 'w' ? 'b' : 'w'
  const c = load(withTurn(fen, other))
  return c === null || c.isCheck()
}

function legalPosition(fen, label) {
  const c = load(fen)
  check(c !== null, `${label} : FEN refusée par chess.js (${fen})`)
  if (!c) return null
  check(!oppositeCheck(fen), `${label} : le camp qui n'a pas le trait est en échec (${fen})`)
  const pieces = c.board().flat().filter(Boolean).length
  check(pieces <= 7, `${label} : plus de 7 pièces, invérifiable par les tables`)
  check(fen.split(' ')[4] === '0', `${label} : compteur des 50 coups non nul`)
  return c
}

const SQUARE = /^[a-h][1-8]$/
function coords(sq) {
  return [sq.charCodeAt(0) - 97, Number(sq[1]) - 1]
}

// Déplacement géométrique d'une pièce (blocages ignorés), pour les flèches de chemin.
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

// Une flèche part d'une pièce : coup légal, ou rayon vers une case occupée (contrôle, clouage), ou
// colonne d'un pion dans son sens de marche (même règle que check-learn-data.mjs). Une flèche qui
// part d'une case vide continue le chemin de la flèche précédente (Rg7-f6-e5) : elle doit partir de
// l'arrivée d'une flèche déjà tracée et suivre le déplacement de la même pièce.
function checkArrows(fen, arrows, label) {
  const c = load(fen)
  const reached = new Map() // case d'arrivée -> pièce qui y arrive
  for (const arrow of arrows) {
    const ok = Array.isArray(arrow) && (arrow.length === 2 || (arrow.length === 3 && arrow[2] === 'red')) && SQUARE.test(arrow[0]) && SQUARE.test(arrow[1])
    check(ok, `${label} : flèche mal formée ${JSON.stringify(arrow)}`)
    if (!ok) continue
    const [from, to] = arrow
    const real = c.get(from)
    if (real) {
      const mover = load(withTurn(fen, real.color))
      const legal = mover !== null && mover.moves({ square: from, verbose: true }).some((m) => m.to === to)
      const ray = onRay(real, from, to) && (real.type === 'p' || Boolean(c.get(to)))
      check(legal || ray, `${label} : flèche ${from}→${to} n'est ni un coup de la pièce ni un rayon vers une pièce`)
      reached.set(to, real)
    } else {
      const piece = reached.get(from)
      check(Boolean(piece), `${label} : flèche ${from}→${to} part d'une case vide qui ne prolonge aucune flèche`)
      if (!piece) continue
      check(onRay(piece, from, to), `${label} : flèche ${from}→${to} ne suit pas le déplacement de la pièce`)
      reached.set(to, piece)
    }
  }
}

// ---------- Textes ----------
const FR_PIECE = { R: 'K', D: 'Q', T: 'R', F: 'B', C: 'N' }
function sanToEnglish(san) {
  return san.replace(/^[RDTFC]/, (p) => FR_PIECE[p]).replace(/=([DTFC])/, (_, p) => `=${FR_PIECE[p]}`)
}

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

const SAN_FR = '[RDTFC]?[a-h]?[1-8]?x?[a-h][1-8](?:=[DTFC])?[+#]?'
const OPENING_SAN = new RegExp(`^(?:\\d+\\.(?:\\.\\.)?\\s?)?(${SAN_FR})(?=[\\s!?,.:;)]|$)`)
const MARKED_SAN = new RegExp(`(?:^|[\\s(«])(${SAN_FR})\\s?[!?]{1,2}`, 'g')
// Coups numérotés « 2.Tb5+ » ou « 3...Rc6 » : vérifiés aussi.
const NUMBERED_SAN = new RegExp(`\\d+\\.(?:\\.\\.)?\\s?(${SAN_FR})(?=[\\s!?,.:;)]|$)`, 'g')
function citedMoves(text) {
  const out = new Set()
  const opening = text.match(OPENING_SAN)
  if (opening) out.add(opening[1])
  for (const m of text.matchAll(MARKED_SAN)) out.add(m[1])
  for (const m of text.matchAll(NUMBERED_SAN)) out.add(m[1])
  return [...out]
}

const ENGLISH_SAN = /\b[KQNB][a-h]?[1-8]?x?[a-h][1-8]\b/
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

function checkText(text, label, max) {
  check(typeof text === 'string' && text.trim().length > 0, `${label} : texte vide`)
  if (typeof text !== 'string') return
  check(text.length <= max, `${label} : ${text.length} caractères, ${max} au plus (la bulle doit tenir sous l'échiquier)`)
  check(!text.includes('—') && !text.includes('–'), `${label} : tiret cadratin ou demi-cadratin`)
  check(!ENGLISH_SAN.test(text), `${label} : notation anglaise (${(text.match(ENGLISH_SAN) || [])[0]})`)
  for (const [re, why] of BANNED) check(!re.test(text), `${label} : ${why}`)
  check(!SHOUTING.test(text), `${label} : majuscules d'insistance (${(text.match(SHOUTING) || [])[0]})`)
}

function checkCited(text, fens, label) {
  for (const san of citedMoves(text ?? '')) {
    check(fens.some((f) => sanPlayable(f, san)), `${label} : coup cité ${san} injouable dans la position`)
  }
}

// ---------- Chapitres et leçons ----------
const lessons = course.lessons ?? {}
const ids = Object.keys(lessons)
const inChapters = []
const chapterIds = new Set()
for (const ch of course.chapters ?? []) {
  check(!chapterIds.has(ch.id), `chapitre ${ch.id} en double`)
  chapterIds.add(ch.id)
  checkText(ch.title, `chapitre ${ch.id} titre`, 40)
  check(Array.isArray(ch.lessons) && ch.lessons.length > 0, `chapitre ${ch.id} vide`)
  inChapters.push(...(ch.lessons ?? []))
}
for (const id of ids) check(inChapters.filter((x) => x === id).length === 1, `leçon ${id} : doit figurer dans exactement un chapitre`)
for (const id of inChapters) check(ids.includes(id), `chapitre : leçon inconnue ${id}`)
for (const id of FROZEN_IDS) check(ids.includes(id), `leçon ${id} supprimée ou renommée : la progression des élèves en dépend`)
for (const id of ids) check(FROZEN_IDS.includes(id), `leçon ${id} : nouvel id à ajouter à FROZEN_IDS`)

const exerciseOwner = new Map()
for (const [id, lesson] of Object.entries(lessons)) {
  const L = `leçon ${id}`
  check(/^[a-z0-9-]+$/.test(id), `${L} : id hors [a-z0-9-]`)
  checkText(lesson.title, `${L} titre`, 40)
  checkText(lesson.summary, `${L} résumé`, 110)
  check(Array.isArray(lesson.keyPoints) && lesson.keyPoints.length >= 2, `${L} : au moins deux points clés`)
  for (const k of lesson.keyPoints ?? []) checkText(k, `${L} point clé`, 120)
  if (lesson.exercise !== undefined) {
    check(endgames.some((e) => e.id === lesson.exercise), `${L} : exercice ${lesson.exercise} absent de endgames.json`)
    check(!exerciseOwner.has(lesson.exercise), `${L} : exercice ${lesson.exercise} déjà lié à ${exerciseOwner.get(lesson.exercise)}`)
    exerciseOwner.set(lesson.exercise, id)
  }
  const steps = lesson.steps ?? []
  check(steps.length >= 2, `${L} : au moins deux étapes`)
  check(steps.some((s) => s.kind === 'line'), `${L} : au moins une ligne à jouer`)
  steps.forEach((step, si) => {
    const S = `${L} étape ${si + 1}`
    if (step.kind === 'diagram') {
      checkText(step.text, S, 300)
      const c = legalPosition(step.fen, S)
      if (!c) return
      check(!c.isCheckmate() && !c.isStalemate(), `${S} : diagramme déjà mat ou pat`)
      check(step.orientation === undefined || step.orientation === 'w' || step.orientation === 'b', `${S} : orientation invalide`)
      check(step.claim === undefined || ['w', 'b', 'draw'].includes(step.claim), `${S} : claim invalide`)
      checkArrows(step.fen, step.arrows ?? [], S)
      for (const [sq, color] of Object.entries(step.marks ?? {})) {
        check(SQUARE.test(sq) && ['green', 'red', 'blue', 'yellow'].includes(color), `${S} : marque invalide ${sq}=${color}`)
      }
      checkCited(step.text, [step.fen], S)
      check(!/seul coup/i.test(step.text), `${S} : « seul coup » n'est vérifiable que sur un coup de ligne (only)`)
      // Un diagramme qui annonce un résultat le fait vérifier par les tables (claim).
      check(!/\b(gagn\w*|nulle|perd\w*)\b/i.test(step.text) || step.claim !== undefined, `${S} : le texte annonce un résultat sans claim vérifié`)
    } else if (step.kind === 'line') {
      checkText(step.text, S, 260)
      checkText(step.end, `${S} fin`, 220)
      check(step.result === 'win' || step.result === 'draw', `${S} : result invalide`)
      const c = legalPosition(step.fen, S)
      if (!c) return
      const player = c.turn()
      const moves = step.moves ?? []
      check(moves.length > 0, `${S} : ligne vide`)
      const fens = [c.fen()]
      for (const [mi, m] of moves.entries()) {
        const M = `${S} coup ${mi + 1} (${m.san})`
        const mine = c.turn() === player
        let mv
        try {
          mv = c.move(m.san)
        } catch {
          check(false, `${M} : injouable`)
          return
        }
        check(mv.san === m.san, `${M} : SAN non canonique (${mv.san})`)
        const uci = mv.from + mv.to + (mv.promotion ?? '')
        if (m.text !== undefined) checkText(m.text, M, 220)
        if (mine) {
          check(Array.isArray(m.keeps) && m.keeps.includes(uci), `${M} : keeps absent ou sans le coup (relance la vérification)`)
          if (m.only) check(m.keeps?.length === 1, `${M} : only mais ${m.keeps?.length} coups gardent le résultat`)
        } else {
          check(m.only === undefined && m.keeps === undefined, `${M} : only/keeps sur un coup adverse`)
        }
        if (/seul coup/i.test(m.text ?? '')) check(m.only === true, `${M} : « seul coup » dans le texte sans only vérifié`)
        fens.push(c.fen())
      }
      check(!/seul coup/i.test(step.text) && !/seul coup/i.test(step.end ?? ''), `${S} : « seul coup » se dit sur le coup concerné, avec only`)
      for (const m of moves) checkCited(m.text ?? '', fens, `${S} coup ${m.san}`)
      checkCited(step.text, fens, S)
      checkCited(step.end ?? '', fens, `${S} fin`)
    } else {
      check(false, `${S} : type d'étape inconnu ${step.kind}`)
    }
  })
}

console.log(`${checks} règles vérifiées, ${failures} manquement${failures > 1 ? 's' : ''}`)
process.exit(failures ? 1 : 0)
