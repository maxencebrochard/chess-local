// « Calcul et visualisation » (/visualisation) : entraîneur de calcul pour le blitz.
// Usage : README.md, rubrique « Calcul et visualisation ».
// Logique pure et persistance dans src/lib/visualisation.ts.
import { useEffect, useMemo, useRef, useState } from 'react'
import { Board, type BoardArrow } from '../components/Board'
import { FigText } from '../components/CoachBubble'
import { Cta } from '../components/Cta'
import { RunHeader, RunSummary, Sparkline } from '../components/mates/RunParts'
import { RunRecorder } from '../lib/mates'
import {
  checkMate, checkSquares, correction, DISPLAY_LABEL, finalPosition, KIND_LABEL, KINDS, LEVELS, lineMoves, loadBank,
  loadVisStats, MAX_ERRORS, pickQuestion, readVisPrefs, recordQuestion, seriesKey, SIDE_NAME, VIS_DOMAIN, writeVisPrefs,
  type DisplayMode, type Level, type Question, type VisBank, type VisPrefs, type VisStats,
} from '../lib/visualisation'

const FLASH_MS = 1600 // durée d'affichage de chaque demi-coup en mode « Un par un »
const GREEN = 'rgba(80, 200, 80, 0.6)'
const RED = 'rgba(220, 50, 50, 0.65)'
const PICK = 'rgba(255, 255, 51, 0.55)'

export default function Visualisation() {
  const [bank, setBank] = useState<VisBank | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [stats, setStats] = useState<VisStats | null>(null)
  const [prefs, setPrefs] = useState<VisPrefs>(readVisPrefs)
  const [run, setRun] = useState<VisPrefs | null>(null)

  function load() {
    setLoadError(false)
    loadBank().then(setBank).catch(() => setLoadError(true))
  }

  function refresh() {
    void loadVisStats().then(setStats)
  }

  useEffect(() => {
    load()
    refresh()
  }, [])

  function update(p: VisPrefs) {
    setPrefs(p)
    writeVisPrefs(p)
  }

  if (run && bank) {
    return <Run bank={bank} level={run.level} mode={run.mode} stats={stats} onDone={refresh} onMenu={() => setRun(null)} />
  }
  return <Hub prefs={prefs} stats={stats} ready={!!bank} loadError={loadError} onRetry={load} onChange={update} onStart={() => setRun(prefs)} />
}

// ---------- Accueil ----------
function Hub({ prefs, stats, ready, loadError, onRetry, onChange, onStart }: {
  prefs: VisPrefs
  stats: VisStats | null
  ready: boolean
  loadError: boolean
  onRetry: () => void
  onChange: (p: VisPrefs) => void
  onStart: () => void
}) {
  const key = seriesKey(prefs.level, prefs.mode)
  const recentOk = stats ? KINDS.reduce((n, k) => n + (stats.rate[k]?.ok ?? 0), 0) : 0
  return (
    <div data-vis-hub className="mx-auto max-w-xl p-4 md:p-6">
      <h1 className="text-2xl font-black">🧠 Calcul et visualisation</h1>
      <p className="mb-4 text-sm text-neutral-400">
        Lis la ligne sans bouger les pièces, imagine la position d'arrivée, puis réponds sur l'échiquier de départ.
      </p>

      <div className="mb-5 grid grid-cols-2 gap-2">
        <div className="rounded-xl bg-surface-2 p-3 text-center">
          <div data-answered className="text-2xl font-black text-accent">{stats?.answered ?? '…'}</div>
          <div className="text-xs text-neutral-400">questions répondues</div>
        </div>
        <div className="rounded-xl bg-surface-2 p-3 text-center">
          <div className="text-2xl font-black">{stats && stats.recent > 0 ? `${Math.round((recentOk / stats.recent) * 100)} %` : '-'}</div>
          <div className="text-xs text-neutral-400">{stats && stats.recent > 0 ? `de réussite sur les ${stats.recent} dernières` : 'de réussite'}</div>
        </div>
      </div>

      <p className="mb-1.5 text-sm font-semibold text-neutral-400">Longueur de la ligne</p>
      <div role="radiogroup" aria-label="Longueur de la ligne" className="mb-4 grid grid-cols-4 gap-2">
        {LEVELS.map((n) => {
          const best = stats?.best[seriesKey(n, prefs.mode)] ?? 0
          return (
            <button
              key={n}
              role="radio"
              aria-checked={n === prefs.level}
              data-level={n}
              onClick={() => onChange({ ...prefs, level: n })}
              className={`cursor-pointer rounded-lg py-2 text-center ${n === prefs.level ? 'bg-accent text-white' : 'bg-surface-2 text-neutral-300 hover:bg-surface-3'}`}
            >
              <span className="block text-xl leading-tight font-black">{n}</span>
              <span className={`block text-[11px] ${n === prefs.level ? 'text-white/85' : 'text-neutral-400'}`}>demi-coups</span>
              <span className={`block text-[11px] font-semibold ${n === prefs.level ? 'text-white' : 'text-neutral-400'}`}>Record {best}</span>
            </button>
          )
        })}
      </div>

      <p className="mb-1.5 text-sm font-semibold text-neutral-400">Affichage de la ligne</p>
      <div role="radiogroup" aria-label="Affichage de la ligne" className="mb-1.5 flex gap-2">
        {(['visible', 'flash'] as DisplayMode[]).map((m) => (
          <button
            key={m}
            role="radio"
            aria-checked={m === prefs.mode}
            data-mode={m}
            onClick={() => onChange({ ...prefs, mode: m })}
            className={`flex-1 cursor-pointer rounded-lg py-2 text-sm font-bold ${m === prefs.mode ? 'bg-accent text-white' : 'bg-surface-2 text-neutral-300 hover:bg-surface-3'}`}
          >
            {DISPLAY_LABEL[m]}
          </button>
        ))}
      </div>
      <p className="mb-4 text-xs text-neutral-500">
        {prefs.mode === 'visible'
          ? 'La ligne reste affichée pendant la question.'
          : 'Chaque coup s\'affiche seul un instant, puis la ligne disparaît : tout se joue de tête.'}
      </p>

      <div className="mb-4 rounded-xl bg-surface-2 p-3">
        <div className="mb-2 flex items-baseline justify-between">
          <span className="text-sm font-semibold text-neutral-400">
            Record ({prefs.level} demi-coups, {DISPLAY_LABEL[prefs.mode].toLowerCase()})
          </span>
          <span data-record className="text-2xl font-black text-accent">{stats?.best[key] ?? 0}</span>
        </div>
        <Sparkline values={stats?.last[key] ?? []} />
      </div>

      {stats && stats.recent > 0 && (
        <div data-rates className="mb-4 grid grid-cols-2 gap-2">
          {KINDS.map((k) => {
            const r = stats.rate[k]
            return (
              <div key={k} data-rate={k} className="flex items-baseline justify-between rounded-lg bg-surface-2 px-3 py-2 text-sm">
                <span className="text-neutral-300">{KIND_LABEL[k]}</span>
                <span className="font-bold">{r ? `${r.ok}/${r.total}` : '-'}</span>
              </div>
            )
          })}
        </div>
      )}

      {loadError && (
        <div className="mb-3 rounded-lg bg-surface-2 p-3 text-center">
          <p className="mb-2 text-sm text-neutral-400">Impossible de charger les positions. Vérifie ta connexion, puis réessaie.</p>
          <Cta variant="secondary" onClick={onRetry}>Réessayer</Cta>
        </div>
      )}
      <Cta className="w-full py-4 text-xl" disabled={!ready} onClick={onStart}>
        {ready ? 'Commencer' : 'Chargement…'}
      </Cta>
    </div>
  )
}

// ---------- Série ----------
function Run(props: { bank: VisBank; level: Level; mode: DisplayMode; stats: VisStats | null; onDone: () => void; onMenu: () => void }) {
  const [series, setSeries] = useState(0)
  return <Series key={series} {...props} onReplay={() => setSeries((s) => s + 1)} />
}

type Phase = 'line' | 'question' | 'reveal' | 'over'

function Series({ bank, level, mode, stats, onDone, onMenu, onReplay }: {
  bank: VisBank
  level: Level
  mode: DisplayMode
  stats: VisStats | null
  onDone: () => void
  onMenu: () => void
  onReplay: () => void
}) {
  const items = bank.levels[String(level)] ?? []
  const key = seriesKey(level, mode)
  const recorder = useRef(new RunRecorder(key, VIS_DOMAIN)).current
  const used = useRef(new Set<string>()).current
  const [question, setQuestion] = useState<Question | null>(() => pickQuestion(items, level, used))
  const [phase, setPhase] = useState<Phase>(mode === 'flash' ? 'line' : 'question')
  const [flashIndex, setFlashIndex] = useState(0)
  const [picked, setPicked] = useState<string[]>([])
  const [yesNo, setYesNo] = useState<boolean | null>(null)
  const [verdict, setVerdict] = useState<boolean | null>(null)
  const [score, setScore] = useState(0)
  const [errors, setErrors] = useState(0)
  const [newRecord, setNewRecord] = useState(false)
  const phaseRef = useRef<Phase>(phase)
  const scoreRef = useRef(0)

  const moves = useMemo(() => (question ? lineMoves(question.item) : []), [question])
  const final = useMemo(() => (question ? finalPosition(question.item) : null), [question])

  function go(p: Phase) {
    phaseRef.current = p
    setPhase(p)
  }

  // Quitter en pleine série (nav, retour) : ses bonnes réponses sont déjà enregistrées ; StrictMode
  // rejoue ce nettoyage au montage sans démontage réel, on ne touche donc pas à la phase.
  useEffect(
    () => () => {
      if (phaseRef.current !== 'over' && scoreRef.current > 0) void recorder.save(scoreRef.current)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  // Mode « Un par un » : un demi-coup à la fois, puis la question. Le minuteur s'arrête quand la
  // page est masquée (PWA en arrière-plan) et reprend le coup affiché au retour.
  useEffect(() => {
    if (phase !== 'line') return
    let timer: ReturnType<typeof setTimeout> | null = null
    const arm = () => {
      if (timer) clearTimeout(timer)
      timer = null
      if (document.visibilityState === 'hidden') return
      timer = setTimeout(() => {
        if (flashIndex + 1 >= moves.length) go('question')
        else setFlashIndex(flashIndex + 1)
      }, FLASH_MS)
    }
    arm()
    document.addEventListener('visibilitychange', arm)
    return () => {
      if (timer) clearTimeout(timer)
      document.removeEventListener('visibilitychange', arm)
    }
  }, [phase, flashIndex, moves.length])

  function answer(success: boolean) {
    if (phaseRef.current !== 'question' || !question) return
    go('reveal')
    setVerdict(success)
    void recordQuestion(question, success)
    if (success) {
      scoreRef.current += 1
      setScore(scoreRef.current)
      void recorder.save(scoreRef.current)
    } else {
      setErrors((e) => e + 1)
    }
  }

  function onTap(square: string) {
    if (phaseRef.current !== 'question' || !question || question.kind === 'mate') return
    if (question.kind === 'best') {
      if (picked.length === 0) {
        setPicked([square])
        return
      }
      if (picked[0] === square) {
        setPicked([]) // re-toucher la case de départ l'annule
        return
      }
      const both = [picked[0], square]
      setPicked(both)
      answer(checkSquares(question, both))
      return
    }
    setPicked([square])
    answer(checkSquares(question, [square]))
  }

  function onYesNo(yes: boolean) {
    if (!question) return
    setYesNo(yes)
    answer(checkMate(question, yes))
  }

  // `stopped` : arrêt par le joueur (✕) ; une série arrêtée à zéro n'est pas enregistrée.
  function finish(stopped: boolean) {
    if (phaseRef.current === 'over') return
    go('over')
    void recorder.finish(scoreRef.current, !stopped).then((record) => {
      setNewRecord(record)
      onDone()
    })
  }

  function next() {
    if (errors >= MAX_ERRORS) {
      finish(false)
      return
    }
    if (question) used.add(question.item.id)
    const q = pickQuestion(items, level, used)
    if (!q) {
      finish(false)
      return
    }
    setQuestion(q)
    setPicked([])
    setYesNo(null)
    setVerdict(null)
    setFlashIndex(0)
    go(mode === 'flash' ? 'line' : 'question')
  }

  if (phase === 'over' || !question || !final) {
    return (
      <div data-vis-run data-phase="over" className="mx-auto w-full max-w-xl p-3">
        <RunSummary score={score} stats={stats ? { best: stats.best[key] ?? 0, last: stats.last[key] ?? [] } : null} newRecord={newRecord}
          units={['bonne réponse', 'bonnes réponses']} onReplay={onReplay} onMenu={onMenu} />
      </div>
    )
  }

  const side = question.side
  const reveal = phase === 'reveal'
  const marks: Record<string, string> = {}
  const arrows: BoardArrow[] = []
  if (reveal) {
    const good = question.kind === 'mate' ? [] : question.answers
    for (const s of picked) marks[s] = RED
    for (const s of good) marks[s] = GREEN
    const arrow = question.kind === 'best' ? question.item.best : question.kind === 'mate' ? question.mate?.[0] : undefined
    if (arrow) arrows.push({ startSquare: arrow.slice(0, 2), endSquare: arrow.slice(2, 4), color: 'rgba(80, 200, 80, 0.85)' })
  } else {
    for (const s of picked) marks[s] = PICK
  }
  const lastMove = !reveal && picked.length === 0 ? { from: question.item.last.slice(0, 2), to: question.item.last.slice(2, 4) } : null
  const showLine = mode === 'visible' || reveal

  return (
    <div
      data-vis-run
      data-phase={phase}
      data-kind={question.kind}
      data-item={question.item.id}
      data-level={level}
      data-target={question.target?.start ?? ''}
      data-verdict={verdict === null ? '' : verdict ? 'ok' : 'ko'}
      className="mx-auto grid w-full max-w-5xl grid-cols-1 gap-2 pb-3 md:grid-cols-[auto_23rem] md:grid-rows-[auto_1fr] md:justify-center md:gap-x-6 md:p-4"
    >
      {/* Un seul en-tête : au-dessus de l'échiquier sur mobile, en tête du panneau à droite sur ordinateur. */}
      <div className="md:col-start-2 md:row-start-1">
        <RunHeader title={`Calcul · ${level} demi-coups`} score={score} errors={errors} onQuit={() => finish(true)} />
      </div>
      <div className="flex justify-center md:col-start-1 md:row-span-2 md:row-start-1">
        <div className="boardbox vis-board">
          <Board
            fen={reveal ? final.fen() : question.item.fen}
            orientation={side}
            interactive={false}
            silent
            lastMove={lastMove}
            markSquares={marks}
            arrows={arrows}
            onSquareTap={onTap}
          />
        </div>
      </div>
      <div className="flex min-w-0 flex-col gap-2 px-3 md:col-start-2 md:row-start-2 md:px-0">
        <div className="flex items-center justify-between gap-2 text-sm">
          <span className="font-semibold text-neutral-300">
            <span aria-hidden className={`mr-1.5 inline-block h-3 w-3 rounded-full align-[-1px] ring-1 ring-white/30 ${side === 'w' ? 'bg-neutral-100' : 'bg-neutral-900'}`} />
            Trait aux {SIDE_NAME[side]}
          </span>
          <span className="text-neutral-500">{reveal ? 'Position finale' : 'Position de départ'}</span>
        </div>

        <div data-line className="min-h-12 rounded-xl bg-surface-2 px-3 py-2">
          {phase === 'line' ? (
            <div className="flex items-center justify-between gap-2">
              <span data-flash-move className="text-2xl font-black"><FigText text={moves[flashIndex]?.numbered ?? ''} /></span>
              <span className="text-xs text-neutral-400">coup {flashIndex + 1}/{moves.length}</span>
            </div>
          ) : showLine ? (
            <p data-line-text className="text-lg leading-snug font-bold break-words">
              {moves.map((m) => (
                <span key={m.ply} data-ply={m.ply} className="mr-1.5 inline-block"><FigText text={m.label} /></span>
              ))}
            </p>
          ) : (
            <p className="py-1 text-sm text-neutral-400">Ligne cachée : {moves.length} demi-coups, à toi de les rejouer de tête.</p>
          )}
        </div>

        {phase === 'question' && (
          <div data-question className="rounded-xl bg-surface-2 p-3">
            <p className="text-base leading-snug font-bold">{question.text}</p>
            {question.kind === 'mate' ? (
              <div className="mt-2 flex gap-2">
                <Cta className="flex-1 py-2" onClick={() => onYesNo(true)}>Oui</Cta>
                <Cta variant="secondary" className="flex-1 py-2" onClick={() => onYesNo(false)}>Non</Cta>
              </div>
            ) : question.kind === 'best' && picked.length === 1 ? (
              <p className="mt-1 text-sm text-neutral-400">Départ {picked[0]} · touche l'arrivée (ou {picked[0]} pour annuler).</p>
            ) : null}
          </div>
        )}

        {reveal && (
          <div data-reveal className="rounded-xl bg-surface-2 p-3">
            <div className="flex items-center gap-3">
              <span className={`text-lg font-black ${verdict ? 'text-accent' : 'text-red-400'}`}>{verdict ? '✓ Juste' : '✗ Faux'}</span>
              {question.kind === 'mate' && yesNo !== null && <span className="text-sm text-neutral-400">Ta réponse : {yesNo ? 'oui' : 'non'}</span>}
              <Cta className="ml-auto px-4 py-2 text-base" onClick={next}>{errors >= MAX_ERRORS ? 'Bilan' : 'Suivant'}</Cta>
            </div>
            <p data-correction className="mt-2 text-sm leading-snug text-neutral-300"><FigText text={correction(question)} /></p>
          </div>
        )}
      </div>
    </div>
  )
}
