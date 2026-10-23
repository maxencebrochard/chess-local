// Destinations de l'onglet Plus, partagées par le hub `/plus` et la sous-liste de la nav latérale.
// Réglages et Mes données ont leurs pages depuis le lot 3 du plan UX (`/reglages`, `/donnees`) ;
// Stats renvoie encore vers elles les anciens states `section` et `backup`.
import type { NavIconName } from '../components/NavIcon'

export interface PlusDestination {
  to: string
  label: string
  /** Libellé de la sous-liste de la nav latérale, étroite (176 px), si différent. */
  short?: string
  description: string
  icon: NavIconName
}

export const PLUS_GROUPS: { title: string; items: PlusDestination[] }[] = [
  {
    title: 'Parties',
    items: [
      { to: '/archive', label: 'Mes parties', description: 'Tes parties contre les bots, à rejouer ou à analyser', icon: 'parties' },
      { to: '/import', label: 'Importer des parties', short: 'Importer', description: 'Tes parties chess.com, pour en lancer le bilan', icon: 'importer' },
    ],
  },
  {
    title: 'Outils et progression',
    items: [
      { to: '/analyse', label: 'Analyse', description: 'Stockfish 18 sur un échiquier libre, une partie ou une position', icon: 'analyse' },
      { to: '/insights', label: 'Mon bilan', description: 'Tes forces et tes faiblesses d’après tes dernières parties', icon: 'bilan' },
      { to: '/stats', label: 'Statistiques', description: 'Classements, résultats, attaques manquées et menaces', icon: 'statistiques' },
    ],
  },
  {
    title: 'Réglages et données',
    items: [
      { to: '/reglages', label: 'Réglages', description: 'Échiquier, pièces, sons, prémouvements et bilan', icon: 'reglages' },
      { to: '/donnees', label: 'Mes données', description: 'Sauvegarder, restaurer ou réinitialiser l’app', icon: 'donnees' },
    ],
  },
]

export const PLUS_DESTINATIONS = PLUS_GROUPS.flatMap((g) => g.items)

/** Racines rattachées à l'onglet Plus (sous-chemins compris, `/analyse/jouer` par exemple). */
export const PLUS_MATCH = ['/archive', '/import', '/analyse', '/insights', '/stats', '/reglages', '/donnees']

/** Une destination est sélectionnée sur son chemin et ses sous-chemins. */
export function isSelected(d: PlusDestination, pathname: string): boolean {
  return pathname === d.to || pathname.startsWith(`${d.to}/`)
}
