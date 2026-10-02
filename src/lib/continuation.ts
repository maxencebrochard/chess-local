// Logique sans React du prolongement d'un exercice (« Aller plus loin ») : position atteinte
// par une ligne de coups, fin de partie, évaluation côté blanc, persistance de l'aller-retour
// vers l'analyseur. Utilisée par EngineContinuation et ses points d'entrée (Apprendre).
import { Chess } from 'chess.js'
import type { EngineLine } from './engine'

// Joue les coups UCI sur une copie de `fen`. Retourne la partie atteinte et les coups
// effectivement joués (arrêt au premier coup illégal ou absent).
export function playUci(fen: string, uci: string[]): { chess: Chess; played: string[] } {
  const chess = new Chess(fen)
  const played: string[] = []
  for (const m of uci) {
    if (!m || m.length < 4 || chess.isGameOver()) break
    try {
      chess.move({ from: m.slice(0, 2), to: m.slice(2, 4), promotion: m[4] })
    } catch {
      break
    }
    played.push(m)
  }
  return { chess, played }
}

// Position atteinte après les `count` premiers coups d'une ligne UCI.
export function fenAfter(fen: string, uci: string[], count: number): string {
  return playUci(fen, uci.slice(0, count)).chess.fen()
}

export function isTerminal(fen: string): boolean {
  return new Chess(fen).isGameOver()
}

// Phrase de fin de partie du point de vue du joueur, ou null si la partie continue.
export function endText(chess: Chess, playerColor: 'w' | 'b'): string | null {
  if (!chess.isGameOver()) return null
  if (chess.isCheckmate()) return chess.turn() === playerColor ? 'Échec et mat, Stockfish gagne' : 'Échec et mat, tu gagnes !'
  if (chess.isStalemate()) return 'Nulle par pat'
  if (chess.isThreefoldRepetition()) return 'Nulle par triple répétition'
  if (chess.isInsufficientMaterial()) return 'Nulle par matériel insuffisant'
  return 'Nulle par la règle des 50 coups'
}

// Évaluation d'une ligne moteur (scores du point de vue du trait) ramenée côté blanc.
export function whiteEval(line: EngineLine | undefined, turn: 'w' | 'b'): { cp: number | null; mate: number | null } {
  if (!line) return { cp: null, mate: null }
  const sign = turn === 'w' ? 1 : -1
  if (line.scoreMate !== null) return { cp: null, mate: line.scoreMate * sign }
  return { cp: line.scoreCp === null ? null : line.scoreCp * sign, mate: null }
}

// Évaluation affichée sur une position déjà terminée (mat : barre pleine du côté gagnant).
export function terminalEval(chess: Chess): { cp: number | null; mate: number | null } {
  if (chess.isCheckmate()) return { cp: chess.turn() === 'w' ? -1 : 1, mate: 0 }
  return { cp: 0, mate: null }
}

// ---------- Aller-retour vers l'analyseur ----------
// Une seule entrée par onglet : l'exercice propriétaire (clé stable), l'index d'avancement du
// puzzle, et le calque ouvert au moment de partir vers l'analyseur. Lecture non destructive
// (StrictMode rejoue les initialiseurs) ; l'appelant efface le calque quand il se ferme.

export type ContinuationMode = 'play' | 'plan'

export interface ContinuationOverlay {
  mode: ContinuationMode
  startFen: string // position de départ du prolongement
  moves: string[] // coups UCI joués depuis startFen (mode jouer)
  resigned?: boolean // partie abandonnée avant le départ vers l'analyseur
}

interface Stash {
  owner: string
  step: number | null
  overlay: ContinuationOverlay | null
}

const KEY = 'engine-continuation-v1'

function readStash(owner: string): Stash | null {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (!raw) return null
    const s = JSON.parse(raw) as Stash
    return s.owner === owner ? s : null
  } catch {
    return null
  }
}

function writeStash(s: Stash) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(s))
  } catch {}
}

// `fresh` : l'exercice démarre (phase de leçon ou de jeu), toute trace est périmée et effacée.
// Seul un exercice restauré dans sa phase de verdict relit l'index et le calque.
export function recallContinuation(owner: string, fresh: boolean): { step: number | null; overlay: ContinuationOverlay | null } {
  if (fresh) {
    try {
      sessionStorage.removeItem(KEY)
    } catch {}
    return { step: null, overlay: null }
  }
  const s = readStash(owner)
  return { step: s?.step ?? null, overlay: s?.overlay ?? null }
}

export function rememberStep(owner: string, step: number | null) {
  const s = readStash(owner)
  writeStash({ owner, step, overlay: s?.overlay ?? null })
}

export function rememberOverlay(owner: string, overlay: ContinuationOverlay | null) {
  const s = readStash(owner)
  writeStash({ owner, step: s?.step ?? null, overlay })
}
