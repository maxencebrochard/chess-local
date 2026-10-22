// Pendule du joueur seul, pour les séries contre la montre (Mats éclair, Finales au chrono) : elle
// ne tourne qu'à son trait, le temps de réflexion du moteur n'est pas compté.
// Prémouvement : 100 ms débitées avant le coup, comme Play (règle chess.com, voir CLAUDE.md) ; si
// le temps tombe à zéro, le drapeau tombe sans jouer. Incrément : ajouté après chaque coup.
import { useEffect, useRef, useState } from 'react'

export const PREMOVE_COST_MS = 100
const TICK_MS = 100

export interface PlayerClock {
  left: number // temps restant affiché (ms)
  remaining: () => number // temps restant exact, hors rendu
  running: () => boolean
  start: () => void // au trait du joueur
  stop: () => number // à son coup : fige le temps restant, rend le temps consommé depuis start
  reset: (ms: number) => void // position suivante, pendule pleine et arrêtée
  expired: () => boolean // drapeau tombé entre deux ticks (coup arrivé trop tard)
  debitPremove: () => boolean // pendule arrêtée (après stop) ; false : le débit fait tomber le drapeau
  addIncrement: (ms: number) => void
}

// `onFlag` est appelé à chaque tick où la pendule en marche est à zéro : l'appelant l'arrête.
export function usePlayerClock(initialMs: number, onFlag: () => void): PlayerClock {
  const [left, setLeft] = useState(initialMs)
  const leftRef = useRef(initialMs)
  const deadline = useRef<number | null>(null)
  const startedAt = useRef(0)
  const flag = useRef(onFlag)
  useEffect(() => {
    flag.current = onFlag
  })

  useEffect(() => {
    const tick = () => {
      if (deadline.current === null) return
      const l = Math.max(0, deadline.current - Date.now())
      setLeft(l)
      if (l === 0) flag.current()
    }
    const id = setInterval(tick, TICK_MS)
    // Retour au premier plan : le drapeau tombé pendant l'arrière-plan se lit tout de suite.
    document.addEventListener('visibilitychange', tick)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', tick)
    }
  }, [])

  function stop(): number {
    let spent = 0
    if (deadline.current !== null) {
      const now = Date.now()
      leftRef.current = Math.max(0, deadline.current - now)
      spent = now - startedAt.current
    }
    deadline.current = null
    setLeft(leftRef.current)
    return spent
  }

  return {
    left,
    remaining: () => leftRef.current,
    running: () => deadline.current !== null,
    start() {
      startedAt.current = Date.now()
      deadline.current = startedAt.current + leftRef.current
    },
    stop,
    reset(ms) {
      deadline.current = null
      leftRef.current = ms
      setLeft(ms)
    },
    expired: () => deadline.current !== null && Date.now() >= deadline.current,
    debitPremove() {
      leftRef.current = Math.max(0, leftRef.current - PREMOVE_COST_MS)
      setLeft(leftRef.current)
      return leftRef.current > 0
    },
    addIncrement(ms) {
      if (ms <= 0) return
      leftRef.current += ms
      setLeft(leftRef.current)
    },
  }
}
