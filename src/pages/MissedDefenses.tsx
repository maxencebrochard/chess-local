// « Mes défenses ratées » : les fautes des bilans jouées pendant que l'adversaire attaquait le roi
// du joueur (calculées sur l'échiquier depuis la table `mistakes`, voir `missedDefense`), rejouées
// contre Stockfish à pleine force, exactement comme « Mes attaques manquées » : retrouver le coup de
// défense du bilan (ou un coup qui tient aussi), puis continuer la partie librement.
import { useEffect, useState } from 'react'
import { REVIEW_BACK } from '../lib/navigation'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { PageHeader } from '../components/PageHeader'
import { EmptyState } from '../components/EmptyState'
import { ATTACK_RED } from '../components/AttackLegend'
import { PositionGame } from '../components/PositionGame'
import { recordReplaced } from '../lib/attempts'
import { db, type Mistake } from '../lib/db'
import {
  countsText, defenseSummary, DEFENSE_KING_META, DEFENSE_PRINCIPLE, diagnoseMissedDefenses, recordMissedDefense,
  solvedMissedDefenses, type DefenseDiagnostic, type MissedDefenseItem,
} from '../lib/kingAttack'
import { inProgressKey } from '../lib/positionGame'

const solvedKey = (m: Mistake) => `${m.id}|${m.fenBefore}`
const playKey = (id: number | undefined) => `defense-ratee:${id}`

function useSolved(): Set<string> {
  const [solved, setSolved] = useState<Set<string>>(new Set())
  useEffect(() => {
    void solvedMissedDefenses().then(setSolved)
  }, [])
  return solved
}

export default function MissedDefenses() {
  const { id } = useParams()
  return id ? <MissedDefensePlay key={id} id={Number(id)} /> : <MissedDefenseList />
}

function MissedDefenseList() {
  const navigate = useNavigate()
  const solved = useSolved()
  const [diag, setDiag] = useState<DefenseDiagnostic | null>(null)
  const [inProgress] = useState(inProgressKey)

  useEffect(() => {
    void db.mistakes.toArray().then((rows) => setDiag(diagnoseMissedDefenses(rows)))
  }, [])

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <PageHeader title="🧱 Mes défenses ratées" back={{ label: REVIEW_BACK.label, onClick: () => navigate(REVIEW_BACK.to) }} />
      {diag === null && <p role="status" className="text-muted">Chargement des parties à rejouer…</p>}

      {diag && (
        <>
          <p data-testid="defense-summary" className="mb-1 text-[15px] font-semibold text-neutral-100">{defenseSummary(diag)}</p>
          <p className="mb-3 text-sm text-muted">
            Comptées : les erreurs et gaffes relevées par un bilan qui connaissait ta couleur, jouées alors que l'adversaire
            visait ton roi avec au moins deux pièces. Une même faute peut aussi figurer dans « Mes attaques manquées ».
          </p>
          <p className="mb-4 rounded-lg bg-surface-2 px-3 py-2 text-sm text-neutral-200">
            <span className="mr-1" aria-hidden="true">🛡</span>
            Ses attaquants dépassent tes défenseurs : avant chaque coup, cherche sa menace, puis neutralise la pièce la plus
            dangereuse ou rapproche un défenseur.
          </p>

          {diag.items.length === 0 ? (
            <EmptyState testId="defense-empty" title="Rien à rejouer pour l'instant." to="/analyse" action="Analyser une partie">
              Fais le bilan d'une partie contre un bot ou importée de chess.com : chaque erreur
              jouée pendant que l'adversaire attaquait ton roi apparaîtra ici, avec le coup de défense de Stockfish à retrouver.
            </EmptyState>
          ) : (
            <div className="flex flex-col gap-2">
              {diag.items.map((it) => (
                <DefenseRow
                  key={it.mistake.id}
                  item={it}
                  done={solved.has(solvedKey(it.mistake))}
                  going={inProgress === `${playKey(it.mistake.id)}|${it.mistake.fenBefore}`}
                  onOpen={() => navigate(`/defenses-ratees/${it.mistake.id}`)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function DefenseRow({ item, done, going, onOpen }: { item: MissedDefenseItem; done: boolean; going: boolean; onOpen: () => void }) {
  const meta = DEFENSE_KING_META[item.where]
  return (
    <button
      data-testid="missed-defense-item"
      data-id={item.mistake.id}
      data-where={item.where}
      onClick={onOpen}
      className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl bg-surface-2 px-3 py-2.5 text-left hover:bg-surface-3"
    >
      <span className="text-2xl" aria-hidden="true">{meta.emoji}</span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-bold">{meta.label}</span>
        <span className="block truncate text-xs text-neutral-400">
          {item.mistake.gameLabel} · tu as joué <span className="font-semibold text-red-300">{item.playedFig}</span>
        </span>
        <span className="block truncate text-sm text-muted">
          Autour de ton roi : <span style={{ color: ATTACK_RED }}>⚔ {item.attackers}</span> · <span className="text-accent">🛡 {item.defenders}</span>
        </span>
      </span>
      {going ? (
        <span className="shrink-0 rounded-full bg-amber-900/40 px-2 py-0.5 text-xs font-semibold text-amber-200">En cours</span>
      ) : done ? (
        <span className="shrink-0 text-sm font-bold text-accent">✓ Retrouvée</span>
      ) : (
        <span aria-hidden="true" className="shrink-0 text-xl text-neutral-500">›</span>
      )}
    </button>
  )
}

function MissedDefensePlay({ id }: { id: number }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [item, setItem] = useState<MissedDefenseItem | null | undefined>(undefined)
  const [next, setNext] = useState<number | null>(null)

  // La défense, prise dans la même liste que la page précédente (même filtre), et pour « Défense
  // suivante » la plus récente des autres défenses pas encore retrouvées.
  useEffect(() => {
    void (async () => {
      const [rows, solved] = await Promise.all([db.mistakes.toArray(), solvedMissedDefenses()])
      const items = diagnoseMissedDefenses(rows).items
      setItem(items.find((it) => it.mistake.id === id) ?? null)
      const others = items.filter((it) => it.mistake.id !== id)
      const fresh = others.filter((it) => !solved.has(solvedKey(it.mistake)))
      setNext((fresh[0] ?? others[0])?.mistake.id ?? null)
    })()
  }, [id])

  if (item === undefined) return null
  if (!item) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-3 p-6 text-center">
        <p data-testid="defense-missing" className="text-neutral-300">Cette défense n'est pas dans ta liste.</p>
        <p className="text-sm text-neutral-400">
          La faute a été supprimée, est incomplète, ou son bilan ne connaissait pas ta couleur.
        </p>
        <Link to="/defenses-ratees" replace className="rounded-lg bg-surface-3 px-4 py-2 font-semibold hover:bg-surface-3/70">
          Retour à la liste
        </Link>
      </div>
    )
  }
  const row = item.mistake
  const restore = !!(location.state as { restore?: boolean } | null)?.restore
  const meta = DEFENSE_KING_META[item.where]
  const lesson = `${meta.lesson} Ici, il avait ${countsText(item.attackers, item.defenders)} autour de ton roi. Tu avais joué ${item.playedFig}.`

  return (
    <PositionGame
      gameKey={playKey(row.id)}
      startFen={row.fenBefore}
      title={meta.label}
      objective={null}
      objectiveLabel="Objectif : trouve la défense"
      goalHint="Au bilan, Stockfish défendait ton roi autrement : joue son coup."
      lesson={lesson}
      restoreFinished={restore}
      returnTo={`/defenses-ratees/${row.id}`}
      returnLabel="Retour à la défense"
      showAttackers
      attackersPrinciple={DEFENSE_PRINCIPLE}
      keyMove={{
        uci: row.bestUci,
        san: item.bestSan,
        onJudged: (found) => void recordMissedDefense(id, row.fenBefore, found),
        cheer: 'tiens bon !',
        keepGoing: 'Tiens la position jusqu\'au bout.',
      }}
      otherLabel="Défense suivante"
      onExit={() => navigate('/defenses-ratees', { replace: true })}
      onOther={next !== null ? () => navigate(`/defenses-ratees/${next}`, { replace: true }) : undefined}
      onReplace={recordReplaced}
    />
  )
}
