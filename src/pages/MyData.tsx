import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  MAX_BACKUP_BYTES,
  TABLES,
  countLabel,
  currentCounts,
  describeCounts,
  willBe,
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
import { Cta } from '../components/Cta'
import { PageHeader } from '../components/PageHeader'
import { isNative } from '../lib/native'

// Page Mes données (onglet Plus) : sauvegarde, restauration et réinitialisation, extraites de
// Stats au lot 3 du plan UX sans changer `backup.ts` ni ses clés. Toute action qui écrase la base
// passe par une feuille de confirmation (deux pour la réinitialisation), qui propose d'exporter
// d'abord.

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
    <p key={msg.id} data-testid={testId} data-kind={msg.kind} role={msg.kind === 'error' ? 'alert' : undefined} className={`text-sm ${MSG_CLASS[msg.kind]}`}>
      {msg.text}
      {retry && msg.kind === 'error' && (
        <button data-testid="share-retry" onClick={onRetry} className="ml-2 min-h-11 cursor-pointer rounded bg-surface-3 px-3 font-semibold text-neutral-200 hover:bg-surface-3/70">
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

// « A », « A et B », « A, B et C ».
function missingNote(plan: BackupPlan): string {
  const labels = plan.missingTables.map(tableLabel)
  return labels.length > 1 ? `${labels.slice(0, -1).join(', ')} et ${labels[labels.length - 1]}` : (labels[0] ?? '')
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

const hasCurrent = (c: Counts | null) => !!c && TABLES.some((t) => c[t] > 0)

export default function MyData() {
  const navigate = useNavigate()
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
  // Contenu de la base, relu après une restauration : l'interface reflète la base sans
  // rechargement (impossible à la main en PWA standalone).
  const [stored, setStored] = useState<Counts | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const recount = () => currentCounts().then(setStored, () => setStored(null))

  useEffect(() => {
    setLastExport(readLastExport())
    void storageProtected().then(setProtectedState)
    void recount()
  }, [])

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

  // Les réglages restaurés arrivent dans le store Zustand par `importBackup` ; seuls les comptes
  // de la base sont à relire.
  async function onConfirmRestore() {
    if (!pending) return
    setBusy(true)
    try {
      const result = await importBackup(pending.plan)
      setMsg(say(successText(pending.plan, result), 'success'))
    } catch (err) {
      setMsg(say((err as Error).message, 'error'))
    } finally {
      void recount()
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

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <PageHeader
        title={<span data-testid="data-heading">Mes données</span>}
        description="Tout reste sur cet appareil : sauvegarde-le, restaure-le ou repars de zéro."
        back={{ label: 'Plus', onClick: () => navigate('/plus') }}
      />

      <section aria-labelledby="donnees-sauvegarde" className="mb-6">
        <h2 id="donnees-sauvegarde" className="mb-2 text-lg font-semibold">Sauvegarde</h2>
        <div data-testid="storage-status" className="space-y-4 rounded-xl bg-surface-2 p-4">
          <p className="text-sm leading-6 text-neutral-300">
            Parties, classements, puzzles, erreurs et réglages ne vivent que sur cet appareil : supprimer l'icône de l'app
            les efface, et Safari et l'app installée ont chacun leur stockage. Exporte régulièrement et garde le fichier
            dans Fichiers ou iCloud.
          </p>
          {isNative && (
            <p data-testid="native-migration-help" className="text-sm leading-6 text-neutral-300">
              Venir de la PWA : dans la PWA, Plus, Mes données, Exporter tout, puis Enregistrer dans Fichiers. Ici,
              Restaurer ce fichier remplace ce que tu as fait dans l'app.
            </p>
          )}
          <dl className="space-y-2 text-sm">
            <div>
              <dt className="text-muted">Sur cet appareil</dt>
              <dd data-testid="stored-counts" className="mt-0.5">{stored ? hasCurrent(stored) ? describeCounts(stored) : 'Aucune donnée' : '…'}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted">Stockage protégé par le système</dt>
              <dd data-testid="storage-persisted" className={protectedState === false ? 'text-amber-300' : ''}>
                {protectedState === true ? 'oui' : protectedState === false ? 'non' : 'inconnu'}
              </dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted">Dernier export</dt>
              <dd data-testid="last-export" className={`text-right ${lastExport ? '' : 'text-amber-300'}`}>
                {lastExport ? `${fmtDate(lastExport.at)} (${countLabel('games', lastExport.games)})` : 'jamais'}
              </dd>
            </div>
          </dl>
          {protectedState === false && (
            <p className="text-sm text-amber-300">iOS peut purger les données d'une app inutilisée : exporte sans attendre.</p>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <Cta data-testid="export-btn" onClick={() => void onExport()} disabled={working !== null} className="w-full">
              {working === 'export' ? '⏳ Export…' : '⬇ Exporter tout'}
            </Cta>
            <Cta variant="secondary" data-testid="restore-btn" onClick={() => fileRef.current?.click()} disabled={working !== null} className="w-full">
              {working === 'inspect' ? '⏳ Lecture du fichier…' : '⬆ Restaurer'}
            </Cta>
            <input ref={fileRef} type="file" accept="application/json,.json" className="hidden" onChange={(e) => void onFile(e)} />
          </div>
          <MsgLine msg={msg} testId="backup-msg" retry={retry && !retry.inSheet ? retry : null} onRetry={onRetry} />
        </div>
      </section>

      <section aria-labelledby="donnees-reinitialiser">
        <h2 id="donnees-reinitialiser" className="mb-2 text-lg font-semibold">Réinitialiser</h2>
        <div className="space-y-3 rounded-xl border border-red-500/30 bg-surface-2 p-4">
          <p className="text-sm leading-6 text-neutral-300">
            Efface tout ce que l'app garde sur cet appareil. Deux confirmations te laissent le temps d'exporter d'abord.
          </p>
          <button
            type="button"
            data-testid="reset-btn"
            onClick={() => void onResetStart()}
            disabled={working !== null}
            className="min-h-11 w-full cursor-pointer rounded-xl border border-red-500/50 px-4 py-2 text-sm font-semibold text-red-400 transition hover:bg-red-500/10 hover:text-red-300 disabled:cursor-default disabled:opacity-40 sm:w-auto"
          >
            Réinitialiser l'app…
          </button>
        </div>
      </section>

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
              ? `${describeCounts(pending.current)} ${willBe(pending.current, 'remplacé')} par ${describeCounts(pending.plan.counts)}.`
              : `Ta base est vide : ${describeCounts(pending.plan.counts)} ${willBe(pending.plan.counts, 'ajouté')}, rien ne sera perdu.`}
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
              className="min-h-11 w-full cursor-pointer rounded-lg bg-surface-3 py-2.5 text-sm font-semibold text-neutral-200 hover:bg-surface-3/70 disabled:opacity-40"
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
              className="min-h-11 w-full cursor-pointer rounded-lg bg-surface-3 py-2.5 text-sm font-semibold text-neutral-200 hover:bg-surface-3/70 disabled:opacity-40"
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
