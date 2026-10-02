// Harnais texte du coach, lancé par `test_coach.py` : construit des GameReview à la main
// (méthode du harnais QA), fait parler `coachComments`, `coachSummary`, `coachQuip` et
// `liveComment`, et imprime un JSON que la suite Python vérifie.
//
//   node e2e/coach_texts.mjs <bundle.mjs> <puzzles.json>
//
// Le bundle est produit par rolldown depuis `e2e/coach_texts_entry.ts`. Aucun moteur ici :
// les classes et le meilleur coup sont annotés à la main, comme les aurait donnés le bilan.
import { readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'

// engine.ts lit `location` au chargement du module : stub avant l'import.
globalThis.location = { href: '' }
const bundle = await import(pathToFileURL(process.argv[2]).href)
const { Chess, coachComments, coachSummary, coachQuip, liveComment, greeting, CLASS_META, winPct } = bundle
const PUZZLES = JSON.parse(readFileSync(process.argv[3], 'utf8'))
// Un détecteur absent ou à l'ancienne signature ne doit pas faire tomber tout le harnais :
// la suite doit pouvoir montrer QUELS checks échouent (preuve d'échec).
const errors = []
const safe = (fn) => { try { return fn() } catch (e) { errors.push(String(e?.message ?? e).slice(0, 120)); return null } }
const det = (name, ...args) => safe(() => (typeof bundle[name] === 'function' ? bundle[name](...args) : null))

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
    let bestUci = a.bestUci
    if (!bestUci && a.best) {
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

// Positions avant/après chaque demi-coup, pour que l'oracle python revérifie chaque motif annoncé.
function fensOf(review) {
  const c = new Chess(review.startFen)
  const out = [c.fen()]
  review.moves.forEach((m) => { c.move(m.san); out.push(c.fen()) })
  return out
}

function scenario(label, fen, sans, ann, pc) {
  const review = mkReview(fen, sans, ann)
  const t0 = performance.now()
  const comments = coachComments(review, pc)
  const ms = performance.now() - t0
  const fens = fensOf(review)
  return {
    ms,
    label, playerColor: pc, plies: review.moves.length,
    sans: review.moves.map((m) => m.san),
    classes: review.moves.map((m) => m.class),
    comments: comments.map((c) => ({
      i: c.moveIndex, san: review.moves[c.moveIndex].san, cls: review.moves[c.moveIndex].class,
      own: pc === null || colorAtOf(review, c.moveIndex) === pc,
      headline: c.headline, body: c.body, severity: c.severity, mood: c.mood ?? null,
      fenBefore: fens[c.moveIndex], fenAfter: fens[c.moveIndex + 1], uci: review.moves[c.moveIndex].uci,
      bestUci: review.moves[c.moveIndex].bestMoveUci, replyUci: review.moves[c.moveIndex + 1]?.bestMoveUci ?? null,
      mover: colorAtOf(review, c.moveIndex),
    })),
    summary: coachSummary(review, pc),
    phases: safe(() => bundle.phaseReport(review)),
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
// quickClass : « meilleur » réservé au pv[0] du moteur ; seuils alignés sur review.ts (3,5 / 7 / 10 / 20).
const cpForDrop = (d) => cpFromWin(50 - d)
out.quick = {
  noBest: safe(() => bundle.quickClass(0, 0, false, false)),
  best: safe(() => bundle.quickClass(0, 0, false, true)),
  drop3: safe(() => bundle.quickClass(0, cpForDrop(3), false, false)),
  drop5: safe(() => bundle.quickClass(0, cpForDrop(5), false, false)),
  drop8: safe(() => bundle.quickClass(0, cpForDrop(8), false, false)),
  drop15: safe(() => bundle.quickClass(0, cpForDrop(15), false, false)),
  drop25: safe(() => bundle.quickClass(0, cpForDrop(25), false, false)),
}


// ---- Détecteurs sur positions réelles : puzzles lichess, chaque coup de la ligne ----
// La suite python compare chaque résultat à l'oracle python-chess (e2e/coach_oracle.py).
const STEP_DET = 160
out.detectors = []
for (let k = 0; k < PUZZLES.length; k += STEP_DET) {
  const [id, fen, moves, , themes] = PUZZLES[k]
  const c = new Chess(fen)
  moves.split(' ').forEach((u, j) => {
    const pre = c.fen()
    const f = det('fork', pre, u)
    const l = det('pinOrSkewer', pre, u)
    out.detectors.push({
      id, j, fen: pre, uci: u, themes, fork: f ? f.targets : null, line: l ? [l.kind, l.front, l.rear] : null,
      br: !!det('backRankMate', pre, u), pp: !!det('passedPawn', pre, u),
    })
    c.move({ from: u.slice(0, 2), to: u.slice(2, 4), promotion: u[4] })
  })
}
// Cas étiquetés à la main (positifs et négatifs), indépendants de lichess.
const HAND = [
  ['fourchette royale ♘c7+', 'r3k3/8/8/1N6/8/8/8/4K3 w - - 0 1', 'b5c7', { fork: ['k', 'r'] }],
  ['cavalier prenable : pas de fourchette', 'rb2k3/8/8/1N6/8/8/8/4K3 w - - 0 1', 'b5c7', { fork: null }],
  ['clouage absolu ♗b5', '4k3/8/2n5/8/8/8/8/4KB2 w - - 0 1', 'f1b5', { line: ['clouage', 'n', 'k'] }],
  ['clouage relatif ♗g2 (cavalier sur la tour)', 'r3k3/1n6/8/8/8/8/8/4KB2 w - - 0 1', 'f1g2', { line: ['clouage', 'n', 'r'] }],
  ['recul sur la même diagonale : clouage déjà là', '4k3/8/2n5/1B6/8/8/8/4K3 w - - 0 1', 'b5a4', { line: null }],
  ['glissade sur la même diagonale : clouage déjà là', '4k3/8/2n5/8/B7/8/8/4K3 w - - 0 1', 'a4b5', { line: null }],
  ['enfilade roi-dame ♖a8+', '4k2q/8/8/8/8/8/8/R3K3 w - - 0 1', 'a1a8', { line: ['enfilade', 'k', 'q'] }],
  ['enfilade sur un fou défendu : rien à gagner', '4k2b/5n2/8/8/8/8/8/R3K3 w - - 0 1', 'a1a8', { line: null }],
  ['mat du couloir ♖a8#', '6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1', 'a1a8', { br: true }],
  ['mat étouffé : pas un mat du couloir', '6rk/6pp/8/6N1/8/8/8/6K1 w - - 0 1', 'g5f7', { br: false }],
  ['pion passé créé par cxd5', '8/8/8/3p4/2P5/8/8/4K2k w - - 0 1', 'c4d5', { pp: true }],
  ['pion déjà passé : rien de créé', '8/8/8/8/2P5/8/8/4K2k w - - 0 1', 'c4c5', { pp: false }],
  ['pion passé aussitôt pris : rien de créé', '8/8/8/3p4/2P5/8/8/3rK2k w - - 0 1', 'c4d5', { pp: false }],
]
out.hand = HAND.map(([label, fen, uci, want]) => {
  const f = det('fork', fen, uci)
  const l = det('pinOrSkewer', fen, uci)
  return {
    label, fen, uci, want,
    got: { fork: f ? f.targets : null, line: l ? [l.kind, l.front, l.rear] : null, br: !!det('backRankMate', fen, uci), pp: !!det('passedPawn', fen, uci) },
  }
})

// ---- Le coach parle sur des positions réelles (puzzles) ----
// R1 « manqué » : le joueur (camp qui résout) joue un autre coup, le meilleur était la solution.
// R2 « autorisé » : le joueur est le camp qui se trompe (moves[0]) ; la réponse adverse est la solution.
// R3 « joué » : le joueur résout, chaque coup est le meilleur.
const uciOf = (mv) => mv.from + mv.to + (mv.promotion ?? '')
function sanFrom(fen, uci) {
  const c = new Chess(fen)
  return c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] }).san
}
function legalUcis(fen) {
  return new Chess(fen).moves({ verbose: true }).map(uciOf).sort()
}
function after(fen, uci) {
  const c = new Chess(fen)
  c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
  return c.fen()
}
function auditRows(label, review, pc) {
  const comments = safe(() => coachComments(review, pc)) ?? []
  const fens = fensOf(review)
  return comments.filter((c) => colorAtOf(review, c.moveIndex) === pc).map((c) => ({
    label, i: c.moveIndex, cls: review.moves[c.moveIndex].class, body: c.body, headline: c.headline,
    fenBefore: fens[c.moveIndex], fenAfter: fens[c.moveIndex + 1], uci: review.moves[c.moveIndex].uci,
    bestUci: review.moves[c.moveIndex].bestMoveUci, replyUci: review.moves[c.moveIndex + 1]?.bestMoveUci ?? null,
    mover: pc,
  }))
}
const STEP_REV = 200
out.puzzleComments = []
const tRev = performance.now()
for (let k = 0; k < PUZZLES.length; k += STEP_REV) {
  const [id, fen, moves, , themes] = PUZZLES[k]
  const ms = moves.split(' ')
  const th = themes.split(' ')
  const mateN = th.includes('mate') ? ms.length / 2 : 0
  const c0 = new Chess(fen)
  const opp = c0.turn()
  const solver = opp === 'w' ? 'b' : 'w'
  const sgn = (col) => (col === 'w' ? 1 : -1)
  const pos1 = after(fen, ms[0])
  const sans = []
  { const c = new Chess(fen); ms.forEach((u) => sans.push(c.move({ from: u.slice(0, 2), to: u.slice(2, 4), promotion: u[4] }).san)) }
  // R1
  const alts = legalUcis(pos1).filter((u) => u !== ms[1])
  if (alts.length) {
    const alt = alts[k % alts.length]
    const r1 = mkReview(fen, [sans[0], sanFrom(pos1, alt)], {
      0: { cls: 'best', mate: mateN ? sgn(solver) * mateN : undefined },
      1: { cls: 'mistake', bestUci: ms[1], wb: 90, wa: 70 },
    })
    out.puzzleComments.push(...auditRows(`R1 ${id}`, r1, solver))
  }
  // R2 : un « meilleur coup » qui ne laisse pas la solution comme motif (ou la rend illégale).
  const alts0 = legalUcis(fen).filter((u) => u !== ms[0])
  const prevent = alts0.find((u) => {
    const a = after(fen, u)
    if (!legalUcis(a).includes(ms[1])) return true
    return !det('fork', a, ms[1]) && !det('pinOrSkewer', a, ms[1]) && !new Chess(after(a, ms[1])).isCheckmate()
  })
  if (prevent) {
    const ann = { 0: { cls: 'blunder', bestUci: prevent, wb: 50, wa: 10, mate: mateN ? sgn(solver) * mateN : undefined } }
    for (let j = 1; j < ms.length; j++) {
      const left = ms.slice(j + 1).filter((_, q) => (j + 1 + q) % 2 === 1).length
      ann[j] = { cls: 'best', mate: mateN && left ? sgn(solver) * left : undefined }
    }
    const r2 = mkReview(fen, sans, ann)
    out.puzzleComments.push(...auditRows(`R2 ${id}`, r2, opp).filter((r) => r.i === 0))
  }
  // R3
  const ann3 = {}
  for (let j = 0; j < ms.length; j++) {
    const left = ms.slice(j + 1).filter((_, q) => (j + 1 + q) % 2 === 1).length
    ann3[j] = { cls: 'best', mate: mateN && left ? sgn(solver) * left : undefined }
  }
  out.puzzleComments.push(...auditRows(`R3 ${id}`, mkReview(fen, sans, ann3), solver))
}
out.puzzleReviewMs = performance.now() - tRev

// ---- Coach live sur positions réelles ----
const STEP_LIVE = 250
out.puzzleLive = []
for (let k = 0; k < PUZZLES.length; k += STEP_LIVE) {
  const [id, fen, moves, , themes] = PUZZLES[k]
  const ms = moves.split(' ')
  const mateN = themes.split(' ').includes('mate') ? ms.length / 2 : 0
  const c0 = new Chess(fen)
  const opp = c0.turn()
  const solver = opp === 'w' ? 'b' : 'w'
  const pos1 = after(fen, ms[0])
  const rows = []
  const say = (kind, uciMoves, byPlayer, moverColor, cls, extra) => {
    const fb = uciMoves.slice(0, -1).reduce((f, u) => after(f, u), fen)
    const uci = uciMoves[uciMoves.length - 1]
    const r = safe(() => liveComment({ san: sanFrom(fb, uci), moverColor, byPlayer, cls, uciMoves, startFen: fen, ...extra }))
    rows.push({ label: `${kind} ${id}`, kind, byPlayer, text: r?.text ?? null, body: r?.text ?? "", headline: r?.headline ?? null,
      fenBefore: fb, fenAfter: after(fb, uci), uci, bestUci: extra.bestUci ?? null, replyUci: extra.replyUci ?? null, mover: moverColor })
  }
  // Le joueur commet moves[0] (gaffe) ; le moteur voit la solution comme meilleure réponse.
  say('L-autorise', [ms[0]], true, opp, 'blunder', { replyUci: ms[1], mateFor: mateN ? -mateN : null })
  // Le bot joue la solution.
  say('L-bot', [ms[0], ms[1]], false, solver, 'best', { replyUci: ms[2] ?? null })
  // Le joueur joue la solution.
  say('L-joue', [ms[0], ms[1]], true, solver, 'best', { bestUci: ms[1], replyUci: ms[2] ?? null, mateFor: mateN > 1 ? mateN - 1 : null })
  // Le joueur joue autre chose alors que la solution était le meilleur coup.
  const alts = legalUcis(pos1).filter((u) => u !== ms[1])
  if (alts.length) say('L-manque', [ms[0], alts[k % alts.length]], true, solver, 'mistake', { bestUci: ms[1], replyUci: null })
  out.puzzleLive.push(...rows)
}

out.errors = errors
process.stdout.write(JSON.stringify(out))
