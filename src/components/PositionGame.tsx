// Partie contre Stockfish à pleine force depuis une position, sans plafond de coups : seules les
// règles du jeu (mat, pat, répétition, 50 coups, matériel insuffisant), l'abandon ou une nulle
// acceptée l'arrêtent. Sert aux finales jouées jusqu'au bout et au bouton « Jouer contre le
// moteur » de l'analyse. Le joueur a le trait au départ ; la partie est persistée à chaque coup.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Chess, type Move } from 'chess.js'
import { useNavigate } from 'react-router-dom'
import { Board, type BoardArrow } from './Board'
import { ConfirmSheet } from './ConfirmSheet'
import { CourseSheet } from './CourseSheet'
import { Cta } from './Cta'
import { MoveStrip } from './MoveStrip'
import { courseFor } from '../lib/courses'
import { Engine } from '../lib/engine'
import {
  boardEnd, engineAcceptsDraw, halfmoveClock, judge, loadStoredGame, repetitions, replay, resignEnd, storeGame,
  verdictText, type GameEnd, type Objective,
} from '../lib/positionGame'
import { sounds } from '../lib/sounds'
import { useSettings } from '../store/settings'

// Temps de réflexion de Stockfish par coup : pleine force, sans faire attendre.
const ENGINE_MOVETIME_MS = 700

export interface PositionGameProps {
  gameKey: string // clé de persistance : `finale:<id>` ou `position`
  startFen: string
  title: string
  objective: Objective
  goalHint?: string | null // précision sous l'objectif (finales)
  lesson?: string | null
  courseId?: string | null
  resume?: boolean // reprendre la partie persistée de cette clé (vrai par défaut)
  restoreFinished?: boolean // retour de l'analyse : reprendre aussi une partie terminée
  returnTo: string // où « Retour » de l'analyse ramène
  returnLabel: string
  onExit: () => void
  onOther?: () => void // « Autre finale »
  onFinished?: (success: boolean) => void // première fin de chaque tentative
  back?: unknown // gardé avec la partie persistée (partie libre)
}

interface Init {
  chess: Chess
  end: GameEnd | null
  assisted: boolean
  recorded: boolean
}

function initialGame(p: PositionGameProps): Init {
  const stored = loadStoredGame()
  if (p.resume !== false && stored && stored.key === p.gameKey && stored.startFen === p.startFen && (!stored.end || p.restoreFinished)) {
    const chess = replay(p.startFen, stored.uci)
    return { chess, end: stored.end ?? boardEnd(chess), assisted: stored.assisted, recorded: stored.recorded ?? !!stored.end }
  }
  const chess = new Chess(p.startFen)
  return { chess, end: boardEnd(chess), assisted: false, recorded: false }
}

export function PositionGame(props: PositionGameProps) {
  const { startFen, title, objective, goalHint, lesson, courseId, onExit, onOther } = props
  const navigate = useNavigate()
  const { playSounds } = useSettings()
  const [init] = useState(() => initialGame(props))
  const player = new Chess(startFen).turn()

  const chessRef = useRef(init.chess)
  const [fen, setFen] = useState(init.chess.fen())
  const [history, setHistory] = useState<Move[]>(init.chess.history({ verbose: true }))
  const [viewIndex, setViewIndex] = useState(-1) // -1 = position courante
  const [end, setEnd] = useState<GameEnd | null>(init.end)
  const [assisted, setAssisted] = useState(init.assisted)
  const recordedRef = useRef(init.recorded)
  // Stockfish joue (dès le montage si une partie reprise lui laisse le trait).
  const [thinking, setThinking] = useState(() => !init.end && init.chess.turn() !== new Chess(startFen).turn())
  const [busy, setBusy] = useState<'hint' | 'draw' | null>(null) // indice ou nulle en calcul
  const [hint, setHint] = useState<BoardArrow | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [showLesson, setShowLesson] = useState(false)
  const [showCourse, setShowCourse] = useState(false)
  const [confirmResign, setConfirmResign] = useState(false)
  const engineRef = useRef<Engine | null>(null)
  // Génération de la partie : un coup moteur, un indice ou une nulle calculés pour une partie
  // remplacée (Recommencer, démontage) sont ignorés à leur retour.
  const genRef = useRef(0)

  const course = courseId ? courseFor(courseId) : null

  function getEngine(): Engine {
    engineRef.current ??= new Engine()
    return engineRef.current
  }

  // Persistance à chaque changement : coups rejoués depuis la FEN de départ à la reprise. Une
  // partie vierge n'écrase pas la partie en cours d'une autre position (simple coup d'œil).
  useEffect(() => {
    if (history.length === 0 && !end) {
      const stored = loadStoredGame()
      if (stored && (stored.key !== props.gameKey || stored.startFen !== startFen)) return
    }
    storeGame({
      key: props.gameKey,
      startFen,
      player,
      label: title,
      uci: history.map((m) => m.lan),
      end,
      assisted,
      recorded: recordedRef.current,
      back: props.back,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history, end, assisted])

  const finish = useCallback((e: GameEnd) => {
    setEnd(e)
    const verdict = judge(e, player, objective)
    if (playSounds) (verdict === 'fail' ? sounds.fail : verdict === 'success' ? sounds.success : sounds.gameEnd)()
    if (!recordedRef.current) {
      recordedRef.current = true
      props.onFinished?.(verdict === 'success' && !assisted)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [player, objective, playSounds, assisted, props.onFinished])

  // Après chaque coup (joueur ou moteur) : affichage, son, fin de partie éventuelle.
  const afterMove = useCallback((move: Move): GameEnd | null => {
    const c = chessRef.current
    if (playSounds) {
      if (c.inCheck()) sounds.check()
      else if (move.captured) sounds.capture()
      else sounds.move()
    }
    setFen(c.fen())
    setHistory(c.history({ verbose: true }))
    setViewIndex(-1)
    setHint(null)
    setNotice(null)
    const e = boardEnd(c)
    if (e) finish(e)
    return e
  }, [playSounds, finish])

  const engineMove = useCallback(async () => {
    const gen = genRef.current
    const c = chessRef.current
    setThinking(true)
    try {
      const res = await getEngine().search({ fen: c.fen(), movetimeMs: ENGINE_MOVETIME_MS, multipv: 1 })
      if (gen !== genRef.current) return
      const move = c.move({ from: res.bestMove.slice(0, 2), to: res.bestMove.slice(2, 4), promotion: res.bestMove[4] })
      afterMove(move)
    } catch {
      // Pas de coup exploitable (ne devrait pas arriver) : dit-le, « Relancer » réessaie.
      if (gen === genRef.current) setNotice("Stockfish n'a pas répondu.")
    } finally {
      if (gen === genRef.current) setThinking(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [afterMove])

  // Reprise d'une partie interrompue pendant que Stockfish réfléchissait, et arrêt du moteur au
  // démontage (null obligatoire : StrictMode rejoue les effets).
  useEffect(() => {
    const c = chessRef.current
    if (!boardEnd(c) && !init.end && c.turn() !== player) void engineMove()
    return () => {
      // Compteur, pas un nœud du DOM : c'est bien la valeur courante qu'il faut incrémenter.
      // eslint-disable-next-line react-hooks/exhaustive-deps
      genRef.current++
      engineRef.current?.quit()
      engineRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const live = viewIndex === -1
  const myTurn = !end && !thinking && chessRef.current.turn() === player

  function handleMove(from: string, to: string, promotion?: string): boolean {
    if (!myTurn || !live || busy) return false
    let move: Move
    try {
      move = chessRef.current.move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    if (!afterMove(move)) void engineMove()
    return true
  }

  function restart() {
    genRef.current++
    chessRef.current = new Chess(startFen)
    recordedRef.current = false
    setFen(startFen)
    setHistory([])
    setViewIndex(-1)
    setEnd(boardEnd(chessRef.current))
    setAssisted(false)
    setThinking(false)
    setBusy(null)
    setHint(null)
    setNotice(null)
  }

  // Reprend le dernier coup du joueur (et la réponse de Stockfish). Possible après une fin sur
  // l'échiquier : le pat accidentel est l'erreur type des mats élémentaires.
  function takeback() {
    const c = chessRef.current
    if (thinking || busy) return
    const mine = c.history({ verbose: true }).filter((m) => m.color === player).length
    if (mine === 0) return
    if (c.turn() === player) c.undo() // la réponse de Stockfish
    c.undo() // mon coup
    genRef.current++
    setFen(c.fen())
    setHistory(c.history({ verbose: true }))
    setViewIndex(-1)
    setEnd(null)
    setAssisted(true)
    setHint(null)
    setNotice(null)
  }

  async function requestHint() {
    if (!myTurn || busy) return
    const gen = genRef.current
    setBusy('hint')
    setAssisted(true)
    try {
      const res = await getEngine().search({ fen: chessRef.current.fen(), depth: 14, multipv: 1 })
      if (gen !== genRef.current) return
      const uci = res.bestMove
      if (uci && uci.length >= 4) setHint({ startSquare: uci.slice(0, 2), endSquare: uci.slice(2, 4), color: '#81b64c' })
    } finally {
      if (gen === genRef.current) setBusy(null)
    }
  }

  async function offerDraw() {
    if (!myTurn || busy) return
    const gen = genRef.current
    setBusy('draw')
    try {
      const res = await getEngine().search({ fen: chessRef.current.fen(), depth: 12, multipv: 1 })
      if (gen !== genRef.current) return
      const line = res.lines[0]
      if (engineAcceptsDraw(line?.scoreCp ?? null, line?.scoreMate ?? null)) finish({ result: '1/2-1/2', kind: 'agreed' })
      else setNotice('Stockfish refuse la nulle.')
    } finally {
      if (gen === genRef.current) setBusy(null)
    }
  }

  function resign() {
    setConfirmResign(false)
    if (end) return
    genRef.current++
    setThinking(false)
    setBusy(null)
    finish(resignEnd(player))
  }

  // `replace` : l'analyse prend la place de la partie, son bouton retour la remet en place.
  function analyse() {
    navigate('/analyse', {
      replace: true,
      state: {
        fen: startFen,
        uci: history.map((m) => m.lan),
        orientation: player,
        label: title,
        returnTo: props.returnTo,
        returnLabel: props.returnLabel,
      },
    })
  }

  // ---------- Rendu ----------
  const verdict = end ? judge(end, player, objective) : null
  const playerMoves = history.filter((m) => m.color === player).length
  const text = end ? verdictText(end, player, objective, playerMoves) : null
  const clock = halfmoveClock(fen)
  const showClock = !end && (objective === 'draw' || clock >= 60)
  // `fen` signale le changement de la partie (mutable, dans une ref).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const reps = useMemo(() => (end ? 0 : repetitions(chessRef.current)), [fen, end])
  const subline =
    notice ??
    (reps === 2 ? 'Position déjà vue 2 fois : une fois de plus et c\'est nulle.' : null) ??
    (objective ? goalHint : `Tu joues les ${player === 'w' ? 'Blancs' : 'Noirs'}, sans limite de coups.`) ??
    null
  const viewFen = live ? fen : history[viewIndex].after
  const lastMove = live ? history[history.length - 1] : history[viewIndex]
  const boardEndKind = end && end.kind !== 'resign' && end.kind !== 'agreed'

  return (
    <div
      data-testid="position-game"
      data-fen={fen}
      data-status={end ? 'over' : 'playing'}
      data-verdict={verdict ?? 'none'}
      data-thinking={thinking || busy ? '1' : '0'}
      className="mx-auto flex h-full max-w-2xl flex-col"
    >
      <header className="flex items-center gap-1 px-2 pt-1">
        <button
          onClick={onExit}
          aria-label="Retour"
          className="flex h-10 w-10 cursor-pointer items-center justify-center rounded-full text-2xl text-neutral-400 hover:text-white"
        >
          ←
        </button>
        <h1 className="min-w-0 flex-1 truncate text-center text-lg font-black">{title}</h1>
        {course ? (
          <button
            onClick={() => setShowCourse(true)}
            title="Voir le cours"
            aria-label="Voir le cours"
            className="flex h-10 w-10 cursor-pointer items-center justify-center rounded-full text-lg font-black text-neutral-400 hover:text-white"
          >
            ?
          </button>
        ) : (
          <span className="w-10" />
        )}
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div
          data-testid="objective"
          className={`mx-3 mt-1 rounded px-3 py-1.5 ${
            verdict === 'success' ? 'bg-accent/15 text-accent'
            : verdict === 'fail' ? 'bg-red-900/40 text-red-200'
            : 'bg-surface-2'
          }`}
        >
          <div className="flex items-center gap-2">
            <p className="min-w-0 flex-1 truncate text-sm font-bold">
              {text
                ? <>{verdict === 'success' ? '✓ ' : verdict === 'fail' ? '✗ ' : ''}{text.title}</>
                : objective === 'win' ? 'Objectif : gagner'
                : objective === 'draw' ? 'Objectif : tenir la nulle'
                : 'Partie libre'}
            </p>
            {lesson && (
              <button
                onClick={() => setShowLesson((s) => !s)}
                aria-expanded={showLesson}
                className="shrink-0 cursor-pointer rounded-full bg-surface-3/80 px-2.5 py-0.5 text-xs font-semibold text-neutral-200 hover:bg-surface-3"
              >
                Leçon {showLesson ? '▴' : '▾'}
              </button>
            )}
          </div>
          <p className={`truncate text-xs ${end ? '' : notice || reps === 2 ? 'text-amber-300' : 'text-neutral-400'}`}>
            {text ? <>{text.reason}{assisted && ' (avec aide)'}</> : (subline ?? ' ')}
          </p>
        </div>
        {showLesson && lesson && (
          <p className="mx-3 mt-1 rounded bg-surface-2 px-3 py-2 text-sm leading-snug text-neutral-200">{lesson}</p>
        )}

        <div className="flex h-7 items-center gap-2 px-3 text-xs text-neutral-400">
          <span className="font-semibold text-neutral-300">🤖 Stockfish 18</span>
          <span>{thinking ? 'réfléchit…' : busy === 'hint' ? 'cherche un indice…' : busy === 'draw' ? 'étudie ta proposition…' : 'pleine force'}</span>
          <span className="ml-auto flex items-center gap-2">
            {assisted && !end && <span className="rounded bg-surface-3 px-1.5 py-0.5">avec aide</span>}
            {showClock && (
              <span className={`rounded px-1.5 py-0.5 ${clock >= 80 ? 'bg-amber-900/50 text-amber-200' : 'bg-surface-3'}`}>
                50 coups : {Math.floor(clock / 2)}/50
              </span>
            )}
          </span>
        </div>

        <div className="flex justify-center">
          <div className="boardbox md:w-[min(62vh,560px)]">
            <Board
              fen={viewFen}
              orientation={player}
              interactive={myTurn && live && !busy}
              movableColor={player}
              onMove={handleMove}
              lastMove={lastMove ? { from: lastMove.from, to: lastMove.to } : null}
              arrows={hint && live ? [hint] : []}
            />
          </div>
        </div>
        <div className="min-h-10">
          <MoveStrip
            sans={history.map((m) => m.san)}
            classes={history.map(() => null)}
            currentIndex={live ? history.length - 1 : viewIndex}
            onSelect={(i) => setViewIndex(i === history.length - 1 ? -1 : i)}
            startTurn={player}
          />
        </div>
      </div>

      <div className="flex items-center gap-1 border-t border-black/40 px-1 py-1.5">
        {!end ? (
          <>
            <Action label="Abandonner" icon="🏳" onClick={() => setConfirmResign(true)} />
            {objective !== 'draw' && (
              <Action label="Nulle" icon="½" onClick={() => void offerDraw()} disabled={!myTurn || !!busy} />
            )}
            {!thinking && chessRef.current.turn() !== player ? (
              <Action label="Relancer" icon="🤖" onClick={() => void engineMove()} />
            ) : (
              <Action label="Indice" icon="💡" onClick={() => void requestHint()} disabled={!myTurn || !!busy} />
            )}
            <Action label="Annuler" icon="↩" onClick={takeback} disabled={thinking || !!busy || playerMoves === 0} />
            <Action label="Recommencer" icon="↺" onClick={restart} disabled={history.length === 0} />
          </>
        ) : (
          <>
            {boardEndKind && <Action label="Annuler" icon="↩" onClick={takeback} disabled={playerMoves === 0} />}
            <Action label="Analyser" icon="♞" onClick={analyse} disabled={history.length === 0} />
            {onOther && <Action label="Rejouer" icon="↺" onClick={restart} />}
            <div className="flex-1" />
            {onOther ? (
              <Cta className="mr-1 px-5 py-2 text-base" onClick={onOther}>Autre finale</Cta>
            ) : (
              <Cta className="mr-1 px-5 py-2 text-base" onClick={restart}>Rejouer</Cta>
            )}
          </>
        )}
      </div>

      {confirmResign && (
        <ConfirmSheet
          title="Abandonner la partie ?"
          confirmLabel="Abandonner"
          danger
          testId="resign"
          onConfirm={resign}
          onCancel={() => setConfirmResign(false)}
        >
          <p>{objective ? 'La partie sera comptée comme un objectif manqué.' : 'La partie sera perdue.'} Tu pourras la rejouer ou l'analyser ensuite.</p>
        </ConfirmSheet>
      )}
      {showCourse && course && <CourseSheet course={course} onClose={() => setShowCourse(false)} />}
    </div>
  )
}

// Action de la barre du bas : icône + libellé, comme le mode entraîneur de Jouer.
function Action({ label, icon, onClick, disabled }: { label: string; icon: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="flex min-w-0 flex-1 cursor-pointer flex-col items-center gap-0.5 rounded px-0.5 py-1 text-[11px] font-semibold whitespace-nowrap text-neutral-300 hover:text-white disabled:cursor-default disabled:opacity-35"
    >
      <span aria-hidden="true" className="text-xl leading-none">{icon}</span>
      {label}
    </button>
  )
}
