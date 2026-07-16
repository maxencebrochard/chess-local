// Convertit les données brutes (data/) en JSON pour l'app.
// - Puzzles : data/puzzles_full.csv (6M, lichess CC0) -> public/puzzles.json,
//   échantillon stratifié par tranche de rating, filtré sur qualité, format
//   compact [id, fen, moves, rating, themes] hors bundle JS (fetch lazy).
// - Openings : TSV lichess -> src/data/openings.json (bundlé, petit).
import { createReadStream, readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { createInterface } from 'node:readline'
import { Chess } from 'chess.js'

mkdirSync('src/data', { recursive: true })

// --- Puzzles ---
const bands = [
  [0, 800], [800, 1000], [1000, 1200], [1200, 1400], [1400, 1600],
  [1600, 1800], [1800, 2000], [2000, 2200], [2200, 2400], [2400, 3200],
]
const PER_BAND = 12_000
const buckets = bands.map(() => [])

const rl = createInterface({ input: createReadStream('data/puzzles_full.csv'), crlfDelay: Infinity })
let header = null
let col = {}
let filled = 0

for await (const line of rl) {
  if (!header) {
    header = line.split(',')
    col = Object.fromEntries(header.map((h, i) => [h, i]))
    continue
  }
  const parts = line.split(',')
  if (parts.length < 8) continue
  const rating = +parts[col.Rating]
  if (+parts[col.Popularity] < 85 || +parts[col.NbPlays] < 100 || +parts[col.RatingDeviation] > 90) continue
  const b = bands.findIndex(([lo, hi]) => rating >= lo && rating < hi)
  if (b === -1 || buckets[b].length >= PER_BAND) continue
  buckets[b].push([parts[col.PuzzleId], parts[col.FEN], parts[col.Moves], rating, parts[col.Themes]])
  filled++
  if (filled >= PER_BAND * bands.length) break
}

const puzzles = buckets.flat()
writeFileSync('public/puzzles.json', JSON.stringify(puzzles))
console.log(`puzzles: ${puzzles.length}`,
  bands.map(([lo], i) => `${lo}+:${buckets[i].length}`).join(' '))

// --- Openings ---
const openings = []
for (const f of ['a', 'b', 'c', 'd', 'e']) {
  const tsv = readFileSync(`data/openings_${f}.tsv`, 'utf8').split('\n')
  for (let i = 1; i < tsv.length; i++) {
    const [eco, name, pgn] = tsv[i].split('\t')
    if (!pgn) continue
    const chess = new Chess()
    try {
      chess.loadPgn(pgn)
    } catch {
      continue
    }
    const uci = chess.history({ verbose: true }).map((m) => m.lan).join(' ')
    openings.push({ eco, name, uci })
  }
}
writeFileSync('src/data/openings.json', JSON.stringify(openings))
console.log(`openings: ${openings.length}`)
