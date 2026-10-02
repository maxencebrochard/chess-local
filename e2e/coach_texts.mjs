// Harnais texte du coach, lancé par `test_coach.py` : construit des GameReview à la main
// (méthode du harnais QA), fait parler `coachComments`, `coachSummary`, `coachQuip` et
// `liveComment`, et imprime un JSON que la suite Python vérifie.
//
//   node e2e/coach_texts.mjs <bundle.mjs>
//
// Le bundle est produit par rolldown depuis `e2e/coach_texts_entry.ts`. Aucun moteur ici :
// les classes et le meilleur coup sont annotés à la main, comme les aurait donnés le bilan.
import { pathToFileURL } from 'node:url'

// engine.ts lit `location` au chargement du module : stub avant l'import.
globalThis.location = { href: '' }
const bundle = await import(pathToFileURL(process.argv[2]).href)
const { Chess, coachComments, coachSummary, coachQuip, liveComment, greeting, CLASS_META, winPct } = bundle

const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
// Chute de win% typique de chaque classe, quand le scénario ne la précise pas.
const DROP = { brilliant: 0, great: 0, best: 0, excellent: 2, good: 5, book: 0, inaccuracy: 8.5, mistake: 15, miss: 12, missedWin: 45, blunder: 30 }
const cpFromWin = (w) => {
  const x = Math.min(99.9, Math.max(0.1, w))
  return Math.round(-Math.log(2 / ((x - 50) / 50 + 1) - 1) / 0.00368208)
}

// ann[i] clairsemé : { cls, best (SAN), mate (point de vue blanc, après le coup), wb, wa }.
// Défaut : 'best', meilleur coup = coup joué.
function mkReview(startFen, sanList, ann = {}) {
  const sans = typeof sanList === 'string' ? sanList.replace(/\d+\.(\.\.)?/g, ' ').trim().split(/\s+/) : sanList
  const c = new Chess(startFen)
  const startTurn = c.turn()
  const moves = []
  let wbRun = 50
  sans.forEach((san, i) => {
    const a = ann[i] ?? {}
    const cls = a.cls ?? 'best'
    let bestUci
    if (a.best) {
      const t = new Chess(c.fen())
      const b = t.move(a.best)
      bestUci = b.from + b.to + (b.promotion ?? '')
    }
    const mover = c.turn()
    const mv = c.move(san)
    const uci = mv.from + mv.to + (mv.promotion ?? '')
    const wb = a.wb ?? wbRun
    const wa = a.wa ?? Math.max(0, wb - DROP[cls])
    const whiteWin = mover === 'w' ? wa : 100 - wa
    moves.push({
      san: mv.san, uci, class: cls,
      evalAfterCp: c.isCheckmate() ? (mover === 'w' ? 10000 : -10000) : cpFromWin(whiteWin),
      mateAfter: c.isCheckmate() ? 0 : (a.mate ?? null),
      bestMoveUci: bestUci ?? uci,
      winPctBefore: wb, winPctAfter: wa,
    })
    wbRun = 100 - wa
  })
  const colorAt = (i) => ((i % 2 === 0) === (startTurn === 'w') ? 'w' : 'b')
  const counts = { w: {}, b: {} }
  for (const k of Object.keys(CLASS_META)) { counts.w[k] = 0; counts.b[k] = 0 }
  const series = [moves.length ? (startTurn === 'w' ? moves[0].winPctBefore : 100 - moves[0].winPctBefore) : 50]
  moves.forEach((x) => series.push(winPct(x.evalAfterCp)))
  const accs = { w: [], b: [] }
  moves.forEach((x, i) => {
    const col = colorAt(i)
    counts[col][x.class]++
    const drop = Math.max(0, x.winPctBefore - x.winPctAfter)
    accs[col].push(Math.max(0, Math.min(100, 103.1668 * Math.exp(-0.04354 * drop) - 3.1669)))
  })
  const mean = (xs) => (xs.length ? xs.reduce((p, q) => p + q, 0) / xs.length : 100)
  const acc = (col) => Math.round(mean(accs[col]) * 10) / 10
  return {
    moves, startFen: new Chess(startFen).fen(), startTurn,
    accuracyWhite: acc('w'), accuracyBlack: acc('b'), counts,
    gameRatingWhite: 1500, gameRatingBlack: 1500, winPctSeries: series,
  }
}

const book = (n, rest = {}) => {
  const o = { ...rest }
  for (let i = 0; i < n; i++) o[i] = { cls: 'book' }
  return o
}

// Partie de référence de la mission : mat en 7 coups, 7.Fe2 autorise ♞f3#.
const REF = '1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#'
const REF_ANN = book(6, {
  6: { cls: 'mistake', best: 'Nxd4', wb: 60, wa: 48 },
  7: { cls: 'best', wb: 52, wa: 52 },
  8: { cls: 'blunder', best: 'Bxf7+', wb: 48, wa: 5 },
  9: { cls: 'great', wb: 95, wa: 97 },
  // 6.♖f1 et 6...♛xe4+ : pas de mat forcé (7.♕e2 tient), le moteur ne l'annonce donc pas.
  10: { cls: 'best', wb: 3, wa: 3 },
  11: { cls: 'best', wb: 97, wa: 97 },
  12: { cls: 'mistake', best: 'Qe2', wb: 3, wa: 0, mate: -1 },
})
// Mat de Legal : 5...Fxd1 prend la dame mais autorise le mat en 2.
const LEGAL = '1. e4 e5 2. Nf3 d6 3. Bc4 Bg4 4. Nc3 g6 5. Nxe5 Bxd1 6. Bxf7+ Ke7 7. Nd5#'
const LEGAL_ANN = book(6, {
  6: { cls: 'good', best: 'd4' },
  7: { cls: 'mistake', best: 'Nf6' },
  8: { cls: 'brilliant', wb: 60, wa: 78 },
  9: { cls: 'blunder', best: 'dxe5', wb: 22, wa: 0, mate: 2 },
  10: { cls: 'best', mate: 1 },
  11: { cls: 'best', mate: 1 },
})
// Dame pendue au 2e coup : accord féminin.
const QHANG = '1. e4 d5 2. Qg4 Bxg4 3. exd5 Qxd5 4. Nc3 Qe5+ 5. Be2 Bxe2 6. Ngxe2 Nc6'
const QHANG_ANN = book(2, { 2: { cls: 'blunder', best: 'exd5', wb: 53, wa: 4 }, 6: { cls: 'good', best: 'Nf3' } })

// Marche aléatoire déterministe (LCG) : partie longue sans théorie, classes variées.
function randomGame(plies, seed) {
  let s = seed >>> 0
  const rnd = () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296 }
  const c = new Chess()
  const sans = []
  const ann = {}
  for (let i = 0; i < plies && !c.isGameOver(); i++) {
    const legal = c.moves({ verbose: true })
    // Préférer les coups non capturants pour garder du matériel et durer 120 demi-coups.
    const quiet = legal.filter((m) => !m.captured)
    const pool = quiet.length && rnd() < 0.85 ? quiet : legal
    const mv = pool[Math.floor(rnd() * pool.length)]
    // Un « meilleur coup » différent du coup joué pour les classes non optimales.
    const other = legal.find((m) => m.san !== mv.san)
    const k = i % 9
    ann[i] = k === 4 ? { cls: 'excellent', best: other?.san } : k === 7 ? { cls: 'good', best: other?.san } : { cls: 'best' }
    if (!ann[i].best) delete ann[i].best
    c.move(mv.san)
    sans.push(mv.san)
  }
  return { sans, ann }
}

// Couleur au trait au demi-coup i (le joueur ou son adversaire).
const colorAtOf = (review, i) => ((i % 2 === 0) === (review.startTurn === 'w') ? 'w' : 'b')

function scenario(label, fen, sans, ann, pc) {
  const review = mkReview(fen, sans, ann)
  const comments = coachComments(review, pc)
  return {
    label, playerColor: pc, plies: review.moves.length,
    sans: review.moves.map((m) => m.san),
    classes: review.moves.map((m) => m.class),
    comments: comments.map((c) => ({
      i: c.moveIndex, san: review.moves[c.moveIndex].san, cls: review.moves[c.moveIndex].class,
      own: pc === null || colorAtOf(review, c.moveIndex) === pc,
      headline: c.headline, body: c.body, severity: c.severity, mood: c.mood ?? null,
    })),
    summary: coachSummary(review, pc),
    quip: coachQuip(review, pc),
  }
}

const out = { scenarios: [], live: [], greetings: [] }
out.scenarios.push(scenario('ref_w', START, REF, REF_ANN, 'w'))
out.scenarios.push(scenario('ref_b', START, REF, REF_ANN, 'b'))
out.scenarios.push(scenario('ref_local', START, REF, REF_ANN, null))
out.scenarios.push(scenario('legal_b', START, LEGAL, LEGAL_ANN, 'b'))
out.scenarios.push(scenario('legal_w', START, LEGAL, LEGAL_ANN, 'w'))
out.scenarios.push(scenario('qhang_w', START, QHANG, QHANG_ANN, 'w'))
out.scenarios.push(scenario('qhang_b', START, QHANG, QHANG_ANN, 'b'))
out.scenarios.push(scenario('mate2', '7k/8/6K1/5Q2/8/8/8/8 w - - 0 1', 'Qa5 Kg8 Qd8#',
  { 0: { cls: 'excellent', best: 'Qf8#', wb: 100, wa: 100, mate: 2 } }, 'w'))
out.scenarios.push(scenario('qtrade', 'r2q2k1/5ppp/8/8/8/8/5PPP/R2QR1K1 w - - 0 1', 'Qb3 Qd2 Rf1',
  { 0: { cls: 'inaccuracy', best: 'Qxd8+', wb: 97, wa: 89 }, 2: { cls: 'mistake', best: 'Qb7', wb: 89, wa: 74 } }, 'w'))
out.scenarios.push(scenario('stalemate', '7k/8/6K1/5Q2/8/8/8/8 w - - 0 1', 'Qf7',
  { 0: { cls: 'missedWin', best: 'Qf8#', wb: 100, wa: 50 } }, 'w'))
// FEN custom, trait aux Noirs, compteur de coups à 4 : numéro du coup pivot (COACH-11).
out.scenarios.push(scenario('custom_black', 'r1bqkbnr/pp1p1ppp/2n5/1N2p3/4P3/5N2/PPPP1PPP/R1BQKB1R b KQkq - 0 4', 'Qf6 d3 a6 Nc3',
  { 0: { cls: 'blunder', best: 'd6', wb: 45, wa: 12 }, 1: { cls: 'miss', best: 'Nc7+', wb: 88, wa: 60 }, 3: { cls: 'miss', best: 'Nc7+', wb: 88, wa: 58 } }, 'w'))
const long = randomGame(120, 20260925)
out.scenarios.push(scenario('long', START, long.sans, long.ann, null))

// ---- Coach live ----
function livePath(label, sans, playerColor, clsOf) {
  const c = new Chess()
  const uci = []
  const rows = []
  sans.split(' ').forEach((san, i) => {
    const mover = c.turn()
    const mv = c.move(san)
    uci.push(mv.from + mv.to + (mv.promotion ?? ''))
    const cls = clsOf(i, mv, c)
    const r = liveComment({ san: mv.san, moverColor: mover, byPlayer: mover === playerColor, cls, uciMoves: [...uci] })
    rows.push({ label, i, san: mv.san, byPlayer: mover === playerColor, cls, text: r?.text ?? null, headline: r?.headline ?? null, mood: r?.mood ?? null })
  })
  return rows
}
out.live.push(...livePath('italian', 'e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6', 'w', () => 'book'))
out.live.push(...livePath('nf3', 'Nf3 d5', 'w', () => 'book'))
out.live.push(...livePath('botfirst', 'e4 e5', 'b', () => 'book'))
out.live.push(...livePath('blunder', 'e4 e5 Qh5 Nc6 Qxf7+', 'w', (i) => (i === 2 ? 'blunder' : i === 4 ? 'mistake' : 'good')))
out.live.push(...livePath('mate', 'e4 e5 Bc4 Nc6 Qh5 Nf6 Qxf7#', 'w', (i, mv, c) => (c.isCheckmate() ? 'best' : i === 5 ? 'blunder' : 'good')))
out.live.push(...livePath('botcheck', 'e4 d5 exd5 Qxd5 Nc3 Qe5+', 'w', (i) => (i === 5 ? 'good' : 'excellent')))
out.live.push(...livePath('botblunder', 'e4 e5 Nf3 f6 Nxe5 fxe5', 'w', (i) => (i === 3 ? 'blunder' : i === 4 ? 'best' : i === 5 ? 'mistake' : 'good')))
for (let i = 0; i < 12; i++) out.greetings.push(greeting().text)

process.stdout.write(JSON.stringify(out))
