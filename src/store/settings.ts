import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface BoardTheme {
  id: string
  name: string
  light: string
  dark: string
}

export const BOARD_THEMES: BoardTheme[] = [
  { id: 'green', name: 'Vert', light: '#eeeed2', dark: '#769656' },
  { id: 'brown', name: 'Bois', light: '#f0d9b5', dark: '#b58863' },
  { id: 'blue', name: 'Océan', light: '#dee3e6', dark: '#788a94' },
  { id: 'purple', name: 'Améthyste', light: '#e8e0ec', dark: '#8877b7' },
]

export type ReviewDepthSetting = 'fast' | 'balanced' | 'deep'
export const REVIEW_DEPTHS: Record<ReviewDepthSetting, number> = { fast: 10, balanced: 12, deep: 16 }

interface SettingsState {
  themeId: string
  setTheme: (id: string) => void
  showLegalMoves: boolean
  setShowLegalMoves: (v: boolean) => void
  playSounds: boolean
  setPlaySounds: (v: boolean) => void
  chesscomUsername: string
  setChesscomUsername: (v: string) => void
  reviewDepth: ReviewDepthSetting
  setReviewDepth: (v: ReviewDepthSetting) => void
}

export const useSettings = create<SettingsState>()(
  persist(
    (set) => ({
      themeId: 'green',
      setTheme: (themeId) => set({ themeId }),
      showLegalMoves: true,
      setShowLegalMoves: (showLegalMoves) => set({ showLegalMoves }),
      playSounds: true,
      setPlaySounds: (playSounds) => set({ playSounds }),
      chesscomUsername: '',
      setChesscomUsername: (chesscomUsername) => set({ chesscomUsername }),
      reviewDepth: 'balanced',
      setReviewDepth: (reviewDepth) => set({ reviewDepth }),
    }),
    { name: 'chess-local-settings' },
  ),
)

export function currentTheme(themeId: string): BoardTheme {
  return BOARD_THEMES.find((t) => t.id === themeId) ?? BOARD_THEMES[0]
}
