// Entraîneur de défense (/defense) : banque de positions où le joueur subit une vraie attaque sur
// son roi mais peut tenir avec des coups précis (src/data/defenses.json, générée et vérifiée par
// scripts/prepare-defenses.py), niveau de l'attaquant, résultats des tentatives.
import { CATEGORY_LABEL, CATEGORY_ORDER, loadLevelFrom, saveLevelTo, type AttackCategory, type Level } from './attack'
import { db } from './db'
import type { Color, GameEnd, StoredGame } from './positionGame'
import defensesData from '../data/defenses.json'

export { CATEGORY_LABEL, CATEGORY_ORDER, type AttackCategory as DefenseCategory }

export interface DefensePosition {
  id: string // `def-<puzzle>`
  fen: string
  defender: Color // camp du joueur, au trait
  category: AttackCategory
  theme: string
  goal: string // consigne courte, vraie pour la position (faits calculés), vue du défenseur
  plan: string // trois à cinq phrases, chacune tirée d'un fait calculé
  eval: number // éval de sélection (Stockfish natif), centipions pour le défenseur : tri seulement
  source: { puzzle: string; game: string; ply: number; before: number }
}

export const DEFENSES = defensesData as DefensePosition[]

// ---------- Attaquant ----------

// Mêmes niveaux que l'entraîneur d'attaque, préférence à part : défendre contre 2100 par défaut.
export const DEFAULT_DEFENSE_LEVEL: Level = 2100
export const DEFENSE_PREFS_KEY = 'chess-local-defense'

export const loadDefenseLevel = (): Level => loadLevelFrom(DEFENSE_PREFS_KEY, DEFAULT_DEFENSE_LEVEL)
export const saveDefenseLevel = (level: Level) => saveLevelTo(DEFENSE_PREFS_KEY, level)

// ---------- Tentatives ----------

export const DEFENSE_DOMAIN = 'defense'
export const defenseKey = (id: string) => `defense:${id}`

// `held` : HOLD_MOVES coups tenus ; `draw` : nulle de l'échiquier ; `win` : mat donné ; `mated` : mat
// subi ; `collapsed` : éval sous le plancher deux tours de suite ou à la confirmation ; `resign` :
// abandon confirmé ; `abandon` : tentative laissée en cours (Recommencer, autre partie, niveau).
export type DefenseOutcome = 'held' | 'draw' | 'win' | 'mated' | 'collapsed' | 'resign' | 'abandon'

export function defenseOutcomeOf(end: GameEnd, player: Color): DefenseOutcome {
  if (end.kind === 'held') return 'held'
  if (end.kind === 'collapsed') return 'collapsed'
  if (end.kind === 'resign') return 'resign'
  if (end.result === '1/2-1/2') return 'draw'
  return (end.result === '1-0') === (player === 'w') ? 'win' : 'mated'
}

export const defenseSucceeded = (outcome: DefenseOutcome) => outcome === 'held' || outcome === 'draw' || outcome === 'win'

export async function recordDefense(pos: DefensePosition, outcome: DefenseOutcome, level: Level, assisted: boolean): Promise<void> {
  await db.learnSessions.add({
    date: Date.now(),
    domain: DEFENSE_DOMAIN,
    itemId: pos.id,
    fen: pos.fen,
    success: defenseSucceeded(outcome) && !assisted ? 1 : 0,
    ratingAfter: null,
    outcome,
    attackerElo: level,
    assisted,
  })
}

export interface DefenseStats {
  attempts: number // toutes les tentatives, abandons compris
  finished: number // tentatives menées à leur terme (hors Recommencer)
  successes: number // défense réussie sans aide
  bestLevel: Level | undefined // meilleur attaquant tenu sans aide (undefined : jamais)
}

const levelRank = (l: Level) => (l === null ? Infinity : l)

// Statistiques par `id|fen` : une position régénérée sous le même id repart de zéro.
export async function defenseStats(): Promise<Map<string, DefenseStats>> {
  const rows = await db.learnSessions.where('domain').equals(DEFENSE_DOMAIN).toArray()
  const out = new Map<string, DefenseStats>()
  for (const r of rows) {
    const key = `${r.itemId}|${r.fen ?? ''}`
    const s = out.get(key) ?? { attempts: 0, finished: 0, successes: 0, bestLevel: undefined }
    s.attempts++
    if (r.outcome !== 'abandon') s.finished++
    if (r.success) {
      s.successes++
      const lvl = r.attackerElo === undefined ? null : r.attackerElo
      if (s.bestLevel === undefined || levelRank(lvl) > levelRank(s.bestLevel)) s.bestLevel = lvl
    }
    out.set(key, s)
  }
  return out
}

export const defenseStatsKey = (p: DefensePosition) => `${p.id}|${p.fen}`

// Tentative de défense en cours écrasée par une autre partie : notée abandonnée (voir attempts.ts).
export function recordDefenseReplaced(stored: StoredGame) {
  if (!stored.key.startsWith('defense:')) return
  const pos = DEFENSES.find((d) => defenseKey(d.id) === stored.key && d.fen === stored.startFen)
  if (pos) void recordDefense(pos, 'abandon', stored.level ?? null, stored.assisted)
}
