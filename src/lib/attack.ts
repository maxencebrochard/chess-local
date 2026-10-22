// Entraîneur d'attaque (/attaque) : banque de positions d'attaque (src/data/attacks.json, générée
// et vérifiée par scripts/prepare-attacks.py), niveau du défenseur, résultats des tentatives.
import { db } from './db'
import type { Color, GameEnd, Opponent, StoredGame } from './positionGame'
import attacksData from '../data/attacks.json'

export type AttackCategory = 'opposes' | 'meme' | 'centre'

export interface AttackPosition {
  id: string
  fen: string
  attacker: Color
  category: AttackCategory
  theme: string
  goal: string // consigne courte, vraie pour la position (faits calculés)
  plan: string // deux à quatre phrases, chacune tirée d'un fait calculé
  eval: number // éval de sélection (Stockfish natif), centipions pour l'attaquant : tri seulement
  source: { puzzle: string; game: string; ply: number; before: number }
}

export const ATTACKS = attacksData as AttackPosition[]

export const CATEGORY_ORDER: AttackCategory[] = ['opposes', 'meme', 'centre']
export const CATEGORY_LABEL: Record<AttackCategory, string> = {
  opposes: 'Roques opposés',
  meme: 'Même aile',
  centre: 'Roi au centre',
}

// ---------- Niveau de l'adversaire (défenseur ici, attaquant dans l'entraîneur de défense) ----------

// Elo de l'adversaire (Stockfish bridé par UCI_Elo, plancher réel 1320), null = pleine force.
export type Level = number | null
export const LEVELS: Level[] = [1320, 1500, 1700, 1900, 2100, 2300, 2500, 2800, 3000, null]
export const DEFAULT_LEVEL: Level = 1700

// Préférence de l'entraîneur, hors persist Zustand et hors sauvegarde (simple confort). Chaque
// entraîneur a sa clé (`DEFENSE_PREFS_KEY` dans defense.ts), même forme `{ level }`.
export const ATTACK_PREFS_KEY = 'chess-local-attack'

export function loadLevelFrom(key: string, fallback: Level): Level {
  try {
    const raw = localStorage.getItem(key)
    const level = raw ? (JSON.parse(raw) as { level?: unknown }).level : undefined
    return LEVELS.includes(level as Level) ? (level as Level) : fallback
  } catch {
    return fallback
  }
}

export function saveLevelTo(key: string, level: Level) {
  try {
    localStorage.setItem(key, JSON.stringify({ level }))
  } catch {}
}

export const loadLevel = (): Level => loadLevelFrom(ATTACK_PREFS_KEY, DEFAULT_LEVEL)
export const saveLevel = (level: Level) => saveLevelTo(ATTACK_PREFS_KEY, level)

// Bridage par les options UCI de Stockfish (Skill Level : il choisit, avec une part de hasard,
// parmi ses meilleurs coups), jamais les coups tirés au hasard des bots faibles de bots.ts.
export function opponentFor(level: Level): Opponent {
  return {
    options: level === null ? { UCI_LimitStrength: false } : { UCI_LimitStrength: true, UCI_Elo: level },
    label: level === null ? 'pleine force' : `Elo ${level}`,
    level,
  }
}

// Avantage décisif : +7 pour l'attaquant (ou un mat), tenu deux tours de suite.
export const DECISIVE_CP = 700

// ---------- Tentatives ----------

export const ATTACK_DOMAIN = 'attack'
export const gameKey = (id: string) => `attaque:${id}`

// Issues d'une tentative d'attaque (champ `outcome` de `LearnSession`, domaine `attack`).
export type AttackOutcome = 'mate' | 'decisive' | 'draw' | 'loss' | 'resign' | 'abandon'

export function outcomeOf(end: GameEnd, player: Color): AttackOutcome {
  if (end.kind === 'decisive') return 'decisive'
  if (end.kind === 'resign') return 'resign'
  if (end.result === '1/2-1/2') return 'draw'
  const won = (end.result === '1-0') === (player === 'w')
  return won ? 'mate' : 'loss'
}

export async function recordAttempt(pos: AttackPosition, outcome: AttackOutcome, level: Level, assisted: boolean): Promise<void> {
  const success = (outcome === 'mate' || outcome === 'decisive') && !assisted
  await db.learnSessions.add({
    date: Date.now(),
    domain: ATTACK_DOMAIN,
    itemId: pos.id,
    fen: pos.fen,
    success: success ? 1 : 0,
    ratingAfter: null,
    outcome,
    defenderElo: level,
    assisted,
  })
}

export interface AttackStats {
  attempts: number // toutes les tentatives, abandons compris
  finished: number // tentatives menées à leur terme (hors Recommencer)
  successes: number // mat ou avantage décisif sans aide
  bestLevel: Level | undefined // meilleur niveau battu sans aide (undefined : jamais)
}

const levelRank = (l: Level) => (l === null ? Infinity : l)

// Statistiques par `id|fen` : une position régénérée sous le même id repart de zéro. Même forme de
// ligne pour l'entraîneur de conversion (domaine `conversion`).
export async function attackStats(domain: string = ATTACK_DOMAIN): Promise<Map<string, AttackStats>> {
  const rows = await db.learnSessions.where('domain').equals(domain).toArray()
  const out = new Map<string, AttackStats>()
  for (const r of rows) {
    const key = `${r.itemId}|${r.fen ?? ''}`
    const s = out.get(key) ?? { attempts: 0, finished: 0, successes: 0, bestLevel: undefined }
    const outcome = r.outcome ?? (r.success ? 'decisive' : 'loss')
    s.attempts++
    if (outcome !== 'abandon') s.finished++
    if (r.success) {
      s.successes++
      const lvl = r.defenderElo === undefined ? null : r.defenderElo
      if (s.bestLevel === undefined || levelRank(lvl) > levelRank(s.bestLevel)) s.bestLevel = lvl
    }
    out.set(key, s)
  }
  return out
}

export const statsKey = (p: { id: string; fen: string }) => `${p.id}|${p.fen}`

// Tentative d'attaque en cours écrasée par une autre partie (autre position, finale, partie
// libre : un seul emplacement de persistance) : notée abandonnée. Appelée par `recordReplaced`
// (attempts.ts), qui aiguille selon le préfixe de la clé.
export function recordAttackReplaced(stored: StoredGame) {
  if (!stored.key.startsWith('attaque:')) return
  const pos = ATTACKS.find((a) => gameKey(a.id) === stored.key && a.fen === stored.startFen)
  if (pos) void recordAttempt(pos, 'abandon', stored.level ?? null, stored.assisted)
}
