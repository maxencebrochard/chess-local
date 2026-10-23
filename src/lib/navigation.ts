// Destinations de l'onglet Plus, partagées par le hub `/plus` et la sous-liste de la nav latérale.
// Réglages et Mes données restent des sections de `/stats` jusqu'au lot 3 du plan UX : le state
// `section` y fait défiler la page jusqu'au bon titre (lu puis effacé par Stats).
import type { NavIconName } from '../components/NavIcon'

export type StatsSection = 'reglages' | 'donnees'

export interface PlusDestination {
  to: string
  label: string
  /** Libellé de la sous-liste de la nav latérale, étroite (176 px), si différent. */
  short?: string
  description: string
  icon: NavIconName
  section?: StatsSection
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
      { to: '/stats', section: 'reglages', label: 'Réglages', description: 'Échiquier, pièces, sons, prémouvements et bilan', icon: 'reglages' },
      { to: '/stats', section: 'donnees', label: 'Mes données', description: 'Sauvegarder, restaurer ou réinitialiser l’app', icon: 'donnees' },
    ],
  },
]

export const PLUS_DESTINATIONS = PLUS_GROUPS.flatMap((g) => g.items)

/** Racines rattachées à l'onglet Plus (sous-chemins compris, `/analyse/jouer` par exemple). */
export const PLUS_MATCH = ['/archive', '/import', '/analyse', '/insights', '/stats']

/** Une destination sans section est sélectionnée sur son chemin et ses sous-chemins. */
export function isSelected(d: PlusDestination, pathname: string): boolean {
  return !d.section && (pathname === d.to || pathname.startsWith(`${d.to}/`))
}
