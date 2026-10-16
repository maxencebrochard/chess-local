// Choix de l'Elo de l'adversaire bridé des entraîneurs d'attaque et de défense (Stockfish limité
// par UCI_Elo, « Max » = pleine force) : grille de pastilles, une seule cochée.
import { LEVELS, type Level } from '../lib/attack'

export const LEVEL_HELP = 'Stockfish bridé à cet Elo : il joue moins précisément, mais jamais au hasard comme les bots faibles. Max : pleine force.'

export function LevelPicker({ value, onChange, label }: { value: Level; onChange: (l: Level) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="grid grid-cols-5 gap-1.5">
      {LEVELS.map((l) => {
        const on = l === value
        return (
          <button
            key={l ?? 'max'}
            role="radio"
            aria-checked={on}
            data-level={l ?? 'max'}
            onClick={() => onChange(l)}
            className={`min-h-10 cursor-pointer rounded-lg px-1 text-sm font-bold tabular-nums ${
              on ? 'bg-accent text-white' : 'bg-surface-3 text-neutral-300 hover:bg-surface-3/70'
            }`}
          >
            {l ?? 'Max'}
          </button>
        )
      })}
    </div>
  )
}
