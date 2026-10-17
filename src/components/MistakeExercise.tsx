// Rejoue la position d'avant une faute (table `mistakes`) : le joueur doit trouver mieux. Le
// meilleur coup ou un mat concluent tout de suite ; tout autre coup est jugé par Stockfish (bon
// s'il ne perd presque rien de win% face au meilleur). Partagé par Apprendre → Mes erreurs et
// la révision espacée. Après le verdict, « Pourquoi ? » déroule la réfutation de la faute
// (RefutationPlayer).
import { useMemo, useRef, useState } from 'react'
import { Chess } from 'chess.js'
import { Board } from './Board'
import { RefutationPlayer } from './RefutationPlayer'
import type { Mistake } from '../lib/db'
import type { Engine } from '../lib/engine'
import { figurine, winPct } from '../lib/review'

interface Props {
  mistake: Mistake
  active: boolean // le joueur peut jouer (pas de verdict rendu)
  onFinish: (success: boolean) => void // appelé une seule fois
  getEngine: () => Engine
}

export function MistakeExercise({ mistake, active, onFinish, getEngine }: Props) {
  const [fen] = useState(mistake.fenBefore)
  const [checking, setChecking] = useState(false)
  const finished = useRef(false)
  const [why, setWhy] = useState(false)
  const moverColor: 'w' | 'b' = new Chess(fen).turn()
  // Coup fautif en UCI, relu depuis la SAN enregistrée (une sauvegarde abîmée ne casse rien).
  const playedUci = useMemo(() => {
    try {
      const mv = new Chess(mistake.fenBefore).move(mistake.playedSan)
      return mv.lan === mistake.bestUci ? null : mv.lan
    } catch {
      return null
    }
  }, [mistake.fenBefore, mistake.playedSan, mistake.bestUci])

  function handleMove(from: string, to: string, promotion?: string): boolean {
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
      onFinish(true)
      return true
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
      onFinish(wBefore - wAfter < 5)
    })()
    return true
  }

  return (
    <div className="flex flex-col gap-2 px-3">
      {/* Après le verdict, le bouton remplace la consigne sur la même ligne : la hauteur ne change pas. */}
      <div className="flex min-h-8 items-center justify-center gap-2 rounded bg-surface-2 px-3 py-1 text-center text-sm">
        <span className="min-w-0">
          <span className="font-semibold">{mistake.gameLabel}</span> : tu avais joué{' '}
          <span className="font-bold text-red-400">{figurine(mistake.playedSan, moverColor)}</span>.{active ? ' Trouve mieux.' : ''}
        </span>
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
        <div className="boardbox md:w-[min(56vh,520px)]">
          <Board fen={fen} orientation={moverColor} interactive={active && !checking} movableColor={moverColor} onMove={handleMove} />
        </div>
      </div>
      {why && playedUci && (
        <RefutationPlayer fenBefore={mistake.fenBefore} playedUci={playedUci} bestUci={mistake.bestUci} orientation={moverColor} onClose={() => setWhy(false)} />
      )}
    </div>
  )
}
