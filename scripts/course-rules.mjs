// Règles communes des contrôles hors ligne des cours d'Apprendre (check-endgame-course.mjs,
// check-attack-course.mjs) : compteur de manquements, positions, flèches, coups cités, textes,
// tampon de vérification. Règles de texte reprises de scripts/check-learn-data.mjs (lot L4).
import { createHash } from 'node:crypto'
import { Chess } from 'chess.js'

// Compteur : n'imprime que les manquements ([KO]) et un bilan ; code de sortie 1 au moindre [KO].
export function createChecker() {
  let checks = 0
  let failures = 0
  return {
    check(ok, label) {
      checks++
      if (!ok) {
        failures++
        console.log(`[KO] ${label}`)
      }
    },
    finish() {
      console.log(`${checks} règles vérifiées, ${failures} manquement${failures > 1 ? 's' : ''}`)
      process.exit(failures ? 1 : 0)
    },
  }
}

// Le tampon est le sha256 du JSON vérifié (premier mot du fichier de tampon).
export function stampMatches(raw, stampText) {
  return stampText.trim().split(/\s+/)[0] === createHash('sha256').update(raw).digest('hex')
}

// ---------- Positions ----------
export function load(fen) {
  try {
    return new Chess(fen)
  } catch {
    return null
  }
}

export function withTurn(fen, color) {
  const f = fen.split(' ')
  f[1] = color
  f[3] = '-'
  return f.join(' ')
}

// Le camp qui n'a pas le trait est-il en échec ? (chess.js accepte ces FEN illégales)
export function oppositeCheck(fen) {
  const other = fen.split(' ')[1] === 'w' ? 'b' : 'w'
  const c = load(withTurn(fen, other))
  return c === null || c.isCheck()
}

export const SQUARE = /^[a-h][1-8]$/
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
export function checkArrows(check, fen, arrows, label) {
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

// ---------- Coups cités dans les textes (notation française) ----------
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

export function checkCited(check, text, fens, label) {
  for (const san of citedMoves(text ?? '')) {
    check(fens.some((f) => sanPlayable(f, san)), `${label} : coup cité ${san} injouable dans la position`)
  }
}

// ---------- Textes ----------
// Mot entier, accents compris : `\b` de JavaScript ne voit pas « é ».
export function word(pattern) {
  return new RegExp(`(?<!\\p{L})(?:${pattern})(?!\\p{L})`, 'iu')
}

// Un texte de coup ou une fin de ligne qui commence par « Mat » (« Mat. », « Mat : ») annonce un mat
// sur l'échiquier : la position atteinte doit l'être. Une menace (« menace Dh7 mat ») reste permise.
const ANNOUNCED_MATE = /^Mat(?!\p{L})/u
export function checkAnnouncedMate(check, chess, text, label) {
  check(!ANNOUNCED_MATE.test(text ?? '') || chess.isCheckmate(), `${label} : annonce « Mat » sans mat sur l'échiquier`)
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

export function checkText(check, text, label, max) {
  check(typeof text === 'string' && text.trim().length > 0, `${label} : texte vide`)
  if (typeof text !== 'string') return
  check(text.length <= max, `${label} : ${text.length} caractères, ${max} au plus (la bulle doit tenir sous l'échiquier)`)
  check(!text.includes('—') && !text.includes('–'), `${label} : tiret cadratin ou demi-cadratin`)
  check(!ENGLISH_SAN.test(text), `${label} : notation anglaise (${(text.match(ENGLISH_SAN) || [])[0]})`)
  for (const [re, why] of BANNED) check(!re.test(text), `${label} : ${why}`)
  check(!SHOUTING.test(text), `${label} : majuscules d'insistance (${(text.match(SHOUTING) || [])[0]})`)
}
