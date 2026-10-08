// Rejoue la position d'avant une faute (table `mistakes`) : le joueur doit trouver mieux. Le
// meilleur coup ou un mat concluent tout de suite ; tout autre coup est jugé par Stockfish (bon
// s'il ne perd presque rien de win% face au meilleur). Partagé par Apprendre → Mes erreurs et
// la révision espacée.
import { useRef, useState } from 'react'
import { Chess } from 'chess.js'
import { Board } from './Board'
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
  const moverColor: 'w' | 'b' = new Chess(fen).turn()

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
      <div className="rounded bg-surface-2 px-3 py-1.5 text-center text-sm">
        <span className="font-semibold">{mistake.gameLabel}</span> : tu avais joué{' '}
        <span className="font-bold text-red-400">{figurine(mistake.playedSan, moverColor)}</span>. Trouve mieux.
      </div>
      {checking && <p className="text-center text-sm text-neutral-400">Je vérifie…</p>}
      <div className="flex justify-center">
        <div className="boardbox md:w-[min(56vh,520px)]">
          <Board fen={fen} orientation={moverColor} interactive={active && !checking} movableColor={moverColor} onMove={handleMove} />
        </div>
      </div>
    </div>
  )
}
