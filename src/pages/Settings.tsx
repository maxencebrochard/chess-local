import { useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageHeader } from '../components/PageHeader'
import { PieceIcon } from '../components/PieceIcon'
import { Toggle } from '../components/Toggle'
import { PIECE_SETS } from '../lib/pieces'
import { play } from '../lib/sounds'
import { loadThreatPrefs, saveThreatPrefs, type ThreatPrefs } from '../lib/threat'
import { BOARD_THEMES, currentTheme, useSettings } from '../store/settings'

// Page Réglages (onglet Plus) : présentation seule. Chaque contrôle écrit exactement là où il
// écrivait dans Stats avant le lot 3 du plan UX : le store Zustand persisté
// (`chess-local-settings`) et, pour l'alerte de menace, `chess-local-threat-check`, partagé avec
// l'écran de configuration de Jouer.

// Touches qui changent le volume du curseur : seules elles déclenchent l'aperçu sonore.
const VOLUME_KEYS = new Set(['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End', 'PageUp', 'PageDown'])

const DEPTHS = [
  ['fast', 'Rapide'],
  ['balanced', 'Équilibré'],
  ['deep', 'Profond'],
] as const

function Group({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={`reglages-${id}`} data-settings-group={id} className="mb-6 last:mb-0">
      <h2 id={`reglages-${id}`} className="mb-2 text-lg font-semibold">{title}</h2>
      <div className="space-y-3 rounded-xl bg-surface-2 p-4">{children}</div>
    </section>
  )
}

function Label({ children }: { children: ReactNode }) {
  return <p className="mb-2 text-sm font-semibold text-neutral-300">{children}</p>
}

function Hint({ children }: { children: ReactNode }) {
  return <p className="mt-1 text-sm text-muted">{children}</p>
}

export default function Settings() {
  const navigate = useNavigate()
  const settings = useSettings()
  const theme = currentTheme(settings.themeId)
  // Hors persist Zustand : relu au montage, comme Jouer le fait à chaque ouverture.
  const [threat, setThreat] = useState<ThreatPrefs>(loadThreatPrefs)
  const chooseThreat = (mode: keyof ThreatPrefs, on: boolean) => {
    const next = { ...threat, [mode]: on }
    setThreat(next)
    saveThreatPrefs(next)
  }

  return (
    <div className="mx-auto max-w-2xl p-4 md:p-6">
      <PageHeader
        title="Réglages"
        description="Échiquier, sons et analyse, appliqués partout dans l’app."
        back={{ label: 'Plus', onClick: () => navigate('/plus') }}
      />

      <Group id="echiquier" title="Échiquier">
        <div>
          <Label>Thème</Label>
          <div className="flex flex-wrap gap-2">
            {BOARD_THEMES.map((t) => (
              <button
                key={t.id}
                onClick={() => settings.setTheme(t.id)}
                className={`cursor-pointer overflow-hidden rounded border-2 ${settings.themeId === t.id ? 'border-accent' : 'border-transparent'}`}
                title={t.name}
                aria-label={t.name}
                aria-pressed={settings.themeId === t.id}
              >
                <div className="flex">
                  <div className="h-10 w-8" style={{ background: t.light }} />
                  <div className="h-10 w-8" style={{ background: t.dark }} />
                </div>
              </button>
            ))}
          </div>
        </div>
        <div>
          <Label>Pièces</Label>
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Pièces">
            {PIECE_SETS.map((ps) => (
              <button
                key={ps.id}
                role="radio"
                aria-checked={settings.pieceSet === ps.id}
                data-piece-set={ps.id}
                onClick={() => settings.setPieceSet(ps.id)}
                className={`cursor-pointer overflow-hidden rounded border-2 ${settings.pieceSet === ps.id ? 'border-accent' : 'border-transparent'}`}
                title={ps.name}
              >
                <div className="flex">
                  <div className="h-9 w-9" style={{ background: theme.light }}>
                    <PieceIcon set={ps.id} code="wN" />
                  </div>
                  <div className="h-9 w-9" style={{ background: theme.dark }}>
                    <PieceIcon set={ps.id} code="bQ" />
                  </div>
                </div>
                <div className="bg-surface-3 px-1 py-0.5 text-[11px] font-semibold text-neutral-300">{ps.name}</div>
              </button>
            ))}
          </div>
        </div>
        <Toggle label="Afficher les coups légaux" value={settings.showLegalMoves} onChange={settings.setShowLegalMoves} />
        <Toggle label="⚔ Compter les attaquants autour des rois" value={settings.showAttackers} onChange={settings.setShowAttackers} testId="toggle-attackers" />
      </Group>

      <Group id="jeu" title="Jeu">
        <div>
          <Toggle label="Prémouvements" value={settings.premoves} onChange={settings.setPremoves} />
          <Hint>Prépare ton coup pendant que l’adversaire réfléchit.</Hint>
        </div>
        <div role="group" aria-labelledby="reglages-menace" data-testid="threat-prefs" className="border-t border-black/30 pt-3">
          <p id="reglages-menace" className="text-sm font-semibold text-neutral-300">🛡 Qu’est-ce qu’il menace ?</p>
          <Hint>Le coach t’arrête quand le bot crée une vraie menace. Indisponible en bullet.</Hint>
          {/* Écart entre les lignes : collées, le pseudo-élément de la seconde (peint après)
              mordrait d'un sous-pixel sur la cible de la première. */}
          <div className="mt-1 space-y-1">
            <Toggle label="Contre un bot" value={threat.bot} onChange={(v) => chooseThreat('bot', v)} testId="toggle-threat-bot" />
            <Toggle label="Avec le coach" value={threat.coach} onChange={(v) => chooseThreat('coach', v)} testId="toggle-threat-coach" />
          </div>
        </div>
      </Group>

      <Group id="sons" title="Sons">
        <Toggle label="Sons" value={settings.playSounds} onChange={settings.setPlaySounds} />
        {settings.playSounds && (
          <label className="flex min-h-11 items-center gap-3 text-sm text-neutral-300">
            <span>Volume</span>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              aria-label="Volume des sons"
              value={Math.round(settings.soundVolume * 100)}
              onChange={(e) => settings.setSoundVolume(Number(e.target.value) / 100)}
              // Aperçu au relâcher : le son d'un coup, au nouveau volume (pas sur Tab ni Échap).
              onPointerUp={() => play('move-self')}
              onKeyUp={(e) => { if (VOLUME_KEYS.has(e.key)) play('move-self') }}
              className="h-6 flex-1 cursor-pointer accent-accent"
            />
            <span className="w-12 whitespace-nowrap text-right tabular-nums">{Math.round(settings.soundVolume * 100)}{' '}%</span>
          </label>
        )}
        <p className="text-sm text-muted">Sur iPhone, le mode silencieux coupe les sons de l’app.</p>
      </Group>

      <Group id="analyse" title="Analyse">
        <div>
          <Label>Profondeur du bilan de partie</Label>
          <div className="flex flex-wrap gap-2">
            {DEPTHS.map(([key, label]) => (
              <button
                key={key}
                onClick={() => settings.setReviewDepth(key)}
                aria-pressed={settings.reviewDepth === key}
                className={`min-h-11 cursor-pointer rounded border-2 px-3 py-1.5 text-sm font-semibold transition ${
                  settings.reviewDepth === key ? 'border-accent bg-accent/10' : 'border-transparent bg-surface-3 hover:bg-surface-3/70'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <Hint>Rapide ≈ 30 s, Équilibré ≈ 1-2 min, Profond ≈ 4-5 min sur iPhone (partie de 40 coups).</Hint>
        </div>
      </Group>
    </div>
  )
}
