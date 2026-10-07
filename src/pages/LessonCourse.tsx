// Cours d'Apprendre (finales, « Démolir le roque »), façon chess.com Lessons : un sommaire par
// chapitres, puis des leçons en étapes (diagramme commenté, ligne à jouer coup par coup, bilan).
// 100 % hors ligne : aucune analyse moteur dans l'app, chaque verdict vient du contenu vérifié hors
// ligne (tables de finales ou Stockfish) et tamponné.
import { useEffect, useMemo, useRef, useState } from 'react'
import { Navigate, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Chess } from 'chess.js'
import { Board, type BoardArrow } from '../components/Board'
import { CoachBubble } from '../components/CoachBubble'
import { Cta } from '../components/Cta'
import { lineUci, type Course, type DiagramStep, type Lesson, type LineStep, type MarkColor } from '../lib/lessonCourse'
import { ENDGAMES } from '../lib/learn'
import { figurine } from '../lib/review'
import { sounds } from '../lib/sounds'
import { useSettings } from '../store/settings'

const MARK_COLORS: Record<MarkColor, string> = {
  green: 'rgba(129, 182, 76, 0.6)',
  red: 'rgba(235, 97, 80, 0.65)',
  blue: 'rgba(105, 195, 242, 0.6)',
  yellow: 'rgba(255, 213, 79, 0.6)',
}
const ARROW_BLUE = '#69c3f2'
const ARROW_RED = '#eb6150'
const ARROW_HINT = '#81b64c'
const REPLY_DELAY_MS = 650
const WRONG_SHOW_MS = 700

// Taille de l'échiquier d'une leçon : pleine largeur sur téléphone, mais bornée par la hauteur
// pour que la bulle et les boutons tiennent sous l'échiquier, même sur un petit écran.
const LESSON_BOARD = 'w-[min(calc(100vw-1.5rem),calc(100dvh-21rem),34rem)]'

// ---------- Sommaire ----------
export default function CourseIndex({ course }: { course: Course }) {
  const navigate = useNavigate()
  const location = useLocation()
  // Venu d'une leçon ouverte depuis une séance d'Apprendre : la séance reste à restaurer.
  const fromSession = Boolean((location.state as { fromSession?: boolean } | null)?.fromSession)
  const [done, setDone] = useState<Set<string> | null>(null)

  useEffect(() => {
    void course.completedLessons().then(setDone)
  }, [course])

  const total = course.lessonIds.length
  const count = done ? course.lessonIds.filter((id) => done.has(id)).length : 0
  let n = 0
  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <button
        onClick={() => navigate('/apprendre', { replace: true, state: fromSession ? { restore: true } : null })}
        className="mb-2 cursor-pointer text-sm font-semibold text-neutral-400 hover:text-white"
      >
        ← Apprendre
      </button>
      <h1 className="mb-1 text-2xl font-black">
        {course.emoji} {course.title}
      </h1>
      <p className="mb-3 text-sm text-neutral-400">{course.intro}</p>
      <div className="mb-5 flex items-center gap-3">
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-3">
          <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${(count / total) * 100}%` }} />
        </div>
        <span data-testid="course-progress" className="text-sm font-bold text-neutral-300">
          {count}/{total}
        </span>
      </div>
      {course.chapters.map((ch, ci) => (
        <section key={ch.id} className="mb-5">
          <h2 className="mb-2 text-sm font-bold tracking-wide text-neutral-400 uppercase">
            {ci + 1}. {ch.title}
          </h2>
          <div className="space-y-2">
            {ch.lessons.map((id) => {
              const lesson = course.lessonById(id)!
              const finished = done?.has(id) ?? false
              n++
              return (
                <button
                  key={id}
                  data-lesson={id}
                  onClick={() => navigate(`${course.path}/${id}`, { state: { fromSession } })}
                  className="flex w-full cursor-pointer items-center gap-3 rounded-xl bg-surface-2 p-3 text-left hover:bg-surface-3"
                >
                  <span
                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-black ${
                      finished ? 'bg-accent text-white' : 'bg-surface-3 text-neutral-300'
                    }`}
                    aria-label={finished ? 'Terminée' : undefined}
                  >
                    {finished ? '✓' : n}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-bold">{lesson.title}</span>
                    <span className="block text-sm leading-snug text-neutral-400">{lesson.summary}</span>
                  </span>
                </button>
              )
            })}
          </div>
        </section>
      ))}
    </div>
  )
}

// ---------- Leçon ----------
export function CourseLesson({ course }: { course: Course }) {
  const { id } = useParams()
  const lesson = course.lessonById(id)
  if (!lesson || !id) return <Navigate to={course.path} replace />
  // `key` : changer de leçon (ou de cours) repart d'un état neuf.
  return <LessonView key={`${course.slug}/${id}`} course={course} id={id} lesson={lesson} />
}

function LessonView({ course, id, lesson }: { course: Course; id: string; lesson: Lesson }) {
  const navigate = useNavigate()
  const location = useLocation()
  // Ouverte depuis une séance d'Apprendre (« Voir la leçon ») : ✕ y retourne et la séance est
  // restaurée. Lu une fois : les changements d'étape (`setParams`) effacent le state.
  const [fromSession] = useState(() => Boolean((location.state as { fromSession?: boolean } | null)?.fromSession))
  const [params, setParams] = useSearchParams()
  const total = lesson.steps.length + 1 // + bilan
  const raw = Number(params.get('etape'))
  const stepIdx = Number.isInteger(raw) && raw >= 1 && raw <= total ? raw - 1 : 0
  const [lineDone, setLineDone] = useState(false)
  const [replay, setReplay] = useState(0)

  const step = lesson.steps[stepIdx] ?? null
  const isSummary = stepIdx === lesson.steps.length

  useEffect(() => {
    if (isSummary) void course.markLessonDone(id)
  }, [isSummary, id, course])

  function goTo(i: number) {
    setLineDone(false)
    setParams(i === 0 ? {} : { etape: String(i + 1) }, { replace: true })
  }

  const close = () =>
    fromSession ? navigate('/apprendre', { replace: true, state: { restore: true } }) : navigate(course.path, { replace: true })
  const goCourse = (path: string) => navigate(path, { replace: true, state: { fromSession } })
  const next = course.nextLessonId(id)
  const exercise = lesson.exercise ? ENDGAMES.find((e) => e.id === lesson.exercise) : undefined
  const canContinue = !step || step.kind === 'diagram' || lineDone

  return (
    <div className="pt-safe fixed inset-0 z-40 flex flex-col bg-surface">
      <header className="flex items-center gap-2 px-3 py-1">
        <button onClick={close} aria-label="Fermer la leçon" className="cursor-pointer p-1.5 text-2xl text-neutral-400 hover:text-white">
          ✕
        </button>
        <h1 className="min-w-0 flex-1 truncate text-center text-base font-black md:text-lg">{lesson.title}</h1>
        <span data-testid="lesson-step" className="w-9 text-right text-sm font-semibold text-neutral-500">
          {stepIdx + 1}/{total}
        </span>
      </header>
      <div className="mx-3 mb-2 h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${((stepIdx + 1) / total) * 100}%` }} />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-xl flex-col gap-3 px-3 pb-3">
          {step?.kind === 'diagram' && <DiagramView step={step} />}
          {step?.kind === 'line' && (
            <LineView key={`${stepIdx}-${replay}`} step={step} refusals={course.refusals} onDone={() => setLineDone(true)} />
          )}
          {isSummary && (
            <div className="flex flex-col gap-3 pt-2">
              <CoachBubble mood="happy" headline="Leçon terminée !">
                {lesson.summary}
              </CoachBubble>
              <div className="rounded-xl bg-surface-2 p-4">
                <h2 className="mb-2 font-bold">À retenir</h2>
                <ul className="space-y-1.5">
                  {lesson.keyPoints.map((k) => (
                    <li key={k} className="flex gap-2 text-[15px] leading-snug text-neutral-300">
                      <span className="text-accent">✓</span>
                      {k}
                    </li>
                  ))}
                </ul>
              </div>
              {fromSession ? (
                <Cta onClick={close}>Retour à la séance</Cta>
              ) : (
                exercise && (
                  <Cta
                    onClick={() =>
                      navigate('/apprendre', { state: { endgame: exercise.id, returnTo: `${course.path}/${id}?etape=${total}` } })
                    }
                  >
                    S'entraîner : {exercise.title}
                  </Cta>
                )
              )}
              {next && (
                <Cta variant={fromSession || exercise ? 'secondary' : 'primary'} onClick={() => goCourse(`${course.path}/${next}`)}>
                  Leçon suivante
                </Cta>
              )}
              <Cta variant="secondary" onClick={() => goCourse(course.path)}>
                Sommaire
              </Cta>
            </div>
          )}
        </div>
      </div>

      {!isSummary && (
        <footer className="pb-safe border-t border-black/30 bg-surface-2">
          <div className="mx-auto flex max-w-xl items-center gap-2 px-3 py-2">
            <button
              onClick={() => goTo(stepIdx - 1)}
              disabled={stepIdx === 0}
              className="cursor-pointer rounded-lg px-3 py-2 text-sm font-semibold text-neutral-300 hover:text-white disabled:cursor-default disabled:opacity-30"
            >
              ← Précédent
            </button>
            {step?.kind === 'line' && lineDone && (
              <button
                onClick={() => {
                  setLineDone(false)
                  setReplay((r) => r + 1)
                }}
                className="cursor-pointer rounded-lg px-3 py-2 text-sm font-semibold text-neutral-300 hover:text-white"
              >
                ↺ Rejouer
              </button>
            )}
            <Cta className="ml-auto px-6 py-2 text-base" disabled={!canContinue} onClick={() => goTo(stepIdx + 1)}>
              Continuer
            </Cta>
          </div>
        </footer>
      )}
    </div>
  )
}

function toBoardArrows(arrows: DiagramStep['arrows']): BoardArrow[] {
  return (arrows ?? []).map(([from, to, color]) => ({ startSquare: from, endSquare: to, color: color === 'red' ? ARROW_RED : ARROW_BLUE }))
}

function toMarks(marks: DiagramStep['marks']): Record<string, string> {
  return Object.fromEntries(Object.entries(marks ?? {}).map(([sq, c]) => [sq, MARK_COLORS[c]]))
}

function DiagramView({ step }: { step: DiagramStep }) {
  return (
    <>
      <div className="flex justify-center">
        <div className={`${LESSON_BOARD} touch-pan-y`}>
          <Board
            fen={step.fen}
            orientation={step.orientation ?? 'w'}
            interactive={false}
            arrows={toBoardArrows(step.arrows)}
            markSquares={toMarks(step.marks)}
          />
        </div>
      </div>
      <CoachBubble mood="thinking">{step.text}</CoachBubble>
    </>
  )
}

type Feedback = { tone: 'ok' | 'info' | 'bad'; headline?: string; text: string; reply?: string }

// Ligne jouable : l'élève joue le camp au trait, l'app répond après une courte pause.
function LineView({ step, refusals, onDone }: { step: LineStep; refusals: Course['refusals']; onDone: () => void }) {
  const { playSounds } = useSettings()
  const player = step.fen.split(' ')[1] as 'w' | 'b'
  const opponent = player === 'w' ? 'b' : 'w'
  const ucis = useMemo(() => lineUci(step), [step])
  const [chess] = useState(() => new Chess(step.fen))
  const chessRef = useRef(chess)
  const [fen, setFen] = useState(step.fen)
  const [ply, setPly] = useState(0)
  const [busy, setBusy] = useState(false)
  const [misses, setMisses] = useState(0)
  const [lastMove, setLastMove] = useState<{ from: string; to: string } | null>(null)
  const [wrongSquare, setWrongSquare] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<Feedback>({ tone: 'info', text: step.text })
  const timers = useRef<number[]>([])
  const finished = ply >= step.moves.length

  // Toute pause en cours (réponse adverse, coup refusé) meurt avec l'étape.
  useEffect(() => () => timers.current.forEach((t) => clearTimeout(t)), [])

  function later(fn: () => void, ms: number) {
    timers.current.push(window.setTimeout(fn, ms))
  }

  function sound(kind: 'move' | 'capture' | 'success' | 'fail') {
    if (playSounds) sounds[kind]()
  }

  function apply(uci: string) {
    const mv = chessRef.current.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
    setFen(chessRef.current.fen())
    setLastMove({ from: mv.from, to: mv.to })
    sound(mv.captured ? 'capture' : 'move')
    return mv
  }

  function accept(i: number) {
    const move = step.moves[i]
    apply(ucis[i])
    const headline = `${figurine(move.san, player)} ${move.only ? '!' : ''}`.trim()
    const after = i + 1
    if (after >= step.moves.length) {
      setPly(after)
      setFeedback({ tone: 'ok', headline, text: [move.text, step.end].filter(Boolean).join(' ') })
      sound('success')
      onDone()
      return
    }
    setPly(after)
    setFeedback({ tone: 'ok', headline, text: move.text ?? 'Bien joué.' })
    setBusy(true)
    later(() => {
      const reply = step.moves[after]
      apply(ucis[after])
      const done = after + 1 >= step.moves.length
      setPly(after + 1)
      setBusy(false)
      setFeedback((f) => ({
        ...f,
        reply: `${opponent === 'w' ? 'Les Blancs' : 'Les Noirs'} répondent ${figurine(reply.san, opponent)}${reply.weak ? ' ?' : '.'}${reply.text ? ` ${reply.text}` : ''}`,
        text: done ? [f.text, step.end].join(' ') : f.text,
      }))
      if (done) onDone()
    }, REPLY_DELAY_MS)
  }

  function handleMove(from: string, to: string, promotion?: string): boolean {
    if (busy || finished || chessRef.current.turn() !== player) return false
    const c = chessRef.current
    let mv
    try {
      mv = c.move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    const uci = mv.from + mv.to + (mv.promotion ?? '')
    const wrongFen = c.fen()
    c.undo()
    if (uci === ucis[ply]) {
      setMisses(0)
      accept(ply)
      return true
    }
    // Mauvais coup : montré un instant, case d'arrivée en rouge, puis repris.
    const expected = step.moves[ply]
    const stillGood = (expected.keeps ?? []).includes(uci)
    const close = !stillGood && refusals.close !== undefined && (expected.close ?? []).includes(uci)
    setMisses(misses + 1)
    setFeedback({
      tone: stillGood || close ? 'info' : 'bad',
      headline: figurine(mv.san, player),
      text: stillGood
        ? refusals.alsoGood(step.result)
        : [close ? refusals.close : refusals.bad(step.result), expected.hint && `Indice : ${expected.hint}`].filter(Boolean).join(' '),
    })
    if (!stillGood && !close) sound('fail')
    setBusy(true)
    setFen(wrongFen)
    setWrongSquare(mv.to)
    later(() => {
      setFen(c.fen())
      setWrongSquare(null)
      setBusy(false)
    }, WRONG_SHOW_MS)
    return true
  }

  function solution() {
    if (busy || finished) return
    setMisses(0)
    accept(ply)
  }

  const hint: BoardArrow[] =
    !finished && !busy && misses >= 2 ? [{ startSquare: ucis[ply].slice(0, 2), endSquare: ucis[ply].slice(2, 4), color: ARROW_HINT }] : []

  return (
    <>
      <div className="flex justify-center">
        <div className={LESSON_BOARD}>
          <Board
            fen={fen}
            orientation={player}
            interactive={!busy && !finished}
            movableColor={player}
            onMove={handleMove}
            lastMove={wrongSquare ? null : lastMove}
            arrows={hint}
            markSquares={wrongSquare ? { [wrongSquare]: MARK_COLORS.red } : undefined}
          />
        </div>
      </div>
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <CoachBubble mood={feedback.tone === 'bad' ? 'worried' : feedback.tone === 'ok' ? 'happy' : 'thinking'} headline={feedback.headline}>
            <span data-testid="line-feedback">{feedback.text}</span>
            {feedback.reply && <span className="mt-1 block text-neutral-600">{feedback.reply}</span>}
          </CoachBubble>
        </div>
      </div>
      <div className="flex items-center justify-between text-sm">
        <span className="font-semibold text-neutral-400">
          {finished ? '✓ Ligne terminée' : `À toi : ${player === 'w' ? 'Blancs' : 'Noirs'} · coup ${Math.floor(ply / 2) + 1}/${Math.ceil(step.moves.length / 2)}`}
        </span>
        {!finished && (
          <button
            onClick={solution}
            disabled={busy}
            className="cursor-pointer rounded-lg bg-surface-2 px-3 py-1.5 font-semibold text-neutral-300 hover:bg-surface-3 disabled:cursor-default disabled:opacity-40"
          >
            💡 Solution
          </button>
        )}
      </div>
    </>
  )
}
