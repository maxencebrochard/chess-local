// Cadences proposées par l'écran Jouer. Hors de la page pour que la restauration d'une
// sauvegarde (backup.ts) valide `playTcLabel` sans importer un composant React.
import type { SavedGame } from './db'

export interface TimeControl {
  label: string
  baseMs: number | null // null = illimité
  incMs: number
  timeClass: SavedGame['timeClass']
}

export const TIME_CONTROLS: TimeControl[] = [
  { label: '1 min', baseMs: 60_000, incMs: 0, timeClass: 'bullet' },
  { label: '3 min', baseMs: 180_000, incMs: 0, timeClass: 'blitz' },
  { label: '3 | 2', baseMs: 180_000, incMs: 2000, timeClass: 'blitz' },
  { label: '5 min', baseMs: 300_000, incMs: 0, timeClass: 'blitz' },
  { label: '10 min', baseMs: 600_000, incMs: 0, timeClass: 'rapid' },
  { label: '15 | 10', baseMs: 900_000, incMs: 10_000, timeClass: 'rapid' },
  { label: '30 min', baseMs: 1_800_000, incMs: 0, timeClass: 'rapid' },
  { label: 'Illimité', baseMs: null, incMs: 0, timeClass: 'unlimited' },
]

export const UNLIMITED = TIME_CONTROLS.find((t) => t.timeClass === 'unlimited')!
