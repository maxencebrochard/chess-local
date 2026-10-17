// « Pourquoi ? » sur une faute : calque plein écran qui déroule, coup par coup, la réfutation du
// moteur (sa meilleure suite après le coup fautif), un commentaire par demi-coup tiré des faits
// calculés par lib/refutation.ts, le bilan de la ligne, puis le bon coup et sa justification.
// Ouvert depuis le bilan d'Analyse et depuis Mes erreurs (MistakeExercise). N'écrit rien en base.
import { useEffect, useMemo, useRef, useState } from 'react'
import { Chess } from 'chess.js'
import { Board, type BoardArrow } from './Board'
import { CoachBubble } from './CoachBubble'
import { Cta } from './Cta'
import { LineStrip } from './EngineContinuation'
import { Engine } from '../lib/engine'
import { uciMove } from '../lib/motifs'
import { buildRefutation, scoreForPlayer, type MoveFacts, type Refutation, type Score } from '../lib/refutation'
import { figurine } from '../lib/review'
import { REVIEW_DEPTHS, useSettings } from '../store/settings'

const NB = ' '
const STEP_MS = 1800 // lecture automatique : le temps de lire un commentaire court
const MIN_DEPTH = 12 // plancher : une ligne de 8 demi-coups à profondeur 10 se dégrade vite
const RED = '#e8524a'
const ORANGE = '#ffa459'
const BLUE = '#69c3f2'
const GREEN = '#81b64c'
const TINT = 'rgba(255, 196, 0, 0.42)' // cases visées par un motif (fourchette, clouage)

interface Props {
  fenBefore: string
  playedUci: string
  bestUci: string | null
  orientation: 'w' | 'b'
  onClose: () => void
}

type Kind = 'intro' | 'played' | 'line' | 'summary' | 'best'
interface View {
  kind: Kind
  fen: string
  headline: string
  text: string
  arrows: BoardArrow[]
  lastMove: { from: string; to: string } | null
  marks?: Record<string, string>
  material: number | null
  strip: number // index dans la bande de coups (coup fautif = 0), -1 = aucun
}

const arrow = (uci: string, color: string): BoardArrow => ({ startSquare: uci.slice(0, 2), endSquare: uci.slice(2, 4), color })
const moveOf = (uci: string) => ({ from: uci.slice(0, 2), to: uci.slice(2, 4) })

// Cases à teinter : cibles de la fourchette, pièces alignées du clouage ou de l'enfilade.
function marksOf(f: MoveFacts): Record<string, string> | undefined {
  const squares = [...(f.fork?.squares ?? []), ...(f.line ? [f.line.frontSquare, f.line.rearSquare] : [])]
  return squares.length ? Object.fromEntries(squares.map((s) => [s, TINT])) : undefined
}

function materialText(n: number): string {
  return n === 0 ? 'Matériel inchangé' : `Depuis la faute${NB}: ${n > 0 ? '+' : '-'}${Math.abs(n)}`
}

function views(r: Refutation, fenBefore: string, loading: boolean): View[] {
  const playedFig = figurine(r.played.san, r.player)
  const out: View[] = [{
    kind: 'intro', fen: fenBefore, headline: `Pourquoi pas ${playedFig}${NB}?`,
    text: loading ? `${r.intro} Je calcule la réponse du moteur…` : r.intro,
    arrows: [arrow(r.played.uci, RED)], lastMove: null, material: null, strip: -1,
  }, {
    kind: 'played', fen: r.played.fenAfter, headline: `Ton coup${NB}: ${playedFig}`, text: r.played.text,
    arrows: [arrow(r.played.uci, RED)], lastMove: moveOf(r.played.uci), marks: marksOf(r.played.facts),
    material: r.played.material, strip: 0,
  }]
  r.line.forEach((s, i) => out.push({
    kind: 'line', fen: s.fenAfter,
    headline: `${s.actor === 'opponent' ? 'Adversaire' : 'Toi'}${NB}: ${figurine(s.san, s.color)}`,
    text: s.text, arrows: [arrow(s.uci, s.actor === 'opponent' ? ORANGE : BLUE)], lastMove: moveOf(s.uci),
    marks: marksOf(s.facts), material: s.material, strip: i + 1,
  }))
  if (loading) return out
  const last = r.line[r.line.length - 1] ?? r.played
  out.push({
    kind: 'summary', fen: last.fenAfter, headline: 'Bilan de la suite', text: r.summary,
    arrows: [], lastMove: moveOf(last.uci), material: last.material, strip: r.line.length,
  })
  if (r.best) {
    out.push({
      kind: 'best', fen: r.best.fenAfter,
      headline: r.best.close ? 'Le coup du moteur' : `Le bon coup${NB}: ${figurine(r.best.san, r.player)}`,
      text: r.best.text, arrows: [arrow(r.best.uci, GREEN)], lastMove: moveOf(r.best.uci), marks: marksOf(r.best.facts),
      material: null, strip: -1,
    })
  }
  return out
}

export function RefutationPlayer({ fenBefore, playedUci, bestUci, orientation, onClose }: Props) {
  const { reviewDepth } = useSettings()
  const depth = Math.max(MIN_DEPTH, REVIEW_DEPTHS[reviewDepth])
  const engineRef = useRef<Engine | null>(null)
  const closeRef = useRef<HTMLButtonElement>(null)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const reduceMotion = useMemo(() => matchMedia('(prefers-reduced-motion: reduce)').matches, [])
  const [engineOut, setEngineOut] = useState<{ pv: string[]; evalPlayed: Score | null; evalBest: Score | null } | null>(null)
  const [idx, setIdx] = useState(0)
  const [playing, setPlaying] = useState(!reduceMotion)

  // Dernier onClose reçu : l'appelant peut en passer un nouveau à chaque rendu.
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  // Recherches : la ligne après le coup fautif, puis l'évaluation après le bon coup. Une position
  // déjà finie (mat, pat) n'est jamais envoyée au moteur. Au démontage, le worker est détruit
  // sur-le-champ : rouvrir le calque n'empile pas les recherches.
  useEffect(() => {
    let alive = true
    void (async () => {
      const engine = (engineRef.current ??= new Engine())
      const after = new Chess(fenBefore)
      const ok = uciMove(after, playedUci)
      let pv: string[] = []
      let evalPlayed: Score | null = null
      if (ok && !after.isGameOver()) {
        const res = await engine.search({ fen: after.fen(), depth, multipv: 1 })
        if (!alive) return
        pv = res.lines[0]?.pv ?? (res.bestMove && res.bestMove.length >= 4 ? [res.bestMove] : [])
        evalPlayed = scoreForPlayer(res.lines[0])
      }
      if (!alive) return
      setEngineOut({ pv, evalPlayed, evalBest: null })
      if (!bestUci || bestUci === playedUci) return
      const afterBest = new Chess(fenBefore)
      if (!uciMove(afterBest, bestUci) || afterBest.isGameOver()) return
      const res = await engine.search({ fen: afterBest.fen(), depth, multipv: 1 })
      if (!alive) return
      setEngineOut({ pv, evalPlayed, evalBest: scoreForPlayer(res.lines[0]) })
    })()
    return () => {
      alive = false
      engineRef.current?.quit({ immediate: true })
      engineRef.current = null
    }
  }, [fenBefore, playedUci, bestUci, depth])

  const ref = useMemo(
    () => buildRefutation({ fenBefore, playedUci, bestUci, pv: engineOut?.pv ?? [], evalAfterPlayed: engineOut?.evalPlayed ?? null, evalAfterBest: engineOut?.evalBest ?? null }),
    [fenBefore, playedUci, bestUci, engineOut],
  )
  const loading = engineOut === null
  const list = useMemo(() => (ref ? views(ref, fenBefore, loading) : []), [ref, fenBefore, loading])
  const n = list.length
  const i = Math.min(idx, Math.max(0, n - 1))
  const view = list[i]
  const summaryIdx = list.findIndex((v) => v.kind === 'summary')
  const bestIdx = list.findIndex((v) => v.kind === 'best')

  // Lecture automatique jusqu'au bilan de la suite (jamais sur la carte du bon coup).
  useEffect(() => {
    if (!playing || loading) return
    if (summaryIdx < 0 || i >= summaryIdx) {
      setPlaying(false)
      return
    }
    const t = setTimeout(() => setIdx(i + 1), STEP_MS)
    return () => clearTimeout(t)
  }, [playing, loading, i, summaryIdx])

  function go(to: number) {
    setPlaying(false)
    setIdx(Math.max(0, Math.min(n - 1, to)))
  }

  // Focus dans le calque, Échap pour fermer, flèches pour naviguer ; focus rendu à la fermeture.
  const goRef = useRef(go)
  const iRef = useRef(i)
  useEffect(() => {
    goRef.current = go
    iRef.current = i
  })
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    const dialog = dialogRef.current!
    dialog.showModal()
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      // Le dialogue rend le fond inerte ; boucler aux extrémités évite aussi de quitter
      // ses contrôles pour la barre d'adresse du navigateur avec Tab ou Maj+Tab.
      if (e.key === 'Tab') {
        const buttons = dialog.querySelectorAll<HTMLButtonElement>('button:not([disabled])')
        const first = buttons[0]
        const last = buttons[buttons.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last?.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first?.focus()
        }
      } else if (e.key === 'ArrowLeft') goRef.current(iRef.current - 1)
      else if (e.key === 'ArrowRight') goRef.current(iRef.current + 1)
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      dialog.close()
      opener?.focus?.()
    }
  }, [])

  const sans = ref ? [ref.played.san, ...ref.line.map((s) => s.san)] : []
  const mood = view?.kind === 'best' ? 'happy' : view?.kind === 'intro' ? 'thinking' : 'worried'
  const atEnd = i >= n - 1
  const togglePlay = () => {
    if (playing) setPlaying(false)
    else {
      if (summaryIdx >= 0 && i >= summaryIdx) setIdx(0)
      setPlaying(true)
    }
  }

  return (
    <dialog
      ref={dialogRef}
      onCancel={(e) => { e.preventDefault(); onCloseRef.current() }}
      aria-modal="true"
      aria-label="Pourquoi ce coup est une faute"
      data-refutation={view?.kind ?? 'none'}
      className="pt-safe pb-safe fixed inset-0 z-50 m-0 h-full max-h-none w-full max-w-none border-0 bg-surface text-inherit"
    >
      <div className="mx-auto flex h-full max-w-2xl flex-col">
        <header className="flex items-center px-3 py-1">
          <button
            ref={closeRef}
            onClick={onClose}
            className="w-24 cursor-pointer p-1.5 text-left text-sm font-semibold text-neutral-400 hover:text-white"
          >
            ← Retour
          </button>
          <h1 className="flex-1 truncate text-center text-lg font-black">Pourquoi{NB}?</h1>
          <span className="w-24" />
        </header>

        {/* Conteneur de taille : l'échiquier se borne à la hauteur de cette zone (cqh), comme le bilan guidé. */}
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain [container-type:size]">
          <div className="px-3 py-2" data-refutation-text>
            {view ? (
              <CoachBubble mood={mood} headline={view.headline} fixed>
                {view.text}
              </CoachBubble>
            ) : (
              <CoachBubble mood="thinking" headline={`Pourquoi${NB}?`} fixed>
                Ce coup ne peut pas être rejoué sur cette position.
              </CoachBubble>
            )}
          </div>
          <div className="flex justify-center">
            {/* Bulle (16 + 116, 96 sous 700 px) + rangée d'infos (~28) + bande (~44). */}
            <div className="boardbox max-w-[max(200px,calc(100cqh_-_210px))] md:w-[min(56vh,520px)] [@media(max-height:700px)]:max-w-[max(200px,calc(100cqh_-_190px))]">
              <Board
                fen={view?.fen ?? fenBefore}
                orientation={orientation}
                interactive={false}
                arrows={view?.arrows ?? []}
                lastMove={view?.lastMove ?? null}
                markSquares={view?.marks}
              />
            </div>
          </div>
          <div className="flex h-7 items-center justify-between px-3 text-sm font-semibold text-neutral-400">
            <span data-refutation-step>
              {view?.kind === 'line' ? `Demi-coup ${view.strip}/${ref!.line.length}` : view?.kind === 'best' ? 'Après le bon coup' : ' '}
            </span>
            {view && view.material !== null && (
              <span data-refutation-material className={view.material < 0 ? 'text-red-400' : view.material > 0 ? 'text-accent' : ''}>
                {materialText(view.material)}
              </span>
            )}
          </div>
          <LineStrip startFen={fenBefore} sans={sans} current={view?.strip ?? -1} onSelect={(s) => go(s + 1)} />
        </div>

        <div className="flex items-center gap-1 border-t border-black/40 p-2">
          <NavButton label="Début" glyph="⏮" onClick={() => go(0)} disabled={i === 0} />
          <NavButton label="Coup précédent" glyph="◀" onClick={() => go(i - 1)} disabled={i === 0} />
          <NavButton label={playing ? 'Pause' : 'Lecture'} glyph={playing ? '⏸' : '▶︎'} onClick={togglePlay} disabled={loading || summaryIdx < 0} />
          <NavButton label="Coup suivant" glyph="▶" onClick={() => go(i + 1)} disabled={atEnd || loading} />
          <div className="flex-1" />
          {bestIdx >= 0 && i !== bestIdx ? (
            <Cta className="px-3 py-2 text-sm whitespace-nowrap" onClick={() => go(bestIdx)}>
              {ref?.best?.close ? 'Coup du moteur' : 'Le bon coup'}
            </Cta>
          ) : (
            <Cta className="px-3 py-2 text-sm whitespace-nowrap" onClick={onClose}>
              Compris
            </Cta>
          )}
        </div>
      </div>
    </dialog>
  )
}

function NavButton({ label, glyph, onClick, disabled }: { label: string; glyph: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="flex h-10 w-11 cursor-pointer items-center justify-center rounded bg-surface-3 text-lg text-neutral-200 hover:bg-surface-3/80 disabled:cursor-default disabled:opacity-35"
    >
      {glyph}
    </button>
  )
}
