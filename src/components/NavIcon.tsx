// Pictogrammes de la navigation et du hub Plus, dessinés pour ChessLocal (aucun jeu d'icônes repris).
// Même grille de 24 px, trait de 1,75 px aux bouts et angles arrondis, couleur héritée du texte
// (`currentColor`). Les formes marquées `data-fill` se remplissent légèrement quand l'onglet est
// actif (`.nav-icon-active`, index.css) : l'état ne repose pas que sur la couleur.
import type { ReactNode } from 'react'

export type NavIconName =
  | 'accueil' | 'jouer' | 'puzzles' | 'apprendre' | 'plus'
  | 'parties' | 'importer' | 'analyse' | 'bilan' | 'statistiques' | 'reglages' | 'donnees'
  | 'seance' | 'reviser'

const PATHS: Record<NavIconName, ReactNode> = {
  // Maison, porte en retrait.
  accueil: <path data-fill d="M4 10.25 12 3.75l8 6.5V19.5a1 1 0 0 1-1 1h-4v-5.75H9v5.75H5a1 1 0 0 1-1-1z" />,
  // Pion : tête, collerette, corps évasé, socle.
  jouer: <>
    <circle data-fill cx="12" cy="6.25" r="2.75" />
    <path data-fill d="M10.25 11.25c0 3.25-1.25 5.5-3 7.25h9.5c-1.75-1.75-3-4-3-7.25z" />
    <path d="M8.75 11.25h6.5M5.75 20.5h12.5" />
  </>,
  // Pièce de puzzle, tenons en haut et à droite.
  puzzles: <path data-fill d="M3.5 7.5H8a2.5 2.5 0 1 1 4 0h4.5V12a2.5 2.5 0 1 1 0 4v4.5h-13z" />,
  // Toque de diplômé, gland à droite.
  apprendre: <>
    <path data-fill d="M2.5 9.25 12 4.75l9.5 4.5-9.5 4.5z" />
    <path d="M6.5 11.25v4.5c0 1.5 2.5 2.75 5.5 2.75s5.5-1.25 5.5-2.75v-4.5M21.5 9.25v5" />
  </>,
  // Cercle et points de suspension.
  plus: <>
    <circle data-fill cx="12" cy="12" r="8.75" />
    <path d="M8 12h.01M12 12h.01M16 12h.01" strokeWidth="2.5" />
  </>,
  // Pile de parties : un échiquier de quatre cases devant un second.
  parties: <>
    <rect data-fill x="7.5" y="3.5" width="13" height="13" rx="1.5" />
    <path d="M4 7.5v11a2 2 0 0 0 2 2h11M14 3.5v13M7.5 10h13" />
  </>,
  // Flèche entrante dans un plateau.
  importer: <path d="M12 3.5v11m-4.25-4.25L12 14.5l4.25-4.25M4 14.5v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />,
  // Loupe.
  analyse: <>
    <circle data-fill cx="10.5" cy="10.5" r="6.5" />
    <path d="m15.25 15.25 5.25 5.25" />
  </>,
  // Courbe d'évaluation dans un cadre.
  bilan: <>
    <rect data-fill x="3.5" y="3.5" width="17" height="17" rx="2" />
    <path d="m7 15 3.25-4 3 2.5L17 8.5" />
  </>,
  // Histogramme.
  statistiques: <path d="M4 20.5h16M6.5 20.5V13M12 20.5V7.5M17.5 20.5V3.5" />,
  // Curseurs de réglage.
  reglages: <>
    <path d="M4 7h3.5m5 0H20M4 17h9.5m5 0H20" />
    <circle data-fill cx="10" cy="7" r="2.5" />
    <circle data-fill cx="16" cy="17" r="2.5" />
  </>,
  // Base de données : cylindre à trois couches.
  donnees: <>
    <ellipse data-fill cx="12" cy="6" rx="7.5" ry="2.75" />
    <path d="M4.5 6v12c0 1.5 3.25 2.75 7.5 2.75s7.5-1.25 7.5-2.75V6M4.5 12c0 1.5 3.25 2.75 7.5 2.75s7.5-1.25 7.5-2.75" />
  </>,
  // Accueil : séance du jour (soleil, disque et huit rayons).
  seance: <>
    <circle data-fill cx="12" cy="12" r="4" />
    <path d="M12 2.75v2M12 19.25v2M2.75 12h2M19.25 12h2M5.46 5.46l1.41 1.41M17.13 17.13l1.41 1.41M5.46 18.54l1.41-1.41M17.13 6.87l1.41-1.41" />
  </>,
  // Accueil : révision espacée (deux flèches en cercle).
  reviser: <>
    <path d="M19.5 12a7.5 7.5 0 0 1-13 5.1M4.5 12a7.5 7.5 0 0 1 13-5.1" />
    <path d="M17.5 3.25v3.85h-3.85M6.5 20.75V16.9h3.85" />
  </>,
}

export function NavIcon({ name, active = false, className = 'h-6 w-6' }: { name: NavIconName; active?: boolean; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      data-icon={name}
      className={`nav-icon shrink-0 ${active ? 'nav-icon-active' : ''} ${className}`}
    >
      {PATHS[name]}
    </svg>
  )
}
