// Harnais des coups de bot, lancé par `test_bots.py` : fait jouer la VRAIE logique de
// `src/lib/bots.ts` sur le VRAI Stockfish WASM de l'app (voir `scripts/bots-node.mjs`) dans des
// positions fixes, et imprime un JSON que la suite Python vérifie.
//
//   node e2e/bots_moves.mjs
//
// Pour chaque bot faible et chaque position, on calcule la LOI EXACTE de son coup (lignes du
// moteur à sa profondeur, puis `weakMoveDistribution`) : les checks ne dépendent pas d'un tirage.
// On joue aussi quelques coups réels par `chooseBotMove` (le chemin de l'app).
// Si bots.ts n'a pas ces exports (code d'avant), la loi est celle de la logique d'avant de
// Play.tsx (coup uniforme avec la probabilité `randomness`, sinon coup du moteur bridé) : la
// suite échoue alors sur ce qu'elle mesure, pas sur un import manquant.
import { hashSeed, loadApp, seededRng } from '../scripts/bots-node.mjs'

const app = await loadApp()
const { Chess, Engine, BOTS } = app
const hasNew = typeof app.chooseBotMove === 'function' && typeof app.weakMoveDistribution === 'function'
const WEAK = ['noa', 'marty', 'lea', 'nina']

function fenOf(spec) {
  if (spec.fen) return spec.fen
  const c = new Chess()
  for (const san of spec.san.split(' ')) c.move(san)
  return c.fen()
}

function play(fen, uci) {
  const c = new Chess(fen)
  const mv = c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
  return { c, mv }
}

const allowsMateInOne = (c) => c.moves({ verbose: true }).some((m) => { c.move(m); const mate = c.isCheckmate(); c.undo(); return mate })

// Positions où un coup s'impose : aucun bot faible ne doit le rater.
const FORCED = [
  { id: 'mat-en-1', fen: '6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1', ok: (c, mv) => c.isCheckmate() && mv.lan === 'a1a8' },
  { id: 'dame-gratuite', san: 'e4 e5 Nf3 Qh4', ok: (_c, mv) => mv.lan === 'f3h4' },
  { id: 'parade-du-berger', san: 'e4 e5 Bc4 Nc6 Qh5', ok: (c) => !allowsMateInOne(c) },
  // Menace calme (sans prise) : seul ...Kh8?? se fait mater par Ta8#.
  { id: 'parade-du-couloir', fen: '6k1/5ppp/8/8/8/8/5PPP/R5K1 b - - 0 1', ok: (c) => !allowsMateInOne(c) },
  // Reprendre la dame, tout de suite (...Nxf6, ...gxf6) ou après un échec intermédiaire : jugé par
  // la référence pleine force, pas par la case d'arrivée. Ce qui s'impose, c'est de ne pas laisser
  // la dame (perte ~900 cp) ; perdre une pièce mineure en route (...Bb4+ c3) est une faute humaine
  // qu'un bot faible a le droit de faire, d'où le seuil à 500 cp.
  { id: 'reprise-de-dame', san: 'e4 e5 Nf3 Nc6 d4 exd4 Nxd4 Nxd4 Qxd4 Qf6 Qxf6', ok: (_c, _mv, loss) => loss < 500 },
]

// Positions calmes : perte espérée, mesurée contre une référence pleine force.
const QUIET = [
  { id: 'ouverture-1', san: 'e4 e5 Nf3' },
  { id: 'gambit-dame', san: 'd4 d5 c4 e6 Nc3 Nf6' },
  { id: 'sicilienne', san: 'e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6' },
  { id: 'italienne', san: 'e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d3 d6 O-O O-O' },
  { id: 'est-indienne', san: 'd4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O' },
  { id: 'finale-tours', fen: '8/5pk1/6p1/8/3R4/6P1/r4PK1/8 w - - 0 1' },
]
const SAMPLES = 8

// Loi exacte du coup d'un bot dans `fen`.
async function distribution(engine, bot, fen) {
  await engine.setOptions(app.botEngineOptions(bot))
  if (hasNew) {
    const res = await engine.search({ fen, depth: bot.style.depth, multipv: bot.style.multipv })
    return app.weakMoveDistribution(res.lines, bot.style)
  }
  // Logique d'avant (Play.tsx eb0b22d).
  const best = (await engine.search({ fen, movetimeMs: bot.movetimeMs, multipv: 1 })).bestMove
  const legal = new Chess(fen).moves({ verbose: true }).map((m) => m.lan)
  const p = new Map(legal.map((u) => [u, bot.randomness / legal.length]))
  p.set(best, (p.get(best) ?? 0) + 1 - bot.randomness)
  return [...p].map(([uci, pr]) => ({ uci, p: pr }))
}

async function sampleMove(engine, bot, fen, rng) {
  if (hasNew) return app.chooseBotMove(engine, bot, fen, { rng })
  const d = await distribution(engine, bot, fen)
  let r = rng()
  for (const { uci, p } of d) if ((r -= p) < 0) return uci
  return d[0].uci
}

// 1. Bots bridés (>= 1320) : options et recherche identiques à l'avant, sur un moteur espion.
async function strongPath() {
  const out = []
  for (const bot of BOTS.filter((b) => !WEAK.includes(b.id))) {
    const calls = []
    const spy = {
      setOptions: async (o) => { calls.push(['setOptions', o]) },
      search: async (o) => { calls.push(['search', o]); return { bestMove: 'e2e4', lines: [] } },
    }
    const fen = new Chess().fen()
    let budget = null
    if (hasNew) {
      await app.chooseBotMove(spy, bot, fen)
      const budgetCalls = []
      const spy2 = { setOptions: async () => {}, search: async (o) => { budgetCalls.push(o); return { bestMove: 'e2e4', lines: [] } } }
      await app.chooseBotMove(spy2, bot, fen, { movetimeMs: 120 })
      budget = budgetCalls[0] ?? null
    } else {
      await spy.setOptions(app.botEngineOptions(bot))
      await spy.search({ fen, movetimeMs: bot.movetimeMs, multipv: 1 })
    }
    out.push({ id: bot.id, calls, budget })
  }
  return out
}

// Valeur de chaque coup légal, pleine force (référence de la perte).
async function reference(engine, fen) {
  await engine.setOptions({ UCI_LimitStrength: false })
  const res = await engine.search({ fen, depth: 12, multipv: 60 })
  const val = new Map()
  for (const l of res.lines) {
    if (!l.pv[0] || val.has(l.pv[0])) continue
    val.set(l.pv[0], l.scoreMate !== null ? (l.scoreMate > 0 ? 10000 : -10000) : l.scoreCp)
  }
  return val
}

async function weakBot(id, refs, forcedRefs) {
  const bot = app.botById(id)
  const engine = new Engine()
  const rng = seededRng(hashSeed('bots_moves', id))
  const forced = {}
  const quiet = {}
  try {
    for (const pos of FORCED) {
      const fen = fenOf(pos)
      const ref = forcedRefs.get(pos.id)
      const best = Math.max(...ref.values())
      const worst = Math.min(...ref.values())
      const isBad = (uci) => { const { c, mv } = play(fen, uci); return !pos.ok(c, mv, best - (ref.get(uci) ?? worst)) }
      const dist = await distribution(engine, bot, fen)
      const badMass = dist.filter(({ uci }) => isBad(uci))
      const sampled = []
      for (let i = 0; i < SAMPLES; i++) sampled.push(await sampleMove(engine, bot, fen, rng))
      const badSampled = sampled.filter(isBad)
      forced[pos.id] = {
        pBad: badMass.reduce((s, x) => s + x.p, 0),
        bad: badMass.filter((x) => x.p > 0).map((x) => `${play(fen, x.uci).mv.san} ${(100 * x.p).toFixed(1)} %`),
        badSampled: badSampled.map((uci) => play(fen, uci).mv.san),
      }
    }
    for (const pos of QUIET) {
      const fen = fenOf(pos)
      const ref = refs.get(pos.id)
      const best = Math.max(...ref.values())
      const worst = Math.min(...ref.values())
      const dist = await distribution(engine, bot, fen)
      const loss = (uci) => best - (ref.get(uci) ?? worst)
      quiet[pos.id] = {
        expectedLoss: dist.reduce((s, x) => s + x.p * loss(x.uci), 0),
        pBlunder: dist.filter((x) => loss(x.uci) >= 300).reduce((s, x) => s + x.p, 0),
        pBest: dist.filter((x) => loss(x.uci) <= 0).reduce((s, x) => s + x.p, 0),
        // Nombre effectif de candidats, exp(entropie) : 1 = coup unique, n = n coups équiprobables.
        candidates: Math.exp(-dist.reduce((s, x) => s + (x.p > 0 ? x.p * Math.log(x.p) : 0), 0)),
      }
    }
  } finally {
    engine.quit()
  }
  return { id, forced, quiet }
}

const refEngine = new Engine()
const refs = new Map()
for (const pos of QUIET) refs.set(pos.id, await reference(refEngine, fenOf(pos)))
const forcedRefs = new Map()
for (const pos of FORCED) forcedRefs.set(pos.id, await reference(refEngine, fenOf(pos)))
refEngine.quit()

const result = {
  hasNew,
  strong: await strongPath(),
  weak: await Promise.all(WEAK.map((id) => weakBot(id, refs, forcedRefs))),
}
console.log(JSON.stringify(result))
process.exit(0)
