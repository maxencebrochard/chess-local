// Répertoire d'ouvertures du joueur : extrait des parties archivées les lignes
// réellement jouées, pour les drills « Apprendre → Ouvertures ».
import { Chess } from 'chess.js'
import { db } from './db'
import { openingForMoves } from './openings'
import openingsData from '../data/openings.json'

export interface DrillLine {
  eco: string
  name: string
  uci: string[] // ligne complète à driller
  playerColor: 'w' | 'b'
  timesPlayed: number
  losses: number
}

const ALL_OPENINGS = openingsData as { eco: string; name: string; uci: string }[]

// Lignes classiques de repli quand l'archive est maigre.
const CLASSICS = ['Italian Game', 'Ruy Lopez', 'Sicilian Defense', 'French Defense', 'Queen\'s Gambit', 'London System', 'Caro-Kann Defense', 'Scandinavian Defense']

export async function buildDrillLines(minMoves = 6): Promise<DrillLine[]> {
  const games = await db.games.toArray()
  const byOpening = new Map<string, DrillLine>()

  for (const g of games) {
    if (g.mode !== 'bot') continue
    try {
      const c = new Chess()
      c.loadPgn(g.pgn)
      const uci = c.history({ verbose: true }).map((m) => m.lan)
      if (uci.length < minMoves) continue
      const opening = openingForMoves(uci)
      if (!opening) continue
      const key = `${opening.eco}|${g.playerColor}`
      const lost = g.result !== '1/2-1/2' && (g.result === '1-0') !== (g.playerColor === 'w')
      const entry = byOpening.get(key)
      if (entry) {
        entry.timesPlayed++
        if (lost) entry.losses++
      } else {
        byOpening.set(key, {
          eco: opening.eco,
          name: opening.name,
          uci: opening.uci.split(' '),
          playerColor: g.playerColor,
          timesPlayed: 1,
          losses: lost ? 1 : 0,
        })
      }
    } catch {
      continue
    }
  }

  // Priorité : les plus perdues, puis les plus jouées.
  const mine = [...byOpening.values()]
    .filter((l) => l.uci.length >= minMoves)
    .sort((a, b) => b.losses - a.losses || b.timesPlayed - a.timesPlayed)

  if (mine.length >= 4) return mine

  // Complément classique.
  const classics: DrillLine[] = []
  for (const name of CLASSICS) {
    const o = ALL_OPENINGS.filter((x) => x.name.startsWith(name) && x.uci.split(' ').length >= minMoves)
      .sort((a, b) => a.uci.length - b.uci.length)[0]
    if (o && !mine.some((m) => m.eco === o.eco)) {
      classics.push({ eco: o.eco, name: o.name, uci: o.uci.split(' '), playerColor: 'w', timesPlayed: 0, losses: 0 })
    }
  }
  return [...mine, ...classics]
}
