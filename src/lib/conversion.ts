// Entraîneur « Convertir l'avantage » (/convertir) : banque de positions gagnantes à +2..+4
// (src/data/conversions.json, générée et vérifiée par scripts/prepare-conversions.py), à gagner
// contre Stockfish bridé à l'Elo choisi. Niveaux et bridage partagés avec l'entraîneur d'attaque.
import { db } from './db'
import { DEFAULT_LEVEL, loadLevelFrom, saveLevelTo, type AttackOutcome, type Level } from './attack'
import type { Color, StoredGame } from './positionGame'
import conversionsData from '../data/conversions.json'

export type ConversionCategory = 'finale' | 'materiel' | 'positionnel'

export interface ConversionPosition {
  id: string
  fen: string
  player: Color // camp qui doit convertir, au trait
  category: ConversionCategory
  theme: string
  goal: string // consigne courte, vraie pour la position (faits calculés)
  plan: string // deux à cinq phrases, chacune tirée d'un fait calculé
  eval: number // éval de sélection (Stockfish natif), centipions pour le joueur : tri seulement
  source: { puzzle: string; uci: string[] } // puzzle lichess d'origine, coups ajoutés après sa solution
}

export const CONVERSIONS = conversionsData as ConversionPosition[]

export const CATEGORY_ORDER: ConversionCategory[] = ['finale', 'materiel', 'positionnel']
// Libellés courts : trois onglets tiennent sur la largeur d'un iPhone sans troncature.
export const CATEGORY_LABEL: Record<ConversionCategory, string> = {
  finale: 'Finale',
  materiel: 'Matériel',
  positionnel: 'Positionnel',
}

// ---------- Défenseur ----------

// Préférence de l'entraîneur, hors persist Zustand et hors sauvegarde (simple confort), à part de
// celle de l'entraîneur d'attaque : la difficulté n'est pas la même.
export const CONVERSION_PREFS_KEY = 'chess-local-conversion'
export const loadLevel = (): Level => loadLevelFrom(CONVERSION_PREFS_KEY, DEFAULT_LEVEL)
export const saveLevel = (level: Level) => saveLevelTo(CONVERSION_PREFS_KEY, level)

// Avantage décisif : +8 pour le joueur (ou un mat), tenu deux tours de suite, jugé par le moteur
// de l'app (WASM lite, 300 ms). Plus haut que l'attaque (+7) : parti de +2..+4, un pion grappillé
// ne suffit pas. Pas plus haut : sans tables de finales, une finale technique gagnée peut rester
// longtemps sous +9 avant qu'un mat ne s'annonce.
export const CONVERT_DECISIVE_CP = 800

// ---------- Tentatives ----------

export const CONVERSION_DOMAIN = 'conversion'
export const gameKey = (id: string) => `convertir:${id}`

export async function recordAttempt(pos: ConversionPosition, outcome: AttackOutcome, level: Level, assisted: boolean): Promise<void> {
  const success = (outcome === 'mate' || outcome === 'decisive') && !assisted
  await db.learnSessions.add({
    date: Date.now(),
    domain: CONVERSION_DOMAIN,
    itemId: pos.id,
    fen: pos.fen,
    success: success ? 1 : 0,
    ratingAfter: null,
    outcome,
    defenderElo: level,
    assisted,
  })
}

// Tentative de conversion en cours écrasée par une autre partie : notée abandonnée. Appelée par
// `recordReplaced` (attempts.ts), qui aiguille selon le préfixe de la clé.
export function recordConversionReplaced(stored: StoredGame) {
  if (!stored.key.startsWith('convertir:')) return
  const pos = CONVERSIONS.find((c) => gameKey(c.id) === stored.key && c.fen === stored.startFen)
  if (pos) void recordAttempt(pos, 'abandon', stored.level ?? null, stored.assisted)
}
