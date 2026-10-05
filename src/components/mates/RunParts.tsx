// Briques partagées des séries de « Mats éclair » : en-tête, gros chrono, progression, bilan.
import type { ReactNode } from 'react'
import { Cta } from '../Cta'
import type { RunStats } from '../../lib/mates'

export function RunHeader({ title, score, onQuit }: { title: string; score: number; onQuit: () => void }) {
  return (
    <header className="flex items-center gap-2 px-2 py-1">
      <button
        onClick={onQuit}
        aria-label="Arrêter la série"
        className="flex h-10 w-10 cursor-pointer items-center justify-center rounded-full text-xl text-neutral-400 hover:text-white"
      >
        ✕
      </button>
      <h1 className="min-w-0 flex-1 truncate text-center text-base font-black">{title}</h1>
      <div data-score={score} className="flex h-10 min-w-10 items-center justify-center rounded-full bg-accent/20 px-3 text-lg font-black text-accent">
        {score}
      </div>
    </header>
  )
}

// Chrono très lisible : dixièmes sous 10 s, rouge sous 5 s (ou sous 20 s pour une série longue).
export function BigClock({ ms, running, warnMs = 5000 }: { ms: number; running: boolean; warnMs?: number }) {
  const t = Math.max(0, ms)
  const totalSec = Math.ceil(t / 1000)
  const text = t < 10_000
    ? `${Math.floor(t / 1000)},${Math.floor((t % 1000) / 100)}`
    : `${Math.floor(totalSec / 60)}:${String(totalSec % 60).padStart(2, '0')}`
  const warn = t < warnMs
  return (
    <div
      role="timer"
      aria-label="Temps restant"
      data-ms={Math.round(t)}
      data-running={running}
      className={`rounded-xl px-4 py-1 text-center font-mono text-5xl leading-tight font-black tabular-nums transition-colors md:text-6xl ${
        warn ? 'bg-red-900/70 text-red-100' : running ? 'bg-neutral-100 text-neutral-900' : 'bg-surface-3 text-neutral-300'
      }`}
    >
      {text}
    </div>
  )
}

// Dix dernières séries en barres, la plus récente à droite.
export function Sparkline({ values }: { values: number[] }) {
  if (values.length === 0) return <p className="text-sm text-neutral-500">Aucune série pour l'instant.</p>
  const max = Math.max(1, ...values)
  return (
    <div className="flex h-12 items-end gap-1" aria-label={`Dernières séries : ${values.join(', ')}`}>
      {values.map((v, i) => (
        <div key={i} className="flex flex-1 flex-col items-center justify-end gap-0.5">
          <span className="text-[10px] leading-none text-neutral-400">{v}</span>
          <div
            className={`w-full rounded-sm ${i === values.length - 1 ? 'bg-accent' : 'bg-neutral-500'}`}
            style={{ height: `${Math.max(3, (v / max) * 32)}px` }}
          />
        </div>
      ))}
    </div>
  )
}

export function RunSummary({ score, stats, newRecord, reason, children, onReplay, onMenu }: {
  score: number
  stats: RunStats | null
  newRecord: boolean
  reason?: string | null
  children?: ReactNode
  onReplay: () => void
  onMenu: () => void
}) {
  return (
    <section data-run-over className="space-y-3 rounded-xl bg-surface-2 p-4 text-center">
      {reason && <p className="text-sm font-semibold text-red-300">{reason}</p>}
      <p className="text-xl font-black">{newRecord ? '🏆 Nouveau record !' : 'Série terminée'}</p>
      <p className="text-5xl font-black text-accent">{score}</p>
      <p className="text-sm text-neutral-400">
        {score > 1 ? 'mats réussis' : 'mat réussi'} · record {Math.max(stats?.best ?? 0, score)}
      </p>
      {stats && stats.last.length > 1 && <Sparkline values={stats.last} />}
      {children}
      <div className="flex justify-center gap-3 pt-1">
        <Cta onClick={onReplay}>Rejouer</Cta>
        <Cta variant="secondary" onClick={onMenu}>
          Menu
        </Cta>
      </div>
    </section>
  )
}
