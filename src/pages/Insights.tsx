// Insights (/insights) : le coach qui analyse mes N dernières parties d'une cadence, façon
// chess.com Insights. Au montage : seulement la lecture du cache (aucune requête, aucun moteur).
// Le tap « Analyser » lit la liste (chess.com + ChessLocal), puis analyse les parties absentes du
// cache sur un seul moteur, avec progression, pause quand la page est masquée, annulation et reprise.
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CoachAvatar } from '../components/CoachBubble'
import { Cta } from '../components/Cta'
import { AccuracySpark, MeterBar, WdlBar, WdlLegend } from '../components/InsightsCharts'
import { db, type ReviewRow } from '../lib/db'
import { Engine } from '../lib/engine'
import { ChesscomNetworkError, normalizeUsername, timeClassLabel } from '../lib/chesscom'
import {
  BACK, COLOR_FR, ERROR_KINDS, ERROR_META, PHASES, PHASE_FR, computeInsights, fr1, frDate, pct,
  type Example, type Finding, type Insights as Report, type PlanStep,
} from '../lib/insights'
import { cachedFor, collectGames, depthFor, estimateForConfig, formatDuration, runSeries, type Candidate, type RunProgress } from '../lib/insightsRun'
import {
  INSIGHTS_COUNTS, readInsights, writeInsights, type InsightsConfig, type InsightsLastRun, type InsightsSource, type InsightsTimeClass,
} from '../lib/insightsStore'
import { getFamily } from '../lib/openingTrainer'
import { useSettings } from '../store/settings'

const TC_OPTIONS: { id: InsightsTimeClass; label: string; icon: string }[] = [
  { id: 'bullet', label: 'Bullet', icon: '🚀' },
  { id: 'blitz', label: 'Blitz', icon: '⚡' },
  { id: 'rapid', label: 'Rapide', icon: '⏱' },
  { id: 'unlimited', label: 'Sans limite', icon: '∞' },
]
// Typographie française : espace insécable avant « % », « : », « ; », « ? », « ! » (jamais de
// « % » seul en début de ligne sur un écran étroit).
const nb = (t: string) => t.replace(/ ([%:;?!])/g, '\u00a0$1')
const shortDate = (ms: number) => new Date(ms).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })
// « Le 7 oct. 2026 », « Du 4 au 19 oct. 2026 », « Du 28 sept. au 3 oct. 2026 », années précisées si elles diffèrent.
function periodFr(from: number, to: number): string {
  const a = new Date(from)
  const b = new Date(to)
  if (a.toDateString() === b.toDateString()) return `Le ${frDate(to)}`
  if (a.getFullYear() !== b.getFullYear()) return `Du ${frDate(from)} au ${frDate(to)}`
  if (a.getMonth() === b.getMonth()) return `Du ${a.getDate()} au ${frDate(to)}`
  return `Du ${shortDate(from)} au ${frDate(to)}`
}
// Ligne de cache conforme au rapport mémorisé : même profondeur et, pour chess.com, même compte.
function rowFitsRun(r: ReviewRow, run: InsightsLastRun): boolean {
  if (run.depth !== undefined && r.depth !== run.depth) return false
  return run.username === undefined || r.source !== 'chesscom' || r.username === run.username
}

interface Shown {
  report: Report
  rows: Map<string, ReviewRow>
  run: InsightsLastRun
  config: InsightsConfig
}

// Série lancée : la liste lisible de `collectGames` (la seule que comptent la progression, le
// bandeau d'interruption et le rapport), sa profondeur, sa configuration et son pseudo.
interface Series {
  cands: Pick<Candidate, 'key' | 'username'>[]
  depth: number
  cfg: InsightsConfig
  user: string | null
  failed: number
}

// Rapport mémorisé pour le retour sur la page : complet, ou partiel après une interruption.
function saveRun(series: Series, rows: ReviewRow[], partial: boolean): InsightsLastRun {
  const lastRun: InsightsLastRun = {
    keys: rows.map((r) => r.key), at: Date.now(), depth: series.depth, username: series.user, partial, total: series.cands.length, failed: series.failed,
  }
  writeInsights({ config: series.cfg, lastRun })
  return lastRun
}

type Stage = { kind: 'idle' } | { kind: 'loading' } | { kind: 'running'; progress: RunProgress | null }

export default function Insights() {
  const navigate = useNavigate()
  const { chesscomUsername, setChesscomUsername } = useSettings()
  const initial = useMemo(() => readInsights(), [])
  const [config, setConfig] = useState<InsightsConfig>(initial.config)
  const [username, setUsername] = useState(chesscomUsername)
  const [shown, setShown] = useState<Shown | null>(null)
  const [editing, setEditing] = useState(false)
  const [restoring, setRestoring] = useState(!!initial.lastRun)
  const [stage, setStage] = useState<Stage>({ kind: 'idle' })
  const [interrupted, setInterrupted] = useState<{ done: number; total: number } | null>(null)
  const [error, setError] = useState<{ message: string; retry: boolean } | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [hidden, setHidden] = useState(() => document.hidden)
  const engineRef = useRef<Engine | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const tokenRef = useRef(0)
  // Série en cours : liste des parties, profondeur et configuration (annulation, sauvegarde).
  const seriesRef = useRef<Series | null>(null)

  // Moteur créé seulement s'il reste une partie à analyser, arrêté au démontage : la série est
  // annulée et le jeton périmé (une liste qui arrive après le départ ne relance rien).
  useEffect(
    () => () => {
      tokenRef.current++
      abortRef.current?.abort()
      engineRef.current?.quit()
      engineRef.current = null
    },
    [],
  )

  useEffect(() => {
    const onVis = () => setHidden(document.hidden)
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [])

  // Retour sur la page (Analyse, Apprendre, app relancée, hors ligne) : rapport reconstruit depuis
  // la table `reviews` si toutes ses parties y sont encore, sinon le panneau.
  useEffect(() => {
    const last = initial.lastRun
    if (!last || last.keys.length === 0) {
      setRestoring(false)
      return
    }
    let alive = true
    void db.reviews.bulkGet(last.keys).then(
      (rows) => {
        if (!alive) return
        setRestoring(false)
        // Une série quittée en cours a pu réécrire des lignes à une autre profondeur (ou depuis un
        // autre compte) : le rapport mélangerait deux analyses, retour au panneau.
        if (!rows.every((r) => r && rowFitsRun(r, last))) return
        try {
          show(rows as ReviewRow[], last, initial.config)
        } catch (e) {
          console.error('[insights] rapport non restauré', e)
          return
        }
        if (last.partial && last.total) setInterrupted({ done: last.keys.length, total: last.total })
      },
      () => alive && setRestoring(false),
    )
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function show(rows: ReviewRow[], run: InsightsLastRun, cfg: InsightsConfig) {
    const report = computeInsights(rows)
    // Parties dont le PGN ne se rejoue pas pendant la série : comptées avec les lignes illisibles.
    if (run.failed) report.games.skipped += run.failed
    setShown({ report, rows: new Map(rows.map((r) => [r.key, r])), run, config: cfg })
    setEditing(false)
  }

  const needsUserFor = (cfg: InsightsConfig) => cfg.sources.includes('chesscom') && cfg.timeClass !== 'unlimited'
  const needsUser = needsUserFor(config)
  const busy = stage.kind !== 'idle'
  let userError: string | null = null
  if (needsUser) {
    try {
      normalizeUsername(username)
    } catch (e) {
      userError = username.trim() ? (e as Error).message : null
    }
  }
  const canRunFor = (cfg: InsightsConfig) => !busy && (cfg.sources.includes('local') || needsUserFor(cfg)) && (!needsUserFor(cfg) || (username.trim() !== '' && !userError))
  const canRun = canRunFor(config)
  // Reprendre relance la série interrompue, même si le panneau a changé depuis.
  const resumeCfg = seriesRef.current?.cfg ?? config

  // `cfg` : configuration de la série (celle du panneau, ou celle de la série interrompue).
  async function run(cfg: InsightsConfig = config) {
    if (!canRunFor(cfg)) return
    // Une seule série à la fois : la précédente (double tap, Reprendre) est annulée.
    abortRef.current?.abort()
    const token = ++tokenRef.current
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setError(null)
    setNotice(null)
    setInterrupted(null)
    setStage({ kind: 'loading' })
    seriesRef.current = null
    let collected
    try {
      collected = await collectGames(cfg, username)
    } catch (e) {
      if (token !== tokenRef.current) return
      setStage({ kind: 'idle' })
      setError({ message: (e as Error).message || 'Impossible de lire tes parties.', retry: e instanceof ChesscomNetworkError })
      return
    }
    if (token !== tokenRef.current) return
    const user = needsUserFor(cfg) ? normalizeUsername(username) : null
    if (user) setChesscomUsername(user)
    const { candidates, failed, offline } = collected
    const found = candidates.length + failed
    const historySource = user ? (cfg.sources.includes('local') ? 'chess.com et ChessLocal' : 'chess.com') : 'ChessLocal'
    const historyMessage = `${found} partie${found === 1 ? '' : 's'} de ${timeClassLabel(cfg.timeClass)} trouvée${found === 1 ? '' : 's'} sur tout ton historique ${historySource}.`
    if (offline) setNotice('Hors ligne : seules tes parties chess.com déjà analysées sont utilisées.')
    else if (found > 0 && found < cfg.count) setNotice(historyMessage)
    if (candidates.length === 0) {
      setStage({ kind: 'idle' })
      setError({
        message: failed
          ? 'Aucune de ces parties ne se laisse analyser (PGN illisibles).'
          : offline
            ? `Aucune partie de ${timeClassLabel(cfg.timeClass)} disponible hors ligne.`
            : historyMessage,
        retry: false,
      })
      return
    }
    const series: Series = { cands: candidates, depth: depthFor(cfg.count), cfg, user, failed }
    seriesRef.current = series
    setStage({ kind: 'running', progress: null })
    const engine = () => {
      if (ctrl.signal.aborted || token !== tokenRef.current) throw new DOMException('Série annulée', 'AbortError')
      engineRef.current ??= new Engine()
      return engineRef.current
    }
    try {
      const rows = await runSeries(candidates, series.depth, engine, ctrl.signal, (p) => {
        if (token === tokenRef.current) setStage({ kind: 'running', progress: p })
      })
      if (token !== tokenRef.current) return
      setStage({ kind: 'idle' })
      show(rows, saveRun(series, rows, false), cfg)
    } catch (e) {
      if (token !== tokenRef.current) return
      if ((e as DOMException)?.name !== 'AbortError') {
        console.error('[insights] série interrompue', e)
        // Moteur peut-être mort (trap WASM) : la relance en crée un neuf.
        engineRef.current?.quit()
        engineRef.current = null
        setError({ message: 'Analyse interrompue par une erreur. Relance : les parties déjà analysées sont gardées.', retry: true })
      }
      setStage({ kind: 'idle' })
      await afterInterruption(series, token)
    }
  }

  // Série arrêtée : rapport sur les parties déjà prêtes (cache), et bandeau de reprise. Ignoré si
  // une autre série a démarré (ou la page est quittée) pendant la lecture.
  async function afterInterruption(series: Series, token: number) {
    let rows: ReviewRow[]
    try {
      rows = (await cachedFor(series.cands, series.depth)).filter((r): r is ReviewRow => !!r)
    } catch (e) {
      console.error('[insights] cache illisible', e)
      rows = []
    }
    if (token !== tokenRef.current) return
    setInterrupted({ done: rows.length, total: series.cands.length })
    if (rows.length > 0) {
      const lastRun = saveRun(series, rows, true)
      try {
        show(rows, lastRun, series.cfg)
      } catch (e) {
        console.error('[insights] rapport partiel non calculé', e)
      }
    }
  }

  // Annuler : l'interface passe tout de suite en « interrompue », sans attendre la recherche en
  // cours (elle garde le mutex du moteur) ; son résultat sera jeté par le jeton. Le rapport partiel
  // se lit dans le cache : seules les parties terminées y sont.
  function cancel() {
    const ctrl = abortRef.current
    if (!ctrl || stage.kind === 'idle') return
    ctrl.abort()
    const token = ++tokenRef.current
    setStage({ kind: 'idle' })
    const series = seriesRef.current
    if (series) void afterInterruption(series, token)
  }

  function openExample(e: Example) {
    const row = shown?.rows.get(e.key)
    if (!row) return
    navigate('/analyse', {
      state: {
        fen: row.review.startFen,
        uci: row.review.moves.map((m) => m.uci),
        viewIndex: e.index - 1,
        orientation: e.color,
        label: e.label,
        ...BACK,
      },
    })
  }

  // Pendant la série, le panneau disparaît : la configuration est figée et la progression reste en haut.
  const showPanel = (!shown || editing) && !busy
  const estimate = estimateForConfig(config)

  return (
    <div className="mx-auto max-w-3xl p-4 pb-10 md:p-6">
      <h1 className="text-2xl font-bold">🧠 Insights</h1>
      <p className="mb-4 text-sm text-neutral-400">Ton coach passe tes dernières parties au crible de Stockfish et te dit où tu pèches.</p>

      {restoring && !shown && <div className="h-24 animate-pulse rounded-lg bg-surface-2" />}

      {shown && !showPanel && (
        <div className="mb-4 flex items-center gap-3 rounded-lg bg-surface-2 px-4 py-3">
          <div className="min-w-0 flex-1 text-sm">
            <div className="font-semibold">
              {shown.report.games.n} partie{shown.report.games.n > 1 ? 's' : ''} de {timeClassLabel(shown.config.timeClass)}
            </div>
            <div className="text-xs text-neutral-400">
              {shown.report.games.from && shown.report.games.to && periodFr(shown.report.games.from, shown.report.games.to)}
            </div>
            <div className="text-xs text-neutral-500">
              Rapport du {shortDate(shown.run.at)}
              {shown.run.depth ? ` · profondeur ${shown.run.depth}` : ''}
            </div>
          </div>
          <button
            data-testid="insights-edit"
            disabled={busy}
            onClick={() => setEditing(true)}
            className="shrink-0 cursor-pointer rounded-lg bg-surface-3 px-3 py-2 text-sm font-semibold hover:brightness-110 disabled:opacity-40"
          >
            Modifier
          </button>
        </div>
      )}

      {stage.kind === 'loading' && (
        <div className="mb-4 rounded-lg bg-surface-2 p-4 text-sm text-neutral-300">Lecture de tes parties…</div>
      )}
      {stage.kind === 'running' && <ProgressCard progress={stage.progress} paused={hidden} onCancel={cancel} />}

      {interrupted && !busy && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-[#f7c631]/40 bg-surface-2 px-4 py-3">
          <div className="min-w-0 flex-1 text-sm">
            <div className="font-semibold">Série interrompue</div>
            <div className="text-neutral-300">
              {interrupted.done} partie{interrupted.done > 1 ? 's' : ''} analysée{interrupted.done > 1 ? 's' : ''} sur {interrupted.total}
              {interrupted.done > 0 ? ' : le rapport ci-dessous ne porte que sur elles.' : '.'}
            </div>
          </div>
          <button
            data-testid="insights-resume"
            onClick={() => void run(resumeCfg)}
            disabled={!canRunFor(resumeCfg)}
            className="shrink-0 cursor-pointer rounded-lg bg-accent px-4 py-2 text-sm font-bold text-white disabled:opacity-40"
          >
            Reprendre
          </button>
        </div>
      )}

      {notice && <div className="mb-4 rounded-lg bg-surface-2 px-4 py-3 text-sm text-neutral-300">{notice}</div>}
      {error && (
        <div role="alert" className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-red-500/40 bg-surface-2 px-4 py-3 text-sm">
          <span className="min-w-0 flex-1 text-red-300">{error.message}</span>
          {error.retry && (
            <button data-testid="insights-retry" onClick={() => void run()} disabled={!canRun} className="shrink-0 cursor-pointer rounded-lg bg-surface-3 px-3 py-2 font-semibold">
              Réessayer
            </button>
          )}
        </div>
      )}

      {!restoring && showPanel && (
        <ConfigPanel
          config={config}
          setConfig={setConfig}
          username={username}
          setUsername={setUsername}
          needsUser={needsUser}
          userError={userError}
          busy={busy}
          canRun={canRun}
          estimate={estimate}
          onRun={() => void run()}
          onClose={shown && !busy ? () => setEditing(false) : undefined}
        />
      )}

      {shown && <ReportView report={shown.report} onExample={openExample} />}
    </div>
  )
}

// ------------------------------------------------------------------ panneau de configuration

function Chip({ on, children, ...rest }: { on: boolean; children: ReactNode } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...rest}
      aria-pressed={on}
      className={`min-h-11 cursor-pointer rounded-lg border-2 px-2 py-2 text-sm font-semibold transition disabled:cursor-default disabled:opacity-50 ${
        on ? 'border-accent bg-accent/15 text-white' : 'border-transparent bg-surface-3 text-neutral-300 hover:brightness-110'
      }`}
    >
      {children}
    </button>
  )
}

function ConfigPanel(props: {
  config: InsightsConfig
  setConfig: (c: InsightsConfig) => void
  username: string
  setUsername: (u: string) => void
  needsUser: boolean
  userError: string | null
  busy: boolean
  canRun: boolean
  estimate: number
  onRun: () => void
  onClose?: () => void
}) {
  const { config, setConfig, busy } = props
  const set = (patch: Partial<InsightsConfig>) => setConfig({ ...config, ...patch })
  const toggleSource = (s: InsightsSource) => {
    const has = config.sources.includes(s)
    set({ sources: has ? config.sources.filter((x) => x !== s) : [...config.sources, s] })
  }
  return (
    <section data-testid="insights-config" className="mb-4 space-y-4 rounded-lg bg-surface-2 p-4">
      <div>
        <h2 className="mb-2 text-sm font-semibold text-neutral-300">Cadence</h2>
        <div className="grid grid-cols-4 gap-2">
          {TC_OPTIONS.map((t) => (
            <Chip key={t.id} data-testid={`tc-${t.id}`} on={config.timeClass === t.id} disabled={busy} onClick={() => set({ timeClass: t.id })}>
              <span className="block text-base leading-none" aria-hidden="true">{t.icon}</span>
              <span className="block text-xs">{t.label}</span>
            </Chip>
          ))}
        </div>
        {config.timeClass === 'unlimited' && <p className="mt-2 text-xs text-neutral-400">chess.com ne fournit pas la cadence « Sans limite ». Sélectionne ChessLocal pour analyser tes parties contre les bots.</p>}
      </div>
      <div>
        <h2 className="mb-2 text-sm font-semibold text-neutral-300">Parties récentes</h2>
        <div className="grid grid-cols-4 gap-2">
          {INSIGHTS_COUNTS.map((n) => (
            <Chip key={n} data-testid={`count-${n}`} on={config.count === n} disabled={busy} onClick={() => set({ count: n })}>
              {n}
            </Chip>
          ))}
        </div>
      </div>
      <div>
        <h2 className="mb-2 text-sm font-semibold text-neutral-300">Sources</h2>
        <div className="grid grid-cols-2 gap-2">
          <Chip data-testid="src-chesscom" on={config.sources.includes('chesscom')} disabled={busy} onClick={() => toggleSource('chesscom')}>
            ♟ chess.com
          </Chip>
          <Chip data-testid="src-local" on={config.sources.includes('local')} disabled={busy} onClick={() => toggleSource('local')}>
            ♞ ChessLocal
          </Chip>
        </div>
        {props.needsUser && (
          <label className="mt-3 block">
            <span className="mb-1 block text-xs text-neutral-400">Pseudo chess.com</span>
            <input
              data-testid="insights-username"
              value={props.username}
              disabled={busy}
              onChange={(e) => props.setUsername(e.target.value)}
              placeholder="ton pseudo"
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              className="w-full rounded-lg bg-surface-3 px-3 py-2.5 text-base outline-none focus:ring-2 focus:ring-accent"
            />
            {props.userError && <span className="mt-1 block text-xs text-red-300">{props.userError}</span>}
          </label>
        )}
      </div>
      <p data-testid="insights-estimate" className="text-xs text-neutral-400">
        Profondeur {depthFor(config.count)} · environ {formatDuration(props.estimate)} sur iPhone pour {config.count} parties (les parties déjà analysées sont instantanées).
      </p>
      <div className="flex gap-2">
        {props.onClose && (
          <Cta variant="secondary" className="shrink-0" onClick={props.onClose}>
            Fermer
          </Cta>
        )}
        <Cta data-testid="insights-run" className="min-w-0 flex-1 text-base" disabled={!props.canRun} onClick={props.onRun}>
          Analyser {config.count} parties
        </Cta>
      </div>
    </section>
  )
}

function ProgressCard({ progress, paused, onCancel }: { progress: RunProgress | null; paused: boolean; onCancel: () => void }) {
  const total = progress?.total ?? 0
  const value = progress ? Math.round((progress.analysed / Math.max(1, total)) * 100) : 0
  return (
    <section className="mb-4 rounded-lg bg-surface-2 p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3 text-sm">
        <span className="font-semibold">{progress ? `Partie ${Math.min(progress.game, total)} sur ${total}` : 'Préparation du moteur…'}</span>
        {paused ? (
          <span data-testid="insights-paused" className="text-xs font-semibold text-[#f7c631]">En pause (app en arrière-plan)</span>
        ) : (
          <span className="text-xs text-neutral-400">{progress?.etaSec ? `≈ ${formatDuration(progress.etaSec)} restantes` : ''}</span>
        )}
      </div>
      <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={value} aria-label="Analyse des parties">
        <MeterBar value={value} />
      </div>
      <p className="mt-2 text-xs text-neutral-400">Stockfish analyse chaque coup. Garde l'app ouverte : la série se met en pause si tu la quittes.</p>
      <button data-testid="insights-cancel" onClick={onCancel} className="mt-3 w-full cursor-pointer rounded-lg bg-surface-3 py-2.5 text-sm font-semibold hover:brightness-110">
        Annuler
      </button>
    </section>
  )
}

// ------------------------------------------------------------------ rapport

function Card({ title, children, testid, aside, ...data }: { title: string; children: ReactNode; testid?: string; aside?: ReactNode } & Record<`data-${string}`, string | number>) {
  return (
    <section data-testid={testid} {...data} className="rounded-lg bg-surface-2 p-4">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="font-bold">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  )
}

function SectionLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="shrink-0 text-xs font-semibold text-accent hover:underline">
      {children}
    </Link>
  )
}

function PlanLink({ step }: { step: PlanStep }) {
  const navigate = useNavigate()
  if (!step.to) return <li className="text-sm text-neutral-300">💡 {step.label}</li>
  const cls = 'inline-flex min-h-9 items-center gap-1 rounded-lg bg-surface-3 px-3 py-1.5 text-sm font-semibold text-white hover:brightness-110'
  return (
    <li>
      {step.state ? (
        <button data-testid="plan-link" data-tactic={step.state.tactic} className={`${cls} cursor-pointer`} onClick={() => navigate(step.to!, { state: step.state })}>
          ▶ {step.label}
        </button>
      ) : (
        <Link data-testid="plan-link" to={step.to} className={cls}>
          ▶ {step.label}
        </Link>
      )}
    </li>
  )
}

function ExampleButton({ e, onOpen, withLabel = false }: { e: Example; onOpen: (e: Example) => void; withLabel?: boolean }) {
  return (
    <button
      data-testid="example"
      data-key={e.key}
      data-ply={e.ply}
      onClick={() => onOpen(e)}
      title={`${e.label} · ${e.moveNo} ${e.san}`}
      className="flex min-h-9 max-w-full cursor-pointer items-center gap-1.5 rounded-lg bg-surface-3 px-2.5 py-1.5 text-left text-xs hover:brightness-110"
    >
      <span className="shrink-0 font-bold text-white">
        {e.moveNo} <span className="text-[1.2em]">{e.sanFig}</span>
      </span>
      {e.bestSan && <span className="shrink-0 text-neutral-400">au lieu de {e.bestSan}</span>}
      {withLabel && <span className="min-w-0 truncate text-neutral-500">· {e.label.replace(/^(chess\.com|ChessLocal) · /, '')}</span>}
    </button>
  )
}

function FindingCard({ f, onExample }: { f: Finding; onExample: (e: Example) => void }) {
  const weak = f.kind === 'faiblesse'
  return (
    <li data-id={f.id} className="rounded-lg bg-surface-2 p-4">
      <div className="flex items-start gap-2">
        <span aria-hidden="true" className="text-lg leading-6">{weak ? '⚠️' : '✅'}</span>
        <div className="min-w-0 flex-1">
          <h3 className="font-bold leading-6">{f.title}</h3>
          <p className="mt-0.5 text-sm text-neutral-300">{nb(f.detail)}</p>
        </div>
      </div>
      {f.plan.length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 text-xs font-semibold tracking-wide text-neutral-400 uppercase">Plan d'entraînement</div>
          <ul className="flex flex-wrap gap-2">
            {f.plan.map((s, i) => (
              <PlanLink key={i} step={s} />
            ))}
          </ul>
        </div>
      )}
      {f.examples.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-semibold text-neutral-300">Exemples tirés de tes parties ({f.examples.length})</summary>
          <div className="mt-2 flex flex-col items-start gap-1.5">
            {f.examples.map((e) => (
              <ExampleButton key={`${e.key}:${e.index}`} e={e} onOpen={onExample} withLabel />
            ))}
          </div>
        </details>
      )}
    </li>
  )
}

// Bulle du coach : l'essentiel (bilan et « à bosser en premier ») visible, le détail sur demande,
// pour que forces et faiblesses restent près du haut de l'écran.
function CoachSummary({ narrative, mood }: { narrative: string[]; mood: 'happy' | 'thinking' }) {
  const [open, setOpen] = useState(false)
  const foldable = narrative.length > 3
  const shown = !foldable || open ? narrative : [narrative[0], narrative[narrative.length - 1]]
  return (
    <section data-testid="insights-coach" className="flex items-start gap-2">
      <CoachAvatar mood={mood} />
      <div className="relative min-w-0 flex-1 rounded-2xl bg-white p-3 text-[15px] leading-snug text-neutral-900 shadow-lg">
        <div className="absolute top-[18px] -left-1.5 h-3 w-3 rotate-45 bg-white" />
        {shown.map((s, i) => (
          <p key={i} className={i ? 'mt-1.5' : ''}>
            {nb(s)}
          </p>
        ))}
        {foldable && (
          <button
            data-testid="coach-more"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
            className="mt-2 cursor-pointer text-sm font-bold text-[#5d9948] hover:underline"
          >
            {open ? 'Réduire' : `Voir le bilan complet (${narrative.length - 2} points de plus)`}
          </button>
        )}
      </div>
    </section>
  )
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="min-w-0">
      <div className="text-xl font-black">{value}</div>
      <div className="text-xs text-neutral-400">{label}</div>
    </div>
  )
}

// Évaluation en pions, signe explicite et vrai signe moins : « +0,6 », « −1,2 ».
const signedPawns = (cp: number) => `${cp > 0 ? '+' : cp < 0 ? '−' : ''}${fr1(Math.abs(cp) / 100)}`

function ReportView({ report: r, onExample }: { report: Report; onExample: (e: Example) => void }) {
  const g = r.games
  const errorsShown = ERROR_KINDS.map((k) => r.errors.find((e) => e.kind === k)!).filter((e) => e.count > 0 && e.kind !== 'missedKingAttack')
  const maxErr = Math.max(1, ...errorsShown.map((e) => e.count))
  const t = r.time
  const bandFr = { weaker: 'Plus faibles', equal: 'Même niveau', stronger: 'Plus forts' } as const
  return (
    <div data-testid="insights-report" className="space-y-4">
      <CoachSummary narrative={r.narrative} mood={r.findings.weaknesses.length === 0 && g.n >= 5 ? 'happy' : 'thinking'} />

      {/* Faiblesses et forces */}
      {g.n >= 5 && (
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <h2 className="mb-2 font-bold">À travailler</h2>
            {r.findings.weaknesses.length ? (
              <ul data-testid="insights-weaknesses" className="space-y-3">
                {r.findings.weaknesses.map((f) => (
                  <FindingCard key={f.id} f={f} onExample={onExample} />
                ))}
              </ul>
            ) : (
              <p data-testid="insights-weaknesses" className="rounded-lg bg-surface-2 p-4 text-sm text-neutral-300">Aucune faiblesse nette sur ces parties.</p>
            )}
          </div>
          <div>
            <h2 className="mb-2 font-bold">Tes forces</h2>
            {r.findings.strengths.length ? (
              <ul data-testid="insights-strengths" className="space-y-3">
                {r.findings.strengths.map((f) => (
                  <FindingCard key={f.id} f={f} onExample={onExample} />
                ))}
              </ul>
            ) : (
              <p data-testid="insights-strengths" className="rounded-lg bg-surface-2 p-4 text-sm text-neutral-300">Pas encore de force qui ressort nettement : il faut plus de parties.</p>
            )}
          </div>
        </div>
      )}

      {/* Précision et résultats */}
      <Card title="Précision et résultats" testid="insights-accuracy">
        <div className="mb-3 grid grid-cols-3 gap-3">
          <Stat value={r.accuracy.mean !== null ? fr1(r.accuracy.mean) : '-'} label="précision moyenne" />
          <Stat value={nb(pct(g.score))} label="score" />
          <Stat value={String(g.n)} label={`partie${g.n > 1 ? 's' : ''}`} />
        </div>
        <WdlBar wins={g.wins} draws={g.draws} losses={g.losses} />
        <div className="mt-1.5">
          <WdlLegend wins={g.wins} draws={g.draws} losses={g.losses} />
        </div>
        {r.accuracy.perGame.length >= 2 && (
          <div className="mt-4">
            <div className="mb-1 text-xs text-neutral-400">Précision par partie, de la plus ancienne à la plus récente (pointillés : moyenne)</div>
            <AccuracySpark
              mean={r.accuracy.mean}
              points={r.accuracy.perGame.map((p) => ({ acc: p.acc, result: p.result, label: `${fr1(p.acc)} · ${frDate(p.date)}` }))}
            />
          </div>
        )}
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {(['w', 'b'] as const).map((c) => {
            const s = g.byColor[c]
            return (
              <div key={c} data-color={c} className="rounded-lg bg-surface-3/60 p-3">
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span className="flex items-center gap-1.5 font-semibold">
                    <span className={`inline-block h-3 w-3 rounded-sm ${c === 'w' ? 'bg-neutral-100' : 'border border-neutral-500 bg-neutral-900'}`} />
                    Avec les {COLOR_FR[c]}
                  </span>
                  <span className="text-neutral-300">{s.n ? nb(`${pct(s.score)} · ${s.accuracy !== null ? fr1(s.accuracy) : '-'}`) : 'aucune partie'}</span>
                </div>
                <WdlBar wins={s.wins} draws={s.draws} losses={s.losses} className="h-2" />
              </div>
            )
          })}
        </div>
        {r.ratingBands && (
          <div className="mt-4 space-y-1.5">
            <div className="text-xs text-neutral-400">Score selon l'Elo adverse (écart de 100 points ou plus)</div>
            {(['weaker', 'equal', 'stronger'] as const).map((k) => {
              const b = r.ratingBands![k]
              return (
                <div key={k} className="grid grid-cols-[1fr_5rem_4.5rem] items-center gap-2 text-sm">
                  <span className="min-w-0 truncate text-neutral-300">{bandFr[k]}</span>
                  <MeterBar value={b.score ?? 0} tone={b.n ? 'accent' : 'muted'} />
                  <span className="text-right text-xs text-neutral-300">{b.n ? nb(`${pct(b.score!)} (${b.n})`) : '-'}</span>
                </div>
              )
            })}
          </div>
        )}
        {r.tilt && (
          <p className="mt-3 text-sm text-neutral-300">
            {nb(`Juste après une défaite : score ${pct(r.tilt.score)} sur ${r.tilt.n} parties (contre ${pct(r.tilt.overall)} en tout).`)}
          </p>
        )}
      </Card>

      {/* Phases */}
      <Card title="Par phase de jeu" testid="insights-phases" aside={<SectionLink to="/finales">Finales</SectionLink>}>
        <p className="mb-3 text-xs text-neutral-400">Coups hors théorie seulement : réciter ses gammes ne compte pas.</p>
        <div className="space-y-3">
          {PHASES.map((p) => {
            const s = r.phases[p]
            const enough = s.moves >= 5 && s.accuracy !== null
            return (
              <div
                key={p}
                data-phase={p}
                data-moves={s.moves}
                data-accuracy={s.accuracy !== null ? fr1(s.accuracy) : ''}
                data-mistakes={fr1(s.mistakesPer100)}
                data-blunders={fr1(s.blundersPer100)}
              >
                <div className="mb-1 flex items-baseline justify-between gap-2 text-sm">
                  <span className="font-semibold">{PHASE_FR[p]}</span>
                  <span className="text-neutral-300">{enough ? fr1(s.accuracy!) : <span className="text-neutral-500">pas assez de coups</span>}</span>
                </div>
                <MeterBar value={enough ? s.accuracy! : 0} tone={!enough ? 'muted' : s.accuracy! >= 80 ? 'accent' : s.accuracy! >= 65 ? 'warn' : 'bad'} />
                <div className="mt-1 text-xs text-neutral-400">
                  {s.moves} coup{s.moves > 1 ? 's' : ''} · {fr1(s.blundersPer100)} gaffes et {fr1(s.mistakesPer100)} erreurs pour 100 coups · {s.gamesEnded} partie{s.gamesEnded > 1 ? 's' : ''} terminée{s.gamesEnded > 1 ? 's' : ''} ici
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      {/* Ouvertures */}
      <Card title="Ouvertures" testid="insights-openings" aside={<SectionLink to="/ouvertures">Entraîneur</SectionLink>}>
        {r.openings.length === 0 ? (
          <p className="text-sm text-neutral-400">Aucune ouverture reconnue.</p>
        ) : (
          <ul className="space-y-2.5">
            {r.openings.slice(0, 12).map((o) => {
              const fam = getFamily(o.key)
              const name = (
                <span className="flex min-w-0 items-center gap-1.5">
                  <span className={`inline-block h-3 w-3 shrink-0 rounded-sm ${o.color === 'w' ? 'bg-neutral-100' : 'border border-neutral-500 bg-neutral-900'}`} title={COLOR_FR[o.color]} />
                  <span className="truncate">{o.name}</span>
                  {o.costly && <span className="shrink-0 rounded bg-red-500/20 px-1.5 text-[10px] font-bold text-red-300">te coûte</span>}
                </span>
              )
              return (
                <li key={`${o.key}|${o.color}`} data-opening={o.name} data-color={o.color}>
                  <div className="mb-1 flex items-center justify-between gap-2 text-sm">
                    {fam ? (
                      <Link to={`/ouvertures?famille=${encodeURIComponent(o.key)}&camp=${o.color}`} className="min-w-0 font-semibold hover:underline">
                        {name}
                      </Link>
                    ) : (
                      <span className="min-w-0 font-semibold">{name}</span>
                    )}
                    <span className="shrink-0 text-xs text-neutral-300">
                      {o.n} partie{o.n > 1 ? 's' : ''} · {nb(pct(o.score))}
                      {o.accuracy !== null ? ` · préc. ${Math.round(o.accuracy)}` : ''}
                      {o.exitEval !== null ? ` · ${signedPawns(o.exitEval)}` : ''}
                    </span>
                  </div>
                  <WdlBar wins={o.wins} draws={o.draws} losses={o.losses} className="h-1.5" />
                </li>
              )
            })}
          </ul>
        )}
        <p className="mt-3 text-xs text-neutral-400">Parties · score · précision · évaluation moyenne à la sortie de l'ouverture (en pions, de ton point de vue).</p>
      </Card>

      {/* Pendule */}
      <Card
        title="Gestion du temps"
        testid="insights-time"
        data-pressure-moves={t?.pressureMoves ?? 0}
        data-pressure-blunders={t?.pressureBlunders ?? 0}
        data-timeouts={g.lostOnTime}
        data-games-with-clocks={t?.gamesWithClocks ?? 0}
        aside={<SectionLink to="/rush">Puzzle Rush</SectionLink>}
      >
        {t ? (
          <>
            <div className="mb-3 grid grid-cols-3 gap-3">
              <Stat value={t.pressureRate !== null ? fr1(t.pressureRate) : '-'} label="gaffes / 100 coups sous pression" />
              <Stat value={t.normalRate !== null ? fr1(t.normalRate) : '-'} label="gaffes / 100 coups sinon" />
              <Stat value={String(g.lostOnTime)} label={`défaite${g.lostOnTime > 1 ? 's' : ''} au temps`} />
            </div>
            <p className="mb-3 text-xs text-neutral-400">
              Sous pression : moins de 10 % du temps de base à la pendule avant de jouer ({t.pressureMoves} coup{t.pressureMoves > 1 ? 's' : ''}, {t.pressureBlunders} gaffe{t.pressureBlunders > 1 ? 's' : ''}).
              {g.lostOnTimeWinning > 0 && ` Dont ${g.lostOnTimeWinning} défaite${g.lostOnTimeWinning > 1 ? 's' : ''} au temps en position gagnante.`}
            </p>
            <div className="text-xs text-neutral-400">Temps moyen par coup</div>
            <div className="mt-1 grid grid-cols-3 gap-3 text-sm">
              {PHASES.map((p) => (
                <div key={p}>
                  <div className="font-bold">{t.avgSecPerMove[p] !== null ? `${fr1(t.avgSecPerMove[p]!)} s` : '-'}</div>
                  <div className="text-xs text-neutral-400">{PHASE_FR[p]}</div>
                </div>
              ))}
            </div>
            {t.gamesWithClocks < g.n && (
              <p className="mt-3 text-xs text-neutral-500">
                {g.n - t.gamesWithClocks} partie{g.n - t.gamesWithClocks > 1 ? 's' : ''} sans pendule enregistrée (ChessLocal n'en garde pas) : hors de cette section.
              </p>
            )}
          </>
        ) : (
          <p className="text-sm text-neutral-400">
            Aucune pendule dans ces parties (ChessLocal n'enregistre pas les temps) : seules les parties chess.com en ont. {g.lostOnTime > 0 && `${g.lostOnTime} défaite${g.lostOnTime > 1 ? 's' : ''} au temps.`}
          </p>
        )}
      </Card>

      {/* Erreurs typiques */}
      <Card title="Erreurs typiques" testid="insights-errors" aside={<SectionLink to="/mats">Mats éclair</SectionLink>}>
        {errorsShown.length === 0 ? (
          <p className="text-sm text-neutral-400">Aucune faute typique repérée dans ces parties.</p>
        ) : (
          <ul className="space-y-4">
            {errorsShown.map((e) => (
              <li key={e.kind} data-kind={e.kind} data-count={e.count}>
                <div className="mb-1 flex items-baseline justify-between gap-2 text-sm">
                  <span className="font-semibold">{ERROR_META[e.kind].label}</span>
                  <span className="shrink-0 text-neutral-300">
                    {e.count} · {fr1(e.count / Math.max(1, g.n))} / partie
                  </span>
                </div>
                <MeterBar value={e.count} max={maxErr} tone="bad" />
                <p className="mt-1 text-xs text-neutral-400">{ERROR_META[e.kind].hint}</p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {e.examples.map((x) => (
                    <ExampleButton key={`${x.key}:${x.index}`} e={x} onOpen={onExample} />
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Attaque sur le roi */}
      <AttackCard r={r} onExample={onExample} />

      {/* Conversion, défense, opportunisme */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Gauge testid="insights-conversion" title="Conversion" ok={r.conversion.converted} of={r.conversion.winning} text="positions gagnantes (+3) gagnées" data={{ 'data-winning': r.conversion.winning, 'data-converted': r.conversion.converted }} />
        <Gauge testid="insights-defense" title="Défense" ok={r.defense.saved} of={r.defense.losing} text="positions perdantes (−3) sauvées" data={{ 'data-losing': r.defense.losing, 'data-saved': r.defense.saved }} />
        <Gauge testid="insights-opportunism" title="Opportunisme" ok={r.opportunism.punished} of={r.opportunism.chances} text="gaffes adverses punies" data={{}} />
      </div>
      {g.skipped > 0 && <p className="text-xs text-neutral-500">{g.skipped} partie{g.skipped > 1 ? 's' : ''} illisible{g.skipped > 1 ? 's' : ''} ignorée{g.skipped > 1 ? 's' : ''}.</p>}
    </div>
  )
}

// Coups offensifs vers le roi adverse que le meilleur coup jouait et que tu as laissés passer
// (heuristique documentée dans insights.ts).
function AttackCard({ r, onExample }: { r: Report; onExample: (e: Example) => void }) {
  const navigate = useNavigate()
  const e = r.errors.find((x) => x.kind === 'missedKingAttack')!
  return (
    <Card title="Attaque sur le roi" testid="insights-attack" data-count={e.count} aside={<SectionLink to="/mats">Mats éclair</SectionLink>}>
      <p className="text-sm text-neutral-300">
        {e.count
          ? `${e.count} coup${e.count > 1 ? 's' : ''} offensif${e.count > 1 ? 's' : ''} vers le roi adverse manqué${e.count > 1 ? 's' : ''} (${fr1(e.count / Math.max(1, r.games.n))} par partie) : le meilleur coup amenait une pièce de plus contre son roi.`
          : "Aucune attaque sur le roi manquée : quand le meilleur coup visait le roi adverse, tu l'as vu ou une autre faute a primé."}
      </p>
      {e.examples.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {e.examples.map((x) => (
            <ExampleButton key={`${x.key}:${x.index}`} e={x} onOpen={onExample} />
          ))}
        </div>
      )}
      <button
        data-testid="plan-link"
        data-tactic="kingsideAttack"
        onClick={() => navigate('/apprendre', { state: { tactic: 'kingsideAttack', ...BACK } })}
        className="mt-3 inline-flex min-h-9 cursor-pointer items-center rounded-lg bg-surface-3 px-3 py-1.5 text-sm font-semibold text-white hover:brightness-110"
      >
        ▶ Séance Tactiques : attaque à l'aile roi
      </button>
    </Card>
  )
}

function Gauge({ testid, title, ok, of, text, data }: { testid: string; title: string; ok: number; of: number; text: string; data: Record<`data-${string}`, number> }) {
  return (
    <section data-testid={testid} {...data} className="rounded-lg bg-surface-2 p-4">
      <h2 className="mb-1 font-bold">{title}</h2>
      <div className="text-2xl font-black">{of ? nb(pct((ok / of) * 100)) : '-'}</div>
      <MeterBar value={of ? (ok / of) * 100 : 0} tone={of ? 'accent' : 'muted'} />
      <p className="mt-1.5 text-xs text-neutral-400">
        {ok} sur {of} {text}
      </p>
    </section>
  )
}
