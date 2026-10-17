// Harnais texte de la réfutation expliquée, lancé par `test_refutation.py` : fait parler
// `buildRefutation` sur des puzzles lichess (position, coup fautif de l'adversaire, puis la
// réfutation réelle du puzzle comme ligne du moteur) et sur des cas construits à la main, et
// imprime un JSON que la suite Python revérifie contre un oracle python-chess.
//
//   node e2e/refutation_texts.mjs <bundle.mjs> <puzzles.json>
import { readFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'

// engine.ts (importé par review.ts) lit `location` au chargement du module : stub avant l'import.
globalThis.location = { href: '' }
const B = await import(pathToFileURL(process.argv[2]).href)
const PUZZLES = JSON.parse(readFileSync(process.argv[3], 'utf8'))
const errors = []

function facts(f) {
  if (!f) return null
  return {
    uci: f.uci, san: f.san, color: f.color, piece: f.piece, forced: f.forced, kinds: B.factKinds(f), mate: f.mate, backRank: f.backRank, stalemate: f.stalemate, check: f.check,
    capture: f.capture && { kind: f.capture.kind, net: f.capture.net, clean: f.capture.clean, captured: f.capture.captured, square: f.capture.square },
    fork: f.fork ? f.fork.targets : null,
    line: f.line ? [f.line.kind, f.line.front, f.line.rear] : null,
    passed: f.passed ? f.passed.square : null,
    promotion: f.promotion, threat: f.threat,
  }
}

function dump(label, input) {
  let r = null
  try {
    r = B.buildRefutation(input)
  } catch (e) {
    errors.push(`${label}: ${String(e?.message ?? e).slice(0, 120)}`)
  }
  if (!r) return { label, input, ok: false }
  const step = (s) => ({ fenBefore: s.fenBefore, fenAfter: s.fenAfter, uci: s.uci, actor: s.actor, facts: facts(s.facts), text: s.text, material: s.material })
  return {
    label, input, ok: true, player: r.player, intro: r.intro, summary: r.summary,
    played: step(r.played), line: r.line.map(step),
    best: r.best && { uci: r.best.uci, fenAfter: r.best.fenAfter, facts: facts(r.best.facts), prevention: r.best.prevention, close: r.best.close, text: r.best.text },
  }
}

// Échantillon déterministe : un puzzle sur 60 (environ 2 000 lignes réelles).
const puzzles = []
for (let i = 0; i < PUZZLES.length; i += 60) {
  const [id, fen, moves, rating, themes] = PUZZLES[i]
  const uci = moves.split(' ')
  puzzles.push(dump(`puzzle ${id}`, { fenBefore: fen, playedUci: uci[0], pv: uci.slice(1), evalAfterPlayed: null }))
  void rating; void themes
}

// Cas à la main : le bon coup est connu, les évaluations sont fournies comme par le moteur.
const SCHOLAR = 'r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3'
const hand = [
  // 3...♞f6?? 4.♕xf7# ; le bon coup 3...♕e7 (ou g6) défend f7.
  dump('berger', { fenBefore: SCHOLAR, playedUci: 'g8f6', bestUci: 'g7g6', pv: ['h5f7'], evalAfterPlayed: { cp: null, mate: -1 }, evalAfterBest: { cp: -30, mate: null } }),
  dump('berger_e7', { fenBefore: SCHOLAR, playedUci: 'g8f6', bestUci: 'd8e7', pv: ['h5f7'], evalAfterPlayed: { cp: null, mate: -1 }, evalAfterBest: { cp: -45, mate: null } }),
  // Fourchette royale du cavalier : 1...♛c6?? 2.♘e7+ puis ♘xc6 gagne la dame.
  dump('fourchette', { fenBefore: '2q3k1/5ppp/8/3N4/8/8/5PPP/6K1 b - - 0 1', playedUci: 'c8c6', bestUci: 'c8c1', pv: ['d5e7', 'g8f8', 'e7c6', 'h7h6'], evalAfterPlayed: { cp: -900, mate: null }, evalAfterBest: { cp: null, mate: 1 } }),
  // Coup fautif qui pate : 1.♕f7?? pat, 1.♕e8# matait.
  dump('pat', { fenBefore: '7k/4Q3/6K1/8/8/8/8/8 w - - 0 1', playedUci: 'e7f7', bestUci: 'e7e8', pv: [], evalAfterPlayed: { cp: 0, mate: null }, evalAfterBest: null }),
  // Ligne vide (moteur sans suite) et éval nulle.
  dump('pv_vide', { fenBefore: SCHOLAR, playedUci: 'a7a6', bestUci: 'g7g6', pv: [], evalAfterPlayed: null }),
  // PV qui contient un coup illégal : la ligne s'arrête avant.
  dump('pv_illegale', { fenBefore: SCHOLAR, playedUci: 'g8f6', pv: ['h5h8', 'e8e7'], evalAfterPlayed: null }),
  // Le moteur, plus profond que le bilan, juge le coup joué aussi bon : pas de « bon coup » affirmé.
  dump('proche', { fenBefore: SCHOLAR, playedUci: 'g7g6', bestUci: 'd8e7', pv: ['h5f3', 'g8f6'], evalAfterPlayed: { cp: -20, mate: null }, evalAfterBest: { cp: -40, mate: null } }),
  // Échange coupé au 8e demi-coup puis repris : la ligne s'allonge de la reprise.
  dump('echange', { fenBefore: 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1', playedUci: 'e2e4', pv: ['d7d5', 'e4d5', 'd8d5', 'b1c3', 'd5a5', 'd2d4', 'c7c6', 'c1d2', 'a5b6'], evalAfterPlayed: { cp: 30, mate: null } }),
  dump('echange_coupe', { fenBefore: 'r3k3/8/8/3p4/8/8/8/3RK2R w - - 0 1', playedUci: 'h1h2', pv: ['e8f7', 'h2h7', 'f7g6', 'h7h4', 'g6f5', 'h4h8', 'f5e4', 'd1d5', 'e4d5', 'h8a8'], evalAfterPlayed: { cp: 30, mate: null } }),
  // La reprise devient légale, même si gagner une dame contre une tour reste avantageux.
  dump('reprise_possible', { fenBefore: 'q1k5/7p/8/8/8/8/7K/R7 b - - 0 1', playedUci: 'h7h6', bestUci: 'c8b8', pv: ['a1a8'], evalAfterPlayed: null }),
  dump('prise_inchangee', { fenBefore: 'q1k5/7p/8/8/8/8/7K/R7 b - - 0 1', playedUci: 'h7h6', bestUci: 'h7h5', pv: ['a1a8'], evalAfterPlayed: null }),
  dump('fourchette_evitee', { fenBefore: '2q3k1/5ppp/8/3N4/8/8/5PPP/6K1 b - - 0 1', playedUci: 'c8c6', bestUci: 'c8c7', pv: ['d5e7'], evalAfterPlayed: null }),
  dump('fourchette_conservee', { fenBefore: '6k1/2q2ppp/8/3N4/8/8/5PPP/6K1 b - - 0 1', playedUci: 'c7c6', bestUci: 'c7c8', pv: ['d5e7'], evalAfterPlayed: null }),
  // Une tour d'avance reste une tour d'avance : variation nulle ne veut pas dire égalité.
  dump('materiel_inegal', { fenBefore: '4k3/8/8/8/8/8/8/4K2R w - - 0 1', playedUci: 'h1h2', pv: ['e8f7', 'h2h3', 'f7g6', 'h3h4'], evalAfterPlayed: null }),
  // Coup joué illégal : pas de réfutation.
  dump('illegal', { fenBefore: SCHOLAR, playedUci: 'e1e2', pv: [], evalAfterPlayed: null }),
]

const scores = [
  ['cp', B.scoreForPlayer({ scoreCp: 120, scoreMate: null })],
  ['mate_contre', B.scoreForPlayer({ scoreCp: null, scoreMate: 2 })],
  ['mate_pour', B.scoreForPlayer({ scoreCp: null, scoreMate: -3 })],
].map(([k, s]) => ({ k, s, text: s ? B.scoreText(s) : null }))

process.stdout.write(JSON.stringify({ puzzles, hand, scores, errors, minPlies: B.MIN_PLIES, maxPlies: B.MAX_PLIES }))
