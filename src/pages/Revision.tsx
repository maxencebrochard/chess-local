// Révision espacée (/revision) : séance mixte et enchaînée de ce qui est dû aujourd'hui, avec
// les lecteurs existants (PuzzlePlayer, MistakeExercise, OpeningDrill). La séance démarre à
// l'arrivée ; la logique d'échéance vit dans src/lib/revision.ts.
import { REVIEW_ROOT } from '../lib/navigation'
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Chess, DEFAULT_POSITION } from 'chess.js'
import { Cta } from '../components/Cta'
import { ExerciseFeedback, ExerciseHeader, ExerciseScreen, ExerciseStage, type ExerciseVerdict } from '../components/Exercise'
import { MistakeConsigne, MistakeExercise } from '../components/MistakeExercise'
import { mistakeVerdictReason, refutedUci } from '../lib/refutation'
import { RefutationPlayer } from '../components/RefutationPlayer'
import { puzzlePlayerColor } from '../components/useExerciseContinuation'
import { OpeningDrill, type DrillSnapshot } from '../components/OpeningDrill'
import { PuzzlePlayer } from '../components/PuzzlePlayer'
import { Engine } from '../lib/engine'
import { displayThemes } from '../lib/puzzleThemes'
import {
  buildReviewSession, describeKinds, dueLabel, LADDER_DAYS, loadReviewQueue, recordReview, resolveSession, resolveVariant,
  returnLabel, StaleReviewError, statusLabel, variantKey, type ReviewPayload, type ReviewQueue,
} from '../lib/revision'
import { sounds } from '../lib/sounds'

type Phase = 'play' | 'success' | 'fail'

type SaveError = 'storage' | 'stale'

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
  drill?: DrillSnapshot // variante jugée laissée pour l'analyseur : son verdict, repris au retour
  reason?: string // explication du verdict affiché (restaurée au retour de l'analyse)
}

// Libellé du lien de sortie, d'après la page qui a ouvert la révision (`state.returnTo`).
function exitLabel(to: string): string {
  if (to === REVIEW_ROOT) return 'Retour à Réviser mes parties'
  if (to === '/apprendre') return 'Retour à Apprendre'
  return "Retour à l'accueil"
}

export default function Revision() {
  const navigate = useNavigate()
  const location = useLocation()
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
  const [saveError, setSaveError] = useState<SaveError | null>(null)
  const [returnTo, setReturnTo] = useState('/')
  // Verdict d'une variante restauré au retour de l'analyseur, pour la clé de drill d'alors.
  const [drillSnap, setDrillSnap] = useState<{ key: string; snapshot: DrillSnapshot } | null>(null)
  // Explication du verdict affiché, et vérification Stockfish en cours (présentation seule).
  const [reason, setReason] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)
  const [why, setWhy] = useState(false)
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
          setReason(saved.reason ?? null)
          // Une variante jugée reprend sur son verdict (drill laissé par « Analyser »). Sans ce
          // verdict (séance d'une version antérieure), le drill repartirait du premier coup : la
          // séance reprend alors à l'item suivant, ou à son écran de fin.
          const judgedVariant = saved.items[saved.idx]?.kind === 'variant' && saved.results.some((r) => r.idx === saved.idx)
          const skip = judgedVariant && !saved.drill
          if (judgedVariant && saved.drill) setDrillSnap({ key: `${saved.idx}-0`, snapshot: saved.drill })
          if (skip && saved.idx + 1 >= saved.items.length) setEnded(true)
          setIdx(skip ? Math.min(saved.idx + 1, saved.items.length - 1) : saved.idx)
          setPhase(skip ? 'play' : saved.phase)
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
      const stored: StoredSession = { items, idx, phase, results, remaining, returnTo, reason: reason ?? undefined }
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(stored))
    } else {
      sessionStorage.removeItem(SESSION_KEY)
    }
  }, [items, idx, phase, results, remaining, returnTo, ended, reason])

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
  function finish(success: boolean, why?: string) {
    if (!items) return
    const item = items[idx]
    setReason(why ?? null)
    // Puzzles et variantes passent par PuzzlePlayer et OpeningDrill, qui ont déjà joué le verdict.
    if (item.kind !== 'puzzle' && item.kind !== 'variant') (success ? sounds.success : sounds.fail)()
    setPhase(success ? 'success' : 'fail')
    if (recorded.current.has(idx)) return
    recorded.current.add(idx)
    const result: Result = { idx, ok: success, label: itemLabel(item), next: returnLabel(success ? item.item.box + 1 : 0) }
    setResults((r) => [...r, result])
    // Chaîne jamais empoisonnée : un échec d'écriture (stockage indisponible) est signalé, et
    // n'empêche ni les écritures suivantes ni « Continuer ».
    writes.current = writes.current.then(() => recordReview(item, success)).then(
      () => setSaveError(null),
      (e) => {
        if (!(e instanceof StaleReviewError)) return setSaveError('storage')
        setSaveError('stale')
        setResults((r) => r.map((x) => (x.idx === idx ? { ...x, next: 'Non enregistré' } : x)))
      },
    )
  }

  function next() {
    if (!items) return
    setReason(null)
    if (idx + 1 < items.length) {
      setIdx(idx + 1)
      setPhase('play')
    } else {
      setEnded(true)
    }
  }

  function retry() {
    setReason(null)
    setRetryTick((t) => t + 1)
    setPhase('play')
  }

  function close() {
    navigate(returnTo, { replace: true })
  }

  function analyse(moves?: string[], drill?: DrillSnapshot) {
    if (!items) return
    const item = items[idx]
    // Le verdict de la variante part avec la séance : le retour le réaffiche tel quel.
    if (drill) {
      const stored: StoredSession = { items, idx, phase, results, remaining, returnTo, reason: reason ?? undefined, drill }
      sessionStorage.setItem(SESSION_KEY, JSON.stringify(stored))
    }
    const back = { returnTo: '/revision', returnLabel: 'Retour à la révision' }
    if (item.kind === 'puzzle') {
      const p = item.puzzle
      navigate('/analyse', {
        state: { fen: p.fen, uci: p.moves, viewIndex: 0, orientation: p.fen.split(' ')[1] === 'w' ? 'b' : 'w', label: `Puzzle ${p.id} (${p.rating})`, ...back },
      })
    } else if (item.kind !== 'variant') {
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
            {missing > 1 ? `${missing} éléments à réviser sont introuvables` : '1 élément à réviser est introuvable'} (position supprimée, puzzle retiré de la base ou variante
            disparue) : {missing > 1 ? 'ils sont ignorés' : 'il est ignoré'}.
          </p>
        ) : soonest ? (
          <p data-review-next-due className="text-neutral-400">
            Prochaine révision {dueLabel(soonest.due)} : {soon.length} {soon.length > 1 ? 'éléments' : 'élément'} ({describeKinds(soon)}).
          </p>
        ) : (
          <p className="text-neutral-400">Les puzzles, erreurs de parties, variantes d'ouverture, attaques manquées et défenses ratées reviendront ici.</p>
        )}
        <p className="text-sm text-neutral-400">
          Calendrier : {LADDER_DAYS.map((d) => `J+${d}`).join(', ')}. Une réussite espace le prochain passage, un échec ramène à J+1.
        </p>
        {puzzlesUnavailable && <Cta className="w-full" onClick={() => void start()}>Réessayer</Cta>}
        <Link to={returnTo} replace className="mt-1 inline-flex min-h-11 items-center text-sm font-semibold text-accent underline underline-offset-2">
          {exitLabel(returnTo)}
        </Link>
      </div>
    )
  }

  // ---------- Fin de séance ----------
  if (ended) {
    const ok = results.filter((r) => r.ok).length
    return (
      <div data-review-end className="pt-safe pb-safe fixed inset-0 z-40 overflow-y-auto overscroll-contain bg-surface">
        <div className="mx-auto flex min-h-full max-w-lg flex-col items-center justify-center gap-4 p-6 text-center">
          <div className="text-6xl">{ok === results.length ? '🏆' : ok > 0 ? '💪' : '📚'}</div>
          <h1 className="text-2xl font-black">
            {ok}/{results.length} réussi{ok > 1 ? 's' : ''}
          </h1>
          {saveError && <SaveAlert kind={saveError} />}
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
        snapshot={drillSnap?.key === key ? drillSnap.snapshot : null}
        title={`🔁 Révision ${progress}`}
        subtitle={statusLabel(item.item)}
        onResult={finish}
        onRetry={retry}
        onNext={next}
        onClose={close}
        onAnalyse={(moves, snapshot) => analyse(moves, snapshot)}
        nextLabel="Suivant"
        resultNote={result?.next ?? null}
      />
    )
  }

  // Consigne avant le coup ; les thèmes (« Mat en 1 », « Fourchette ») livreraient la solution :
  // ils ne passent dans l'explication qu'après le verdict.
  const status = <span className="mt-1 block text-xs font-semibold text-neutral-400">{statusLabel(item.item)}</span>
  const prompt = item.kind === 'puzzle' ? (
    <>
      <span className="font-semibold">Puzzle {item.puzzle.id} · {item.puzzle.rating}</span> : trouve le meilleur coup, trait aux {puzzlePlayerColor(item.puzzle) === 'w' ? 'Blancs' : 'Noirs'}.
      {status}
    </>
  ) : checking ? 'Je vérifie ton coup avec Stockfish…' : (
    <>
      {item.kind === 'missed-attack' ? 'Attaque manquée · ' : item.kind === 'missed-defense' ? 'Défense ratée · ' : ''}
      {<MistakeConsigne mistake={item.mistake} active />}
      {status}
    </>
  )
  const refuted = item.kind === 'puzzle' ? null : refutedUci(item.mistake)
  const verdict: ExerciseVerdict | null = phase === 'play' ? null : {
    ok: phase === 'success',
    // Séance restaurée d'un stockage antérieur à l'explication : phrase générique.
    reason: reason ?? (phase === 'success' ? 'Exercice réussi.' : 'Rejoue la position pour la fixer.'),
    note: result ? <span data-review-next>{result.next}</span> : undefined,
  }

  return (
    <ExerciseScreen data-review-item={item.kind}>
      <ExerciseHeader title="🔁 Révision" index={idx + 1} total={items.length} done={results.length} onClose={close} closeLabel="Quitter la révision" />
      <ExerciseStage
        feedback={
          <ExerciseFeedback
            verdict={verdict}
            prompt={prompt}
            onNext={next}
            onRetry={retry}
            onAnalyse={() => analyse()}
            onWhy={refuted ? () => setWhy(true) : undefined}
          />
        }
        below={saveError && <div className="px-3"><SaveAlert kind={saveError} /></div>}
      >
        {item.kind === 'puzzle' ? (
          <PuzzlePlayer
            key={key}
            puzzle={item.puzzle}
            onComplete={(ok) => {
              if (phase !== 'play') return
              const motif = `Motif : ${displayThemes(item.puzzle.themes).join(', ')}.`
              finish(ok, ok ? `Bien vu. ${motif}` : `Pas le coup attendu. ${motif}`)
            }}
          />
        ) : (
          <MistakeExercise
            key={key}
            bare
            mistake={item.mistake}
            active={phase === 'play'}
            getEngine={getEngine}
            onChecking={setChecking}
            onFinish={(ok, { best }) => finish(ok, mistakeVerdictReason(ok, best, refuted !== null))}
          />
        )}
      </ExerciseStage>
      {why && refuted && item.kind !== 'puzzle' && (
        <RefutationPlayer
          fenBefore={item.mistake.fenBefore}
          playedUci={refuted}
          bestUci={item.mistake.bestUci}
          orientation={new Chess(item.mistake.fenBefore).turn()}
          onClose={() => setWhy(false)}
        />
      )}
    </ExerciseScreen>
  )
}

function SaveAlert({ kind }: { kind: SaveError }) {
  return (
    <p role="alert" className="w-full rounded bg-red-900/40 px-3 py-2 text-sm text-red-200">
      {kind === 'stale'
        ? "Cette position a été modifiée ou supprimée pendant la séance : la dernière tentative n'a pas été enregistrée."
        : "La dernière tentative n'a pas pu être enregistrée (stockage indisponible)."}
    </p>
  )
}

// Libellé court d'un item pour le récapitulatif.
function itemLabel(item: ReviewPayload): string {
  if (item.kind === 'puzzle') return `Puzzle ${item.puzzle.id} (${item.puzzle.rating})`
  if (item.kind !== 'variant') {
    const prefix = item.kind === 'missed-attack' ? 'Attaque manquée · ' : item.kind === 'missed-defense' ? 'Défense ratée · ' : ''
    return `${prefix}${item.mistake.gameLabel} : ${item.mistake.playedSan}`
  }
  return item.label
}
