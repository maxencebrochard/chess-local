// Banc de calibration des bots : fait jouer des bots entre eux et contre des références
// Stockfish, puis estime un Elo par joueur (Bradley-Terry, intervalle de confiance par bootstrap).
//
//   node scripts/bench-bots.mjs --preset chain --games 80 --out bench.jsonl
//   node scripts/bench-bots.mjs --pair bot:nina,bot:iris --games 40 --out bench.jsonl
//   node scripts/bench-bots.mjs --report bench.jsonl [--anchor bot:iris=1600] [--chain a,b,c]
//
// Fidélité : la logique de coup est celle de `src/lib/bots.ts` (bundlée par rolldown) et le moteur
// est la classe `Engine` de l'app sur le MÊME WASM (`public/engine/`), lancé dans Node
// (voir `scripts/bots-node.mjs`). Pas de Stockfish natif : son réseau NNUE et sa vitesse
// diffèrent, il fausserait les bots à movetime (Iris et au-delà).
//
// Limite : les parties sont jouées en Illimité sur la machine qui lance le banc. Les bots faibles
// (profondeur fixe) ont la même force partout, mais Iris, l'ancre à 1600, joue au movetime : sur
// iPhone, ou en blitz et bullet (botThinkBudget), elle s'affaiblit et l'écart Nina-Iris rétrécit.
//
// Joueurs :
//   bot:<id>        le bot tel que codé dans bots.ts (chooseBotMove), ou, si bots.ts ne l'exporte pas
//                   (code d'avant), la logique de Play.tsx d'avant appliquée aux champs du bot ;
//   legacy:<id>     la logique d'avant figée (UCI_Elo plancher 1320 + coup uniforme selon randomness),
//                   pour remesurer « l'avant » après le changement ;
//   sf:<elo>@<ms>   Stockfish UCI_LimitStrength à <elo>, go movetime <ms> ;
//   style:d<profondeur>m<multipv>t<température>l<perte max>g<écart forcé>   bot faible synthétique (réglage).
//
// Chaque partie est ajoutée au fichier JSONL avec l'empreinte du réglage de ses deux joueurs :
// relancer la même commande reprend là où elle s'était arrêtée, et un fichier qui mélangerait
// deux réglages d'un même joueur est refusé (changer de --out après avoir modifié bots.ts).
import { appendFileSync, existsSync, readFileSync } from 'node:fs'
import { cpus, hostname } from 'node:os'
import { parseArgs } from 'node:util'
import { hashSeed, loadApp, seededRng } from './bots-node.mjs'

// Logique d'avant, figée depuis eb0b22d (bots.ts + Play.tsx playBotMove).
const LEGACY = {
  noa: { elo: 400, randomness: 0.45, movetimeMs: 150 },
  marty: { elo: 700, randomness: 0.3, movetimeMs: 200 },
  lea: { elo: 1000, randomness: 0.18, movetimeMs: 250 },
  nina: { elo: 1300, randomness: 0.08, movetimeMs: 300 },
}

// Ouvertures courantes et équilibrées : chaque ligne est jouée deux fois, couleurs inversées.
const OPENINGS = [
  'e4 e5 Nf3 Nc6', 'e4 c5 Nf3 d6', 'e4 e6 d4 d5', 'e4 c6 d4 d5', 'd4 d5 c4 e6',
  'd4 Nf6 c4 g6', 'd4 Nf6 c4 e6', 'c4 e5 Nc3 Nf6', 'Nf3 d5 g3 Nf6', 'e4 e5 Nf3 Nc6 Bc4 Bc5',
  'e4 e5 Nf3 Nc6 Bb5 a6', 'e4 d5 exd5 Qxd5', 'd4 d5 Bf4 Nf6', 'e4 c5 Nc3 Nc6', 'd4 f5 g3 Nf6',
  'e4 g6 d4 Bg7', 'e4 e5 f4 exf4', 'd4 d5 c4 c6', 'e4 Nf6 e5 Nd5', 'c4 c5 Nc3 Nc6',
]
const MAX_PLIES = 400

const PRESETS = {
  // Chaîne des bots faibles + Iris (ancre, inchangée) + Stockfish 1320 (le moteur commun des
  // bots faibles d'avant). Voisins, voisins à deux crans, et références.
  chain: (kind) => {
    const n = (id) => `${kind}:${id}`
    return [
      [n('noa'), n('marty')], [n('marty'), n('lea')], [n('lea'), n('nina')], [n('nina'), 'bot:iris'],
      [n('noa'), n('lea')], [n('marty'), n('nina')], [n('lea'), 'bot:iris'],
      [n('nina'), 'sf:1320@300'], ['bot:iris', 'sf:1320@300'],
    ]
  },
}

function usage(msg) {
  if (msg) console.error(msg)
  console.error('usage : node scripts/bench-bots.mjs (--preset chain[:legacy] | --pair a,b ...) [--games N] [--jobs N] --out f.jsonl')
  console.error('        node scripts/bench-bots.mjs --report f.jsonl [--anchor bot:iris=1600] [--chain a,b,...]')
  process.exit(2)
}

const { values: args } = parseArgs({
  options: {
    preset: { type: 'string' },
    pair: { type: 'string', multiple: true },
    games: { type: 'string', default: '80' },
    jobs: { type: 'string', default: String(Math.max(1, cpus().length - 1)) },
    out: { type: 'string' },
    report: { type: 'string' },
    anchor: { type: 'string', default: 'bot:iris=1600' },
    chain: { type: 'string' },
    seed: { type: 'string', default: '1' },
    bootstrap: { type: 'string', default: '400' },
  },
})

// ---------- joueurs ----------

function parseStyle(rest) {
  const m = rest.match(/^d(\d+)m(\d+)t(\d+)l(\d+)g(\d+)$/)
  if (!m) return null
  const [depth, multipv, temperatureCp, maxLossCp, forcedGapCp] = m.slice(1).map(Number)
  if (depth < 1 || multipv < 1 || temperatureCp <= 0) return null
  return { depth, multipv, temperatureCp, maxLossCp, forcedGapCp }
}

// Comment le joueur choisit ses coups, et l'empreinte de ce réglage.
function resolvePlayer(app, spec) {
  const [kind, rest = ''] = spec.split(':')
  const hasNew = typeof app.chooseBotMove === 'function'
  if (kind === 'sf') {
    const [elo, ms] = rest.split('@').map(Number)
    if (!elo || !ms) usage(`référence invalide : ${spec}`)
    const options = { UCI_LimitStrength: true, UCI_Elo: elo }
    return { cfg: spec, play: (engine, chess) => sfMove(engine, chess, options, ms) }
  }
  if (kind === 'legacy') {
    const b = LEGACY[rest]
    if (!b) usage(`bot legacy inconnu : ${rest}`)
    const options = { UCI_LimitStrength: true, UCI_Elo: Math.max(1320, b.elo) }
    return { cfg: `legacy ${JSON.stringify(b)}`, play: (engine, chess, rng) => legacyMove(engine, chess, b, options, rng) }
  }
  if (kind === 'bot') {
    const bot = app.botById(rest)
    if (!bot) usage(`bot inconnu : ${rest}`)
    if (hasNew) {
      const cfg = `bot ${JSON.stringify({ options: app.botEngineOptions(bot), movetimeMs: bot.movetimeMs, style: bot.style ?? null })}`
      return { cfg, play: (engine, chess, rng) => app.chooseBotMove(engine, bot, chess.fen(), { rng }) }
    }
    const cfg = `legacy ${JSON.stringify({ elo: bot.elo, randomness: bot.randomness, movetimeMs: bot.movetimeMs })}`
    return { cfg, play: (engine, chess, rng) => legacyMove(engine, chess, bot, app.botEngineOptions(bot), rng) }
  }
  if (kind === 'style') {
    const style = parseStyle(rest)
    if (!style || !hasNew) usage(`style invalide : ${spec}`)
    const bot = { id: spec, name: spec, elo: 0, emoji: '', description: '', movetimeMs: 0, style }
    return { cfg: spec, play: (engine, chess, rng) => app.chooseBotMove(engine, bot, chess.fen(), { rng }) }
  }
  usage(`joueur inconnu : ${spec}`)
}

async function sfMove(engine, chess, options, movetimeMs) {
  await engine.setOptions(options)
  return (await engine.search({ fen: chess.fen(), movetimeMs, multipv: 1 })).bestMove
}

// Réplique de playBotMove d'avant (Play.tsx, eb0b22d), latence artificielle exclue.
async function legacyMove(engine, chess, bot, options, rng) {
  await engine.setOptions(options)
  if (bot.randomness > 0 && rng() < bot.randomness) {
    const moves = chess.moves({ verbose: true })
    return moves[Math.floor(rng() * moves.length)].lan
  }
  return (await engine.search({ fen: chess.fen(), movetimeMs: bot.movetimeMs, multipv: 1 })).bestMove
}

// ---------- partie ----------

async function playGame(app, players, white, black, index, seed) {
  const opening = OPENINGS[Math.floor(index / 2) % OPENINGS.length]
  const chess = new app.Chess()
  for (const san of opening.split(' ')) chess.move(san)
  const rng = seededRng(hashSeed(seed, white, black, String(index)))
  // Un moteur neuf par joueur et par partie (dans l'app, la table de hachage survit d'une partie
  // à l'autre : effet négligeable à profondeur fixe comme à movetime court).
  const side = { w: { p: players.get(white), engine: new app.Engine() }, b: { p: players.get(black), engine: new app.Engine() } }
  try {
    while (!chess.isGameOver() && chess.history().length < MAX_PLIES) {
      const s = side[chess.turn()]
      const uci = await s.p.play(s.engine, chess, rng)
      chess.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
    }
  } finally {
    side.w.engine.quit()
    side.b.engine.quit()
  }
  let score = 0.5
  let reason = 'limite'
  if (chess.isCheckmate()) {
    score = chess.turn() === 'w' ? 0 : 1
    reason = 'mat'
  } else if (chess.isStalemate()) reason = 'pat'
  else if (chess.isInsufficientMaterial()) reason = 'matériel'
  else if (chess.isThreefoldRepetition()) reason = 'répétition'
  else if (chess.isDrawByFiftyMoves()) reason = '50 coups'
  return {
    white, black, index, opening, score, reason, plies: chess.history().length,
    cfg: { [white]: players.get(white).cfg, [black]: players.get(black).cfg },
  }
}

// ---------- estimation Elo ----------

function readResults(file) {
  if (!existsSync(file)) return []
  return readFileSync(file, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)).filter((g) => !g.error)
}

// Un joueur = un réglage : refuse un fichier qui mélange deux réglages d'un même nom.
function cfgByPlayer(games) {
  const seen = new Map()
  for (const g of games) {
    for (const [p, cfg] of Object.entries(g.cfg ?? {})) {
      if (seen.has(p) && seen.get(p) !== cfg) {
        throw new Error(`${p} a deux réglages dans ce fichier :\n  ${seen.get(p)}\n  ${cfg}\nUtiliser un autre --out.`)
      }
      seen.set(p, cfg)
    }
  }
  return seen
}

const pairKey = (a, b) => [a, b].sort().join(' vs ')

// Bradley-Terry par MM, nulles = demi-victoires, une nulle virtuelle par paire (évite
// l'infini sur un 100 %). Renvoie l'Elo de chaque joueur, ancré.
function fitElo(games, anchorName, anchorElo) {
  const players = [...new Set(games.flatMap((g) => [g.white, g.black]))]
  const idx = new Map(players.map((p, i) => [p, i]))
  const n = players.length
  const wins = new Float64Array(n)
  const count = Array.from({ length: n }, () => new Float64Array(n))
  for (const g of games) {
    const w = idx.get(g.white)
    const b = idx.get(g.black)
    wins[w] += g.score
    wins[b] += 1 - g.score
    count[w][b] += 1
    count[b][w] += 1
  }
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (count[i][j] > 0) {
        count[i][j] += 1
        count[j][i] += 1
        wins[i] += 0.5
        wins[j] += 0.5
      }
    }
  }
  let gamma = new Float64Array(n).fill(1)
  for (let it = 0; it < 5000; it++) {
    const next = new Float64Array(n)
    let delta = 0
    for (let i = 0; i < n; i++) {
      let denom = 0
      for (let j = 0; j < n; j++) if (count[i][j] > 0) denom += count[i][j] / (gamma[i] + gamma[j])
      next[i] = denom > 0 ? wins[i] / denom : gamma[i]
    }
    const norm = next.reduce((s, x) => s + Math.log(x), 0) / n
    for (let i = 0; i < n; i++) {
      next[i] = Math.exp(Math.log(next[i]) - norm)
      delta = Math.max(delta, Math.abs(next[i] - gamma[i]) / gamma[i])
    }
    gamma = next
    if (delta < 1e-10) break
  }
  const elo = new Map(players.map((p, i) => [p, (400 * Math.log(gamma[i])) / Math.LN10]))
  const shift = elo.has(anchorName) ? anchorElo - elo.get(anchorName) : 0
  for (const p of players) elo.set(p, elo.get(p) + shift)
  return elo
}

const expected = (d) => 1 / (1 + 10 ** (-d / 400))

function report(games, anchor, bootstrap, seed, chainArg) {
  const cfgs = cfgByPlayer(games)
  const [anchorName, anchorEloStr] = anchor.split('=')
  const anchorElo = Number(anchorEloStr)
  const elo = fitElo(games, anchorName, anchorElo)
  // Bootstrap : on rééchantillonne, dans chaque paire, des COUPLES de parties (même ouverture,
  // couleurs inversées), puis on refait tout l'ajustement (l'incertitude se cumule le long de la
  // chaîne).
  const byPair = new Map()
  for (const g of games) {
    const k = pairKey(g.white, g.black)
    if (!byPair.has(k)) byPair.set(k, new Map())
    const couples = byPair.get(k)
    const c = Math.floor(g.index / 2)
    if (!couples.has(c)) couples.set(c, [])
    couples.get(c).push(g)
  }
  const rng = seededRng(hashSeed('bootstrap', seed))
  const samples = []
  for (let r = 0; r < bootstrap; r++) {
    const resampled = []
    for (const couples of byPair.values()) {
      const list = [...couples.values()]
      for (let i = 0; i < list.length; i++) resampled.push(...list[Math.floor(rng() * list.length)])
    }
    samples.push(fitElo(resampled, anchorName, anchorElo))
  }
  const q = (arr, p) => {
    const s = [...arr].sort((a, b) => a - b)
    return s[Math.min(s.length - 1, Math.max(0, Math.round(p * (s.length - 1))))]
  }
  const ci = (values) => `${Math.round(q(values, 0.025))} à ${Math.round(q(values, 0.975))}`
  const lines = []
  lines.push(`Machine : ${hostname()}, ${cpus()[0]?.model ?? '?'} ; ${games.length} parties ; ancre ${anchorName} = ${anchorElo} ; bootstrap ${bootstrap} (couples d'ouverture)`)
  lines.push('')
  lines.push('| Joueur | Elo estimé | IC 95 % | Parties | Score |')
  lines.push('|---|---:|---:|---:|---:|')
  const rows = [...elo.entries()].sort((a, b) => a[1] - b[1])
  for (const [p, v] of rows) {
    const mine = games.filter((g) => g.white === p || g.black === p)
    const pts = mine.reduce((s, g) => s + (g.white === p ? g.score : 1 - g.score), 0)
    const c = p === anchorName ? 'ancre' : ci(samples.map((s) => s.get(p)))
    lines.push(`| ${p} | ${Math.round(v)} | ${c} | ${mine.length} | ${((100 * pts) / mine.length).toFixed(1)} % |`)
  }
  // Écarts entre voisins de la chaîne (ordre donné, sinon ordre des Elo estimés) : IC propres à
  // chaque écart, indépendants de la distance à l'ancre.
  const chain = chainArg ? chainArg.split(',') : rows.map(([p]) => p)
  lines.push('')
  lines.push('| Écart (B - A) | Elo | IC 95 % | Strictement positif ? |')
  lines.push('|---|---:|---:|---|')
  for (let i = 1; i < chain.length; i++) {
    const [a, b] = [chain[i - 1], chain[i]]
    if (!elo.has(a) || !elo.has(b)) continue
    const d = samples.map((s) => s.get(b) - s.get(a))
    const lo = q(d, 0.025)
    lines.push(`| ${b} - ${a} | ${Math.round(elo.get(b) - elo.get(a))} | ${ci(d)} | ${lo > 0 ? 'oui (IC > 0)' : 'non prouvé'} |`)
  }
  lines.push('')
  lines.push('| Paire (A vs B) | Parties | Score de A | Prédit par l\'ajustement | Écart Elo observé | Nulles | Demi-coups moyens |')
  lines.push('|---|---:|---:|---:|---:|---:|---:|')
  for (const [k, couples] of byPair) {
    const list = [...couples.values()].flat()
    const [a, b] = k.split(' vs ')
    const pts = list.reduce((s, g) => s + (g.white === a ? g.score : 1 - g.score), 0)
    const p = Math.min(0.995, Math.max(0.005, pts / list.length))
    const diff = Math.round(-400 * Math.log10(1 / p - 1))
    const pred = expected(elo.get(a) - elo.get(b))
    const draws = list.filter((g) => g.score === 0.5).length
    const plies = Math.round(list.reduce((s, g) => s + g.plies, 0) / list.length)
    lines.push(`| ${k} | ${list.length} | ${((100 * pts) / list.length).toFixed(1)} % | ${(100 * pred).toFixed(1)} % | ${diff >= 0 ? '+' : ''}${diff} | ${draws} | ${plies} |`)
  }
  lines.push('')
  lines.push('Réglages :')
  for (const [p, cfg] of cfgs) lines.push(`- ${p} : \`${cfg}\``)
  return lines.join('\n')
}

// ---------- main ----------

async function main() {
  if (args.report) {
    console.log(report(readResults(args.report), args.anchor, Number(args.bootstrap), args.seed, args.chain))
    return
  }
  if (!args.out) usage('--out requis')
  let pairs = (args.pair ?? []).map((p) => p.split(','))
  if (args.preset) {
    const [name, kind = 'bot'] = args.preset.split(':')
    if (!PRESETS[name]) usage(`preset inconnu : ${name}`)
    pairs = pairs.concat(PRESETS[name](kind))
  }
  if (pairs.length === 0) usage('aucune paire')
  const games = Number(args.games)
  const jobs = Number(args.jobs)
  const app = await loadApp()
  const players = new Map()
  for (const spec of new Set(pairs.flat())) players.set(spec, resolvePlayer(app, spec))
  // Reprise : le fichier existant doit porter les mêmes réglages que le code courant.
  const previous = readResults(args.out)
  const known = cfgByPlayer(previous)
  for (const [spec, p] of players) {
    if (known.has(spec) && known.get(spec) !== p.cfg) {
      usage(`${args.out} contient ${spec} avec un autre réglage :\n  ${known.get(spec)}\n  ${p.cfg}\nUtiliser un autre --out.`)
    }
  }
  const done = new Set(previous.map((g) => `${pairKey(g.white, g.black)}#${g.index}`))
  // Paires lentes (moteurs à movetime) d'abord pour équilibrer la fin du lot.
  const slow = (p) => (p.some((x) => x.startsWith('sf:') || x === 'bot:iris' || x.startsWith('legacy:')) ? 0 : 1)
  const tasks = []
  for (const [a, b] of [...pairs].sort((x, y) => slow(x) - slow(y))) {
    for (let i = 0; i < games; i++) {
      if (done.has(`${pairKey(a, b)}#${i}`)) continue
      tasks.push(i % 2 === 0 ? [a, b, i] : [b, a, i])
    }
  }
  console.error(`${tasks.length} parties à jouer (${done.size} déjà faites), ${jobs} en parallèle`)
  let finished = 0
  let failed = 0
  const t0 = Date.now()
  let next = 0
  async function worker() {
    while (next < tasks.length) {
      const [w, b, i] = tasks[next++]
      try {
        const g = await playGame(app, players, w, b, i, args.seed)
        appendFileSync(args.out, `${JSON.stringify(g)}\n`)
      } catch (e) {
        // Une partie qui casse (coup illégal, moteur mort) est journalisée, le banc continue.
        failed++
        appendFileSync(args.out, `${JSON.stringify({ white: w, black: b, index: i, error: String(e?.stack ?? e) })}\n`)
        console.error(`  ÉCHEC ${w} - ${b} #${i} : ${e}`)
      }
      finished++
      if (finished % 10 === 0 || finished === tasks.length) {
        console.error(`  ${finished}/${tasks.length} (${Math.round((Date.now() - t0) / 1000)} s)`)
      }
    }
  }
  await Promise.all(Array.from({ length: jobs }, worker))
  if (failed) console.error(`${failed} partie(s) en échec, voir les lignes "error" de ${args.out}`)
  console.log(report(readResults(args.out), args.anchor, Number(args.bootstrap), args.seed, args.chain))
  process.exit(failed ? 1 : 0)
}

await main()
