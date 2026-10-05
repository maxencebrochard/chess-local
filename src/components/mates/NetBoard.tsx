// Réseau de mat dessiné : échiquier figé avec les flèches (rouge : l'échec, couleurs : les lignes
// tenues par chaque pièce), les cases de fuite teintées de la couleur de la pièce qui les couvre,
// les cases bloquées grisées, et la légende qui nomme le rôle de chaque pièce.
import { useMemo } from 'react'
import { Board } from '../Board'
import { analyseMate, netView, principleOf } from '../../lib/mateNet'

interface NetBoardProps {
  fen: string
  orientation?: 'w' | 'b' // défaut : le camp qui mate en bas
  legend?: boolean
  principle?: string // principe imposé (fiche) ; sinon celui déduit de la position
}

export function NetBoard({ fen, orientation, legend = true, principle }: NetBoardProps) {
  const net = useMemo(() => analyseMate(fen), [fen])
  const view = useMemo(() => (net ? netView(net, fen) : null), [net, fen])
  const side = orientation ?? (net ? (net.mated === 'w' ? 'b' : 'w') : 'w')
  return (
    <div data-net={net ? net.tags.join(' ') || 'aucune' : 'aucun'} className="flex flex-col gap-2">
      <Board fen={fen} orientation={side} interactive={false} arrows={view?.arrows} markSquares={view?.marks} />
      {legend && net && view && <NetLegend principle={principle ?? principleOf(net)} view={view} />}
    </div>
  )
}

export function NetLegend({ principle, view }: { principle: string; view: ReturnType<typeof netView> }) {
  return (
    <div className="space-y-1.5 text-sm leading-snug">
      {principle && <p className="font-bold text-neutral-100">{principle}</p>}
      <ul className="space-y-1">
        {view.pieces.map((p) => (
          <li key={p.square} data-net-piece={p.square} className="flex gap-2 text-neutral-300">
            <span
              aria-hidden
              className="mt-1 h-3 w-3 shrink-0 rounded-full"
              // Pièce qui donne l'échec : cerclée du rouge de la flèche d'échec.
              style={{ backgroundColor: p.color, boxShadow: p.checking ? '0 0 0 2px rgb(220, 38, 38)' : undefined }}
            />
            <span>{p.sentence}</span>
          </li>
        ))}
        {view.blocked && (
          <li className="flex gap-2 text-neutral-400">
            <span aria-hidden className="mt-1 h-3 w-3 shrink-0 rounded-full bg-black/60 ring-1 ring-neutral-600" />
            <span>{view.blocked}</span>
          </li>
        )}
      </ul>
    </div>
  )
}
