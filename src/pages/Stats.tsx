import { useEffect, useRef, useState } from 'react'
import { db, DEFAULT_RATING, type PuzzleAttempt, type Rating, type SavedGame } from '../lib/db'
import { downloadBackup, exportBackup, importBackup } from '../lib/backup'
import { BOARD_THEMES, useSettings } from '../store/settings'

export default function Stats() {
  const [ratings, setRatings] = useState<Rating[]>([])
  const [games, setGames] = useState<SavedGame[]>([])
  const [attempts, setAttempts] = useState<PuzzleAttempt[]>([])
  const [backupMsg, setBackupMsg] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const settings = useSettings()

  useEffect(() => {
    void db.ratings.toArray().then(setRatings)
    void db.games.toArray().then(setGames)
    void db.puzzleAttempts.toArray().then(setAttempts)
  }, [])

  const ratingOf = (key: string) => ratings.find((r) => r.key === key)
  const botGames = games.filter((g) => g.mode === 'bot')
  const wins = botGames.filter((g) => (g.result === '1-0') === (g.playerColor === 'w') && g.result !== '1/2-1/2').length
  const draws = botGames.filter((g) => g.result === '1/2-1/2').length
  const losses = botGames.length - wins - draws
  const solved = attempts.filter((a) => a.success).length

  const cats: { key: string; label: string; icon: string }[] = [
    { key: 'bullet', label: 'Bullet', icon: '🚀' },
    { key: 'blitz', label: 'Blitz', icon: '⚡' },
    { key: 'rapid', label: 'Rapide', icon: '⏱' },
    { key: 'puzzle', label: 'Puzzles', icon: '🧩' },
  ]

  return (
    <div className="mx-auto max-w-3xl p-6">
      <h1 className="mb-5 text-2xl font-bold">Statistiques</h1>

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {cats.map((c) => {
          const r = ratingOf(c.key)
          return (
            <div key={c.key} className="rounded-lg bg-surface-2 p-4 text-center">
              <div className="text-2xl">{c.icon}</div>
              <div className="text-2xl font-bold">{r?.value ?? DEFAULT_RATING}</div>
              <div className="text-xs text-neutral-400">
                {c.label} · {r?.games ?? 0} {c.key === 'puzzle' ? 'essais' : 'parties'}
              </div>
            </div>
          )
        })}
      </div>

      <div className="mb-6 grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded-lg bg-surface-2 p-4">
          <h2 className="mb-2 font-semibold">Parties contre les bots</h2>
          <div className="flex justify-between text-sm">
            <span className="text-accent">{wins} gagnées</span>
            <span className="text-neutral-400">{draws} nulles</span>
            <span className="text-red-400">{losses} perdues</span>
          </div>
          {botGames.length > 0 && (
            <div className="mt-2 flex h-2 overflow-hidden rounded-full">
              <div className="bg-accent" style={{ width: `${(wins / botGames.length) * 100}%` }} />
              <div className="bg-neutral-500" style={{ width: `${(draws / botGames.length) * 100}%` }} />
              <div className="bg-red-500" style={{ width: `${(losses / botGames.length) * 100}%` }} />
            </div>
          )}
        </div>
        <div className="rounded-lg bg-surface-2 p-4">
          <h2 className="mb-2 font-semibold">Puzzles</h2>
          <p className="text-sm text-neutral-300">
            {solved} résolus / {attempts.length} tentés
            {attempts.length > 0 && ` (${Math.round((solved / attempts.length) * 100)} %)`}
          </p>
        </div>
      </div>

      <h2 className="mb-3 text-lg font-bold">Réglages</h2>
      <div className="space-y-3 rounded-lg bg-surface-2 p-4">
        <div>
          <p className="mb-2 text-sm font-semibold text-neutral-300">Thème de l'échiquier</p>
          <div className="flex gap-2">
            {BOARD_THEMES.map((t) => (
              <button
                key={t.id}
                onClick={() => settings.setTheme(t.id)}
                className={`cursor-pointer overflow-hidden rounded border-2 ${settings.themeId === t.id ? 'border-accent' : 'border-transparent'}`}
                title={t.name}
              >
                <div className="flex">
                  <div className="h-8 w-8" style={{ background: t.light }} />
                  <div className="h-8 w-8" style={{ background: t.dark }} />
                </div>
              </button>
            ))}
          </div>
        </div>
        <Toggle label="Afficher les coups légaux" value={settings.showLegalMoves} onChange={settings.setShowLegalMoves} />
        <Toggle label="Sons" value={settings.playSounds} onChange={settings.setPlaySounds} />
        <div>
          <p className="mb-2 text-sm font-semibold text-neutral-300">Profondeur du bilan de partie</p>
          <div className="flex gap-2">
            {(
              [
                ['fast', 'Rapide'],
                ['balanced', 'Équilibré'],
                ['deep', 'Profond'],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => settings.setReviewDepth(key)}
                className={`cursor-pointer rounded border-2 px-3 py-1.5 text-sm font-semibold transition ${
                  settings.reviewDepth === key ? 'border-accent bg-accent/10' : 'border-transparent bg-surface-3 hover:bg-surface-3/70'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="mt-1 text-xs text-neutral-500">
            Rapide ≈ 30 s, Équilibré ≈ 1-2 min, Profond ≈ 4-5 min sur iPhone (partie de 40 coups).
          </p>
        </div>
        <div>
          <p className="mb-2 text-sm font-semibold text-neutral-300">Sauvegarde des données</p>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => void exportBackup().then(downloadBackup)}
              className="cursor-pointer rounded bg-surface-3 px-3 py-1.5 text-sm font-semibold hover:bg-surface-3/70"
            >
              ⬇ Exporter tout
            </button>
            <button
              onClick={() => fileRef.current?.click()}
              className="cursor-pointer rounded bg-surface-3 px-3 py-1.5 text-sm font-semibold hover:bg-surface-3/70"
            >
              ⬆ Restaurer
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="application/json"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (!f) return
                void f.text().then(async (json) => {
                  try {
                    await importBackup(json)
                    setBackupMsg('Sauvegarde restaurée. Recharge la page.')
                  } catch (err) {
                    setBackupMsg((err as Error).message)
                  }
                })
              }}
            />
          </div>
          {backupMsg && <p className="mt-1 text-xs text-accent">{backupMsg}</p>}
          <p className="mt-1 text-xs text-neutral-500">
            Classements, parties, puzzles, erreurs et réglages dans un fichier JSON. À faire de temps en temps :
            iOS peut purger le stockage d'une app web inutilisée.
          </p>
        </div>
      </div>
    </div>
  )
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-neutral-300">{label}</span>
      <button
        onClick={() => onChange(!value)}
        className={`h-6 w-11 cursor-pointer rounded-full p-0.5 transition ${value ? 'bg-accent' : 'bg-surface-3'}`}
      >
        <div className={`h-5 w-5 rounded-full bg-white transition ${value ? 'translate-x-5' : ''}`} />
      </button>
    </div>
  )
}
