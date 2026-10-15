import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { DEFAULT_PIECE_SET, isPieceSet } from '../lib/pieces'

export interface BoardTheme {
  id: string
  name: string
  light: string
  dark: string
}

export const BOARD_THEMES: BoardTheme[] = [
  { id: 'green', name: 'Vert', light: '#E9E9CA', dark: '#6A8A4B' },
  { id: 'brown', name: 'Bois', light: '#f0d9b5', dark: '#b58863' },
  { id: 'blue', name: 'Océan', light: '#dee3e6', dark: '#788a94' },
  { id: 'purple', name: 'Améthyste', light: '#e8e0ec', dark: '#8877b7' },
]

export type ReviewDepthSetting = 'fast' | 'balanced' | 'deep'
export const REVIEW_DEPTHS: Record<ReviewDepthSetting, number> = { fast: 10, balanced: 12, deep: 16 }

// Dernière configuration de l'écran Jouer (mode, bot, couleur, cadence), retrouvée à la visite suivante.
export const PLAY_MODES = ['bot', 'local', 'coach'] as const
export type PlayMode = (typeof PLAY_MODES)[number]
export const PLAY_COLORS = ['w', 'b', 'random'] as const
export type PlayColor = (typeof PLAY_COLORS)[number]
export interface PlayConfig {
  playMode: PlayMode
  playBotId: string
  playColor: PlayColor
  playTcLabel: string
}

interface SettingsState {
  themeId: string
  setTheme: (id: string) => void
  premoves: boolean
  setPremoves: (v: boolean) => void
  showLegalMoves: boolean
  setShowLegalMoves: (v: boolean) => void
  // Calque « Compte les attaquants » : zone de chaque roi et compte attaquants / défenseurs,
  // dans l'Analyse, Jouer et la partie contre le moteur lancée depuis l'analyse ; l'exercice
  // « Mes attaques manquées » l'affiche toujours.
  showAttackers: boolean
  setShowAttackers: (v: boolean) => void
  pieceSet: string
  setPieceSet: (id: string) => void
  playSounds: boolean
  setPlaySounds: (v: boolean) => void
  // Volume des sons, de 0 à 1.
  soundVolume: number
  setSoundVolume: (v: number) => void
  chesscomUsername: string
  setChesscomUsername: (v: string) => void
  reviewDepth: ReviewDepthSetting
  setReviewDepth: (v: ReviewDepthSetting) => void
  playMode: PlayMode
  playBotId: string
  playColor: PlayColor
  playTcLabel: string
  setPlayConfig: (v: Partial<PlayConfig>) => void
}

// Même migration pour une montée de version locale et une ancienne sauvegarde.
export function migrateSettings(persisted: unknown, version: number): Partial<SettingsState> {
  const settings = (persisted ?? {}) as Partial<SettingsState>
  // L'ancien défaut n'a été déployé que le 15 octobre 2026.
  // En version 1, Celtique reste un choix explicite à conserver.
  if (version < 1 && (!settings.pieceSet || settings.pieceSet === 'celtique')) {
    return { ...settings, pieceSet: DEFAULT_PIECE_SET }
  }
  return settings
}

export const useSettings = create<SettingsState>()(
  persist(
    (set) => ({
      themeId: 'green',
      setTheme: (themeId) => set({ themeId }),
      premoves: true,
      setPremoves: (premoves) => set({ premoves }),
      showLegalMoves: true,
      setShowLegalMoves: (showLegalMoves) => set({ showLegalMoves }),
      showAttackers: false,
      setShowAttackers: (showAttackers) => set({ showAttackers }),
      pieceSet: DEFAULT_PIECE_SET,
      setPieceSet: (pieceSet) => set({ pieceSet: isPieceSet(pieceSet) ? pieceSet : DEFAULT_PIECE_SET }),
      playSounds: true,
      setPlaySounds: (playSounds) => set({ playSounds }),
      soundVolume: 1,
      setSoundVolume: (soundVolume) => set({ soundVolume: Math.min(1, Math.max(0, soundVolume)) }),
      chesscomUsername: '',
      setChesscomUsername: (chesscomUsername) => set({ chesscomUsername }),
      reviewDepth: 'balanced',
      setReviewDepth: (reviewDepth) => set({ reviewDepth }),
      playMode: 'bot',
      playBotId: 'nina',
      playColor: 'w',
      playTcLabel: '10 min',
      setPlayConfig: (v) => set(v),
    }),
    {
      name: 'chess-local-settings',
      version: 1,
      migrate: migrateSettings,
    },
  ),
)

export function currentTheme(themeId: string): BoardTheme {
  return BOARD_THEMES.find((t) => t.id === themeId) ?? BOARD_THEMES[0]
}
