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

// Modes de l'onglet Puzzles (lot 6 du plan UX) : trois racines sœurs, reliées par le sélecteur
// `PuzzleModes` en tête de chacune. `/puzzles` reste le puzzle classé : l'activité quotidienne de
// l'onglet s'ouvre sans geste de plus, et les anciennes URL rendent toujours la même page.
export interface PuzzleMode {
  to: '/puzzles' | '/rush' | '/mats'
  label: string
}

export const PUZZLE_MODES: PuzzleMode[] = [
  { to: '/puzzles', label: 'Classés' },
  { to: '/rush', label: 'Rush' },
  { to: '/mats', label: 'Mats éclair' },
]

// Apprendre (lot 5 du plan UX) : un hub guidé, avec des sous-pages routées plutôt qu'un dépliage
// sur place. Une route garde le retour arrière, le lien direct et le rechargement ; chaque page
// d'une activité connaît la sienne pour son retour (`PageHeader`), même ouverte directement.
export const LESSONS_ROOT = '/apprendre/lecons'
export const TRAINING_ROOT = '/apprendre/entrainement'
export const REVIEW_ROOT = '/apprendre/mes-parties'
export const MOMENTS_ROOT = '/apprendre/moments-critiques'

/** Domaine d'une séance d'Apprendre, lancée depuis un groupe (`state.domain` de `/apprendre`). */
export type SessionDomain = 'tactic' | 'endgame' | 'opening' | 'strategy'

export type TrainingSlug = 'tactique' | 'attaque-defense' | 'finales' | 'ouvertures' | 'strategie'

export interface TrainingItem {
  label: string
  description: string
  icon: string
  /** Page de l'activité ; absent pour une séance, qui s'ouvre sur `/apprendre`. */
  to?: string
  /** State de descente : seul le raccourci Mats éclair en porte un (retour vers le groupe). */
  state?: { from: TrainingSlug }
  session?: SessionDomain
  testId?: string
}

export interface TrainingGroup {
  slug: TrainingSlug
  title: string
  objective: string
  icon: string
  /** Seule information de progression du groupe : classement d'un domaine ou positions réussies. */
  progress: SessionDomain | 'positions'
  items: TrainingItem[]
  /** Cours de « Toutes les leçons » qui expliquent ce que le groupe entraîne (raccourcis). */
  lessons: { to: string; label: string; icon: string }[]
}

// Les cinq groupes de compétences, dans l'ordre du hub. Les noms des activités sont ceux de leurs
// pages (titre affiché à l'arrivée) ; « Finales au chrono » est conservé (décision de Max).
export const TRAINING_GROUPS: TrainingGroup[] = [
  {
    slug: 'tactique',
    title: 'Tactique et calcul',
    objective: 'Trouver le coup qui gagne, calculer et visualiser la suite',
    icon: '💡',
    progress: 'tactic',
    items: [
      { session: 'tactic', label: 'Séance de tactique', description: "Trois puzzles d'un même motif, adaptés à ton niveau", icon: '⚡' },
      { to: '/visualisation', label: 'Calcul et visualisation', description: 'Imagine la ligne sans bouger les pièces, puis réponds', icon: '🧠' },
      { to: '/mats', state: { from: 'tactique' }, label: 'Mats éclair', description: 'Mater vite : contre la montre, mat en N, géométrie, motifs', icon: '♚' },
    ],
    lessons: [],
  },
  {
    slug: 'attaque-defense',
    title: 'Attaque et défense',
    objective: "Mener l'attaque sur le roi, tenir sous la pression, convertir l'avantage",
    icon: '⚔️',
    progress: 'positions',
    items: [
      { to: '/attaque', label: "Entraîneur d'attaque", description: "Roques opposés, même aile, roi au centre : mène l'attaque au bout", icon: '⚔️' },
      { to: '/defense', label: 'Entraîneur de défense', description: "Tiens face à l'attaque sur ton roi", icon: '🛡️' },
      { to: '/convertir', label: "Convertir l'avantage", description: 'Tu es mieux de +2 à +4 : gagne la partie sans la laisser filer', icon: '🏆' },
    ],
    lessons: [
      { to: '/apprendre/roque', label: 'Démolir le roque', icon: '🔥' },
      { to: '/apprendre/defense', label: "Tenir sous l'attaque", icon: '🛡️' },
    ],
  },
  {
    slug: 'finales',
    title: 'Finales',
    objective: 'Connaître les finales clés et les conclure contre Stockfish',
    icon: '🏁',
    progress: 'endgame',
    items: [
      { session: 'endgame', label: 'Séance de finales', description: 'Une finale théorique à gagner ou à tenir, à ton niveau', icon: '🎯' },
      { to: '/finales', label: "Jouer une finale jusqu'au bout", description: 'Contre Stockfish, sans limite de coups', icon: '🏁' },
      { to: '/finales/chrono', label: 'Finales au chrono', description: 'Lucena, Philidor, roi et pion : gagne ou tiens la nulle à la pendule', icon: '⏱', testId: 'endgame-clock-card' },
    ],
    lessons: [{ to: '/apprendre/finales', label: 'Cours de finales', icon: '📚' }],
  },
  {
    slug: 'ouvertures',
    title: 'Ouvertures',
    objective: 'Connaître tes lignes et savoir où tu sors de la théorie',
    icon: '📖',
    progress: 'opening',
    items: [
      { session: 'opening', label: "Séance d'ouvertures", description: "Déroule les premiers coups d'une ouverture sans te tromper", icon: '🎯' },
      { to: '/ouvertures', label: "Entraîneur d'ouvertures", description: 'Sicilienne, écossaise, gambit dame… variante par variante', icon: '🧭' },
      { to: '/repertoire', label: 'Mon répertoire', description: 'Où tu sors de la théorie dans tes parties chess.com', icon: '🗺️' },
    ],
    lessons: [],
  },
  {
    slug: 'strategie',
    title: 'Stratégie',
    objective: 'Choisir un plan et lire la structure de pions',
    icon: '♟️',
    progress: 'strategy',
    items: [
      { session: 'strategy', label: 'Séance de stratégie', description: "Une idée de plan, puis deux positions pour l'appliquer", icon: '🎯' },
      { to: '/structures', label: 'Mes structures de pions', description: 'Pion isolé, Carlsbad, chaînes… dans tes parties : résultats et positions à rejouer', icon: '🔎', testId: 'my-structures-tile' },
    ],
    lessons: [{ to: '/apprendre/structures', label: 'Structures de pions', icon: '♟️' }],
  },
]

export const groupPath = (slug: TrainingSlug) => `${TRAINING_ROOT}/${slug}`

export function trainingGroup(slug: string | undefined): TrainingGroup | undefined {
  return TRAINING_GROUPS.find((g) => g.slug === slug)
}

/** Retour d'en-tête : destination et libellé (« Retour à <label> »). */
export interface BackTarget {
  to: string
  label: string
}

/** Retour vers un groupe d'Entraînement, propriétaire de la page. */
export function groupBack(slug: TrainingSlug): BackTarget {
  return { to: groupPath(slug), label: trainingGroup(slug)!.title }
}

export const LEARN_BACK: BackTarget = { to: '/apprendre', label: 'Apprendre' }
export const LESSONS_BACK: BackTarget = { to: LESSONS_ROOT, label: 'Toutes les leçons' }
export const TRAINING_BACK: BackTarget = { to: TRAINING_ROOT, label: 'Entraînement' }
export const REVIEW_BACK: BackTarget = { to: REVIEW_ROOT, label: 'Réviser mes parties' }

/** Groupe d'origine porté par un state de descente (`{ from }`), sinon undefined. */
export function originGroup(state: unknown): TrainingSlug | undefined {
  const from = (state as { from?: unknown } | null)?.from
  return typeof from === 'string' ? trainingGroup(from)?.slug : undefined
}
