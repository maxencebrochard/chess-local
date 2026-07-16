// Écran de résumé du bilan, réplique de l'interface chess.com :
// bulle coach, graphe, joueurs + précision (carte blanche / carte sombre),
// tallies à pastilles, classement de la partie, verdicts par phase, CTA.
import { CoachBubble } from './CoachBubble'
import { ClassIcon } from './ClassIcon'
import { Cta } from './Cta'
import { EvalGraph } from './EvalGraph'
import { coachQuip, phaseReport, type PhaseVerdict } from '../lib/coach'
import { CLASS_META, type GameReview, type MoveClass } from '../lib/review'

const TALLY_ORDER: MoveClass[] = [
  'brilliant', 'great', 'best', 'excellent', 'good', 'book',
  'inaccuracy', 'mistake', 'miss', 'missedWin', 'blunder',
]

interface ReviewSummaryProps {
  review: GameReview
  whiteName: string
  blackName: string
  playerColor: 'w' | 'b' | null
  onStart: () => void
  onClose: () => void
  onSelectMove: (index: number) => void
}

export function ReviewSummary({ review, whiteName, blackName, playerColor, onStart, onClose, onSelectMove }: ReviewSummaryProps) {
  const phases = phaseReport(review)
  const mood = (playerColor === 'b' ? review.accuracyBlack : review.accuracyWhite) >= 75 ? 'happy' : 'worried'

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center px-3 py-2">
        <button onClick={onClose} className="cursor-pointer p-2 text-2xl text-neutral-400 hover:text-white">
          ✕
        </button>
        <h1 className="flex-1 text-center text-xl font-black">Bilan de la partie</h1>
        <span className="w-10" />
      </header>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 pb-4">
        <CoachBubble mood={mood}>{coachQuip(review, playerColor)}</CoachBubble>

        <EvalGraph review={review} currentIndex={-1} onSelect={(i) => { onSelectMove(i); onStart() }} />

        {/* Joueurs + précision */}
        <div className="grid grid-cols-[1fr_auto_auto] items-center gap-x-3 gap-y-2">
          <span />
          <span className="w-24 text-center text-sm font-semibold text-neutral-300">{whiteName}</span>
          <span className="w-24 text-center text-sm font-semibold text-neutral-300">{blackName}</span>
          <span className="text-[15px] font-semibold text-neutral-200">Précision</span>
          <StatCard value={review.accuracyWhite.toFixed(1)} white />
          <StatCard value={review.accuracyBlack.toFixed(1)} />
        </div>

        {/* Tallies */}
        <div className="space-y-0.5 border-t border-white/10 pt-3">
          {TALLY_ORDER.map((cls) => (
            <div key={cls} className="grid grid-cols-[1fr_3rem_2rem_3rem] items-center gap-2 py-1">
              <span className="text-[15px] font-semibold text-neutral-200">{CLASS_META[cls].label}</span>
              <span className="text-center text-lg font-black" style={{ color: CLASS_META[cls].color }}>
                {review.counts.w[cls]}
              </span>
              <span className="flex justify-center">
                <ClassIcon cls={cls} size={26} />
              </span>
              <span className="text-center text-lg font-black" style={{ color: CLASS_META[cls].color }}>
                {review.counts.b[cls]}
              </span>
            </div>
          ))}
        </div>

        {/* Classement de la partie + phases */}
        <div className="grid grid-cols-[1fr_auto_auto] items-center gap-x-3 gap-y-3 border-t border-white/10 pt-3">
          <span className="text-[15px] leading-tight font-semibold text-neutral-200">
            Classement de<br />la partie
          </span>
          <StatCard value={String(review.gameRatingWhite)} white />
          <StatCard value={String(review.gameRatingBlack)} />
          <PhaseRow label="Ouverture" verdicts={phases.opening} />
          <PhaseRow label="Milieu de jeu" verdicts={phases.middlegame} />
          <PhaseRow label="Finale" verdicts={phases.endgame} />
        </div>
      </div>

      <div className="border-t border-black/40 p-3">
        <Cta className="w-full" onClick={onStart}>
          Démarrer le bilan
        </Cta>
      </div>
    </div>
  )
}

function StatCard({ value, white = false }: { value: string; white?: boolean }) {
  return (
    <span
      className={`w-24 rounded-lg py-2 text-center text-xl font-black ${
        white ? 'bg-neutral-100 text-neutral-900' : 'bg-surface-3 text-white'
      }`}
    >
      {value}
    </span>
  )
}

function PhaseRow({ label, verdicts }: { label: string; verdicts: { w: PhaseVerdict; b: PhaseVerdict } }) {
  return (
    <>
      <span className="text-[15px] font-semibold text-neutral-200">{label}</span>
      <span className="flex w-24 justify-center"><VerdictIcon v={verdicts.w} /></span>
      <span className="flex w-24 justify-center"><VerdictIcon v={verdicts.b} /></span>
    </>
  )
}

function VerdictIcon({ v }: { v: PhaseVerdict }) {
  if (v === 'none') return <span className="text-lg text-neutral-500">–</span>
  const map = {
    good: { bg: '#81b64c', symbol: '✓' },
    meh: { bg: '#f7c631', symbol: '?!' },
    bad: { bg: '#ffa459', symbol: '?' },
  } as const
  const { bg, symbol } = map[v]
  return (
    <span
      className="inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-black text-white"
      style={{ background: bg }}
    >
      {symbol}
    </span>
  )
}
