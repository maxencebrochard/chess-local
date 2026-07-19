import { useCallback, useEffect, useRef, useState } from 'react'
import { Chess } from 'chess.js'
import { Board, type BoardArrow } from '../components/Board'
import { CoachBubble } from '../components/CoachBubble'
import { Cta } from '../components/Cta'
import { HEvalBar } from '../components/HEvalBar'
import { PuzzlePlayer } from '../components/PuzzlePlayer'
import { db } from '../lib/db'
import { Engine } from '../lib/engine'
import {
  buildSession, DOMAIN_META, domainRating, pickNextDomain, scoreItem,
  type LearnDomain, type Session, type SessionItem,
} from '../lib/learn'
import { figurine, winPct } from '../lib/review'
import { sounds } from '../lib/sounds'
import { useSettings } from '../store/settings'

type ItemPhase = 'lesson' | 'play' | 'success' | 'fail'

export default function Learn() {
  const { playSounds } = useSettings()
  const [ratings, setRatings] = useState<Record<string, number | null>>({})
  const [mistakeCount, setMistakeCount] = useState(0)
  const [session, setSession] = useState<Session | null>(null)
  const [itemIdx, setItemIdx] = useState(0)
  const [phase, setPhase] = useState<ItemPhase>('lesson')
  const [results, setResults] = useState<boolean[]>([])
  const [ratingDelta, setRatingDelta] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const engineRef = useRef<Engine | null>(null)

  const refresh = useCallback(async () => {
    const entries = await Promise.all(
      (['endgame', 'tactic', 'opening', 'strategy'] as LearnDomain[]).map(async (d) => [d, await domainRating(d)] as const),
    )
    setRatings(Object.fromEntries(entries))
    setMistakeCount(await db.mistakes.where('solved').equals(0).count())
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  useEffect(
    () => () => {
      engineRef.current?.quit()
      engineRef.current = null
    },
    [],
  )

  function getEngine(): Engine {
    engineRef.current ??= new Engine()
    return engineRef.current
  }

  async function start(domain?: LearnDomain) {
    setLoading(true)
    try {
      const d = domain ?? (await pickNextDomain())
      const s = await buildSession(d)
      if (s.items.length === 0) return
      setSession(s)
      setItemIdx(0)
      setResults([])
      setRatingDelta(null)
      setPhase('lesson')
    } finally {
      setLoading(false)
    }
  }

  async function finishItem(success: boolean) {
    if (!session) return
    const item = session.items[itemIdx]
    if (playSounds) (success ? sounds.success : sounds.fail)()
    const before = item.kind === 'mistake' ? null : (ratings[session.domain] ?? 800)
    const after = await scoreItem(session.domain, itemKey(item), success, item.difficulty)
    if (item.kind === 'mistake') {
      await db.mistakes.update(item.mistake.id!, {
        attempts: item.mistake.attempts + 1,
        solved: success ? 1 : 0,
      })
    }
    if (after !== null && before !== null) setRatingDelta(after - before)
    setResults((r) => [...r, success])
    setPhase(success ? 'success' : 'fail')
    void refresh()
  }

  function nextItem() {
    if (!session) return
    if (itemIdx + 1 < session.items.length) {
      setItemIdx(itemIdx + 1)
      setPhase('lesson')
    } else {
      setPhase('lesson')
      setSession({ ...session, items: [] }) // écran de fin
    }
  }

  // ---------- Écran de fin de séance ----------
  if (session && session.items.length === 0) {
    const ok = results.filter(Boolean).length
    return (
      <div className="pt-safe pb-safe fixed inset-0 z-40 bg-surface">
        <div className="mx-auto flex h-full max-w-lg flex-col items-center justify-center gap-4 p-6 text-center">
          <div className="text-6xl">{ok === results.length ? '🏆' : ok > 0 ? '💪' : '📚'}</div>
          <h1 className="text-2xl font-black">
            {ok}/{results.length} réussi{ok > 1 ? 's' : ''}
          </h1>
          <p className="text-neutral-400">
            {DOMAIN_META[session.domain].emoji} {DOMAIN_META[session.domain].label}
            {ratings[session.domain] !== null && ratings[session.domain] !== undefined && (
              <> · classement <b className="text-white">{ratings[session.domain]}</b></>
            )}
          </p>
          <Cta className="w-full" onClick={() => void start()}>
            Encore une séance
          </Cta>
          <Cta variant="secondary" className="w-full" onClick={() => { setSession(null); setResults([]) }}>
            Terminer
          </Cta>
        </div>
      </div>
    )
  }

  // ---------- Écran de séance ----------
  if (session) {
    const item = session.items[itemIdx]
    return (
      <div className="pt-safe pb-safe fixed inset-0 z-40 overflow-y-auto bg-surface">
        <div className="mx-auto flex min-h-full max-w-2xl flex-col">
          <header className="flex items-center px-3 py-1">
            <button
              onClick={() => { setSession(null); setResults([]) }}
              className="cursor-pointer p-1.5 text-2xl text-neutral-400 hover:text-white"
            >
              ✕
            </button>
            <h1 className="flex-1 text-center text-lg font-black">
              {DOMAIN_META[session.domain].emoji} {DOMAIN_META[session.domain].label}
              <span className="ml-2 text-sm font-semibold text-neutral-500">
                {itemIdx + 1}/{session.items.length}
              </span>
            </h1>
            <span className="w-9" />
          </header>
          <ExerciseView
            key={`${itemIdx}-${itemKey(item)}`}
            item={item}
            phase={phase}
            setPhase={setPhase}
            onFinish={(s) => void finishItem(s)}
            onNext={nextItem}
            getEngine={getEngine}
            ratingDelta={ratingDelta}
          />
        </div>
      </div>
    )
  }

  // ---------- Accueil Apprendre ----------
  const domains: LearnDomain[] = ['endgame', 'tactic', 'opening', 'strategy']
  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <h1 className="mb-1 text-2xl font-black">🎓 Apprendre</h1>
      <p className="mb-4 text-sm text-neutral-400">
        Séances de 1 à 2 minutes, adaptées à ton niveau. Un bouton, zéro décision.
      </p>

      <div className="mb-4 grid grid-cols-4 gap-2">
        {domains.map((d) => (
          <div key={d} className="rounded-xl bg-surface-2 p-3 text-center">
            <div className="text-2xl">{DOMAIN_META[d].emoji}</div>
            <div className="text-xl font-black">{ratings[d] ?? '…'}</div>
            <div className="text-xs text-neutral-400">{DOMAIN_META[d].label}</div>
          </div>
        ))}
      </div>

      <Cta className="mb-4 w-full py-4 text-2xl" onClick={() => void start()} disabled={loading}>
        {loading ? 'Préparation…' : 'Séance'}
      </Cta>

      <p className="mb-2 text-sm font-semibold text-neutral-400">Ou cible un domaine :</p>
      <div className="grid grid-cols-2 gap-2">
        {domains.map((d) => (
          <button
            key={d}
            onClick={() => void start(d)}
            className="flex cursor-pointer items-center gap-3 rounded-xl bg-surface-2 p-3 text-left hover:bg-surface-3"
          >
            <span className="text-2xl">{DOMAIN_META[d].emoji}</span>
            <span className="font-bold">{DOMAIN_META[d].label}</span>
          </button>
        ))}
        <button
          onClick={() => void start('mistakes')}
          disabled={mistakeCount === 0}
          className="col-span-2 flex cursor-pointer items-center gap-3 rounded-xl bg-surface-2 p-3 text-left hover:bg-surface-3 disabled:cursor-default disabled:opacity-40"
        >
          <span className="text-2xl">🩹</span>
          <span className="font-bold">Mes erreurs</span>
          <span className="ml-auto rounded-full bg-accent/20 px-2.5 py-0.5 text-sm font-bold text-accent">
            {mistakeCount}
          </span>
        </button>
      </div>
      {mistakeCount === 0 && (
        <p className="mt-2 text-xs text-neutral-500">
          « Mes erreurs » se remplit automatiquement quand tu fais le bilan d'une partie.
        </p>
      )}
    </div>
  )
}

function itemKey(item: SessionItem): string {
  switch (item.kind) {
    case 'endgame': return item.endgame.id
    case 'tactic': return item.puzzle.id
    case 'strategy': return `${item.card.id}:${item.puzzle.id}`
    case 'opening': return item.line.eco
    case 'mistake': return String(item.mistake.id)
  }
}

// ---------- Rendu d'un exercice ----------
interface ExerciseProps {
  item: SessionItem
  phase: ItemPhase
  setPhase: (p: ItemPhase) => void
  onFinish: (success: boolean) => void
  onNext: () => void
  getEngine: () => Engine
  ratingDelta: number | null
}

function ExerciseView(props: ExerciseProps) {
  const { item, phase, setPhase, onNext } = props

  const lesson =
    item.kind === 'endgame' ? { title: item.endgame.title, text: item.endgame.lesson }
    : item.kind === 'strategy' ? { title: item.card.title, text: item.card.lesson }
    : item.kind === 'tactic' ? { title: item.themeLabel, text: `Séquence « ${item.themeLabel} ». Repère le motif avant de calculer : il est dans chaque position.` }
    : item.kind === 'opening' ? { title: item.line.name.split(':')[0], text: `Rejoue tes ${Math.ceil(item.depth / 2)} premiers coups de la ${item.line.name.split(':')[0]}. Un mauvais coup = correction, puis on continue.` }
    : { title: 'Répare ta partie', text: `${item.mistake.gameLabel} : tu as joué ${figurine(item.mistake.playedSan)}. Trouve mieux cette fois.` }

  if (phase === 'lesson') {
    return (
      <div className="flex flex-1 flex-col justify-center gap-4 p-4">
        <CoachBubble mood="happy" headline={lesson.title}>{lesson.text}</CoachBubble>
        <Cta className="w-full" onClick={() => setPhase('play')}>
          C'est parti
        </Cta>
      </div>
    )
  }

  const verdictBar = (phase === 'success' || phase === 'fail') && (
    <div className="flex items-center gap-3 px-3 py-2">
      <span className={`text-lg font-black ${phase === 'success' ? 'text-accent' : 'text-red-400'}`}>
        {phase === 'success' ? '✓ Réussi !' : '✗ Raté'}
      </span>
      {props.ratingDelta !== null && props.ratingDelta !== 0 && (
        <span className={props.ratingDelta > 0 ? 'text-accent' : 'text-red-400'}>
          ({props.ratingDelta > 0 ? '+' : ''}{props.ratingDelta})
        </span>
      )}
      <Cta className="ml-auto px-6 py-2 text-base" onClick={onNext}>
        Suivant
      </Cta>
    </div>
  )

  return (
    <div className="flex flex-1 flex-col">
      {(item.kind === 'tactic' || item.kind === 'strategy') && <PuzzleExercise {...props} />}
      {item.kind === 'endgame' && <EndgameExercise {...props} />}
      {item.kind === 'opening' && <OpeningExercise {...props} />}
      {item.kind === 'mistake' && <MistakeExercise {...props} />}
      {verdictBar}
    </div>
  )
}

// ---------- Puzzle (tactique / stratégie) ----------
function PuzzleExercise({ item, phase, onFinish }: ExerciseProps) {
  if (item.kind !== 'tactic' && item.kind !== 'strategy') return null
  const puzzle = item.kind === 'tactic' ? item.puzzle : item.puzzle
  return (
    <div className="flex justify-center px-1">
      <div className="boardbox md:w-[min(60vh,560px)]">
        <PuzzlePlayer
          puzzle={puzzle}
          onComplete={(ok) => {
            if (phase === 'play') onFinish(ok)
          }}
        />
      </div>
    </div>
  )
}

// ---------- Finale contre Stockfish ----------
function EndgameExercise({ item, phase, onFinish, getEngine }: ExerciseProps) {
  const eg = item.kind === 'endgame' ? item.endgame : null
  const chessRef = useRef(new Chess(eg?.fen))
  const [fen, setFen] = useState(chessRef.current.fen())
  const [liveCp, setLiveCp] = useState<number | null>(0)
  const plies = useRef(0)
  const badStreak = useRef(0)
  const goodStreak = useRef(0)
  const finished = useRef(false)

  const conclude = useCallback((ok: boolean) => {
    if (finished.current || phase !== 'play') return
    finished.current = true
    onFinish(ok)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onFinish, phase])

  const evalAndCheck = useCallback(async () => {
    if (!eg || finished.current) return
    const c = chessRef.current
    if (c.isCheckmate()) {
      conclude(c.turn() !== eg.side) // mat donné par le joueur = succès (objectif win)
      return
    }
    if (c.isDraw()) {
      conclude(eg.objective === 'draw')
      return
    }
    const engine = getEngine()
    const res = await engine.search({ fen: c.fen(), depth: 10, multipv: 1 })
    const line = res.lines[0]
    const cpTurn = line ? (line.scoreMate !== null ? (line.scoreMate > 0 ? 10000 : -10000) : (line.scoreCp ?? 0)) : 0
    const cpPlayer = c.turn() === eg.side ? cpTurn : -cpTurn
    setLiveCp(eg.side === 'w' ? cpPlayer : -cpPlayer)
    if (eg.objective === 'win') {
      if (cpPlayer >= 600) goodStreak.current++
      else goodStreak.current = 0
      if (cpPlayer <= 80) badStreak.current++
      else badStreak.current = 0
      if (goodStreak.current >= 6) conclude(true)
      else if (badStreak.current >= 4) conclude(false)
      else if (plies.current >= 60) conclude(cpPlayer >= 300)
    } else {
      if (cpPlayer <= -350) badStreak.current++
      else badStreak.current = 0
      if (badStreak.current >= 4) conclude(false)
      else if (plies.current >= 30) conclude(true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eg, conclude, getEngine])

  const botMove = useCallback(async () => {
    if (!eg || finished.current) return
    const c = chessRef.current
    if (c.isGameOver()) return
    const engine = getEngine()
    const res = await engine.search({ fen: c.fen(), movetimeMs: 350, multipv: 1 })
    if (finished.current || !res.bestMove || res.bestMove.length < 4) return
    try {
      c.move({ from: res.bestMove.slice(0, 2), to: res.bestMove.slice(2, 4), promotion: res.bestMove[4] })
    } catch {
      return
    }
    plies.current++
    setFen(c.fen())
    void evalAndCheck()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eg, getEngine, evalAndCheck])

  if (!eg) return null

  function handleMove(from: string, to: string, promotion?: string): boolean {
    const c = chessRef.current
    if (phase !== 'play' || c.turn() !== eg!.side) return false
    try {
      c.move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    plies.current++
    setFen(c.fen())
    void (async () => {
      await evalAndCheck()
      if (!finished.current) await botMove()
    })()
    return true
  }

  return (
    <div className="flex flex-col gap-2 px-3">
      <div className="rounded bg-surface-2 px-3 py-1.5 text-center text-sm font-semibold">
        Objectif : {eg.objective === 'win' ? 'gagne cette position' : 'tiens la nulle'} — trait aux {eg.side === 'w' ? 'Blancs' : 'Noirs'}
      </div>
      <HEvalBar cp={liveCp} mate={null} />
      <div className="flex justify-center">
        <div className="boardbox md:w-[min(56vh,520px)]">
          <Board fen={fen} orientation={eg.side} interactive={phase === 'play'} movableColor={eg.side} onMove={handleMove} />
        </div>
      </div>
    </div>
  )
}

// ---------- Drill d'ouverture ----------
function OpeningExercise({ item, phase, onFinish }: ExerciseProps) {
  const line = item.kind === 'opening' ? item.line : null
  const depth = item.kind === 'opening' ? item.depth : 0
  const chessRef = useRef(new Chess())
  const [fen, setFen] = useState(chessRef.current.fen())
  const [step, setStep] = useState(0)
  const [faults, setFaults] = useState(0)
  const [hintArrow, setHintArrow] = useState<BoardArrow | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const finished = useRef(false)

  const playerColor = line?.playerColor ?? 'w'

  // L'app joue le camp adverse.
  useEffect(() => {
    if (!line || finished.current || phase !== 'play') return
    const c = chessRef.current
    if (step >= depth) {
      finished.current = true
      onFinish(faults <= 1)
      return
    }
    if (c.turn() !== playerColor) {
      const t = setTimeout(() => {
        const uci = line.uci[step]
        try {
          c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
          setStep((s) => s + 1)
          setFen(c.fen())
        } catch {
          finished.current = true
          onFinish(faults <= 1)
        }
      }, 450)
      return () => clearTimeout(t)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, phase, line, depth, playerColor, faults])

  if (!line) return null

  function handleMove(from: string, to: string, promotion?: string): boolean {
    const c = chessRef.current
    if (phase !== 'play' || c.turn() !== playerColor || finished.current) return false
    const expected = line!.uci[step]
    let mv
    try {
      mv = c.move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    const played = mv.from + mv.to + (mv.promotion ?? '')
    if (played === expected) {
      setHintArrow(null)
      setMsg(null)
      setStep(step + 1)
      setFen(c.fen())
      return true
    }
    // Mauvais coup : correction et nouvel essai.
    c.undo()
    setFen(c.fen())
    setFaults(faults + 1)
    setHintArrow({ startSquare: expected.slice(0, 2), endSquare: expected.slice(2, 4), color: '#69c3f2' })
    setMsg(`Pas la ligne : ici on joue ${figurine(new Chess(c.fen()).move({ from: expected.slice(0, 2), to: expected.slice(2, 4), promotion: expected[4] }).san, playerColor)}.`)
    return false
  }

  return (
    <div className="flex flex-col gap-2 px-3">
      <div className="rounded bg-surface-2 px-3 py-1.5 text-center text-sm font-semibold">
        {line.name.split(':')[0]} — joue les {Math.ceil(depth / 2)} premiers coups ({playerColor === 'w' ? 'Blancs' : 'Noirs'})
      </div>
      {msg && <p className="rounded bg-red-900/40 px-3 py-1.5 text-sm text-red-200">{msg}</p>}
      <div className="flex justify-center">
        <div className="boardbox md:w-[min(56vh,520px)]">
          <Board
            fen={fen}
            orientation={playerColor}
            interactive={phase === 'play'}
            movableColor={playerColor}
            onMove={handleMove}
            arrows={hintArrow ? [hintArrow] : []}
          />
        </div>
      </div>
    </div>
  )
}

// ---------- Mes erreurs (retry) ----------
function MistakeExercise({ item, phase, onFinish, getEngine }: ExerciseProps) {
  const mistake = item.kind === 'mistake' ? item.mistake : null
  const [fen] = useState(mistake?.fenBefore ?? '')
  const [checking, setChecking] = useState(false)
  const finished = useRef(false)
  const moverColor: 'w' | 'b' = fen ? (new Chess(fen).turn()) : 'w'

  if (!mistake) return null

  function handleMove(from: string, to: string, promotion?: string): boolean {
    if (phase !== 'play' || checking || finished.current) return false
    const c = new Chess(fen)
    let mv
    try {
      mv = c.move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    const played = mv.from + mv.to + (mv.promotion ?? '')
    if (played === mistake!.bestUci || c.isCheckmate()) {
      finished.current = true
      onFinish(true)
      return true
    }
    setChecking(true)
    void (async () => {
      const engine = getEngine()
      // Le coup joué est bon s'il ne perd presque rien face au meilleur.
      const before = await engine.search({ fen, depth: 12, multipv: 1 })
      const after = await engine.search({ fen: c.fen(), depth: 12, multipv: 1 })
      const cp = (l?: { scoreMate: number | null; scoreCp: number | null }) =>
        l ? (l.scoreMate !== null ? (l.scoreMate > 0 ? 10000 : -10000) : (l.scoreCp ?? 0)) : 0
      const wBefore = winPct(cp(before.lines[0]))
      const wAfter = winPct(-cp(after.lines[0]))
      finished.current = true
      setChecking(false)
      onFinish(wBefore - wAfter < 5)
    })()
    return true
  }

  return (
    <div className="flex flex-col gap-2 px-3">
      <div className="rounded bg-surface-2 px-3 py-1.5 text-center text-sm">
        <span className="font-semibold">{mistake.gameLabel}</span> — tu avais joué{' '}
        <span className="font-bold text-red-400">{figurine(mistake.playedSan, moverColor)}</span>. Trouve mieux.
      </div>
      {checking && <p className="text-center text-sm text-neutral-400">Je vérifie…</p>}
      <div className="flex justify-center">
        <div className="boardbox md:w-[min(56vh,520px)]">
          <Board fen={fen} orientation={moverColor} interactive={phase === 'play' && !checking} movableColor={moverColor} onMove={handleMove} />
        </div>
      </div>
    </div>
  )
}
