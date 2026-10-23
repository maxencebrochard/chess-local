// Accueil quotidien : quelle action proposer en premier, combien de révisions dues la séance du jour
// reprend déjà, et l'activité de la semaine. Pur (sans React, Dexie ni stockage) : Home.tsx lit les
// sources, ce module décide. Exécuté aussi sous Node par la suite E2E `accueil`.
//
// Aucun second ordonnanceur : la séance du jour reste seule à choisir ses blocs (seance.ts,
// seanceRun.ts). L'accueil n'en lit que ce qui est sûr sans charger puzzles.json : la séance en
// cours, la série de jours et la règle `revisionBlockSize` des révisions qu'une nouvelle séance reprend.
import { addDays, startOfDay } from './days'
import { BLOCK_META, type BlockKind } from './seance'

// Séance du jour en cours (sessionStorage), telle que Seance.tsx la reprend à son montage.
export interface SeanceResume {
  idx: number // étape courante, 0 pour la première
  total: number
  kind: BlockKind // type de l'étape courante
  pendingRevisions: string[] // révisions pas encore jugées, clés `<kind>:<key>` de la file de révision
}

// Partie de Jouer en cours (localStorage), telle que Play.tsx la reprend à son montage.
export interface GameResume {
  mode: 'bot' | 'local' | 'coach'
  botName: string | null
  color: 'w' | 'b'
  tcLabel: string
  plies: number
}

export type HomePrimary =
  | { kind: 'resume-seance'; seance: SeanceResume }
  | { kind: 'resume-game'; game: GameResume }
  | { kind: 'seance' } // séance du jour à faire
  | { kind: 'quick' } // séance du jour déjà faite aujourd'hui : séance rapide d'Apprendre
  | { kind: 'pending' } // aucune reprise, série de jours pas encore lue

// Priorité déterministe du plan UX : une reprise que sa page sait restaurer (la séance du jour avant
// la partie, qui reste à un geste par le raccourci Jouer), sinon la séance du jour, sinon, une fois
// celle-ci faite, la séance rapide existante.
export function homePrimary(input: { seance: SeanceResume | null; game: GameResume | null; doneToday: boolean | null }): HomePrimary {
  if (input.seance) return { kind: 'resume-seance', seance: input.seance }
  if (input.game) return { kind: 'resume-game', game: input.game }
  if (input.doneToday === null) return { kind: 'pending' }
  return input.doneToday ? { kind: 'quick' } : { kind: 'seance' }
}

// Révisions dues déjà comptées par la séance du jour : celles pas encore jugées de la séance en
// cours ; sinon, tant que la séance du jour n'est pas faite, celles qu'une nouvelle séance
// reprendrait (`fresh` : buildReviewSession de la file due, revisionBlockSize éléments). Séance
// faite ou série inconnue : aucune.
export function revisionsInSeance(input: { due: string[]; seance: SeanceResume | null; doneToday: boolean | null; fresh: string[] }): string[] {
  const claimed = new Set(input.seance ? input.seance.pendingRevisions : input.doneToday === false ? input.fresh : [])
  return input.due.filter((k) => claimed.has(k))
}

const plural = (n: number, one: string, many: string) => `${n} ${n > 1 ? many : one}`

// Ligne secondaire « À réviser aujourd'hui » : la quantité totale n'est affichée qu'ici ; la part
// reprise par la séance est nommée comme telle, jamais ajoutée une seconde fois. `kinds` décrit par
// type les éléments à détailler : tous quand la séance les reprend tous ou n'en reprend aucun,
// sinon les seuls éléments hors séance (« 2 puzzles · 1 faute »).
export function revisionLine(total: number, inSeance: number, kinds: string): string {
  if (inSeance <= 0) return kinds
  if (inSeance >= total) return `${total > 1 ? 'Toutes dans ta séance du jour' : 'Dans ta séance du jour'} : ${kinds}`
  return `${inSeance} dans ta séance du jour, en plus : ${kinds}`
}

export function seanceStepLabel(s: SeanceResume): string {
  return `Étape ${s.idx + 1} sur ${s.total} · ${BLOCK_META[s.kind].label}`
}

export function gameTitle(g: GameResume): string {
  if (g.mode === 'coach') return 'Partie avec le coach'
  if (g.mode === 'local') return 'Partie à deux'
  return g.botName ? `Partie contre ${g.botName}` : 'Partie contre un bot'
}

export function gameMeta(g: GameResume): string {
  const parts = [g.tcLabel || null, `coup ${Math.floor(g.plies / 2) + 1}`, g.mode === 'local' ? null : `tu as les ${g.color === 'w' ? 'Blancs' : 'Noirs'}`]
  return parts.filter(Boolean).join(' · ')
}

// Lundi 0 h, heure locale, de la semaine de `now`.
export function weekStart(now: number): number {
  const today = startOfDay(now)
  return addDays(today, -((new Date(today).getDay() + 6) % 7))
}

// Activité de la semaine, sans chiffre de classement : séances menées au bilan, puzzles classés
// réussis, parties terminées contre un bot ou à deux.
export function weekSummary(w: { seances: number; puzzles: number; games: number }): string {
  const parts = [
    w.seances > 0 ? plural(w.seances, 'séance', 'séances') : null,
    w.puzzles > 0 ? plural(w.puzzles, 'puzzle réussi', 'puzzles réussis') : null,
    w.games > 0 ? plural(w.games, 'partie', 'parties') : null,
  ].filter((p): p is string => p !== null)
  return parts.length ? `Cette semaine : ${parts.join(' · ')}` : 'Rien encore cette semaine : ton bilan se remplit en jouant'
}
