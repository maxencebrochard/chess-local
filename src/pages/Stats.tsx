import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react'
import { db, DEFAULT_RATING, type PuzzleAttempt, type Rating, type SavedGame } from '../lib/db'
import {
  MAX_BACKUP_BYTES,
  TABLES,
  countLabel,
  currentCounts,
  describeCounts,
  importBackup,
  inspectBackup,
  readLastExport,
  resetApp,
  retryShare,
  runExport,
  storageProtected,
  tableLabel,
  type BackupPlan,
  type Counts,
  type ImportResult,
  type LastExport,
  type SaveOutcome,
} from '../lib/backup'
import { ConfirmSheet } from '../components/ConfirmSheet'
import { BOARD_THEMES, useSettings } from '../store/settings'

// Chaque message a son id : le <p role="alert"> est remonté à chaque nouveau message, donc un
// lecteur d'écran ré-annonce même une erreur identique à la précédente.
type Msg = { id: number; text: string; kind: 'success' | 'error' | 'info' }
type Pending = { plan: BackupPlan; current: Counts }
let msgSeq = 0
const say = (text: string, kind: Msg['kind']): Msg => ({ id: ++msgSeq, text, kind })
// Partage refusé : le fichier déjà préparé est gardé pour un nouvel essai lancé par un tap.
type Retry = { file: File; counts: Counts; inSheet: boolean }

const MSG_CLASS: Record<Msg['kind'], string> = { success: 'text-accent', error: 'text-red-400', info: 'text-neutral-300' }

function exportMsg(outcome: SaveOutcome, counts: Counts): Msg {
  if (outcome === 'cancelled') return say('Export annulé : aucun fichier enregistré.', 'info')
  if (outcome === 'failed') return say("Le partage n'a pas abouti : aucun fichier enregistré. Réessaie.", 'error')
  return say(`Sauvegarde exportée : ${describeCounts(counts)}.`, 'success')
}

function MsgLine({ msg, testId, retry, onRetry }: { msg: Msg | null; testId?: string; retry: Retry | null; onRetry: () => void }) {
  if (!msg) return null
  return (
    <p key={msg.id} data-testid={testId} data-kind={msg.kind} role={msg.kind === 'error' ? 'alert' : undefined} className={`text-xs ${MSG_CLASS[msg.kind]}`}>
      {msg.text}
      {retry && msg.kind === 'error' && (
        <button data-testid="share-retry" onClick={onRetry} className="ml-2 cursor-pointer rounded bg-surface-3 px-2 py-1 font-semibold text-neutral-200 hover:bg-surface-3/70">
          Partager le fichier
        </button>
      )}
    </p>
  )
}

function fmtDate(ms: number): string {
  const d = new Date(ms)
  return `le ${d.toLocaleDateString('fr-FR')} à ${d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}`
}

function settingsFate(plan: BackupPlan): string {
  if (plan.settings === 'restored') return 'Réglages restaurés.'
  if (plan.settings === 'absent') return 'Réglages conservés (absents du fichier).'
  return 'Réglages du fichier illisibles : les tiens sont conservés.'
}

function missingNote(plan: BackupPlan): string {
  return plan.missingTables.map(tableLabel).join(' et ')
}

// Message de succès : dit ce qui a été restauré (recompté en base), jamais un succès si rien ne l'a été.
function successText(plan: BackupPlan, result: ImportResult): string {
  const when = plan.date ? ` (faite ${fmtDate(plan.date)})` : ''
  const settings =
    !result.settingsApplied && plan.settings === 'restored'
      ? 'Réglages non appliqués (stockage saturé ?) : les tiens sont conservés.'
      : settingsFate(plan)
  let text = `Sauvegarde restaurée${when} : ${describeCounts(result.counts)}. ${settings}`
  if (plan.missingTables.length > 0) {
    const note = missingNote(plan)
    text += ` ${note.charAt(0).toUpperCase()}${note.slice(1)} vidées : absentes de cette ancienne sauvegarde.`
  }
  return text
}

export default function Stats() {
  const [ratings, setRatings] = useState<Rating[]>([])
  const [games, setGames] = useState<SavedGame[]>([])
  const [attempts, setAttempts] = useState<PuzzleAttempt[]>([])
  const [msg, setMsg] = useState<Msg | null>(null)
  const [sheetMsg, setSheetMsg] = useState<Msg | null>(null)
  const [pending, setPending] = useState<Pending | null>(null)
  const [resetStep, setResetStep] = useState<0 | 1 | 2>(0)
  const [resetCounts, setResetCounts] = useState<Counts | null>(null)
  const [busy, setBusy] = useState(false)
  const [working, setWorking] = useState<null | 'export' | 'inspect'>(null) // gèle les boutons pendant un export ou la lecture d'un fichier
  const [retry, setRetry] = useState<Retry | null>(null)
  const [protectedState, setProtectedState] = useState<boolean | null>(null)
  const [lastExport, setLastExport] = useState<LastExport | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const settings = useSettings()

  // Relu après une restauration : l'interface doit refléter la base sans rechargement
  // (impossible à la main en PWA standalone).
  const reload = useCallback(() => {
    void db.ratings.toArray().then(setRatings)
    void db.games.toArray().then(setGames)
    void db.puzzleAttempts.toArray().then(setAttempts)
  }, [])

  useEffect(() => {
    reload()
    setLastExport(readLastExport())
    void storageProtected().then(setProtectedState)
  }, [reload])

  const ratingOf = (key: string) => ratings.find((r) => r.key === key)
  const botGames = games.filter((g) => g.mode === 'bot')
  const wins = botGames.filter((g) => (g.result === '1-0') === (g.playerColor === 'w') && g.result !== '1/2-1/2').length
  const draws = botGames.filter((g) => g.result === '1/2-1/2').length
  const losses = botGames.length - wins - draws
  const solved = attempts.filter((a) => a.success).length

  const cats: { key: string; label: string; icon: string }[] = [
    { key: 'bullet', label: 'Bullet', icon: '🚀' },
    { key: 'blitz', label: 'Blitz', icon: '⚡' },
    { key: 'rapid', label: 'Rapide', icon: '⏱' },
    { key: 'puzzle', label: 'Puzzles', icon: '🧩' },
  ]

  // Export : feuille de partage iOS ou téléchargement. La date n'est mémorisée qu'après succès.
  async function doExport(inSheet: boolean): Promise<Msg> {
    setRetry(null)
    setWorking('export')
    try {
      const { outcome, counts, file } = await runExport()
      setLastExport(readLastExport())
      if (outcome === 'failed') setRetry({ file, counts, inSheet })
      return exportMsg(outcome, counts)
    } catch (err) {
      return say(`Export impossible : ${(err as Error).message}`, 'error')
    } finally {
      setWorking(null)
    }
  }

  async function onExport() {
    setMsg(null)
    setMsg(await doExport(false))
  }

  // Dans une feuille de confirmation : exporter l'état courant avant de l'écraser.
  async function onExportFirst() {
    setSheetMsg(null)
    setBusy(true)
    setSheetMsg(await doExport(true))
    setBusy(false)
  }

  // Nouvel essai de partage : rien d'asynchrone avant `share()`, l'activation du tap doit
  // être encore fraîche pour WebKit.
  function onRetry() {
    if (!retry) return
    const { counts, inSheet } = retry
    void retryShare(retry.file, counts.games).then((outcome) => {
      setLastExport(readLastExport())
      if (outcome !== 'failed') setRetry(null)
      ;(inSheet ? setSheetMsg : setMsg)(exportMsg(outcome, counts))
    })
  }

  // Fichier choisi : validation ENTIÈRE sans toucher à la base, puis confirmation. Un refus
  // garantit que rien n'a changé.
  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    e.target.value = '' // le même fichier doit pouvoir être rechoisi
    if (!f) return
    setMsg(null)
    setWorking('inspect')
    try {
      if (f.size > MAX_BACKUP_BYTES) throw new Error('Fichier trop volumineux : 50 Mo maximum.')
      const plan = inspectBackup(await f.text())
      setSheetMsg(null)
      setPending({ plan, current: await currentCounts() })
    } catch (err) {
      setMsg(say((err as Error).message, 'error'))
    } finally {
      setWorking(null)
    }
  }

  async function onConfirmRestore() {
    if (!pending) return
    setBusy(true)
    try {
      const result = await importBackup(pending.plan)
      setMsg(say(successText(pending.plan, result), 'success'))
    } catch (err) {
      setMsg(say((err as Error).message, 'error'))
    } finally {
      reload()
      setBusy(false)
      setPending(null)
    }
  }

  async function onResetStart() {
    setMsg(null)
    setSheetMsg(null)
    setResetCounts(await currentCounts())
    setResetStep(1)
  }

  async function onResetConfirm() {
    setBusy(true)
    try {
      await resetApp()
    } catch (err) {
      setBusy(false)
      setResetStep(0)
      setMsg(say(`Réinitialisation impossible : ${(err as Error).message}`, 'error'))
    }
  }

  const hasCurrent = (c: Counts | null) => !!c && TABLES.some((t) => c[t] > 0)

  return (
    <div className="mx-auto max-w-3xl p-6">
      <h1 className="mb-5 text-2xl font-bold">Statistiques</h1>

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        {cats.map((c) => {
          const r = ratingOf(c.key)
          return (
            <div key={c.key} className="rounded-lg bg-surface-2 p-4 text-center">
              <div className="text-2xl">{c.icon}</div>
              <div className="text-2xl font-bold">{r?.value ?? DEFAULT_RATING}</div>
              <div className="text-xs text-neutral-400">
                {c.label} · {r?.games ?? 0} {c.key === 'puzzle' ? 'essais' : 'parties'}
              </div>
            </div>
          )
        })}
      </div>

      <div className="mb-6 grid grid-cols-1 gap-3 md:grid-cols-2">
        <div className="rounded-lg bg-surface-2 p-4">
          <h2 className="mb-2 font-semibold">Parties contre les bots</h2>
          <div className="flex justify-between text-sm">
            <span className="text-accent">{wins} gagnées</span>
            <span className="text-neutral-400">{draws} nulles</span>
            <span className="text-red-400">{losses} perdues</span>
          </div>
          {botGames.length > 0 && (
            <div className="mt-2 flex h-2 overflow-hidden rounded-full">
              <div className="bg-accent" style={{ width: `${(wins / botGames.length) * 100}%` }} />
              <div className="bg-neutral-500" style={{ width: `${(draws / botGames.length) * 100}%` }} />
              <div className="bg-red-500" style={{ width: `${(losses / botGames.length) * 100}%` }} />
            </div>
          )}
        </div>
        <div className="rounded-lg bg-surface-2 p-4">
          <h2 className="mb-2 font-semibold">Puzzles</h2>
          <p className="text-sm text-neutral-300">
            {solved} résolus / {attempts.length} tentés
            {attempts.length > 0 && ` (${Math.round((solved / attempts.length) * 100)} %)`}
          </p>
        </div>
      </div>

      <h2 className="mb-3 text-lg font-bold">Réglages</h2>
      <div className="mb-6 space-y-3 rounded-lg bg-surface-2 p-4">
        <div>
          <p className="mb-2 text-sm font-semibold text-neutral-300">Thème de l'échiquier</p>
          <div className="flex gap-2">
            {BOARD_THEMES.map((t) => (
              <button
                key={t.id}
                onClick={() => settings.setTheme(t.id)}
                className={`cursor-pointer overflow-hidden rounded border-2 ${settings.themeId === t.id ? 'border-accent' : 'border-transparent'}`}
                title={t.name}
              >
                <div className="flex">
                  <div className="h-8 w-8" style={{ background: t.light }} />
                  <div className="h-8 w-8" style={{ background: t.dark }} />
                </div>
              </button>
            ))}
          </div>
        </div>
        <Toggle label="Afficher les coups légaux" value={settings.showLegalMoves} onChange={settings.setShowLegalMoves} />
        <Toggle label="Sons" value={settings.playSounds} onChange={settings.setPlaySounds} />
        <div>
          <p className="mb-2 text-sm font-semibold text-neutral-300">Profondeur du bilan de partie</p>
          <div className="flex gap-2">
            {(
              [
                ['fast', 'Rapide'],
                ['balanced', 'Équilibré'],
                ['deep', 'Profond'],
              ] as const
            ).map(([key, label]) => (
              <button
                key={key}
                onClick={() => settings.setReviewDepth(key)}
                className={`cursor-pointer rounded border-2 px-3 py-1.5 text-sm font-semibold transition ${
                  settings.reviewDepth === key ? 'border-accent bg-accent/10' : 'border-transparent bg-surface-3 hover:bg-surface-3/70'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="mt-1 text-xs text-neutral-500">
            Rapide ≈ 30 s, Équilibré ≈ 1-2 min, Profond ≈ 4-5 min sur iPhone (partie de 40 coups).
          </p>
        </div>
      </div>

      <h2 className="mb-3 text-lg font-bold">Tes données</h2>
      <div data-testid="storage-status" className="space-y-3 rounded-lg bg-surface-2 p-4">
        <p className="text-sm text-neutral-300">
          Parties, classements, puzzles, erreurs et réglages ne vivent que sur cet appareil : supprimer l'icône de l'app
          les efface, et Safari et l'app installée ont chacun leur stockage. Exporte régulièrement et garde le fichier
          dans Fichiers ou iCloud.
        </p>
        <div className="space-y-1 text-sm">
          <div className="flex justify-between gap-3">
            <span className="text-neutral-400">Stockage protégé par le système</span>
            <span data-testid="storage-persisted" className={protectedState === false ? 'text-amber-300' : ''}>
              {protectedState === true ? 'oui' : protectedState === false ? 'non' : 'inconnu'}
            </span>
          </div>
          {protectedState === false && (
            <p className="text-xs text-amber-300">iOS peut purger les données d'une app inutilisée : exporte sans attendre.</p>
          )}
          <div className="flex justify-between gap-3">
            <span className="text-neutral-400">Dernier export</span>
            <span data-testid="last-export" className={`text-right ${lastExport ? '' : 'text-amber-300'}`}>
              {lastExport ? `${fmtDate(lastExport.at)} (${countLabel('games', lastExport.games)})` : 'jamais'}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            data-testid="export-btn"
            onClick={() => void onExport()}
            disabled={working !== null}
            className="cursor-pointer rounded bg-accent px-3 py-1.5 text-sm font-semibold text-white hover:bg-accent-hover disabled:cursor-default disabled:opacity-40"
          >
            {working === 'export' ? '⏳ Export…' : '⬇ Exporter tout'}
          </button>
          <button
            data-testid="restore-btn"
            onClick={() => fileRef.current?.click()}
            disabled={working !== null}
            className="cursor-pointer rounded bg-surface-3 px-3 py-1.5 text-sm font-semibold hover:bg-surface-3/70 disabled:cursor-default disabled:opacity-40"
          >
            {working === 'inspect' ? '⏳ Lecture du fichier…' : '⬆ Restaurer'}
          </button>
          <input ref={fileRef} type="file" accept="application/json,.json" className="hidden" onChange={(e) => void onFile(e)} />
        </div>
        <MsgLine msg={msg} testId="backup-msg" retry={retry && !retry.inSheet ? retry : null} onRetry={onRetry} />
        <button
          data-testid="reset-btn"
          onClick={() => void onResetStart()}
          disabled={working !== null}
          className="cursor-pointer text-xs text-red-400 hover:text-red-300 disabled:cursor-default disabled:opacity-40"
        >
          Réinitialiser l'app (tout effacer sur cet appareil)…
        </button>
      </div>

      {pending && (
        <ConfirmSheet
          title="Remplacer tes données ?"
          confirmLabel="Remplacer"
          danger
          busy={busy}
          testId="restore"
          onConfirm={() => void onConfirmRestore()}
          onCancel={() => setPending(null)}
        >
          <p>Sauvegarde {pending.plan.date ? `faite ${fmtDate(pending.plan.date)}` : 'sans date'}.</p>
          <p className="font-semibold text-neutral-100">
            {hasCurrent(pending.current)
              ? `${describeCounts(pending.current)} seront remplacés par ${describeCounts(pending.plan.counts)}.`
              : `Ta base est vide : ${describeCounts(pending.plan.counts)} seront ajoutés, rien ne sera perdu.`}
          </p>
          <ul className="space-y-0.5 text-xs text-neutral-400">
            {TABLES.filter((t) => pending.current[t] > 0 || pending.plan.counts[t] > 0).map((t) => (
              <li key={t} className="first-letter:uppercase">
                {tableLabel(t)} : {pending.current[t]} → {pending.plan.counts[t]}
              </li>
            ))}
          </ul>
          {pending.plan.missingTables.length > 0 && (
            <p className="text-amber-300">
              Ancienne sauvegarde sans {missingNote(pending.plan)} : ces listes seront vidées (
              {describeCounts(pending.current, pending.plan.missingTables)} actuellement).
            </p>
          )}
          <p>{settingsFate(pending.plan).replace(/restaurés\.$/, 'remplacés par ceux de la sauvegarde.')}</p>
          {hasCurrent(pending.current) && (
            <button
              data-testid="restore-export-first"
              onClick={() => void onExportFirst()}
              disabled={busy}
              className="w-full cursor-pointer rounded-lg bg-surface-3 py-2.5 text-sm font-semibold text-neutral-200 hover:bg-surface-3/70 disabled:opacity-40"
            >
              ⬇ Exporter d'abord mes données actuelles
            </button>
          )}
          <MsgLine msg={sheetMsg} retry={retry?.inSheet ? retry : null} onRetry={onRetry} />
        </ConfirmSheet>
      )}

      {resetStep === 1 && (
        <ConfirmSheet
          title="Réinitialiser l'app ?"
          confirmLabel="Continuer"
          danger
          busy={busy}
          testId="reset"
          onConfirm={() => setResetStep(2)}
          onCancel={() => setResetStep(0)}
        >
          <p className="font-semibold text-neutral-100">
            {resetCounts && hasCurrent(resetCounts)
              ? `Tout ce qui est sur cet appareil sera effacé : ${describeCounts(resetCounts)} et tes réglages.`
              : 'Ta base est déjà vide : seuls tes réglages seront effacés.'}
          </p>
          <p>C'est définitif. C'est la sortie de secours si une restauration a rendu l'app inutilisable.</p>
          {hasCurrent(resetCounts) && (
            <button
              data-testid="reset-export-first"
              onClick={() => void onExportFirst()}
              disabled={busy}
              className="w-full cursor-pointer rounded-lg bg-surface-3 py-2.5 text-sm font-semibold text-neutral-200 hover:bg-surface-3/70 disabled:opacity-40"
            >
              ⬇ Exporter d'abord mes données
            </button>
          )}
          <MsgLine msg={sheetMsg} retry={retry?.inSheet ? retry : null} onRetry={onRetry} />
        </ConfirmSheet>
      )}

      {resetStep === 2 && (
        <ConfirmSheet
          title="Vraiment tout effacer ?"
          confirmLabel="Tout effacer"
          danger
          busy={busy}
          testId="reset-final"
          onConfirm={() => void onResetConfirm()}
          onCancel={() => setResetStep(0)}
        >
          <p className="font-semibold text-neutral-100">
            Dernière vérification : {resetCounts && hasCurrent(resetCounts) ? `${describeCounts(resetCounts)} et tes réglages` : 'tes réglages'} seront
            supprimés définitivement de cet appareil, puis l'app redémarrera.
          </p>
        </ConfirmSheet>
      )}
    </div>
  )
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-sm text-neutral-300">{label}</span>
      <button
        onClick={() => onChange(!value)}
        className={`h-6 w-11 cursor-pointer rounded-full p-0.5 transition ${value ? 'bg-accent' : 'bg-surface-3'}`}
      >
        <div className={`h-5 w-5 rounded-full bg-white transition ${value ? 'translate-x-5' : ''}`} />
      </button>
    </div>
  )
}
