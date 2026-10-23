import { Link } from 'react-router-dom'
import { PUZZLE_MODES, type PuzzleMode } from '../lib/navigation'

// Sélecteur des trois modes de l'onglet Puzzles, en tête du puzzle classé, du menu du Rush et de
// l'accueil de Mats éclair : la sortie déterministe vers les modes voisins, même pour une page
// ouverte directement. Liens en `replace`, comme les onglets : ces trois pages sont des racines
// sœurs, le retour arrière ne fait pas la navette entre elles. Absent des écrans immersifs (série
// en cours, fiche d'un schéma), qui ont leur croix ou leur flèche.
// `div role="navigation"` plutôt que `<nav>` : même rôle pour les lecteurs d'écran, mais
// `nav a[aria-current]` reste réservé aux onglets de la navigation principale.
export function PuzzleModes({ current, className = '' }: { current: PuzzleMode['to']; className?: string }) {
  return (
    <div role="navigation" aria-label="Modes de puzzles" data-puzzle-modes className={`grid grid-cols-3 gap-1 rounded-xl bg-surface-2 p-1 ${className}`}>
      {PUZZLE_MODES.map((m) => {
        const active = m.to === current
        return (
          <Link
            key={m.to}
            to={m.to}
            replace
            aria-current={active ? 'page' : undefined}
            data-puzzle-mode={m.to.slice(1)}
            className={`flex min-h-11 items-center justify-center rounded-lg px-2 text-center text-sm leading-tight font-semibold transition ${
              active ? 'bg-accent/20 text-accent-light' : 'text-neutral-300 hover:bg-surface-3 hover:text-white'
            }`}
          >
            {m.label}
          </Link>
        )
      })}
    </div>
  )
}
