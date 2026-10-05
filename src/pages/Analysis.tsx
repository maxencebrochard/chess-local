import { useCallback, useEffect, useLayoutEffect, useMemo, useReducer, useRef, useState } from 'react'
import { Chess, type Move } from 'chess.js'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Board, type BoardArrow } from '../components/Board'
import { CoachAvatar, CoachBubble } from '../components/CoachBubble'
import { Cta } from '../components/Cta'
import { EvalBar } from '../components/EvalBar'
import { EvalGraph } from '../components/EvalGraph'
import { HEvalBar } from '../components/HEvalBar'
import { EngineLineRow } from '../components/EngineLineRow'
import { MoveList } from '../components/MoveList'
import { MoveStrip } from '../components/MoveStrip'
import { ReviewSummary } from '../components/ReviewSummary'
import { Engine, type EngineLine } from '../lib/engine'
import { db } from '../lib/db'
import { bookContinuations, openingForMoves } from '../lib/openings'
import { openingFr } from '../lib/openingNames'
import { CLASS_META, figurine, reviewGame, winPct, type GameReview, type MoveClass } from '../lib/review'
import { coachComments, coachSummary } from '../lib/coach'
import { sounds } from '../lib/sounds'
import { REVIEW_DEPTHS, useSettings } from '../store/settings'

interface RetryState {
  moveIndex: number
  baseFen: string // position avant le coup fautif
  status: 'trying' | 'checking' | 'found' | 'failed'
  // Essai dont la vérification moteur est en cours : son verdict ne s'applique qu'à lui (CP-11).
  attemptId?: number
  lastTried?: string
  solutionShown?: boolean
}

const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

// Analyse live : 3 lignes, arrêt à la profondeur 22 (une recherche infinie vide la batterie).
const LIVE_MULTIPV = 3
const LIVE_DEPTH = 22
// En dessous, les évals sont instables (jusqu'à 0,00 sur un mat) : jamais affichées, sauf mat annoncé.
const MIN_SHOWN_DEPTH = 8
const EVAL_CACHE_MAX = 300

function minDepth(lines: EngineLine[]): number {
  return lines.reduce((m, l) => Math.min(m, l.depth), Infinity)
}

// Recherche terminée pour cette position : toutes les lignes attendues à la profondeur cible.
function liveComplete(lines: EngineLine[], expected: number): boolean {
  return lines.length >= expected && minDepth(lines) >= LIVE_DEPTH
}

export default function Analysis() {
  const [params, setParams] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { reviewDepth, playSounds } = useSettings()
  const [startFen, setStartFen] = useState(START_FEN)
  const [moves, setMoves] = useState<Move[]>([])
  const [viewIndexRaw, setViewIndex] = useState(-1) // -1 = position de départ
  // Évals live par FEN analysée : les scores UCI sont du point de vue du trait, une ligne n'est donc
  // valable (et de bon signe) que pour SA position. Dans un ref (une copie de Map par `info` coûterait
  // cher sur iPhone), avec un compteur pour redessiner.
  const evalsRef = useRef(new Map<string, EngineLine[]>())
  const [, bumpEvals] = useReducer((n: number) => n + 1, 0)
  // Dernière éval live affichée, côté blanc : tenue pendant le calcul d'une position encore sans éval,
  // au lieu de retomber au neutre (la barre ferait l'aller-retour à chaque coup).
  const heldEvalRef = useRef<{ cp: number; mate: number | null } | null>(null)
  const [hidden, setHidden] = useState(() => document.hidden)
  const [engineOn, setEngineOn] = useState(true)
  const [review, setReview] = useState<GameReview | null>(null)
  const [reviewProgress, setReviewProgress] = useState<number | null>(null)
  const [reviewColor, setReviewColor] = useState<'w' | 'b' | null>(null)
  const [showImport, setShowImport] = useState(false)
  const [showOptions, setShowOptions] = useState(false)
  const [showExplorer, setShowExplorer] = useState(false)
  const [importText, setImportText] = useState('')
  const [importError, setImportError] = useState('')
  const [gameMeta, setGameMeta] = useState<string | null>(null)
  const [orientation, setOrientation] = useState<'w' | 'b'>('w')
  const [retry, setRetry] = useState<RetryState | null>(null)
  const [reviewStage, setReviewStage] = useState<'summary' | 'guided' | null>(null)
  const [showBest, setShowBest] = useState(false)
  const [showLines, setShowLines] = useState(false)
  const [names, setNames] = useState<{ w: string; b: string }>({ w: 'Blancs', b: 'Noirs' })
  const [returnTo, setReturnTo] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const engineRef = useRef<Engine | null>(null)
  // Moteur de la vérification de Réessayer, séparé de l'analyse live : le `stop()` du nettoyage
  // de l'effet live ne doit jamais toucher une vérification en vol.
  const checkEngineRef = useRef<Engine | null>(null)
  // Jeton des vérifications de Réessayer : incrémenté à chaque essai vérifié, à chaque Réessayer
  // et à chaque sortie du mode Réessayer. Un verdict dont le jeton n'est plus le dernier est jeté.
  const attemptSeq = useRef(0)
  const checkInFlight = useRef(false)
  // Jeton du bilan en cours : tout résultat d'un bilan remplacé ou annulé est jeté.
  const reviewAbortRef = useRef<AbortController | null>(null)
  const aliveRef = useRef(false)
  const reviewTimer = useRef<number | null>(null)
  const noticeTimer = useRef<number | null>(null)

  // Index affiché toujours borné par la liste de coups : un bilan ou une navigation périmée
  // ne doit jamais faire lire `moves[i]` hors de la liste (écran blanc).
  const viewIndex = Math.max(-1, Math.min(viewIndexRaw, moves.length - 1))

  const viewFen = useMemo(() => {
    const c = new Chess(startFen)
    for (let i = 0; i <= viewIndex; i++) c.move(moves[i].san)
    return c.fen()
  }, [startFen, moves, viewIndex])

  const viewChess = useMemo(() => new Chess(viewFen), [viewFen])
  const startTurn = useMemo(() => new Chess(startFen).turn(), [startFen])
  const colorAtIndex = (i: number): 'w' | 'b' => ((i % 2 === 0) === (startTurn === 'w') ? 'w' : 'b')
  const uciMoves = useMemo(() => moves.slice(0, viewIndex + 1).map((m) => m.lan), [moves, viewIndex])
  const opening = useMemo(
    () => (startFen === START_FEN ? openingForMoves(moves.map((m) => m.lan)) : null),
    [startFen, moves],
  )
  const book = useMemo(
    () => (startFen === START_FEN ? bookContinuations(uciMoves).slice(0, 6) : []),
    [startFen, uciMoves],
  )

  // Chargement depuis l'import chess.com ou une position externe (state de navigation).
  useEffect(() => {
    const state = location.state as {
      pgn?: string
      fen?: string
      uci?: string[]
      viewIndex?: number
      color?: 'w' | 'b'
      orientation?: 'w' | 'b'
      label?: string
      review?: boolean
      returnTo?: string
    } | null
    if (state?.returnTo) setReturnTo(state.returnTo)
    // Position (+ séquence de coups optionnelle, ex : puzzle) : analyse live immédiate.
    if (state?.fen && !state.pgn) {
      if (loadFen(state.fen)) {
        if (state.uci?.length) {
          const c = new Chess(state.fen)
          for (const uci of state.uci) {
            try {
              c.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] })
            } catch {
              break
            }
          }
          const played = c.history({ verbose: true })
          setMoves(played)
          setViewIndex(Math.min(state.viewIndex ?? played.length - 1, played.length - 1))
        }
        setOrientation(state.orientation ?? 'w')
        if (state.label) setGameMeta(state.label)
      }
      navigate('.', { replace: true, state: null })
      return
    }
    if (!state?.pgn) return
    if (loadPgn(state.pgn)) {
      setGameMeta(state.label ?? null)
      if (state.color) {
        setReviewColor(state.color)
        setOrientation(state.color)
      }
      if (state.review) {
        const ctx = { color: state.color ?? null, label: state.label ?? null }
        reviewTimer.current = window.setTimeout(() => void runReview(state.pgn, ctx), 300)
      }
    }
    navigate('.', { replace: true, state: null })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Chargement depuis l'archive (?game=id).
  useEffect(() => {
    const gameId = params.get('game')
    if (!gameId) return
    void (async () => {
      // Clé non numérique : Dexie lève, traité comme une partie absente.
      const saved = await db.games.get(+gameId).catch(() => undefined)
      if (!aliveRef.current) return // page quittée pendant la lecture : ne pas naviguer ni charger
      setParams({}, { replace: true })
      if (!saved) {
        showNotice('Partie introuvable (supprimée ?)')
        return
      }
      if (!loadPgn(saved.pgn)) {
        showNotice('Partie vide, rien à analyser')
        return
      }
      const label = `${saved.timeControl} · ${saved.result} ${saved.termination}`
      const color = saved.mode === 'bot' ? saved.playerColor : null
      setGameMeta(label)
      if (saved.playerColor === 'b') setOrientation('b')
      setReviewColor(color)
      if (params.get('review') === '1') {
        reviewTimer.current = window.setTimeout(() => void runReview(saved.pgn, { color, label }), 300)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Analyse live sur la position affichée. Coupée pendant un Game Review (deux recherches
  // entrelacées sur le même worker), pendant un retry (les lignes révéleraient la solution),
  // moteur désactivé, et page masquée (batterie).
  const reviewing = reviewProgress !== null
  const retrying = retry !== null
  const guidedNoLines = reviewStage === 'guided' && !showLines
  const liveOn = engineOn && !reviewing && !retrying && reviewStage !== 'summary' && !guidedNoLines

  useEffect(() => {
    const onVisibility = () => setHidden(document.hidden)
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [])

  useEffect(() => {
    // Sortie anticipée : jamais de `stop()` ici. Il fait `searchId++` hors mutex et viderait les
    // lignes d'un bilan ou d'un Réessayer en vol. La recherche live, elle, est arrêtée par le
    // nettoyage de l'exécution qui l'a lancée.
    if (!liveOn) {
      heldEvalRef.current = null
      return
    }
    if (hidden || viewChess.isGameOver()) return
    const fen = viewFen
    const expected = Math.min(LIVE_MULTIPV, viewChess.moves().length)
    // Cache lu dans le ref, pas en dépendance : l'effet ne doit tourner qu'au changement de position
    // ou d'état, jamais à chaque `info` (il bouclerait stop/relance).
    const done = evalsRef.current.get(fen)
    if (done && liveComplete(done, expected)) {
      // LRU : une position relue repasse en tête du cache.
      evalsRef.current.delete(fen)
      evalsRef.current.set(fen, done)
      return
    }
    engineRef.current ??= new Engine()
    const engine = engineRef.current
    let cancelled = false
    engine.onLines = (ls, lineFen) => {
      if (cancelled || lineFen !== fen) return
      const cache = evalsRef.current
      const known = cache.get(fen)
      // Plancher levé seulement si la ligne PRINCIPALE annonce un mat (c'est elle qui fait la barre).
      if (minDepth(ls) < MIN_SHOWN_DEPTH && ls[0]?.scoreMate == null) return
      // Une recherche relancée ne remplace l'éval connue qu'une fois au moins aussi profonde et complète.
      if (known && (minDepth(ls) < minDepth(known) || ls.length < Math.min(known.length, expected))) return
      cache.delete(fen)
      cache.set(fen, ls)
      if (cache.size > EVAL_CACHE_MAX) cache.delete(cache.keys().next().value!)
      bumpEvals()
      if (liveComplete(ls, expected)) void engine.stop()
    }
    void engine.startInfinite(fen, LIVE_MULTIPV)
    return () => {
      cancelled = true
      engine.onLines = null
      void engine.stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewFen, liveOn, hidden])

  useEffect(() => {
    aliveRef.current = true
    return () => {
      // Plus aucun bilan différé ni en vol ne doit toucher la page ni créer un moteur après le démontage.
      aliveRef.current = false
      if (reviewTimer.current !== null) window.clearTimeout(reviewTimer.current)
      if (noticeTimer.current !== null) window.clearTimeout(noticeTimer.current)
      reviewAbortRef.current?.abort()
      reviewAbortRef.current = null
      // Null obligatoire : StrictMode rejoue les effets, un worker terminé ne doit pas être réutilisé.
      engineRef.current?.quit()
      engineRef.current = null
      checkEngineRef.current?.quit()
      checkEngineRef.current = null
    }
  }, [])

  // Bandeau d'information (partie introuvable, partie vide) : fermé au tap ou après 5 s.
  function showNotice(text: string) {
    setNotice(text)
    if (noticeTimer.current !== null) window.clearTimeout(noticeTimer.current)
    noticeTimer.current = window.setTimeout(() => setNotice(null), 5000)
  }

  // Annule le bilan en vol : son résultat, sa progression et ses fautes ne seront jamais appliqués.
  function cancelReview() {
    // Bilan différé (archive, state de navigation) pas encore parti : il analyserait l'ancien PGN.
    if (reviewTimer.current !== null) window.clearTimeout(reviewTimer.current)
    reviewTimer.current = null
    reviewAbortRef.current?.abort()
    reviewAbortRef.current = null
    setReviewProgress(null)
  }

  function loadPgn(pgn: string): boolean {
    try {
      const c = new Chess()
      c.loadPgn(pgn)
      // En-tête FEN (puzzle, position importée) : l'historique part de cette position, pas de
      // la position initiale. Normalisée pour que `startFen === START_FEN` reste fiable.
      const fen = c.header().FEN
      const history = c.history({ verbose: true })
      if (history.length === 0 && !fen) return false // en-têtes seuls, rien à analyser
      cancelReview()
      heldEvalRef.current = null // une autre partie : rien à tenir de l'ancienne
      setStartFen(fen ? new Chess(fen).fen() : START_FEN)
      setMoves(history)
      setViewIndex(history.length - 1)
      setReview(null)
      setReviewColor(null)
      setReviewStage(null)
      clearRetry()
      setGameMeta(null)
      const h = c.header()
      const clean = (v: string | null | undefined, fallback: string) => (v && v !== '?' ? v : fallback)
      setNames({ w: clean(h.White, 'Blancs'), b: clean(h.Black, 'Noirs') })
      return true
    } catch {
      return false
    }
  }

  function loadFen(fen: string): boolean {
    try {
      new Chess(fen)
      cancelReview()
      heldEvalRef.current = null
      setStartFen(fen)
      setMoves([])
      setViewIndex(-1)
      setReview(null)
      setReviewColor(null)
      setReviewStage(null)
      clearRetry()
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
      // Ligne modifiée (tronquée ou prolongée) : le bilan, affiché ou en vol, ne la décrit plus.
      cancelReview()
      setReview(null)
      setReviewStage(null)
      clearRetry()
      return true
    } catch {
      return false
    }
  }

  // `ctx` : couleur du joueur et libellé de la partie, passés explicitement (les appels différés
  // depuis le premier rendu ne voient pas `reviewColor` ni `gameMeta`).
  const runReview = useCallback(async (pgnOverride?: string, ctx?: { color: 'w' | 'b' | null; label: string | null }) => {
    const pgn = pgnOverride ?? currentPgn()
    if (!pgn || !aliveRef.current) return
    cancelReview()
    const ctrl = new AbortController()
    reviewAbortRef.current = ctrl
    const isCurrent = () => reviewAbortRef.current === ctrl
    const color = ctx?.color ?? null
    const label = ctx?.label ?? null
    engineRef.current ??= new Engine()
    const engine = engineRef.current
    setReviewColor(color)
    setReviewProgress(0)
    // Laisse l'effet d'analyse se couper (dépend de `reviewing`) avant de chercher.
    await new Promise((r) => setTimeout(r, 50))
    if (!isCurrent()) return
    await engine.stop()
    if (!isCurrent()) return // bilan remplacé pendant le stop : ne pas couper la barre d'éval réarmée
    engine.onLines = null
    try {
      const result = await reviewGame(
        pgn,
        engine,
        REVIEW_DEPTHS[reviewDepth],
        (done, total) => {
          if (isCurrent()) setReviewProgress(Math.round((done / total) * 100))
        },
        ctrl.signal,
      )
      if (!isCurrent()) return
      setReview(result)
      setViewIndex(-1)
      setReviewStage('summary') // ouvre sur l'écran de résumé
      void recordMistakes(result, color, label)
    } catch (e) {
      if (!ctrl.signal.aborted) throw e
    } finally {
      // L'effet d'analyse live réarme `engine.onLines` lui-même quand `reviewing` retombe.
      if (isCurrent()) {
        reviewAbortRef.current = null
        setReviewProgress(null)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moves, startFen, reviewDepth])

  function currentPgn(): string | null {
    if (moves.length === 0) return null
    const c = new Chess(startFen)
    if (startFen !== START_FEN) {
      c.header('SetUp', '1')
      c.header('FEN', startFen)
    }
    for (const m of moves) c.move(m.san)
    return c.pgn()
  }

  // Lignes live de la position AFFICHÉE uniquement (jamais celles d'une autre position).
  const lines = (liveOn && evalsRef.current.get(viewFen)) || []
  // Eval affichée point de vue blanc.
  const topLine = lines[0] ?? null
  let evalCp: number | null = null
  let evalMate: number | null = null
  if (viewChess.isCheckmate()) {
    evalMate = 0
    evalCp = viewChess.turn() === 'w' ? -10000 : 10000
  } else if (viewChess.isGameOver()) {
    evalCp = 0 // pat, répétition, 50 coups, matériel insuffisant : nulle, pas de recherche
  } else if (topLine) {
    const sign = viewChess.turn() === 'w' ? 1 : -1
    if (topLine.scoreMate !== null) evalMate = sign * topLine.scoreMate
    evalCp = sign * (topLine.scoreCp ?? (topLine.scoreMate! > 0 ? 10000 : -10000))
  } else if (review && viewIndex >= 0) {
    evalCp = review.moves[viewIndex]?.evalAfterCp ?? null
    evalMate = review.moves[viewIndex]?.mateAfter ?? null
  } else if (liveOn && heldEvalRef.current) {
    // Position en cours de calcul : la barre reste sur la dernière éval affichée (déjà côté blanc).
    evalCp = heldEvalRef.current.cp
    evalMate = heldEvalRef.current.mate
  }
  const liveEval = topLine && evalCp !== null ? { cp: evalCp, mate: evalMate } : null
  useLayoutEffect(() => {
    if (liveEval) heldEvalRef.current = liveEval
  })

  const reviewedCurrent = review && viewIndex >= 0 ? review.moves[viewIndex] : null

  const BAD: MoveClass[] = ['inaccuracy', 'mistake', 'miss', 'missedWin', 'blunder']
  const arrows: BoardArrow[] = []
  if (retry) {
    // Pas de flèche : ne pas révéler la solution.
  } else if (reviewedCurrent && BAD.includes(reviewedCurrent.class)) {
    // Coup fautif : coup joué en rouge, meilleur coup en vert.
    arrows.push({
      startSquare: reviewedCurrent.uci.slice(0, 2),
      endSquare: reviewedCurrent.uci.slice(2, 4),
      color: '#ca3431',
    })
    arrows.push({
      startSquare: reviewedCurrent.bestMoveUci.slice(0, 2),
      endSquare: reviewedCurrent.bestMoveUci.slice(2, 4),
      color: '#81b64c',
    })
  } else if (engineOn && topLine?.pv[0] && topLine.pv[0].length >= 4) {
    // Bleu chess.com pour l'analyse libre ; le vert reste réservé au bilan.
    arrows.push({ startSquare: topLine.pv[0].slice(0, 2), endSquare: topLine.pv[0].slice(2, 4), color: '#69c3f2' })
  }
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

  // Alimente « Apprendre → Mes erreurs » avec les fautes du joueur.
  async function recordMistakes(result: GameReview, color: 'w' | 'b' | null, label: string | null) {
    const BAD_FOR_LEARN = ['mistake', 'miss', 'missedWin', 'blunder']
    const replay = new Chess(result.startFen)
    for (let i = 0; i < result.moves.length; i++) {
      const m = result.moves[i]
      const fenBefore = replay.fen()
      const moverColor = replay.turn()
      replay.move(m.san)
      if (color && moverColor !== color) continue
      if (!BAD_FOR_LEARN.includes(m.class)) continue
      const existing = await db.mistakes.where('fenBefore').equals(fenBefore).count()
      if (existing > 0) continue
      await db.mistakes.add({
        date: Date.now(),
        gameLabel: label ?? 'Partie analysée',
        fenBefore,
        playedSan: m.san,
        bestUci: m.bestMoveUci,
        cls: m.class,
        attempts: 0,
        solved: 0,
      })
    }
  }

  // --- Retry : rejouer la position avant une faute et trouver mieux ---
  function fenBeforeMove(idx: number): string {
    const c = new Chess(startFen)
    for (let i = 0; i < idx; i++) c.move(moves[i].san)
    return c.fen()
  }

  // Une vérification abandonnée ne doit pas retarder la suivante : `stop()` passe par le mutex et
  // attendrait la fin de sa recherche. Le moteur de vérification est jeté, le prochain essai en
  // recrée un.
  function abandonCheck() {
    attemptSeq.current++
    if (!checkInFlight.current) return
    checkInFlight.current = false
    checkEngineRef.current?.quit()
    checkEngineRef.current = null
  }

  function startRetry(idx: number) {
    abandonCheck()
    setRetry({ moveIndex: idx, baseFen: fenBeforeMove(idx), status: 'trying' })
  }

  // Sortie du mode Réessayer : une vérification encore en vol ne rendra plus de verdict.
  function clearRetry() {
    abandonCheck()
    setRetry(null)
  }

  const retrySolution = useMemo(() => {
    if (!retry || !review) return null
    const best = review.moves[retry.moveIndex]?.bestMoveUci // bilan périmé : pas de solution
    if (!best) return null
    try {
      return new Chess(retry.baseFen).move({ from: best.slice(0, 2), to: best.slice(2, 4), promotion: best[4] }).san
    } catch {
      return best
    }
  }, [retry, review])

  function handleRetryMove(from: string, to: string, promotion?: string): boolean {
    if (!aliveRef.current || !retry || !review || retry.status === 'checking' || retry.status === 'found') return false
    const c = new Chess(retry.baseFen)
    let move
    try {
      move = c.move({ from, to, promotion: promotion ?? 'q' })
    } catch {
      return false
    }
    const m = review.moves[retry.moveIndex]
    if (!m) return false
    if (move.lan === m.bestMoveUci || c.isCheckmate()) {
      if (playSounds) sounds.success()
      setRetry({ ...retry, status: 'found', lastTried: move.san })
      return true
    }
    // Un autre coup peut aussi être bon : on demande au moteur.
    const id = ++attemptSeq.current
    setRetry({ ...retry, attemptId: id, status: 'checking', lastTried: move.san })
    void (async () => {
      const engine = (checkEngineRef.current ??= new Engine())
      checkInFlight.current = true
      const res = await engine.search({ fen: c.fen(), depth: REVIEW_DEPTHS[reviewDepth], multipv: 1 })
      if (!aliveRef.current || attemptSeq.current !== id) return
      checkInFlight.current = false
      // Sans ligne, la position après le coup est finie (pat, nulle) : éval nulle.
      const line = res.lines[0]
      const cpAfterUser = line
        ? -(line.scoreMate !== null ? (line.scoreMate > 0 ? 10000 : -10000) : (line.scoreCp ?? 0))
        : 0
      const drop = m.winPctBefore - winPct(cpAfterUser)
      const ok = drop < 5
      if (playSounds) (ok ? sounds.success : sounds.fail)()
      setRetry((r) => (r && r.attemptId === id && r.status === 'checking' ? { ...r, status: ok ? 'found' : 'failed' } : r))
    })()
    return true
  }

  const lastMove = viewIndex >= 0 ? { from: moves[viewIndex].from, to: moves[viewIndex].to } : null

  // --- Écran résumé du bilan (style chess.com, plein écran par-dessus la nav) ---
  if (reviewStage === 'summary' && review) {
    return (
      <div className="pt-safe pb-safe fixed inset-0 z-40 bg-surface">
        <div className="mx-auto h-full max-w-lg">
        <ReviewSummary
          review={review}
          whiteName={names.w}
          blackName={names.b}
          playerColor={reviewColor}
          onStart={() => {
            setReviewStage('guided')
            setViewIndex((v) => (v >= 0 ? v : 0))
          }}
          onClose={() => setReviewStage(null)}
          onSelectMove={setViewIndex}
        />
        </div>
      </div>
    )
  }

  // --- Bilan guidé coup par coup (style chess.com, plein écran par-dessus la nav) ---
  if (reviewStage === 'guided' && review && viewIndex >= 0 && review.moves[viewIndex]) {
    const m = review.moves[viewIndex]
    const moverColor = colorAtIndex(viewIndex)
    const comment = coach?.comments.find((c) => c.moveIndex === viewIndex) ?? null
    const guidedArrows: BoardArrow[] = []
    if (!retry && showBest && m.uci !== m.bestMoveUci) {
      guidedArrows.push({
        startSquare: m.bestMoveUci.slice(0, 2),
        endSquare: m.bestMoveUci.slice(2, 4),
        color: '#81b64c',
      })
    }
    const tint = `${CLASS_META[m.class].color}59` // ~35 % d'opacité
    const evalBadge =
      m.mateAfter !== null
        ? m.mateAfter === 0
          ? '#'
          : `M${Math.abs(m.mateAfter)}`
        : m.evalAfterCp !== null
          ? ((m.evalAfterCp > 0 ? '+' : '') + (m.evalAfterCp / 100).toFixed(2)).replace('.', ',')
          : ''
    const canRetry = BAD.includes(m.class)
    const mood = comment?.severity === 'praise' ? 'happy' : comment?.severity === 'alarm' ? 'worried' : 'thinking'

    return (
      <div className="pt-safe pb-safe fixed inset-0 z-40 bg-surface">
      <div className="mx-auto flex h-full max-w-2xl flex-col">
        <header className="flex items-center px-3 py-1">
          <button
            onClick={() => { clearRetry(); setReviewStage('summary') }}
            className="cursor-pointer p-1.5 text-2xl text-neutral-400 hover:text-white"
          >
            ←
          </button>
          <h1 className="flex-1 text-center text-xl font-black">Bilan de la partie</h1>
          <span className="w-10" />
        </header>

        <div className="px-3">
          <HEvalBar cp={m.evalAfterCp} mate={m.mateAfter} />
        </div>

        {/* Conteneur de taille : l'échiquier se borne à la hauteur de cette zone (cqh). */}
        <div className="min-h-0 flex-1 overflow-y-auto [container-type:size]">
        <div className="px-3 py-2">
          {retry ? (
            <CoachBubble
              mood={retry.status === 'found' ? 'happy' : 'thinking'}
              headline="À toi de jouer"
              fixed
              actions={
                <>
                  {(retry.status === 'trying' || retry.status === 'failed') && (
                    <button
                      onClick={() => setRetry({ ...retry, solutionShown: true })}
                      className="cursor-pointer rounded bg-neutral-200 px-2 py-1 text-xs font-bold hover:bg-neutral-300"
                    >
                      Solution
                    </button>
                  )}
                  <button
                    onClick={() => clearRetry()}
                    className="cursor-pointer rounded bg-neutral-200 px-2 py-1 text-xs font-bold hover:bg-neutral-300"
                  >
                    {retry.status === 'found' ? 'Continuer' : 'Quitter'}
                  </button>
                </>
              }
            >
              {/* Une seule chaîne : CoachBubble agrandit alors les figurines (FigText). */}
              {(retry.status === 'trying' ? `Trouve mieux que ${figurine(m.san, moverColor)}. Joue ton coup sur l'échiquier.`
                : retry.status === 'checking' ? `Je vérifie ${figurine(retry.lastTried ?? '', moverColor)}…`
                : retry.status === 'found' ? `Trouvé ! ${figurine(retry.lastTried ?? '', moverColor)} ${retry.lastTried === retrySolution ? 'était exactement le coup.' : 'fait aussi le travail.'}`
                : `${figurine(retry.lastTried ?? '', moverColor)} ne suffit pas. Réessaie !`)
                + (retry.solutionShown ? ` La solution était ${figurine(retrySolution ?? '', moverColor)}.` : '')}
            </CoachBubble>
          ) : (
            <CoachBubble cls={m.class} headline={comment?.headline ?? figurine(m.san, moverColor)} evalBadge={evalBadge} mood={comment?.mood ?? mood} fixed>
              {comment?.body ?? ''}
            </CoachBubble>
          )}
        </div>

        <div className="flex justify-center">
          {/* Bulle (16 + 116, 96 sous 700 px) + bande des coups (~43) : tout tient sans défiler.
              Plancher de 200 px : en paysage, on défile plutôt que de perdre l'échiquier. */}
          <div className="boardbox max-w-[max(200px,calc(100cqh_-_178px))] md:w-[min(56vh,520px)] [@media(max-height:700px)]:max-w-[max(200px,calc(100cqh_-_158px))]">
            <Board
              fen={retry ? retry.baseFen : viewFen}
              orientation={orientation}
              interactive={!!retry && (retry.status === 'trying' || retry.status === 'failed')}
              movableColor={retry ? colorAtIndex(retry.moveIndex) : undefined}
              onMove={retry ? handleRetryMove : undefined}
              lastMove={null}
              arrows={guidedArrows}
              badge={retry ? null : { square: m.uci.slice(2, 4), cls: m.class }}
              markSquares={retry ? undefined : { [m.uci.slice(0, 2)]: tint, [m.uci.slice(2, 4)]: tint }}
            />
          </div>
        </div>

        {showLines && !retry && (
          <div className="space-y-0.5 px-3 pt-2">
            {lines.slice(0, 2).map((l) => (
              <EngineLineRow key={l.multipv} line={l} fen={viewFen} />
            ))}
          </div>
        )}

        <MoveStrip
          sans={moves.map((mv) => mv.san)}
          classes={review.moves.map((mv) => mv.class)}
          currentIndex={viewIndex}
          onSelect={(i) => { clearRetry(); setViewIndex(i) }}
          startTurn={startTurn}
        />
        </div>

        <div className="flex items-center gap-2 border-t border-black/40 p-3">
          <BarAction label="Afficher" icon="♞" active={showLines} onClick={() => setShowLines(!showLines)} />
          <BarAction label="Meilleur" icon="🔍" active={showBest} onClick={() => setShowBest(!showBest)} />
          <BarAction label="Réessayer" icon="↺" disabled={!canRetry} onClick={() => startRetry(viewIndex)} />
          <Cta
            className="flex-1"
            onClick={() => {
              clearRetry()
              setShowBest(false)
              if (viewIndex >= moves.length - 1) setReviewStage('summary')
              else setViewIndex(viewIndex + 1)
            }}
          >
            {viewIndex >= moves.length - 1 ? 'Résumé' : 'Suivant'}
          </Cta>
        </div>
      </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col items-center justify-start gap-1.5 p-2 md:flex-row md:items-stretch md:justify-center md:gap-4 md:p-4">
      {/* Barre d'éval horizontale + lignes compactes : mobile uniquement */}
      <div className="w-full md:hidden">
        <HEvalBar cp={evalCp} mate={evalMate} />
        {/* Hauteur fixe (2 lignes) : le board ne doit jamais sauter quand les lignes arrivent. */}
        {engineOn && (
          <div className="mt-1.5 h-[38px] space-y-0.5 overflow-hidden">
            {[0, 1].map((i) =>
              lines[i] ? (
                <EngineLineRow key={i} line={lines[i]} fen={viewFen} compact />
              ) : (
                <p key={i} className="h-[17px] truncate text-[13px] leading-[17px] text-neutral-400">
                  {i === 0 ? (viewChess.isGameOver() ? 'Partie terminée.' : 'Calcul…') : ' '}
                </p>
              ),
            )}
          </div>
        )}
      </div>

      <div className="flex w-full flex-none justify-center gap-2 md:w-auto md:items-center md:gap-0">
        <div className="hidden items-stretch md:flex md:items-center">
          <div className="self-stretch md:h-[min(76vh,640px)] md:self-auto">
            <EvalBar cp={evalCp} mate={evalMate} orientation={orientation} />
          </div>
        </div>

        {/* `boardbox` sur la colonne : le bandeau d'ouverture se tronque à la largeur du board au lieu de l'élargir */}
        <div className="boardbox flex flex-col justify-center gap-2 md:ml-4 md:w-[min(76vh,640px)]">
          {returnTo && (
            <button
              onClick={() => navigate(returnTo, { state: { restore: true } })}
              className="flex w-fit cursor-pointer items-center gap-1 rounded px-1 py-1 text-sm font-semibold text-neutral-300 hover:text-white"
            >
              ← Retour à l'exercice
            </button>
          )}
          <div className="w-full">
            <Board
              fen={retry ? retry.baseFen : viewFen}
              orientation={orientation}
              interactive={!retry || retry.status === 'trying' || retry.status === 'failed'}
              movableColor={retry ? colorAtIndex(retry.moveIndex) : undefined}
              onMove={retry ? handleRetryMove : handleMove}
              lastMove={retry ? null : lastMove}
              arrows={arrows}
            />
          </div>
          {/* Bandeau ouverture, façon chess.com (mobile), 1 ligne fixe */}
          <div className="truncate rounded bg-surface-2 px-3 py-1.5 text-center text-sm font-semibold text-neutral-200 md:hidden">
            {opening ? openingFr(opening.name) : moves.length === 0 ? 'Position de départ' : 'Hors théorie'}
          </div>
          {review && !retry && (
            <EvalGraph review={review} currentIndex={viewIndex} onSelect={setViewIndex} />
          )}
          <div className="hidden items-center gap-2 text-sm text-neutral-400 md:flex">
          {opening && (
            <span>
              <span className="font-mono text-xs text-neutral-500">{opening.eco}</span> {openingFr(opening.name)}
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
        <div className="hidden items-center justify-between rounded bg-surface-2 px-3 py-2 md:flex">
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
          <div className="hidden space-y-1 rounded bg-surface-2 p-2 md:block">
            {lines.length === 0 && <p className="px-1 text-sm text-neutral-500">{viewChess.isGameOver() ? 'Partie terminée.' : 'Calcul…'}</p>}
            {lines.map((l) => (
              <div key={l.multipv} className="px-1">
                <EngineLineRow line={l} fen={viewFen} />
              </div>
            ))}
          </div>
        )}

        <div className="md:hidden">
          <MoveStrip
            sans={moves.map((m) => m.san)}
            classes={review ? review.moves.map((m) => m.class) : moves.map(() => null)}
            currentIndex={viewIndex}
            onSelect={setViewIndex}
            startTurn={startTurn}
          />
        </div>

        <div className="hidden md:block md:h-auto md:min-h-0 md:flex-1">
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
                <div className="text-xs font-semibold text-neutral-300">~{review.gameRatingWhite}</div>
              </div>
              <div>
                <div className="text-xl font-bold text-white">{review.accuracyBlack}</div>
                <div className="text-xs text-neutral-400">Précision Noirs</div>
                <div className="text-xs font-semibold text-neutral-300">~{review.gameRatingBlack}</div>
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

        {coach && !retry && (
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
              <span className="shrink-0">
                <CoachAvatar size={32} mood={viewIndex === -1 ? 'happy' : coachCurrent?.mood ?? 'thinking'} />
              </span>
              <p className="min-h-10 text-sm leading-snug text-neutral-200">
                {viewIndex === -1
                  ? coach.summary
                  : coachCurrent
                    ? `${coachCurrent.headline}. ${coachCurrent.body}`
                    : 'Coup adverse. Avance pour retrouver mes commentaires.'}
              </p>
            </div>
            <div className="mt-2 flex gap-2">
              {keyMoments.length > 0 && (
                <>
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
                </>
              )}
              {coachCurrent && (coachCurrent.severity === 'warn' || coachCurrent.severity === 'alarm') && (
                <button
                  onClick={() => { setReviewStage('guided'); startRetry(viewIndex) }}
                  className="flex-1 cursor-pointer rounded bg-accent/20 py-1 text-xs font-bold text-accent hover:bg-accent/30"
                >
                  🎯 Réessayer
                </button>
              )}
            </div>
          </div>
        )}

        <div className="hidden flex-wrap gap-2 md:flex">
          <NavBtn label="⏮" onClick={() => setViewIndex(-1)} />
          <NavBtn label="◀" onClick={() => setViewIndex((v) => Math.max(-1, v - 1))} />
          <NavBtn label="▶" onClick={() => setViewIndex((v) => Math.min(moves.length - 1, v + 1))} />
          <NavBtn label="⏭" onClick={() => setViewIndex(moves.length - 1)} />
          <NavBtn label="⇅" title="Retourner l'échiquier" onClick={() => setOrientation((o) => (o === 'w' ? 'b' : 'w'))} />
        </div>

        <div className="hidden gap-2 md:flex">
          <button
            onClick={() => (review ? setReviewStage('summary') : void runReview(undefined, { color: reviewColor, label: gameMeta }))}
            disabled={reviewProgress !== null || moves.length === 0}
            className="flex-1 cursor-pointer rounded bg-accent py-2 text-sm font-bold text-white hover:bg-accent-hover disabled:cursor-default disabled:opacity-40"
          >
            {reviewProgress !== null ? `Analyse… ${reviewProgress}%` : '🔍 Bilan de partie'}
          </button>
          <button onClick={() => navigate('/import')} className="cursor-pointer rounded bg-surface-3 px-3 py-2 text-sm font-semibold hover:bg-surface-3/70">
            ♟ chess.com
          </button>
          <button onClick={() => { setShowImport(true); setImportText(''); setImportError('') }} className="cursor-pointer rounded bg-surface-3 px-3 py-2 text-sm font-semibold hover:bg-surface-3/70">
            PGN
          </button>
          <button
            onClick={() => { const pgn = currentPgn(); if (pgn) void navigator.clipboard.writeText(pgn) }}
            disabled={moves.length === 0}
            className="cursor-pointer rounded bg-surface-3 px-3 py-2 text-sm font-semibold hover:bg-surface-3/70 disabled:cursor-default disabled:opacity-40"
          >
            Copier PGN
          </button>
        </div>

        {book.length > 0 && (
          <div className={`${showExplorer ? '' : 'hidden md:block'} rounded bg-surface-2 p-2`}>
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

      {notice && (
        <div role="alert" className="pt-safe pointer-events-none fixed inset-x-0 top-0 z-50 flex justify-center px-4">
          <button
            onClick={() => setNotice(null)}
            className="pointer-events-auto cursor-pointer rounded-lg bg-surface-3 px-4 py-2 text-sm font-semibold text-neutral-100 shadow-lg"
          >
            {notice}
          </button>
        </div>
      )}

      {/* Barre d'actions mobile, façon chess.com */}
      <div className="sticky bottom-0 z-20 mt-auto flex w-full items-center justify-around border-t border-black/40 bg-surface py-1 md:hidden">
        <BarAction label="Options" icon="⚙" onClick={() => setShowOptions(true)} />
        <BarAction
          label="Bilan"
          icon="★"
          disabled={reviewProgress !== null || moves.length === 0}
          onClick={() => (review ? setReviewStage('summary') : void runReview(undefined, { color: reviewColor, label: gameMeta }))}
        />
        <BarAction label="Explorer" icon="🧭" active={showExplorer} onClick={() => setShowExplorer(!showExplorer)} />
        <BarAction label="Précédent" icon="‹" onClick={() => setViewIndex((v) => Math.max(-1, v - 1))} />
        <BarAction label="Suivant" icon="›" onClick={() => setViewIndex((v) => Math.min(moves.length - 1, v + 1))} />
      </div>

      {showOptions && (
        <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/60 md:items-center" onClick={() => setShowOptions(false)}>
          <div className="w-full max-w-md rounded-t-2xl bg-surface-2 p-4 md:rounded-2xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-3 text-center text-lg font-bold">Options</h2>
            <div className="space-y-2">
              <SheetBtn label="⇅ Retourner l'échiquier" onClick={() => { setOrientation((o) => (o === 'w' ? 'b' : 'w')); setShowOptions(false) }} />
              <SheetBtn
                label={`Moteur : ${engineOn ? 'activé' : 'désactivé'}`}
                onClick={() => setEngineOn(!engineOn)}
              />
              <SheetBtn
                label="Copier le PGN"
                disabled={moves.length === 0}
                onClick={() => { const pgn = currentPgn(); if (pgn) void navigator.clipboard.writeText(pgn); setShowOptions(false) }}
              />
              <SheetBtn label="Importer PGN ou FEN" onClick={() => { setShowOptions(false); setShowImport(true); setImportText(''); setImportError('') }} />
              <SheetBtn label="♟ Importer depuis chess.com" onClick={() => navigate('/import')} />
              <SheetBtn label="Fermer" onClick={() => setShowOptions(false)} />
            </div>
          </div>
        </div>
      )}

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
                else setImportError('Format non reconnu : ni PGN avec des coups, ni FEN valide.')
              }}
              disabled={!importText.trim()}
              className="w-full cursor-pointer rounded bg-accent py-2 font-bold text-white hover:bg-accent-hover disabled:cursor-default disabled:opacity-40"
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

function SheetBtn({ label, onClick, disabled }: { label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="w-full cursor-pointer rounded-lg bg-surface-3 py-2.5 font-semibold text-neutral-200 hover:bg-surface-3/70 disabled:cursor-default disabled:opacity-40"
    >
      {label}
    </button>
  )
}

// Action de la barre du bilan guidé : icône + libellé, style chess.com.
function BarAction({ label, icon, active, disabled, onClick }: {
  label: string
  icon: string
  active?: boolean
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`flex cursor-pointer flex-col items-center gap-0.5 rounded px-2 py-1 text-xs font-semibold disabled:cursor-default disabled:opacity-35 ${
        active ? 'text-accent' : 'text-neutral-300 hover:text-white'
      }`}
    >
      <span className="text-xl leading-none">{icon}</span>
      {label}
    </button>
  )
}
