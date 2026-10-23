import { Link, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { ActivityCard } from '../components/ActivityCard'
import { Cta } from '../components/Cta'
import { db, DEFAULT_RATING } from '../lib/db'
import { loadChunk } from '../lib/lazyPage'
import type { ReviewItem } from '../lib/revision'
import type { PathState } from '../lib/learningPath'
import { streak, streakLabel } from '../lib/seance'
import { readStoredSeance, seanceDates } from '../lib/seanceSession'
import { dismissMigration, isNative, migrationDismissed } from '../lib/native'

// Import dynamique (homeExtras.ts) : le compteur de révision et la progression du parcours tirent les
// ouvertures et les cours bundlés, que l'accueil n'a pas à charger avant son premier affichage.
// Chargé une seule fois : revenir à l'accueil après une mise à jour de l'app ne recharge pas l'app
// pour une chunk déjà en mémoire.
let extras: Promise<typeof import('../lib/homeExtras')> | null = null
function loadExtras() {
  extras ??= loadChunk(() => import('../lib/homeExtras')).catch((error: unknown) => {
    extras = null
    throw error
  })
  return extras
}

export default function Home() {
  const navigate = useNavigate()
  const [ratings, setRatings] = useState<Record<string, number>>({})
  const [solved, setSolved] = useState(0)
  const [nbGames, setNbGames] = useState(0)
  const [due, setDue] = useState<ReviewItem[] | null>(null) // null : compte pas encore connu
  const [path, setPath] = useState<PathState | null>(null) // progression du parcours, null : pas encore connue
  const [seance, setSeance] = useState<{ days: number; today: boolean } | null>(null) // série de séances du jour
  const [current] = useState(() => readStoredSeance()) // séance du jour en cours (sessionStorage)
  // App native : proposer de récupérer les données de la PWA (docs/ios-app.md), jusqu'à une
  // restauration réussie ou « Non merci », même après un premier puzzle joué dans l'app.
  const [offerMigration, setOfferMigration] = useState(() => isNative && !migrationDismissed())
  const [kinds, setKinds] = useState('') // description du dû (« 2 puzzles, 1 faute »)

  useEffect(() => {
    void db.ratings.toArray().then((rs) => setRatings(Object.fromEntries(rs.map((r) => [r.key, r.value]))))
    void db.puzzleAttempts.where('date').above(0).toArray().then((a) => setSolved(a.filter((x) => x.success).length))
    void db.games.count().then(setNbGames)
    // Chunk introuvable malgré le rechargement : l'accueil reste utilisable, sans le compteur ni la
    // progression du parcours.
    const loaded = loadExtras()
    void loaded.then(async ({ describeKinds, loadReviewQueue }) => {
      const q = await loadReviewQueue()
      setKinds(describeKinds(q.due))
      setDue(q.due)
    }, () => {})
    void loaded.then(async ({ computePath, EMPTY_FACTS, loadPathFacts }) => {
      // Même lecture que usePathState : base illisible, parcours vide.
      setPath(computePath(await loadPathFacts().catch(() => EMPTY_FACTS)))
    }, () => {})
    void seanceDates().then((d) => setSeance(streak(d)), () => setSeance({ days: 0, today: false }))
  }, [])

  const r = (key: string) => ratings[key] ?? DEFAULT_RATING

  const statCards = [
    { icon: '⏱', label: 'Rapide', value: r('rapid') },
    { icon: '⚡', label: 'Blitz', value: r('blitz') },
    { icon: '🚀', label: 'Bullet', value: r('bullet') },
    { icon: '🧩', label: 'Puzzles', value: r('puzzle') },
  ]

  const tiles = [
    { to: '/analyse', icon: '🔍', title: 'Analyse', desc: 'Stockfish 18, bilan, coach', tab: true },
    { to: '/rush', icon: '⚡', title: 'Puzzle Rush', desc: '3 min, 5 min ou survie', tab: false },
    { to: '/archive', icon: '📚', title: 'Archive', desc: `${nbGames} partie${nbGames > 1 ? 's' : ''}`, tab: true },
    { to: '/import', icon: '♟', title: 'chess.com', desc: 'Importer tes parties', tab: false },
  ]

  return (
    <div data-review-ready={due !== null ? '' : undefined} data-seance-ready={seance !== null ? '' : undefined} data-path-ready={path !== null ? '' : undefined} className="mx-auto flex h-full max-w-2xl flex-col p-4 md:justify-center md:p-8">
      <h1 className="mb-2 md:mb-4 text-3xl font-black">
        ♞ Chess<span className="text-accent">Local</span>
      </h1>

      {/* App native : elle n'a pas la même origine que la PWA, la sauvegarde est le seul pont.
          La carte disparaît après une restauration réussie ou « Non merci ». */}
      {offerMigration && (
        <div data-testid="native-migration" className="mb-2 md:mb-4 flex items-center rounded-2xl border border-accent/40 bg-surface-2 shadow-lg">
          <button
            data-testid="native-migration-go"
            onClick={() => navigate('/stats', { replace: true, state: { backup: true } })}
            className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 rounded-l-2xl py-2 pl-4 text-left transition hover:bg-surface-3"
          >
            <span className="text-2xl" aria-hidden="true">📲</span>
            <span className="min-w-0 flex-1">
              <span className="block font-bold">Récupérer tes données</span>
              <span className="block truncate text-xs text-neutral-400">Exporte-les dans la PWA, puis restaure-les ici</span>
            </span>
            <span className="text-xl text-neutral-500" aria-hidden="true">›</span>
          </button>
          <button
            data-testid="native-migration-dismiss"
            aria-label="Non merci"
            title="Non merci"
            onClick={() => { dismissMigration(); setOfferMigration(false) }}
            className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-r-2xl text-lg text-neutral-500 transition hover:text-neutral-200"
          >
            ✕
          </button>
        </div>
      )}

      {/* Navigations d'onglet (racines de la nav) en `replace`, comme la nav basse : le swipe-back
          iOS ne ramène pas à l'accueil en pleine partie. Puzzle Rush et chess.com sont des
          descentes (/rush, /import), empilées. */}
      {/* Carte Problèmes, façon chess.com */}
      <Link
        to="/puzzles"
        replace
        className="mb-2 md:mb-4 block rounded-2xl bg-gradient-to-br from-[#4e7837] to-[#2e4a20] p-3 md:p-5 shadow-lg transition hover:brightness-110 [@media(max-height:700px)]:py-2"
      >
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-2xl font-black text-white">🧩 Problèmes</div>
            <div className="mt-1 text-sm text-white/80">
              {solved} résolus · classement {r('puzzle')}
            </div>
          </div>
          <span className="shrink-0 rounded-xl bg-accent px-5 py-2.5 text-lg font-black text-on-accent shadow-[0_3px_0_#5d9948]">
            Résolvez !
          </span>
        </div>
      </Link>

      {/* Séance du jour : descente (push) ; la séance en cours se reprend à l'arrivée. */}
      <Link
        to="/seance"
        data-seance-tile
        className="mb-2 md:mb-4 flex items-center gap-3 rounded-2xl border border-accent/30 bg-surface-2 px-4 py-2 shadow-lg transition hover:bg-surface-3 [@media(max-height:700px)]:py-1.5"
      >
        <span className="text-2xl" aria-hidden="true">☀️</span>
        <span className="min-w-0 flex-1">
          <span className="block font-bold">Séance du jour</span>
          <span data-seance-status className="block truncate text-xs text-neutral-400">
            {current
              ? `Reprendre · étape ${current.idx + 1}/${current.steps.length}`
              : seance?.today
                ? `✓ Faite aujourd'hui · ${streakLabel(seance.days)}`
                : seance && seance.days > 0
                  ? `10 à 15 min guidées · ${streakLabel(seance.days)}`
                  : '10 à 15 min guidées'}
          </span>
        </span>
        <span className="text-xl text-neutral-500" aria-hidden="true">›</span>
      </Link>

      {/* Révision espacée : visible seulement quand quelque chose est dû ; descente (push), la
          séance démarre à l'arrivée. */}
      {due !== null && due.length > 0 && (
        <Link
          to="/revision"
          className="mb-2 md:mb-4 flex items-center gap-3 rounded-2xl border border-amber-400/30 bg-surface-2 px-4 py-2 shadow-lg transition hover:bg-surface-3 [@media(max-height:700px)]:py-1.5"
        >
          <span className="text-2xl" aria-hidden="true">🔁</span>
          <span className="min-w-0 flex-1">
            <span className="block font-bold">À réviser aujourd'hui</span>
            <span className="block truncate text-xs text-neutral-400">{kinds}</span>
          </span>
          <span data-review-count className="shrink-0 rounded-full bg-amber-400 px-3 py-1 text-base font-black text-neutral-900">
            {due.length}
          </span>
          <span className="text-xl text-neutral-500" aria-hidden="true">›</span>
        </Link>
      )}

      {/* Cartes stats horizontales. Écran court (Safari avec ses barres, 393x660) : icônes masquées,
          carte Problèmes et tuiles resserrées, pour que la tuile Séance, la carte Révision et la
          rangée Parcours/Insights tiennent avec Jouer sans défilement. */}
      <div className="mb-2 md:mb-4 grid grid-cols-4 gap-2">
        {statCards.map((s) => (
          <Link key={s.label} to="/stats" replace className="rounded-xl bg-surface-2 p-3 text-center transition hover:bg-surface-3">
            <div className="text-2xl [@media(max-height:700px)]:hidden">{s.icon}</div>
            <div className="text-xl font-black">{s.value}</div>
            <div className="text-xs text-neutral-400">{s.label}</div>
          </Link>
        ))}
      </div>

      {/* Tuiles secondaires */}
      <div className="mb-2 md:mb-4 grid grid-cols-2 gap-2">
        {tiles.map((t) => (
          <ActivityCard key={t.to} to={t.to} replace={t.tab} icon={t.icon} title={t.title} description={t.desc} className="py-2 [@media(max-height:700px)]:py-1.5" />
        ))}
      </div>

      {/* Parcours d'apprentissage et Insights : descentes (empilées), côte à côte pour que l'Accueil
          tienne sans défiler à 393x660. */}
      <div className="mb-2 md:mb-4 grid grid-cols-2 gap-2">
        <Link to="/apprendre/parcours" data-testid="home-path" className="flex min-h-11 min-w-0 items-center gap-2 rounded-xl bg-surface-2 px-3 py-2 transition hover:bg-surface-3">
          <span className="text-xl" aria-hidden="true">🗺️</span>
          <span className="font-bold">Parcours</span>
          <span data-testid="home-path-progress" className="min-w-0 flex-1 truncate text-xs text-neutral-400">
            {path ? (path.current ? `${path.done}/${path.total}` : 'terminé') : ''}
          </span>
          <span className="text-lg text-neutral-500" aria-hidden="true">›</span>
        </Link>
        {/* Insights : hors des cartes Elo qui mènent à Stats. */}
        <Link to="/insights" className="flex min-h-11 min-w-0 items-center gap-2 rounded-xl bg-surface-2 px-3 py-2 transition hover:bg-surface-3">
          <span className="text-xl" aria-hidden="true">🧠</span>
          <span className="min-w-0 flex-1 truncate font-bold">Insights</span>
          <span className="text-lg text-neutral-500" aria-hidden="true">›</span>
        </Link>
      </div>

      {/* CTA Jouer géant, collé en bas */}
      <div className="mt-auto md:mt-4">
        <Cta className="w-full py-4 text-2xl [@media(max-height:700px)]:py-3" onClick={() => navigate('/jouer', { replace: true })}>
          Jouer
        </Cta>
      </div>
    </div>
  )
}
