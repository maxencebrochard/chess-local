// Rejoue la position d'avant une faute (table `mistakes`) : le joueur doit trouver mieux. Le
// meilleur coup ou un mat concluent tout de suite ; tout autre coup est jugé par Stockfish (bon
// s'il ne perd presque rien de win% face au meilleur). Partagé par Apprendre → Mes erreurs et
// la révision espacée. Après le verdict, « Pourquoi ? » déroule la réfutation de la faute
// (RefutationPlayer). En mode `bare` (habillage commun d'exercice d'Apprendre et de la révision),
// seul l'échiquier est rendu : consigne, vérification et « Pourquoi ? » passent par le
// propriétaire (`MistakeConsigne`, `onChecking`, `refutedUci` de lib/refutation.ts).
import { useMemo, useRef, useState } from 'react'
import { Chess, type Move } from 'chess.js'
import { Board } from './Board'
import { RefutationPlayer } from './RefutationPlayer'
import type { Mistake } from '../lib/db'
import type { Engine } from '../lib/engine'
import { refutedUci } from '../lib/refutation'
import { figurine, winPct } from '../lib/review'

interface Props {
  mistake: Mistake
  active: boolean // le joueur peut jouer (pas de verdict rendu)
  // Appelé une seule fois ; `best` : le coup joué est celui de Stockfish (ou un mat).
  onFinish: (success: boolean, info: { best: boolean }) => void
  getEngine: () => Engine
  bare?: boolean
  onChecking?: (checking: boolean) => void
}

// Consigne de l'exercice : la partie, le coup joué alors, et la demande.
export function MistakeConsigne({ mistake, active }: { mistake: Mistake; active: boolean }) {
  const moverColor: 'w' | 'b' = new Chess(mistake.fenBefore).turn()
  return (
    <>
      <span className="font-semibold">{mistake.gameLabel}</span> : tu avais joué{' '}
      <span className="font-bold text-red-400">{figurine(mistake.playedSan, moverColor)}</span>.{active ? ' Trouve mieux.' : ''}
    </>
  )
}

export function MistakeExercise({ mistake, active, onFinish, getEngine, bare = false, onChecking }: Props) {
  const [fen] = useState(mistake.fenBefore)
  const [checking, setCheckingState] = useState(false)
  const setChecking = (v: boolean) => {
    setCheckingState(v)
    onChecking?.(v)
  }
  const finished = useRef(false)
  const [why, setWhy] = useState(false)
  const moverColor: 'w' | 'b' = new Chess(fen).turn()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const playedUci = useMemo(() => refutedUci(mistake), [mistake.fenBefore, mistake.playedSan, mistake.bestUci])

  function handleMove(from: string, to: string, promotion?: string): Move | false {
    if (!active || checking || finished.current) return false
    const c = new Chess(fen)
    let mv
    try {
      mv = c.move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    const played = mv.from + mv.to + (mv.promotion ?? '')
    if (played === mistake.bestUci || c.isCheckmate()) {
      finished.current = true
      onFinish(true, { best: true })
      return mv
    }
    setChecking(true)
    void (async () => {
      const engine = getEngine()
      // Le coup joué est bon s'il ne perd presque rien face au meilleur.
      const before = await engine.search({ fen, depth: 12, multipv: 1 })
      const after = await engine.search({ fen: c.fen(), depth: 12, multipv: 1 })
      const cp = (l?: { scoreMate: number | null; scoreCp: number | null }) =>
        l ? (l.scoreMate !== null ? (l.scoreMate > 0 ? 10000 : -10000) : (l.scoreCp ?? 0)) : 0
      const wBefore = winPct(cp(before.lines[0]))
      const wAfter = winPct(-cp(after.lines[0]))
      finished.current = true
      setChecking(false)
      onFinish(wBefore - wAfter < 5, { best: false })
    })()
    return mv
  }

  const board = <Board fen={fen} orientation={moverColor} interactive={active && !checking} movableColor={moverColor} onMove={handleMove} />
  if (bare) return board

  return (
    <div className="flex flex-col gap-2 px-3">
      {/* Après le verdict, le bouton remplace la consigne sur la même ligne : la hauteur ne change pas. */}
      <div className="flex min-h-8 items-center justify-center gap-2 rounded bg-surface-2 px-3 py-1 text-center text-sm">
        <span className="min-w-0"><MistakeConsigne mistake={mistake} active={active} /></span>
        {!active && playedUci && (
          <button
            onClick={() => setWhy(true)}
            className="shrink-0 cursor-pointer rounded bg-surface-3 px-2 py-0.5 text-sm font-bold text-neutral-100 hover:bg-surface-3/70"
          >
            💡 Pourquoi{'\u00a0'}?
          </button>
        )}
      </div>
      {checking && <p className="text-center text-sm text-neutral-400">Je vérifie…</p>}
      <div className="flex justify-center">
        <div className="boardbox md:w-[min(56vh,520px)]">{board}</div>
      </div>
      {why && playedUci && (
        <RefutationPlayer fenBefore={mistake.fenBefore} playedUci={playedUci} bestUci={mistake.bestUci} orientation={moverColor} onClose={() => setWhy(false)} />
      )}
    </div>
  )
}
