// État « Aller plus loin » d'un exercice-puzzle : index d'avancement dans la solution, calque
// EngineContinuation ouvert, et leur survie à un aller-retour vers l'analyseur (sessionStorage).
// Ne touche ni au score ni au verdict de l'exercice.
import { useState } from 'react'
import type { PuzzleData } from './PuzzlePlayer'
import {
  fenAfter, isTerminal, recallContinuation, rememberOverlay, rememberStep,
  type ContinuationMode, type ContinuationOverlay,
} from '../lib/continuation'

// `verdict` : l'exercice est monté directement dans sa phase de verdict (séance restaurée).
export function useExerciseContinuation(owner: string, verdict: boolean) {
  // Lecture non destructive : StrictMode rejoue cet initialiseur.
  const [recalled] = useState(() => recallContinuation(owner, !verdict))
  const [step, setStep] = useState<number | null>(recalled.step)
  const [overlay, setOverlay] = useState<ContinuationOverlay | null>(recalled.overlay)

  return {
    step,
    overlay,
    // Index du prochain coup attendu, remonté par PuzzlePlayer.onStep pendant la phase de jeu.
    recordStep(s: number) {
      setStep(s)
      rememberStep(owner, s)
    },
    open(mode: ContinuationMode, startFen: string) {
      setOverlay({ mode, startFen, moves: [] })
    },
    close() {
      setOverlay(null)
      rememberOverlay(owner, null)
    },
    // Juste avant de partir vers l'analyseur : le calque se rouvrira au retour.
    leave(o: ContinuationOverlay) {
      rememberOverlay(owner, o)
    },
  }
}

// Position où l'exercice s'est arrêté, ou null s'il n'y a rien à prolonger :
// réussi = fin de la solution ; raté = position où le joueur devait jouer (avant son coup faux).
// Un raté sans index connu (séance restaurée sans trace) n'a pas de position fiable.
export function puzzleContinuationStart(puzzle: PuzzleData, step: number | null, success: boolean): string | null {
  const end = success ? (step ?? puzzle.moves.length) : step
  if (end === null) return null
  const fen = fenAfter(puzzle.fen, puzzle.moves, end)
  return isTerminal(fen) ? null : fen
}

// Camp du joueur d'un puzzle lichess : l'adversaire joue le coup d'amorce.
export function puzzlePlayerColor(puzzle: PuzzleData): 'w' | 'b' {
  return puzzle.fen.split(' ')[1] === 'w' ? 'b' : 'w'
}
