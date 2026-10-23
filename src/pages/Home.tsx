import { useNavigate } from 'react-router-dom'
import { Fragment, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ActivityCard } from '../components/ActivityCard'
import { Cta } from '../components/Cta'
import { NavIcon } from '../components/NavIcon'
import { ProgressBar } from '../components/ProgressBar'
import { db } from '../lib/db'
import {
  gameMeta, gameTitle, homePrimary, revisionLine, revisionsInSeance, seanceStepLabel, weekStart, weekSummary,
  type GameResume, type SeanceResume,
} from '../lib/homePlan'
import { loadChunk } from '../lib/lazyPage'
import type { PathState } from '../lib/learningPath'
import { readStoredGame } from '../lib/playSession'
import { BLOCK_META, revisionBlockSize, streak, streakLabel } from '../lib/seance'
import { readStoredSeance, seanceDates } from '../lib/seanceSession'
import { dismissMigration, isNative, migrationDismissed } from '../lib/native'

// Imports dynamiques, indépendants : le compteur de révision (revision.ts tire l'entraîneur
// d'ouvertures et ses 470 Ko d'ouvertures) et la progression du parcours (learningPathStore.ts, sans
// les cours) arrivent après le premier affichage, chacun sans attendre l'autre.
// Chargés une seule fois : revenir à l'accueil après une mise à jour de l'app ne recharge pas l'app
// pour une chunk déjà en mémoire.
function loadOnce<T>(load: () => Promise<T>): () => Promise<T> {
  let chunk: Promise<T> | null = null
  return () =>
    (chunk ??= loadChunk(load).catch((error: unknown) => {
      chunk = null
      throw error
    }))
}
const loadRevision = loadOnce(() => import('../lib/revision'))
const loadPath = loadOnce(() => import('../lib/learningPathStore'))

// File de révision due vue de l'accueil : clés `<kind>:<key>`, celles qu'une nouvelle séance du jour
// reprendrait, et la description par type de chacune.
interface DueView {
  keys: string[]
  fresh: string[]
  describe: (keys: string[]) => string
}

// Lecture synchrone des reprises : la carte principale est juste dès le premier affichage.
function readSeanceResume(): SeanceResume | null {
  const s = readStoredSeance()
  // Étape d'un type inconnu (stockage abîmé) : la séance ne saurait pas la restaurer.
  if (!s || !Object.hasOwn(BLOCK_META, s.steps[s.idx]?.kind)) return null
  const judged = new Set(s.results.map((r) => r.idx))
  return {
    idx: s.idx,
    total: s.steps.length,
    kind: s.steps[s.idx].kind,
    pendingRevisions: s.steps.flatMap((step, i) => (step.kind === 'revision' && !judged.has(i) ? [`${step.payload.item.kind}:${step.payload.item.key}`] : [])),
  }
}

function readGameResume(): GameResume | null {
  const g = readStoredGame()
  if (!g) return null
  return { mode: g.mode, botName: typeof g.botName === 'string' && g.botName ? g.botName : null, color: g.playerColor === 'b' ? 'b' : 'w', tcLabel: typeof g.tcLabel === 'string' ? g.tcLabel : '', plies: g.sans.length }
}

// Énumérations « a · b · c » et quantités « 2 puzzles » : le point médian reste collé au mot qui le
// précède, un nombre au mot qui le suit ; ni « · » ni un nom sans son nombre ne passent en début de
// ligne. Texte rendu identique (espaces ordinaires), seules ces coupures sont interdites.
function keepNumbers(part: string): ReactNode {
  const pieces = part.split(/(\d+ \S+)/)
  if (pieces.length < 2) return part
  return pieces.map((piece, i) => (i % 2 ? <span key={i} className="whitespace-nowrap">{piece}</span> : piece))
}

function dots(text: string): ReactNode {
  const parts = text.split(' · ')
  return parts.map((part, i) => (
    <Fragment key={i}>
      {keepNumbers(part)}
      {i < parts.length - 1 && <><span className="whitespace-nowrap"> ·</span>{' '}</>}
    </Fragment>
  ))
}

export default function Home() {
  const navigate = useNavigate()
  const [seanceResume] = useState(readSeanceResume)
  const [game] = useState(readGameResume)
  const [series, setSeries] = useState<{ days: number; today: boolean } | null>(null) // série de séances du jour
  const [seanceWeek, setSeanceWeek] = useState(0)
  const [due, setDue] = useState<DueView | 'unavailable' | null>(null) // null : file pas encore lue
  const [path, setPath] = useState<PathState | null>(null) // progression du parcours, null : pas encore connue
  const [week, setWeek] = useState<{ puzzles: number; games: number } | null>(null)
  // App native : proposer de récupérer les données de la PWA (docs/ios-app.md), jusqu'à une
  // restauration réussie ou « Non merci », même après un premier puzzle joué dans l'app.
  const [offerMigration, setOfferMigration] = useState(() => isNative && !migrationDismissed())

  useEffect(() => {
    const from = weekStart(Date.now())
    // Requêtes indexées seulement : jamais puzzles.json ni une table entière.
    void Promise.all([
      db.puzzleAttempts.where('date').aboveOrEqual(from).toArray().then((a) => a.filter((x) => x.success).length),
      db.games.where('date').aboveOrEqual(from).count(),
    ]).then(([puzzles, games]) => setWeek({ puzzles, games }), () => setWeek({ puzzles: 0, games: 0 }))
    void seanceDates().then(
      (d) => {
        setSeries(streak(d))
        setSeanceWeek(d.filter((x) => x >= from).length)
      },
      () => setSeries({ days: 0, today: false }),
    )
    // Chunk introuvable malgré le rechargement : l'accueil reste utilisable, sans le compteur ou sans
    // la progression du parcours.
    void loadRevision().then(async ({ buildReviewSession, describeKinds, loadReviewQueue }) => {
      const q = await loadReviewQueue()
      const key = (i: { kind: string; key: string }) => `${i.kind}:${i.key}`
      const byKey = new Map(q.due.map((i) => [key(i), i]))
      setDue({
        keys: q.due.map(key),
        fresh: buildReviewSession(q.due, revisionBlockSize(q.due.length)).map(key),
        describe: (keys) => describeKinds(keys.flatMap((k) => byKey.get(k) ?? [])),
      })
    }).catch(() => setDue('unavailable'))
    void loadPath().then(async ({ loadPathState }) => setPath(await loadPathState()), () => {})
  }, [])

  const doneToday = series ? series.today : null
  const primary = homePrimary({ seance: seanceResume, game, doneToday })
  const dueKeys = due && due !== 'unavailable' ? due.keys : []
  const inSeance = useMemo(
    () => (due && due !== 'unavailable' ? revisionsInSeance({ due: due.keys, seance: seanceResume, doneToday, fresh: due.fresh }) : []),
    [due, seanceResume, doneToday],
  )
  const extraKeys = dueKeys.filter((k) => !inSeance.includes(k))
  const streakText = series && series.days > 0 ? streakLabel(series.days) : null
  // Compteurs prêts (révision et série de jours, dont dépend le partage des révisions) : posé une
  // fois les deux connus, même indisponibles, pour les mesures et les tests.
  const reviewReady = due === null || series === null ? undefined : due === 'unavailable' ? 'unavailable' : ''

  const seanceMeta = [
    inSeance.length > 0 ? `Commence par ${inSeance.length} révision${inSeance.length > 1 ? 's' : ''} due${inSeance.length > 1 ? 's' : ''}` : null,
    streakText,
  ].filter(Boolean).join(' · ')

  // Carte principale : une seule action immédiate, remplacée par la reprise quand il y en a une.
  let card: { eyebrow: string; title: string; description: ReactNode; status?: ReactNode; cta: string; go: () => void; progress?: ReactNode }
  if (primary.kind === 'resume-seance') {
    const s = primary.seance
    card = {
      eyebrow: 'Séance en cours',
      title: 'Ta séance du jour',
      description: <span data-seance-status>{dots(seanceStepLabel(s))}</span>,
      cta: 'Reprendre la séance',
      go: () => navigate('/seance'),
      progress: <ProgressBar value={s.idx} total={s.total} label="Étapes de la séance du jour terminées" />,
    }
  } else if (primary.kind === 'resume-game') {
    card = {
      eyebrow: 'Partie en cours',
      title: gameTitle(primary.game),
      description: dots(gameMeta(primary.game)),
      cta: 'Reprendre la partie',
      go: () => navigate('/jouer', { replace: true }),
    }
  } else if (primary.kind === 'quick') {
    card = {
      eyebrow: 'Pour aller plus loin',
      title: 'Envie de continuer ?',
      description: 'Une séance rapide de 1 à 2 minutes, adaptée à ton niveau.',
      status: dots(`✓ Faite aujourd'hui${streakText ? ` · ${streakText}` : ''}`),
      cta: 'Séance rapide',
      go: () => navigate('/apprendre', { replace: true, state: { quick: true } }),
    }
  } else {
    card = {
      eyebrow: 'Ta séance du jour',
      title: '10 à 15 minutes guidées',
      description: 'Révisions, puzzles et positions choisis pour toi, enchaînés sans avoir à choisir.',
      status: seanceMeta ? dots(seanceMeta) : undefined,
      cta: 'Commencer',
      go: () => navigate('/seance'),
    }
  }
  const seanceCard = primary.kind === 'seance' || primary.kind === 'pending' || primary.kind === 'resume-seance'

  return (
    <div
      data-testid="home"
      data-home-primary={primary.kind}
      data-review-ready={reviewReady}
      data-seance-ready={series !== null ? '' : undefined}
      data-path-ready={path !== null ? '' : undefined}
      className="mx-auto flex min-h-full max-w-2xl flex-col gap-4 p-4 md:justify-center md:p-8"
    >
      <h1 className="text-2xl leading-tight font-black">
        <span aria-hidden="true">♞ </span>Chess<span className="text-accent">Local</span>
      </h1>

      {/* App native : elle n'a pas la même origine que la PWA, la sauvegarde est le seul pont.
          La carte disparaît après une restauration réussie ou « Non merci ». */}
      {offerMigration && (
        <div data-testid="native-migration" className="flex items-center rounded-xl border border-accent/40 bg-surface-2">
          <button
            type="button"
            data-testid="native-migration-go"
            onClick={() => navigate('/donnees', { replace: true })}
            className="flex min-w-0 flex-1 cursor-pointer items-center gap-3 rounded-l-xl py-2 pl-4 text-left transition hover:bg-surface-3"
          >
            <span className="text-2xl" aria-hidden="true">📲</span>
            <span className="min-w-0 flex-1">
              <span className="block font-semibold">Récupérer tes données</span>
              <span className="block text-sm text-muted">Exporte-les dans la PWA, puis restaure-les ici</span>
            </span>
            <span className="text-xl text-neutral-500" aria-hidden="true">›</span>
          </button>
          <button
            type="button"
            data-testid="native-migration-dismiss"
            aria-label="Non merci"
            title="Non merci"
            onClick={() => { dismissMigration(); setOfferMigration(false) }}
            className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-r-xl text-lg text-neutral-400 transition hover:text-neutral-200"
          >
            ✕
          </button>
        </div>
      )}

      {/* Carte principale. Série de jours pas encore lue (sans reprise) : la carte de la séance garde
          sa place, invisible, pour ne jamais montrer un CTA qui changerait l'instant d'après. */}
      <section
        data-home-card
        aria-labelledby="home-card-title"
        aria-busy={primary.kind === 'pending' || undefined}
        className={`rounded-2xl border border-accent/30 bg-surface-2 p-4 shadow-lg ${primary.kind === 'pending' ? 'invisible' : ''}`}
      >
        <p className="text-sm font-semibold text-accent-light">{card.eyebrow}</p>
        <h2 id="home-card-title" className="mt-1 text-xl leading-tight font-bold">{card.title}</h2>
        <p className="mt-1 text-base leading-6 text-muted">{card.description}</p>
        {card.progress}
        {card.status && (
          <p data-seance-status className="mt-2 text-sm font-semibold text-neutral-300">
            {card.status}
          </p>
        )}
        <Cta data-home-cta data-seance-tile={seanceCard ? '' : undefined} className="mt-4 w-full" onClick={card.go}>
          {card.cta}
        </Cta>
      </section>

      {/* Lignes secondaires : révision due (quantité affichée une seule fois, part de la séance
          nommée), et la séance du jour quand une partie ou la séance rapide tient la carte. */}
      {(dueKeys.length > 0 || !seanceCard) && (
        <div className="grid gap-2">
          {dueKeys.length > 0 && (
            <ActivityCard
              to="/revision"
              data-testid="home-revision"
              data-review-in-seance={inSeance.length}
              icon={<NavIcon name="reviser" className="h-6 w-6 text-amber-300" />}
              title="À réviser aujourd'hui"
              description={dots(revisionLine(dueKeys.length, inSeance.length, due && due !== 'unavailable' ? due.describe(extraKeys.length ? extraKeys : dueKeys) : ''))}
              aside={
                <span
                  data-review-count
                  className={`shrink-0 rounded-full px-3 py-1 text-base font-bold tabular-nums ${extraKeys.length > 0 ? 'bg-amber-400 text-neutral-900' : 'bg-surface-3 text-neutral-200'}`}
                >
                  {dueKeys.length}
                </span>
              }
            />
          )}
          {!seanceCard && (
            <ActivityCard
              to="/seance"
              data-seance-tile
              icon={<NavIcon name="seance" className="h-6 w-6 text-accent" />}
              title={primary.kind === 'quick' ? 'Refaire une séance du jour' : 'Ta séance du jour'}
              description={
                // Séance rapide en carte : le statut de la séance (faite, série) y est déjà.
                primary.kind === 'quick' ? '10 à 15 minutes guidées' : <span data-seance-status>{seanceMeta ? dots(seanceMeta) : '10 à 15 minutes guidées'}</span>
              }
            />
          )}
        </div>
      )}

      {/* Raccourcis discrets vers deux onglets : `replace`, comme la nav basse. */}
      <div className="grid grid-cols-2 gap-2">
        <ActivityCard
          to="/jouer"
          replace
          data-testid="home-play"
          icon={<NavIcon name="jouer" className="h-6 w-6 text-accent" />}
          title="Jouer"
          description={game && primary.kind !== 'resume-game' ? 'Partie en cours' : 'Une partie'}
        />
        <ActivityCard
          to="/puzzles"
          replace
          data-testid="home-puzzles"
          icon={<NavIcon name="puzzles" className="h-6 w-6 text-accent" />}
          title="Puzzles"
          description="À ton niveau"
        />
      </div>

      {/* Progression, après les actions : parcours d'apprentissage (tuile de transition du plan) et
          Mon bilan. Descentes empilées. */}
      <section aria-labelledby="home-progress-title">
        <h2 id="home-progress-title" className="mb-2 text-lg font-semibold">Ta progression</h2>
        <div className="grid gap-2">
          <ActivityCard
            to="/apprendre/parcours"
            data-testid="home-path"
            icon={<NavIcon name="apprendre" className="h-6 w-6 text-accent" />}
            title="Parcours d'apprentissage"
            description={path ? (path.current ? `Prochaine étape : ${path.current.step.title}` : 'Parcours terminé') : undefined}
          >
            {path && <ProgressBar value={path.done} total={path.total} label="Étapes du parcours validées" testId="home-path-progress" />}
          </ActivityCard>
          <ActivityCard
            to="/insights"
            data-testid="home-bilan"
            icon={<NavIcon name="bilan" className="h-6 w-6 text-accent" />}
            title="Voir mon bilan"
            description={week ? dots(weekSummary({ seances: seanceWeek, ...week })) : undefined}
          />
        </div>
      </section>
    </div>
  )
}
