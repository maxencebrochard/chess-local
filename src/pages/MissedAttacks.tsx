// « Mes attaques manquées » : les fautes des bilans dont le meilleur coup attaquait le roi
// adverse (mat, sacrifice près du roi, pion contre le roque, pièce vers le roi), calculées sur
// l'échiquier depuis la table `mistakes`, puis rejouées contre Stockfish à pleine force :
// retrouver le coup du bilan, puis mener l'attaque.
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { ATTACK_RED } from '../components/AttackLegend'
import { PositionGame } from '../components/PositionGame'
import { recordReplaced } from '../lib/attempts'
import { db, type Mistake } from '../lib/db'
import {
  ATTACK_KIND_META, ATTACK_KINDS, ATTACK_PRINCIPLE, attackSummary, countsText, diagnoseMissedAttacks,
  recordMissedAttack, solvedMissedAttacks, type AttackDiagnostic, type MissedAttackItem,
} from '../lib/kingAttack'
import { inProgressKey } from '../lib/positionGame'

const solvedKey = (m: Mistake) => `${m.id}|${m.fenBefore}`

function useSolved(): Set<string> {
  const [solved, setSolved] = useState<Set<string>>(new Set())
  useEffect(() => {
    void solvedMissedAttacks().then(setSolved)
  }, [])
  return solved
}

export default function MissedAttacks() {
  const { id } = useParams()
  return id ? <MissedAttackPlay key={id} id={Number(id)} /> : <MissedAttackList />
}

function MissedAttackList() {
  const navigate = useNavigate()
  const solved = useSolved()
  const [diag, setDiag] = useState<AttackDiagnostic | null>(null)
  const [inProgress] = useState(inProgressKey)

  useEffect(() => {
    void db.mistakes.toArray().then((rows) => setDiag(diagnoseMissedAttacks(rows)))
  }, [])

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <div className="mb-1 flex items-center gap-1">
        <button
          onClick={() => navigate('/apprendre')}
          aria-label="Retour à Apprendre"
          className="-ml-2 flex h-10 w-10 cursor-pointer items-center justify-center rounded-full text-2xl text-neutral-400 hover:text-white"
        >
          ←
        </button>
        <h1 className="text-2xl font-black">🎯 Mes attaques manquées</h1>
      </div>

      {diag && (
        <>
          <p data-testid="attack-summary" className="mb-1 text-[15px] font-semibold text-neutral-100">{attackSummary(diag)}</p>
          <p className="mb-3 text-xs text-neutral-500">
            Comptées : les fautes relevées par un bilan qui connaissait ta couleur (partie contre un bot, partie chess.com).
            Refaire le bilan d'une partie de l'Archive complète les anciennes fautes.
          </p>
          <p className="mb-4 rounded-lg bg-surface-2 px-3 py-2 text-sm text-neutral-200">
            <span className="mr-1" aria-hidden="true">⚔</span>
            {ATTACK_PRINCIPLE} Compte-les avant de lancer l'assaut : l'exercice affiche ce compte autour de chaque roi.
          </p>

          <div className="mb-4 grid grid-cols-4 gap-2">
            {ATTACK_KINDS.map((k) => (
              <div key={k} data-testid="attack-kind-count" data-kind={k} data-count={diag.byKind[k]} className="rounded-xl bg-surface-2 p-2 text-center">
                <div className="text-xl">{ATTACK_KIND_META[k].emoji}</div>
                <div className="text-lg font-black">{diag.byKind[k]}</div>
                <div className="text-[11px] leading-tight text-neutral-400">{ATTACK_KIND_META[k].label}</div>
              </div>
            ))}
          </div>

          {diag.items.length === 0 ? (
            <p data-testid="attack-empty" className="rounded-xl bg-surface-2 p-4 text-sm text-neutral-300">
              Rien à rejouer pour l'instant. Fais le bilan d'une partie contre un bot ou importée de chess.com : chaque
              moment où Stockfish attaquait le roi adverse et où tu as joué autre chose apparaîtra ici.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {diag.items.map((it) => (
                <AttackRow
                  key={it.mistake.id}
                  item={it}
                  done={solved.has(solvedKey(it.mistake))}
                  going={inProgress === `attaque:${it.mistake.id}|${it.mistake.fenBefore}`}
                  onOpen={() => navigate(`/attaques-manquees/${it.mistake.id}`)}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function AttackRow({ item, done, going, onOpen }: { item: MissedAttackItem; done: boolean; going: boolean; onOpen: () => void }) {
  const meta = ATTACK_KIND_META[item.kind]
  return (
    <button
      data-testid="attack-item"
      data-id={item.mistake.id}
      data-kind={item.kind}
      onClick={onOpen}
      className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl bg-surface-2 px-3 py-2.5 text-left hover:bg-surface-3"
    >
      <span className="text-2xl" aria-hidden="true">{meta.emoji}</span>
      <span className="min-w-0 flex-1">
        <span className="block truncate font-bold">{meta.label}</span>
        <span className="block truncate text-xs text-neutral-400">
          {item.mistake.gameLabel} · tu as joué <span className="font-semibold text-red-300">{item.playedFig}</span>
        </span>
        <span className="block truncate text-xs text-neutral-500">
          Après le bon coup : <span style={{ color: ATTACK_RED }}>⚔ {item.attackers}</span> · <span className="text-accent">🛡 {item.defenders}</span>
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

function MissedAttackPlay({ id }: { id: number }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [item, setItem] = useState<MissedAttackItem | null | undefined>(undefined)
  const [next, setNext] = useState<number | null>(null)

  // L'attaque, prise dans la même liste que la page précédente (même filtre), et pour « Attaque
  // suivante » la plus récente des autres attaques pas encore retrouvées.
  useEffect(() => {
    void (async () => {
      const [rows, solved] = await Promise.all([db.mistakes.toArray(), solvedMissedAttacks()])
      const items = diagnoseMissedAttacks(rows).items
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
        <p data-testid="attack-missing" className="text-neutral-300">Cette attaque n'est pas dans ta liste.</p>
        <p className="text-sm text-neutral-400">
          La faute a été supprimée, est incomplète, ou son bilan ne connaissait pas ta couleur.
        </p>
        <Link to="/attaques-manquees" replace className="rounded-lg bg-surface-3 px-4 py-2 font-semibold hover:bg-surface-3/70">
          Retour à la liste
        </Link>
      </div>
    )
  }
  const row = item.mistake
  const restore = !!(location.state as { restore?: boolean } | null)?.restore
  const meta = ATTACK_KIND_META[item.kind]
  const lesson = `${meta.lesson} ${ATTACK_PRINCIPLE} Ici, après le bon coup, ${countsText(item.attackers, item.defenders)} autour du roi adverse. Tu avais joué ${item.playedFig}.`

  return (
    <PositionGame
      gameKey={`attaque:${row.id}`}
      startFen={row.fenBefore}
      title={meta.label}
      objective={null}
      objectiveLabel="Objectif : retrouve l'attaque"
      goalHint="Au bilan, Stockfish attaquait le roi : joue son coup."
      lesson={lesson}
      restoreFinished={restore}
      returnTo={`/attaques-manquees/${row.id}`}
      returnLabel="Retour à l'attaque"
      showAttackers
      keyMove={{ uci: row.bestUci, san: item.bestSan, onJudged: (found) => void recordMissedAttack(id, row.fenBefore, found) }}
      otherLabel="Attaque suivante"
      onExit={() => navigate('/attaques-manquees', { replace: true })}
      onOther={next !== null ? () => navigate(`/attaques-manquees/${next}`, { replace: true }) : undefined}
      onReplace={recordReplaced}
    />
  )
}
