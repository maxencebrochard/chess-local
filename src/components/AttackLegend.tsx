// Légende du calque « Compte les attaquants », sous l'échiquier : une puce par roi (attaquants en
// rouge, défenseurs en vert, ▲ quand les attaquants dépassent les défenseurs) et le principe.
// Les comptes vivent ici et non sur l'échiquier : rien ne couvre les pièces.
import { useMemo } from 'react'
import { ATTACK_PRINCIPLE, attackCounts } from '../lib/kingAttack'

export const ATTACK_RED = '#ff7769'

// `compact` : le principe s'efface sous 700 px de haut (exercice : l'échiquier doit rester au-dessus
// de la barre d'actions) ; il reste dans le `title` des puces et dans la leçon.
// `principle` : repère affiché, celui de l'attaquant par défaut.
export function AttackLegend({ fen, className = '', compact = false, principle = ATTACK_PRINCIPLE }: { fen: string; className?: string; compact?: boolean; principle?: string }) {
  const counts = useMemo(() => attackCounts(fen), [fen])
  return (
    <div data-testid="attack-legend" className={`flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-neutral-400 ${className}`}>
      {(['w', 'b'] as const).map((side) => {
        const a = counts[side].attackers.length
        const d = counts[side].defenders.length
        const over = a > d
        return (
          <span
            key={side}
            data-testid="attack-count"
            data-side={side}
            data-attackers={a}
            data-defenders={d}
            data-over={over ? '1' : '0'}
            title={`Roi ${side === 'w' ? 'blanc' : 'noir'} : ${a} attaquant${a > 1 ? 's' : ''}, ${d} défenseur${d > 1 ? 's' : ''}`}
            className="inline-flex items-center gap-1.5 rounded-full bg-surface-2 px-2 py-0.5 font-semibold whitespace-nowrap text-neutral-200"
            style={over ? { boxShadow: `inset 0 0 0 1px ${ATTACK_RED}` } : undefined}
          >
            <span aria-hidden="true" className="text-sm leading-none">{side === 'w' ? '♔' : '♚'}</span>
            <span style={{ color: ATTACK_RED }}>⚔ {a}</span>
            <span className="text-accent">🛡 {d}</span>
            {over && <span style={{ color: ATTACK_RED }}>▲</span>}
          </span>
        )
      })}
      <span className={`min-w-0 ${compact ? '[@media(max-height:700px)]:hidden' : ''}`}>
        Repère : {principle.charAt(0).toLowerCase() + principle.slice(1)}
      </span>
    </div>
  )
}
