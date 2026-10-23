import { useEffect, useState } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { db, DEFAULT_RATING, type PuzzleAttempt, type Rating, type SavedGame } from '../lib/db'
import { attackSummary, loadAttackDiagnostic, type AttackDiagnostic } from '../lib/kingAttack'
import { THREAT_DOMAIN, THREAT_KIND_LABEL, threatStatsOf, type ThreatStats } from '../lib/threat'

// Anciennes entrées vers les sections de Stats (lot 2 du plan UX : `state.section` de Plus et de
// la nav latérale ; `state.backup` de la carte de migration de l'app native). Réglages et Mes
// données ont leurs pages depuis le lot 3 : ces states y mènent, en replace.
type LegacyState = { backup?: boolean; section?: 'reglages' | 'donnees' } | null

function legacyTarget(state: LegacyState): string | null {
  if (state?.section === 'reglages') return '/reglages'
  if (state?.section === 'donnees' || state?.backup) return '/donnees'
  return null
}

export default function Stats() {
  const target = legacyTarget(useLocation().state as LegacyState)
  if (target) return <Navigate to={target} replace />
  return <StatsPage />
}

function StatsPage() {
  const [ratings, setRatings] = useState<Rating[]>([])
  const [games, setGames] = useState<SavedGame[]>([])
  const [attempts, setAttempts] = useState<PuzzleAttempt[]>([])
  const [attacks, setAttacks] = useState<AttackDiagnostic | null>(null)
  const [threats, setThreats] = useState<ThreatStats | null>(null)

  useEffect(() => {
    void db.ratings.toArray().then(setRatings)
    void db.games.toArray().then(setGames)
    void db.puzzleAttempts.toArray().then(setAttempts)
    void loadAttackDiagnostic().then(setAttacks)
    void db.learnSessions.where('domain').equals(THREAT_DOMAIN).toArray().then((rows) => setThreats(threatStatsOf(rows)))
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
    <div className="mx-auto max-w-3xl p-4 md:p-6">
      <h1 className="mb-5 text-2xl font-bold">Statistiques</h1>

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {cats.map((c) => {
          const r = ratingOf(c.key)
          return (
            <div key={c.key} className="rounded-lg bg-surface-2 p-4 text-center">
              <div className="text-2xl">{c.icon}</div>
              <div className="text-2xl font-bold">{r?.value ?? DEFAULT_RATING}</div>
              <div className="text-xs text-neutral-400">
                {c.label} · {r?.games ?? 0} {c.key === 'puzzle' ? 'essai' : 'partie'}{(r?.games ?? 0) > 1 ? 's' : ''}
              </div>
            </div>
          )
        })}
      </div>

      <Link to="/insights" className="mb-6 flex items-center gap-3 rounded-lg bg-surface-2 p-4 transition hover:bg-surface-3">
        <span className="text-3xl" aria-hidden="true">🧠</span>
        <span className="min-w-0 flex-1">
          <span className="block font-bold">Insights</span>
          <span className="block text-sm text-neutral-400">Tes dernières parties passées au crible : où tu pèches, tes forces, quoi travailler.</span>
        </span>
        <span className="text-xl text-neutral-500" aria-hidden="true">›</span>
      </Link>

      <div className="mb-6 grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded-lg bg-surface-2 p-4">
          <h2 className="mb-2 font-semibold">Parties contre les bots</h2>
          <div className="flex justify-between text-sm">
            <span className="text-accent">{wins} gagnée{wins > 1 ? 's' : ''}</span>
            <span className="text-neutral-400">{draws} nulle{draws > 1 ? 's' : ''}</span>
            <span className="text-red-400">{losses} perdue{losses > 1 ? 's' : ''}</span>
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

      {/* Attaques sur le roi manquées, lues dans les fautes des bilans (calcul sur l'échiquier). */}
      <div data-testid="attack-stats" className="mb-6 rounded-lg bg-surface-2 p-4">
        <h2 className="mb-2 font-semibold">🎯 Attaques manquées</h2>
        <p className="text-sm text-neutral-300">{attacks ? attackSummary(attacks) : '…'}</p>
        <Link to="/attaques-manquees" className="mt-1 inline-flex min-h-11 items-center text-sm font-semibold text-accent hover:underline">
          Voir et rejouer ›
        </Link>
      </div>

      {/* Questions « Qu'est-ce qu'il menace ? » des parties contre les bots (domaine threat-check). */}
      <div data-testid="threat-stats" className="rounded-lg bg-surface-2 p-4">
        <h2 className="mb-2 font-semibold">🛡 Menaces adverses</h2>
        {!threats ? (
          <p className="text-sm text-neutral-300">…</p>
        ) : threats.total === 0 ? (
          <p className="text-sm text-neutral-300">Aucune question encore : active « Qu'est-ce qu'il menace ? » dans Jouer ou les Réglages.</p>
        ) : (
          <>
            <p className="text-sm text-neutral-300" data-testid="threat-summary">
              {threats.seen} {threats.seen > 1 ? 'menaces repérées' : 'menace repérée'} sur {threats.total} ({Math.round((threats.seen / threats.total) * 100)} %)
            </p>
            <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-400">
              {threats.byKind.map((k) => (
                <li key={k.kind} data-threat-kind={k.kind}>
                  {THREAT_KIND_LABEL[k.kind]} <b className="text-neutral-200">{k.seen}/{k.total}</b>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  )
}
