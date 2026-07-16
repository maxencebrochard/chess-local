import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Chess, type Move } from 'chess.js'
import { useSearchParams } from 'react-router-dom'
import { Board, type BoardArrow } from '../components/Board'
import { EvalBar } from '../components/EvalBar'
import { MoveList } from '../components/MoveList'
import { Engine, type EngineLine } from '../lib/engine'
import { db } from '../lib/db'
import { bookContinuations, openingForMoves } from '../lib/openings'
import { CLASS_META, reviewGame, type GameReview, type MoveClass } from '../lib/review'
import { coachComments, coachSummary } from '../lib/coach'

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

export default function Analysis() {
  const [params, setParams] = useSearchParams()
  const [startFen, setStartFen] = useState(START_FEN)
  const [moves, setMoves] = useState<Move[]>([])
  const [viewIndex, setViewIndex] = useState(-1) // -1 = position de départ
  const [lines, setLines] = useState<EngineLine[]>([])
  const [engineOn, setEngineOn] = useState(true)
  const [review, setReview] = useState<GameReview | null>(null)
  const [reviewProgress, setReviewProgress] = useState<number | null>(null)
  const [reviewColor, setReviewColor] = useState<'w' | 'b' | null>(null)
  const [showImport, setShowImport] = useState(false)
  const [importText, setImportText] = useState('')
  const [importError, setImportError] = useState('')
  const [gameMeta, setGameMeta] = useState<string | null>(null)
  const [orientation, setOrientation] = useState<'w' | 'b'>('w')
  const engineRef = useRef<Engine | null>(null)

  const viewFen = useMemo(() => {
    const c = new Chess(startFen)
    for (let i = 0; i <= viewIndex; i++) c.move(moves[i].san)
    return c.fen()
  }, [startFen, moves, viewIndex])

  const viewChess = useMemo(() => new Chess(viewFen), [viewFen])
  const uciMoves = useMemo(() => moves.slice(0, viewIndex + 1).map((m) => m.lan), [moves, viewIndex])
  const opening = useMemo(
    () => (startFen === START_FEN ? openingForMoves(moves.map((m) => m.lan)) : null),
    [startFen, moves],
  )
  const book = useMemo(
    () => (startFen === START_FEN ? bookContinuations(uciMoves).slice(0, 6) : []),
    [startFen, uciMoves],
  )

  // Chargement depuis l'archive (?game=id).
  useEffect(() => {
    const gameId = params.get('game')
    if (!gameId) return
    void (async () => {
      const saved = await db.games.get(+gameId)
      if (!saved) return
      loadPgn(saved.pgn)
      setGameMeta(`${saved.timeControl} · ${saved.result} ${saved.termination}`)
      if (saved.playerColor === 'b') setOrientation('b')
      if (saved.mode === 'bot') setReviewColor(saved.playerColor)
      if (params.get('review') === '1') setTimeout(() => void runReview(saved.pgn), 300)
      setParams({}, { replace: true })
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Analyse infinie sur la position affichée. Coupée pendant un Game Review
  // pour ne pas entrelacer deux recherches sur le même worker.
  const reviewing = reviewProgress !== null
  useEffect(() => {
    if (!engineOn || reviewing) {
      setLines([])
      return
    }
    engineRef.current ??= new Engine()
    const engine = engineRef.current
    engine.onLines = setLines
    let cancelled = false
    void (async () => {
      await engine.stop()
      if (cancelled || viewChess.isGameOver()) {
        setLines([])
        return
      }
      await engine.startInfinite(viewFen, 3)
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewFen, engineOn, reviewing])

  useEffect(
    () => () => {
      // Null obligatoire : StrictMode rejoue les effets, un worker terminé ne doit pas être réutilisé.
      engineRef.current?.quit()
      engineRef.current = null
    },
    [],
  )

  function loadPgn(pgn: string): boolean {
    try {
      const c = new Chess()
      c.loadPgn(pgn)
      setStartFen(START_FEN)
      setMoves(c.history({ verbose: true }))
      setViewIndex(c.history().length - 1)
      setReview(null)
      setReviewColor(null)
      setGameMeta(null)
      return true
    } catch {
      return false
    }
  }

  function loadFen(fen: string): boolean {
    try {
      new Chess(fen)
      setStartFen(fen)
      setMoves([])
      setViewIndex(-1)
      setReview(null)
      setReviewColor(null)
      setGameMeta(null)
      return true
    } catch {
      return false
    }
  }

  function handleMove(from: string, to: string, promotion?: string): boolean {
    try {
      const c = new Chess(viewFen)
      const move = c.move({ from, to, promotion: promotion ?? 'q' })
      const kept = moves.slice(0, viewIndex + 1)
      // Si le coup joué est le coup suivant de la ligne existante, avancer sans tronquer.
      const nextExisting = moves[viewIndex + 1]
      if (nextExisting && nextExisting.lan === move.lan) {
        setViewIndex(viewIndex + 1)
        return true
      }
      setMoves([...kept, move])
      setViewIndex(kept.length)
      if (moves.length > kept.length) setReview(null) // ligne modifiée, review obsolète
      return true
    } catch {
      return false
    }
  }

  const runReview = useCallback(async (pgnOverride?: string) => {
    const pgn = pgnOverride ?? currentPgn()
    if (!pgn) return
    engineRef.current ??= new Engine()
    const engine = engineRef.current
    setReviewProgress(0)
    // Laisse l'effet d'analyse se couper (dépend de `reviewing`) avant de chercher.
    await new Promise((r) => setTimeout(r, 50))
    await engine.stop()
    engine.onLines = null
    try {
      const result = await reviewGame(pgn, engine, 12, (done, total) =>
        setReviewProgress(Math.round((done / total) * 100)),
      )
      setReview(result)
      setViewIndex(-1) // ouvre sur le résumé du coach

    } finally {
      setReviewProgress(null)
      engine.onLines = setLines
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moves, startFen])

  function currentPgn(): string | null {
    if (startFen !== START_FEN || moves.length === 0) return null
    const c = new Chess()
    for (const m of moves) c.move(m.san)
    return c.pgn()
  }

  // Eval affichée point de vue blanc.
  const topLine = lines[0] ?? null
  let evalCp: number | null = null
  let evalMate: number | null = null
  if (viewChess.isCheckmate()) {
    evalMate = 0
    evalCp = viewChess.turn() === 'w' ? -10000 : 10000
  } else if (topLine) {
    const sign = viewChess.turn() === 'w' ? 1 : -1
    if (topLine.scoreMate !== null) evalMate = sign * topLine.scoreMate
    evalCp = sign * (topLine.scoreCp ?? (topLine.scoreMate! > 0 ? 10000 : -10000))
  } else if (review && viewIndex >= 0) {
    evalCp = review.moves[viewIndex]?.evalAfterCp ?? null
    evalMate = review.moves[viewIndex]?.mateAfter ?? null
  }

  const arrows: BoardArrow[] = []
  if (engineOn && topLine?.pv[0] && topLine.pv[0].length >= 4) {
    arrows.push({ startSquare: topLine.pv[0].slice(0, 2), endSquare: topLine.pv[0].slice(2, 4), color: '#95bb4a' })
  }
  const reviewedCurrent = review && viewIndex >= 0 ? review.moves[viewIndex] : null

  const coach = useMemo(
    () =>
      review
        ? { comments: coachComments(review, reviewColor), summary: coachSummary(review, reviewColor) }
        : null,
    [review, reviewColor],
  )
  const coachCurrent = coach?.comments.find((c) => c.moveIndex === viewIndex) ?? null
  const keyMoments = useMemo(
    () => coach?.comments.filter((c) => c.severity === 'warn' || c.severity === 'alarm' || c.severity === 'praise') ?? [],
    [coach],
  )

  function jumpKeyMoment(dir: 1 | -1) {
    if (keyMoments.length === 0) return
    const next =
      dir === 1
        ? keyMoments.find((c) => c.moveIndex > viewIndex)
        : [...keyMoments].reverse().find((c) => c.moveIndex < viewIndex)
    if (next) setViewIndex(next.moveIndex)
  }

  const lastMove = viewIndex >= 0 ? { from: moves[viewIndex].from, to: moves[viewIndex].to } : null

  function sanLine(line: EngineLine): string {
    const c = new Chess(viewFen)
    const sans: string[] = []
    for (const uci of line.pv.slice(0, 8)) {
      try {
        sans.push(c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] }).san)
      } catch {
        break
      }
    }
    return sans.join(' ')
  }

  function lineScore(line: EngineLine): string {
    const sign = viewChess.turn() === 'w' ? 1 : -1
    if (line.scoreMate !== null) {
      const m = sign * line.scoreMate
      return `M${Math.abs(m)}${m < 0 ? ' (adv.)' : ''}`
    }
    const cp = (sign * (line.scoreCp ?? 0)) / 100
    return (cp > 0 ? '+' : '') + cp.toFixed(2)
  }

  return (
    <div className="flex h-full flex-col items-center justify-start gap-2 p-2 md:flex-row md:items-stretch md:justify-center md:gap-4 md:p-4">
      <div className="flex w-full flex-none justify-center gap-2 md:w-auto md:items-center md:gap-0">
        <div className="flex items-stretch md:items-center">
          <div className="self-stretch md:h-[min(76vh,640px)] md:self-auto">
            <EvalBar cp={evalCp} mate={evalMate} orientation={orientation} />
          </div>
        </div>

        <div className="flex flex-col justify-center gap-2 md:ml-4">
          <div className="w-[min(100vw-2.5rem,76vh,640px)]">
            <Board
              fen={viewFen}
              orientation={orientation}
              interactive
              onMove={handleMove}
              lastMove={lastMove}
              arrows={arrows}
            />
          </div>
          <div className="flex items-center gap-2 text-sm text-neutral-400">
          {opening && (
            <span>
              <span className="font-mono text-xs text-neutral-500">{opening.eco}</span> {opening.name}
            </span>
          )}
          {gameMeta && <span className="text-neutral-500">· {gameMeta}</span>}
          {reviewedCurrent && (
            <span className="ml-auto font-semibold" style={{ color: CLASS_META[reviewedCurrent.class].color }}>
              {moves[viewIndex].san} : {CLASS_META[reviewedCurrent.class].label}
            </span>
          )}
          </div>
        </div>
      </div>

      <div className="flex w-full flex-col gap-3 px-1 pb-2 md:w-96 md:px-0 md:py-2">
        <div className="flex items-center justify-between rounded bg-surface-2 px-3 py-2">
          <span className="text-sm font-semibold">Stockfish 18</span>
          <div className="flex items-center gap-2">
            {topLine && <span className="text-xs text-neutral-500">prof. {topLine.depth}</span>}
            <button
              onClick={() => setEngineOn(!engineOn)}
              className={`h-6 w-11 cursor-pointer rounded-full p-0.5 transition ${engineOn ? 'bg-accent' : 'bg-surface-3'}`}
            >
              <div className={`h-5 w-5 rounded-full bg-white transition ${engineOn ? 'translate-x-5' : ''}`} />
            </button>
          </div>
        </div>

        {engineOn && (
          <div className="space-y-1 rounded bg-surface-2 p-2">
            {lines.length === 0 && <p className="px-1 text-sm text-neutral-500">{viewChess.isGameOver() ? 'Partie terminée.' : 'Calcul…'}</p>}
            {lines.map((l) => (
              <div key={l.multipv} className="flex gap-2 truncate px-1 text-sm">
                <span className="w-14 shrink-0 font-bold text-neutral-100">{lineScore(l)}</span>
                <span className="truncate text-neutral-400">{sanLine(l)}</span>
              </div>
            ))}
          </div>
        )}

        <div className="h-36 md:h-auto md:min-h-0 md:flex-1">
          <MoveList
            sans={moves.map((m) => m.san)}
            currentIndex={viewIndex}
            onSelect={setViewIndex}
            classes={review ? review.moves.map((m) => m.class as MoveClass | null) : undefined}
          />
        </div>

        {review && (
          <div className="rounded bg-surface-2 p-3">
            <div className="mb-2 flex justify-around text-center">
              <div>
                <div className="text-xl font-bold text-white">{review.accuracyWhite}</div>
                <div className="text-xs text-neutral-400">Précision Blancs</div>
              </div>
              <div>
                <div className="text-xl font-bold text-white">{review.accuracyBlack}</div>
                <div className="text-xs text-neutral-400">Précision Noirs</div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-x-4 text-xs">
              {(Object.keys(CLASS_META) as MoveClass[]).map((k) => (
                <div key={k} className="flex justify-between py-0.5">
                  <span style={{ color: CLASS_META[k].color }}>
                    {CLASS_META[k].symbol} {CLASS_META[k].label}
                  </span>
                  <span className="text-neutral-300">
                    {review.counts.w[k]} · {review.counts.b[k]}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {coach && (
          <div
            className="rounded border-l-4 bg-surface-2 p-3"
            style={{
              borderLeftColor:
                coachCurrent?.severity === 'alarm' ? '#ca3431'
                : coachCurrent?.severity === 'warn' ? '#e58f2a'
                : coachCurrent?.severity === 'praise' ? '#81b64c'
                : '#5b8bb0',
            }}
          >
            <div className="flex items-start gap-2">
              <span className="text-2xl leading-none">🧑‍🏫</span>
              <p className="min-h-10 text-sm leading-snug text-neutral-200">
                {viewIndex === -1
                  ? coach.summary
                  : coachCurrent?.text ?? 'Coup adverse. Avance pour retrouver mes commentaires.'}
              </p>
            </div>
            {keyMoments.length > 0 && (
              <div className="mt-2 flex gap-2">
                <button
                  onClick={() => jumpKeyMoment(-1)}
                  className="flex-1 cursor-pointer rounded bg-surface-3 py-1 text-xs font-semibold hover:bg-surface-3/70"
                >
                  ← Moment clé
                </button>
                <button
                  onClick={() => jumpKeyMoment(1)}
                  className="flex-1 cursor-pointer rounded bg-surface-3 py-1 text-xs font-semibold hover:bg-surface-3/70"
                >
                  Moment clé →
                </button>
              </div>
            )}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <NavBtn label="⏮" onClick={() => setViewIndex(-1)} />
          <NavBtn label="◀" onClick={() => setViewIndex((v) => Math.max(-1, v - 1))} />
          <NavBtn label="▶" onClick={() => setViewIndex((v) => Math.min(moves.length - 1, v + 1))} />
          <NavBtn label="⏭" onClick={() => setViewIndex(moves.length - 1)} />
          <NavBtn label="⇅" title="Retourner l'échiquier" onClick={() => setOrientation((o) => (o === 'w' ? 'b' : 'w'))} />
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => void runReview()}
            disabled={reviewProgress !== null || moves.length === 0 || startFen !== START_FEN}
            className="flex-1 cursor-pointer rounded bg-accent py-2 text-sm font-bold text-white hover:bg-accent-hover disabled:cursor-default disabled:opacity-40"
          >
            {reviewProgress !== null ? `Analyse… ${reviewProgress}%` : '🔍 Bilan de partie'}
          </button>
          <button onClick={() => { setShowImport(true); setImportText(''); setImportError('') }} className="cursor-pointer rounded bg-surface-3 px-3 py-2 text-sm font-semibold hover:bg-surface-3/70">
            Importer
          </button>
          <button
            onClick={() => { const pgn = currentPgn(); if (pgn) void navigator.clipboard.writeText(pgn) }}
            className="cursor-pointer rounded bg-surface-3 px-3 py-2 text-sm font-semibold hover:bg-surface-3/70"
          >
            Copier PGN
          </button>
        </div>

        {book.length > 0 && (
          <div className="rounded bg-surface-2 p-2">
            <p className="mb-1 px-1 text-xs font-semibold text-neutral-400">Explorer d'ouvertures</p>
            {book.map((b) => {
              const c = new Chess(viewFen)
              let san = b.move
              try {
                san = c.move({ from: b.move.slice(0, 2), to: b.move.slice(2, 4), promotion: b.move[4] }).san
              } catch { /* coup hors position */ }
              return (
                <button
                  key={b.move}
                  onClick={() => handleMove(b.move.slice(0, 2), b.move.slice(2, 4), b.move[4])}
                  className="flex w-full cursor-pointer justify-between rounded px-2 py-1 text-sm hover:bg-surface-3"
                >
                  <span className="font-semibold">{san}</span>
                  <span className="truncate pl-2 text-neutral-500">{b.openings[0].name}</span>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {showImport && (
        <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/70" onClick={() => setShowImport(false)}>
          <div className="w-[520px] rounded-xl bg-surface-2 p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-3 text-lg font-bold">Importer PGN ou FEN</h2>
            <textarea
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder={'1. e4 e5 2. Nf3 …\nou\nrnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'}
              className="mb-3 h-40 w-full resize-none rounded bg-surface p-3 font-mono text-sm outline-none"
            />
            {importError && <p className="mb-2 text-sm text-red-400">{importError}</p>}
            <button
              onClick={() => {
                const text = importText.trim()
                const ok = text.split('\n').length === 1 && text.split('/').length === 8 ? loadFen(text) : loadPgn(text)
                if (ok) setShowImport(false)
                else setImportError('Format non reconnu : ni PGN valide, ni FEN valide.')
              }}
              className="w-full cursor-pointer rounded bg-accent py-2 font-bold text-white hover:bg-accent-hover"
            >
              Charger
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function NavBtn({ label, onClick, title }: { label: string; onClick: () => void; title?: string }) {
  return (
    <button title={title} onClick={onClick} className="flex-1 cursor-pointer rounded bg-surface-3 py-1.5 hover:bg-surface-3/70">
      {label}
    </button>
  )
}
