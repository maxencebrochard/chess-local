// Génère src/data/mateIndex.json : ids des puzzles de public/puzzles.json classés par géométrie de
// mat (escalier, batteries, diagonale + ligne, dame au contact, Damiano), pour /mats.
// Le classement est celui de l'app (src/lib/mateNet.ts, importé tel quel) appliqué à la position
// finale de la ligne principale de chaque mat en 1 ou en 2. Fait hors ligne : rejouer des milliers
// de lignes sur iPhone à chaque visite serait trop lent.
//
// Usage : node scripts/prepare-mates-index.mjs           (écrit le fichier)
//         node scripts/prepare-mates-index.mjs --check   (vérifie qu'il est à jour, code 1 sinon)
// À relancer après `node scripts/prepare-data.mjs` (nouveau puzzles.json).
import { readFileSync, writeFileSync } from 'node:fs'
import { Chess } from 'chess.js'
import { analyseMate } from '../src/lib/mateNet.ts'

const OUT = 'src/data/mateIndex.json'
const TAGS = ['escalier', 'batterie-diagonale', 'batterie-ligne', 'diagonale-ligne', 'contact', 'damiano']
// Seuils de matériel (pièces sur l'échiquier, rois compris) essayés du plus bas au plus haut :
// on garde le plus bas qui donne assez de positions, pour rester proche des finales de bullet.
const THRESHOLDS = [12, 16, 20, 24, 32]
const MIN_POOL = 40
const MAX_POOL = 300

const pieces = (fen) => fen.split(' ')[0].replace(/[^a-zA-Z]/g, '').length
const puzzles = JSON.parse(readFileSync('public/puzzles.json', 'utf8'))

const found = Object.fromEntries(TAGS.map((t) => [t, []]))
for (const [id, fen, moves, rating, themes] of puzzles) {
  const th = themes.split(' ')
  if (!th.includes('mateIn1') && !th.includes('mateIn2')) continue
  const c = new Chess(fen)
  for (const m of moves.split(' ')) c.move({ from: m.slice(0, 2), to: m.slice(2, 4), promotion: m[4] })
  const net = analyseMate(c.fen())
  if (!net) throw new Error(`puzzle ${id} : la ligne principale ne finit pas sur un mat`)
  for (const t of net.tags) found[t].push({ id, n: pieces(fen), rating })
}

const index = {}
for (const t of TAGS) {
  const all = found[t]
  const limit = THRESHOLDS.find((k) => all.filter((p) => p.n <= k).length >= MIN_POOL) ?? 32
  // Les plus épurés d'abord, puis par id : sortie stable d'une génération à l'autre.
  const pool = all.filter((p) => p.n <= limit).sort((a, b) => a.n - b.n || (a.id < b.id ? -1 : 1)).slice(0, MAX_POOL)
  index[t] = pool.map((p) => p.id).sort()
  console.log(`${t} : ${index[t].length} puzzles (≤ ${limit} pièces, ${all.length} au total)`)
}

const text = JSON.stringify(index) + '\n'
if (process.argv.includes('--check')) {
  const current = readFileSync(OUT, 'utf8')
  if (current !== text) {
    console.log(`[KO] ${OUT} n'est pas à jour : relancer node scripts/prepare-mates-index.mjs`)
    process.exit(1)
  }
  console.log(`${OUT} à jour`)
} else {
  writeFileSync(OUT, text)
  console.log(`écrit : ${OUT}`)
}
