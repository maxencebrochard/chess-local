// Contrôle hors ligne de la banque de « Calcul et visualisation » (src/data/visualisation.json) avec
// chess.js : structure, positions légales, amorce cohérente, lignes jouables de la bonne longueur,
// meilleur coup légal (pas de sous-promotion) dans une position finale non terminée, au moins 150
// items et 25 mats en 1 par niveau, ids uniques, et tampon de vérification.
// Le meilleur coup est confirmé par Stockfish 18 dans scripts/prepare-visualisation.py ; ce contrôle
// exige que le JSON soit exactement celui qu'il a tamponné.
// Lancé par e2e/test_visualisation.py (donc par le gate) :
//   node scripts/check-visualisation.mjs [json] [tampon]
// N'imprime que les manquements ([KO]) et un bilan ; code de sortie 1 au moindre [KO].
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { Chess } from 'chess.js'

const DATA = process.argv[2] ?? 'src/data/visualisation.json'
const STAMP = process.argv[3] ?? 'scripts/visualisation.verified'
const LEVELS = ['2', '4', '6', '8']
const PER_LEVEL = 150
const MIN_MATE = 25

let failures = 0
function check(ok, msg) {
  if (!ok) {
    failures += 1
    if (failures <= 40) console.log(`[KO] ${msg}`)
  }
}

const RAW = readFileSync(DATA, 'utf8')
const STAMP_TEXT = readFileSync(STAMP, 'utf8').trim().split(/\s+/)
check(STAMP_TEXT[0] === createHash('sha256').update(RAW).digest('hex'), `${DATA} a changé depuis sa vérification par Stockfish : lance python3 scripts/prepare-visualisation.py`)
const scriptSha = createHash('sha256').update(readFileSync('scripts/prepare-visualisation.py')).digest('hex')
check(STAMP_TEXT[1] === scriptSha, 'scripts/prepare-visualisation.py a changé depuis le tampon : relance-le')

function play(c, uci) {
  try {
    return c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
  } catch {
    return null
  }
}

const UCI = /^[a-h][1-8][a-h][1-8][qrbn]?$/
const bank = JSON.parse(RAW)
check(bank.version === 1, 'version 1')
check(JSON.stringify(Object.keys(bank.levels ?? {})) === JSON.stringify(LEVELS), `niveaux ${LEVELS.join(', ')} dans l'ordre`)
const ids = new Set()
let total = 0
for (const lv of LEVELS) {
  const items = bank.levels?.[lv] ?? []
  const n = Number(lv)
  check(items.length >= PER_LEVEL, `niveau ${lv} : ${items.length} items (au moins ${PER_LEVEL})`)
  let mates = 0
  for (const it of items) {
    total += 1
    const label = `niveau ${lv}, ${it.id}`
    check(typeof it.id === 'string' && it.id.length > 0 && !ids.has(it.id), `${label} : id absent ou en double`)
    ids.add(it.id)
    check(Number.isInteger(it.rating), `${label} : classement`)
    check(Array.isArray(it.line) && it.line.length === n, `${label} : ligne de ${n} demi-coups`)
    check([it.last, it.best, ...(it.line ?? [])].every((u) => typeof u === 'string' && UCI.test(u)), `${label} : coups UCI`)
    let c
    try {
      c = new Chess(it.fen)
    } catch {
      check(false, `${label} : FEN refusée`)
      continue
    }
    const lastPiece = c.get(it.last.slice(2, 4))
    check(!!lastPiece && lastPiece.color !== c.turn(), `${label} : l'amorce ${it.last} n'arrive pas sur une pièce du camp adverse`)
    let ok = true
    for (const u of it.line) {
      if (!play(c, u)) {
        check(false, `${label} : coup ${u} illégal`)
        ok = false
        break
      }
    }
    if (!ok) continue
    check(!c.isGameOver(), `${label} : position finale terminée`)
    check(!(it.best.length === 5 && it.best[4] !== 'q'), `${label} : sous-promotion`)
    check(c.moves({ verbose: true }).some((m) => m.from + m.to + (m.promotion ?? '') === it.best), `${label} : meilleur coup ${it.best} illégal`)
    if (c.moves({ verbose: true }).some((m) => m.san.endsWith('#'))) mates += 1
  }
  check(mates >= MIN_MATE, `niveau ${lv} : ${mates} positions finales avec mat en 1 (au moins ${MIN_MATE})`)
}

if (failures > 0) {
  console.log(`${failures} manquement(s) sur ${total} items`)
  process.exit(1)
}
console.log(`OK : ${total} items contrôlés, tampon à jour`)
