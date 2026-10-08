// Révision espacée (/revision) : séance mixte et enchaînée de ce qui est dû aujourd'hui, avec
// les lecteurs existants (PuzzlePlayer, MistakeExercise, OpeningDrill). La séance démarre à
// l'arrivée ; la logique d'échéance vit dans src/lib/revision.ts.
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Chess, DEFAULT_POSITION } from 'chess.js'
import { Cta } from '../components/Cta'
import { MistakeExercise } from '../components/MistakeExercise'
import { OpeningDrill } from '../components/OpeningDrill'
import { PuzzlePlayer } from '../components/PuzzlePlayer'
import { Engine } from '../lib/engine'
import { displayThemes } from '../lib/puzzleThemes'
import {
  buildReviewSession, describeKinds, dueLabel, LADDER_DAYS, loadReviewQueue, recordReview, resolveSession, resolveVariant,
  returnLabel, statusLabel, variantKey, type ReviewPayload, type ReviewQueue,
} from '../lib/revision'
import { sounds } from '../lib/sounds'
import { useSettings } from '../store/settings'

type Phase = 'play' | 'success' | 'fail'

const SESSION_KEY = 'revision-session-v1'

interface Result {
  idx: number
  ok: boolean
  label: string
  next: string // « Revient demain »...
}

// Séance persistée pour survivre à l'aller-retour vers l'analyseur (comme Apprendre).
interface StoredSession {
  items: ReviewPayload[]
  idx: number
  phase: Phase
  results: Result[]
  remaining: number
  returnTo: string
}

export default function Revision() {
  const navigate = useNavigate()
  const location = useLocation()
  const { playSounds } = useSettings()
  const [queue, setQueue] = useState<ReviewQueue | null>(null)
  const [items, setItems] = useState<ReviewPayload[] | null>(null)
  const [idx, setIdx] = useState(0)
  const [phase, setPhase] = useState<Phase>('play')
  const [results, setResults] = useState<Result[]>([])
  const [ended, setEnded] = useState(false)
  const [retryTick, setRetryTick] = useState(0)
  const [puzzlesUnavailable, setPuzzlesUnavailable] = useState(false)
  const [missing, setMissing] = useState(0) // items dus introuvables (puzzle retiré de la base...)
  const [remaining, setRemaining] = useState(0) // items dus au-delà du plafond de la séance
  const [saveError, setSaveError] = useState(false)
  const [returnTo, setReturnTo] = useState('/')
  const engineRef = useRef<Engine | null>(null)
  // Items déjà jugés (index), posés de façon synchrone : un second verdict dans le même rendu
  // (Réessayer sur le drill refait feu `onResult`) n'écrit jamais deux fois.
  const recorded = useRef(new Set<number>())
  // Écritures en cours : « Continuer » relit la base, il doit attendre la dernière.
  const writes = useRef<Promise<unknown>>(Promise.resolve())

  useEffect(
    () => () => {
      engineRef.current?.quit()
      engineRef.current = null
    },
    [],
  )

  // Arrivée : séance restaurée (retour de l'analyseur) ou nouvelle séance sur les items dus.
  useEffect(() => {
    const state = location.state as { restore?: boolean; returnTo?: string } | null
    if (state?.restore) {
      const raw = sessionStorage.getItem(SESSION_KEY)
      if (raw) {
        try {
          const saved = JSON.parse(raw) as StoredSession
          setItems(saved.items)
          setResults(saved.results)
          recorded.current = new Set(saved.results.map((r) => r.idx))
          setRemaining(saved.remaining ?? 0)
          setReturnTo(saved.returnTo)
          // Une variante déjà jugée ne se restaure pas (le drill repartirait du premier coup) :
          // la séance reprend à l'item suivant, ou à son écran de fin.
          const judgedVariant = saved.items[saved.idx]?.kind === 'variant' && saved.results.some((r) => r.idx === saved.idx)
          if (judgedVariant && saved.idx + 1 >= saved.items.length) setEnded(true)
          setIdx(judgedVariant ? Math.min(saved.idx + 1, saved.items.length - 1) : saved.idx)
          setPhase(judgedVariant ? 'play' : saved.phase)
          navigate('.', { replace: true, state: null })
          return
        } catch {}
      }
    }
    if (state?.returnTo) setReturnTo(state.returnTo)
    if (state) navigate('.', { replace: true, state: null })
    void start()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Tant que rien n'est chargé, la clé n'est pas touchée : en StrictMode, les effets du montage
  // rejouent, et un retrait ici entre deux lectures ferait perdre la séance à restaurer.
  useEffect(() => {
    if (items === null) return
    if (items.length > 0 && !ended) {
      const stored: StoredSession = { items, idx, phase, results, remaining, returnTo }
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(stored))
    } else {
      sessionStorage.removeItem(SESSION_KEY)
    }
  }, [items, idx, phase, results, remaining, returnTo, ended])

  async function start() {
    setItems(null)
    setEnded(false)
    setIdx(0)
    setPhase('play')
    setResults([])
    recorded.current.clear()
    await writes.current
    const q = await loadReviewQueue()
    setQueue(q)
    if (q.due.length === 0) {
      setItems([])
      return
    }
    // Toute la file est résolue d'abord : un item introuvable ne prend pas la place d'un valide.
    const { payloads, missing, puzzlesUnavailable } = await resolveSession(q.due)
    const byKey = new Map(payloads.map((p) => [`${p.item.kind}:${p.item.key}`, p]))
    const picked = buildReviewSession(payloads.map((p) => p.item))
    setRemaining(payloads.length - picked.length)
    setMissing(missing)
    setPuzzlesUnavailable(puzzlesUnavailable)
    setItems(picked.map((i) => byKey.get(`${i.kind}:${i.key}`)!))
  }

  function getEngine(): Engine {
    engineRef.current ??= new Engine()
    return engineRef.current
  }

  // Verdict : seule la première tentative d'un item s'enregistre (Réessayer est sans enjeu).
  function finish(success: boolean) {
    if (!items) return
    const item = items[idx]
    if (playSounds) (success ? sounds.success : sounds.fail)()
    setPhase(success ? 'success' : 'fail')
    if (recorded.current.has(idx)) return
    recorded.current.add(idx)
    const result: Result = { idx, ok: success, label: itemLabel(item), next: returnLabel(success ? item.item.box + 1 : 0) }
    setResults((r) => [...r, result])
    // Chaîne jamais empoisonnée : un échec d'écriture (stockage indisponible) est signalé, et
    // n'empêche ni les écritures suivantes ni « Continuer ».
    writes.current = writes.current.then(() => recordReview(item, success)).then(
      () => setSaveError(false),
      () => setSaveError(true),
    )
  }

  function next() {
    if (!items) return
    if (idx + 1 < items.length) {
      setIdx(idx + 1)
      setPhase('play')
    } else {
      setEnded(true)
    }
  }

  function retry() {
    setRetryTick((t) => t + 1)
    setPhase('play')
  }

  function close() {
    navigate(returnTo, { replace: true })
  }

  function analyse(moves?: string[]) {
    if (!items) return
    const item = items[idx]
    const back = { returnTo: '/revision', returnLabel: 'Retour à la révision' }
    if (item.kind === 'puzzle') {
      const p = item.puzzle
      navigate('/analyse', {
        state: { fen: p.fen, uci: p.moves, viewIndex: 0, orientation: p.fen.split(' ')[1] === 'w' ? 'b' : 'w', label: `Puzzle ${p.id} (${p.rating})`, ...back },
      })
    } else if (item.kind === 'mistake') {
      navigate('/analyse', { state: { fen: item.mistake.fenBefore, orientation: new Chess(item.mistake.fenBefore).turn(), label: item.mistake.gameLabel, ...back } })
    } else {
      navigate('/analyse', { state: { fen: DEFAULT_POSITION, uci: moves ?? item.uci.split(' '), orientation: item.color, label: item.label, ...back } })
    }
  }

  // ---------- Chargement ----------
  if (items === null) {
    return <div className="p-8 text-center text-neutral-400">Préparation de la révision…</div>
  }

  // ---------- Rien de dû (ou séance vidée par des items introuvables) ----------
  if (items.length === 0) {
    const upcoming = queue?.upcoming ?? []
    const soonest = upcoming[0]
    const soon = soonest ? upcoming.filter((i) => i.due === soonest.due) : []
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-4 p-6 pt-12 text-center">
        <div className="text-6xl">{puzzlesUnavailable ? '📡' : '✅'}</div>
        <h1 className="text-2xl font-black">{puzzlesUnavailable ? 'Puzzles indisponibles' : "Rien à réviser aujourd'hui"}</h1>
        {puzzlesUnavailable ? (
          <p className="text-neutral-400">Impossible de charger les puzzles. Vérifie ta connexion, puis réessaie.</p>
        ) : missing > 0 ? (
          <p data-review-missing className="text-neutral-400">
            {missing > 1 ? `${missing} éléments à réviser sont introuvables` : '1 élément à réviser est introuvable'} (puzzle retiré de la base ou variante
            disparue) : {missing > 1 ? 'ils sont ignorés' : 'il est ignoré'}.
          </p>
        ) : soonest ? (
          <p data-review-next-due className="text-neutral-400">
            Prochaine révision {dueLabel(soonest.due)} : {soon.length} {soon.length > 1 ? 'éléments' : 'élément'} ({describeKinds(soon)}).
          </p>
        ) : (
          <p className="text-neutral-400">Les puzzles, erreurs de parties et variantes d'ouverture que tu rates reviendront ici.</p>
        )}
        <p className="text-sm text-neutral-500">
          Calendrier : {LADDER_DAYS.map((d) => `J+${d}`).join(', ')}. Une réussite espace le prochain passage, un échec ramène à J+1.
        </p>
        {puzzlesUnavailable && <Cta className="w-full" onClick={() => void start()}>Réessayer</Cta>}
        <Link to={returnTo} replace className="mt-2 text-sm font-semibold text-accent underline underline-offset-2">
          {returnTo === '/apprendre' ? 'Retour à Apprendre' : "Retour à l'accueil"}
        </Link>
      </div>
    )
  }

  // ---------- Fin de séance ----------
  if (ended) {
    const ok = results.filter((r) => r.ok).length
    return (
      <div data-review-end className="pt-safe pb-safe fixed inset-0 z-40 overflow-y-auto bg-surface">
        <div className="mx-auto flex min-h-full max-w-lg flex-col items-center justify-center gap-4 p-6 text-center">
          <div className="text-6xl">{ok === results.length ? '🏆' : ok > 0 ? '💪' : '📚'}</div>
          <h1 className="text-2xl font-black">
            {ok}/{results.length} réussi{ok > 1 ? 's' : ''}
          </h1>
          {saveError && <SaveAlert />}
          <ul className="w-full text-left text-sm">
            {results.map((r) => (
              <li key={r.idx} className="flex items-center gap-2 border-b border-white/10 py-2">
                <span className={`shrink-0 font-black ${r.ok ? 'text-accent' : 'text-red-400'}`}>{r.ok ? '✓' : '✗'}</span>
                <span className="min-w-0 flex-1 truncate">{r.label}</span>
                <span className="shrink-0 text-xs text-neutral-400">{r.next}</span>
              </li>
            ))}
          </ul>
          {remaining > 0 && (
            <Cta className="w-full" onClick={() => void start()}>
              Continuer ({remaining} restant{remaining > 1 ? 's' : ''})
            </Cta>
          )}
          <Cta variant={remaining > 0 ? 'secondary' : 'primary'} className="w-full" onClick={close}>
            Terminer
          </Cta>
        </div>
      </div>
    )
  }

  // ---------- Item courant ----------
  const item = items[idx]
  const result = results.find((r) => r.idx === idx) ?? null
  const progress = `${idx + 1}/${items.length}`
  const key = `${idx}-${retryTick}`

  if (item.kind === 'variant') {
    // La famille (non sérialisable) se résout au rendu, depuis les familles en cache ; le repli ne
    // sert qu'à une séance restaurée après une mise à jour d'openings.json.
    const resolved = resolveVariant(variantKey(item.color, item.uci))
    if (!resolved) {
      return (
        <div className="mx-auto flex max-w-lg flex-col items-center gap-4 p-6 pt-12 text-center">
          <p className="text-neutral-400">Cette variante n'existe plus dans la base d'ouvertures.</p>
          <Cta onClick={next}>Suivant</Cta>
        </div>
      )
    }
    return (
      <OpeningDrill
        key={key}
        fam={resolved.fam}
        color={resolved.color}
        item={{ mode: 'full', variant: resolved.variant, start: 0, position: null }}
        plyTarget={null}
        getEngine={getEngine}
        session={{ ok: 0, total: 0 }}
        title={`🔁 Révision ${progress}`}
        subtitle={statusLabel(item.item)}
        onResult={finish}
        onRetry={retry}
        onNext={next}
        onClose={close}
        onAnalyse={(moves) => analyse(moves)}
        nextLabel="Suivant"
        resultNote={result?.next ?? null}
      />
    )
  }

  // Les thèmes (« Mat en 1 », « Fourchette ») livreraient la solution : après le verdict seulement.
  const banner = item.kind === 'puzzle'
    ? `Puzzle ${item.puzzle.id} · ${item.puzzle.rating}${phase !== 'play' ? ` · ${displayThemes(item.puzzle.themes).join(', ')}` : ''}`
    : null

  return (
    <div className="pt-safe pb-safe fixed inset-0 z-40 overflow-y-auto bg-surface">
      <div data-review-item={item.kind} className="mx-auto flex min-h-full max-w-2xl flex-col">
        <header className="flex items-center px-3 py-1">
          <button onClick={close} aria-label="Quitter la révision" className="cursor-pointer p-1.5 text-2xl text-neutral-400 hover:text-white">
            ✕
          </button>
          <h1 className="flex-1 text-center text-lg font-black">
            🔁 Révision
            <span className="ml-2 text-sm font-semibold text-neutral-500">{progress}</span>
          </h1>
          <span className="w-9" />
        </header>
        <p className="px-3 pb-2 text-center text-xs font-semibold text-neutral-400">{statusLabel(item.item)}</p>
        {saveError && <div className="mx-3 mb-2"><SaveAlert /></div>}
        {banner && <p className="mx-3 mb-2 truncate rounded bg-surface-2 px-3 py-1.5 text-center text-sm font-semibold">{banner}</p>}
        {item.kind === 'puzzle' ? (
          <div className="flex justify-center px-3">
            <div className="boardbox md:w-[min(56vh,520px)]">
              <PuzzlePlayer
                key={key}
                puzzle={item.puzzle}
                onComplete={(ok) => {
                  if (phase === 'play') finish(ok)
                }}
              />
            </div>
          </div>
        ) : (
          <MistakeExercise key={key} mistake={item.mistake} active={phase === 'play'} onFinish={finish} getEngine={getEngine} />
        )}
        {phase !== 'play' && (
          // Une seule rangée à 393 px : verdict et échéance empilés dans un bloc qui ne rétrécit
          // pas, actions serrées à droite (même gabarit qu'Apprendre).
          <div className="flex items-center gap-2 px-3 py-2">
            <div className="flex min-w-0 shrink-0 flex-col whitespace-nowrap">
              <span className={`text-lg leading-tight font-black ${phase === 'success' ? 'text-accent' : 'text-red-400'}`}>
                {phase === 'success' ? '✓ Réussi !' : '✗ Raté'}
              </span>
              {result && (
                <span data-review-next className="text-xs leading-tight font-semibold text-neutral-400">
                  {result.next}
                </span>
              )}
            </div>
            <div className="ml-auto flex items-center gap-1">
              <button onClick={retry} className="flex cursor-pointer flex-col items-center rounded px-1.5 py-1 text-xs font-semibold text-neutral-300 hover:text-white">
                <span className="text-lg leading-none">↺</span>
                Réessayer
              </button>
              <button onClick={() => analyse()} className="flex cursor-pointer flex-col items-center rounded px-1.5 py-1 text-xs font-semibold text-neutral-300 hover:text-white">
                <span className="text-lg leading-none">♞</span>
                Analyser
              </button>
              <Cta className="ml-1 px-5 py-2 text-base" onClick={next}>
                Suivant
              </Cta>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function SaveAlert() {
  return (
    <p role="alert" className="w-full rounded bg-red-900/40 px-3 py-2 text-sm text-red-200">
      La dernière tentative n'a pas pu être enregistrée (stockage indisponible).
    </p>
  )
}

// Libellé court d'un item pour le récapitulatif.
function itemLabel(item: ReviewPayload): string {
  if (item.kind === 'puzzle') return `Puzzle ${item.puzzle.id} (${item.puzzle.rating})`
  if (item.kind === 'mistake') return `${item.mistake.gameLabel} : ${item.mistake.playedSan}`
  return item.label
}
