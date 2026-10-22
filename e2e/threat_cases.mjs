// Harnais de la détection de menace, lancé par `test_menace.py` : fait tourner la VRAIE
// `findThreat` de `src/lib/threat.ts` sur le VRAI Stockfish WASM de l'app (voir
// `scripts/bots-node.mjs`), et imprime un JSON que la suite Python revérifie avec python-chess.
//
//   node e2e/threat_cases.mjs <cases.json> <sortie.json>
//
// cases.json : [{ id, fenPrev, lastUci }]. Pour chaque cas : le veto sans moteur, chaque recherche
// faite (FEN, score du point de vue du trait, ligne principale), la menace annoncée, et le
// jugement pur `judgeThreat` rejoué sur ces mêmes scores (il doit redonner la même menace).
import { readFileSync, writeFileSync } from 'node:fs'
import { loadApp } from '../scripts/bots-node.mjs'

const app = await loadApp('e2e/threat_entry.ts')
const { Engine, findThreat, judgeThreat, quickVeto, nullMoveFen, playLine, materialGain } = app
const cases = JSON.parse(readFileSync(process.argv[2], 'utf8'))
const engine = new Engine()
const searches = []
const search = engine.search.bind(engine)
engine.search = async (opts) => {
  const res = await search(opts)
  const line = res.lines[0]
  searches.push({ fen: opts.fen, depth: opts.depth, cp: line?.scoreCp ?? null, mate: line?.scoreMate ?? null, pv: line?.pv ?? [] })
  return res
}

const out = []
const errors = []
for (const k of cases) {
  searches.length = 0
  try {
    const setup = quickVeto(k.fenPrev, k.lastUci)
    const veto = typeof setup === 'string' ? setup : null
    const threat = await findThreat(engine, k.fenPrev, k.lastUci)
    const done = [...searches]
    const byFen = (fen) => done.find((s) => s.fen === fen)
    let rejudged = null
    if (!veto) {
      const now = byFen(setup.fen)
      const nul = byFen(setup.nullFen)
      const prev = byFen(k.fenPrev)
      if (now && nul) {
        rejudged = judgeThreat({
          fenPrev: k.fenPrev, lastUci: k.lastUci,
          prev: prev ? { cp: prev.cp, mate: prev.mate } : null,
          now: { cp: now.cp, mate: now.mate },
          nul: { cp: nul.cp, mate: nul.mate },
          pv: nul.pv,
        })
      }
    }
    out.push({
      id: k.id, veto, fen: veto ? null : setup.fen, nullFen: veto ? null : setup.nullFen,
      nullFenDirect: veto ? null : nullMoveFen(setup.fen), searches: done, threat, rejudged,
    })
  } catch (e) {
    errors.push(`${k.id}: ${String(e?.message ?? e).slice(0, 160)}`)
  }
}
// Ligne observée en production : le second pion pris en d5 est repris au coup suivant.
// La coupure à cinq demi-coups ne doit pas transformer un pion gagné en menace majeure.
const pawn = cases.find((c) => c.id === 'pion')
const pawnSetup = quickVeto(pawn.fenPrev, pawn.lastUci)
const pawnPv = ['f3e5', 'd7d5', 'd2d4', 'g8f6', 'e4d5', 'd8d5']
const horizon = {
  gain: materialGain(playLine(pawnSetup.nullFen, pawnPv)),
  threat: judgeThreat({ ...pawn, prev: null, now: { cp: -38, mate: null }, nul: { cp: 140, mate: null }, pv: pawnPv }),
}
engine.quit()
// Fichier et non stdout : `process.exit` couperait un tube encore plein.
writeFileSync(process.argv[3], JSON.stringify({ cases: out, errors, horizon }))
process.exit(0)
