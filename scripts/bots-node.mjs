// Charge la VRAIE logique des bots (`src/lib/bots.ts`) et la VRAIE classe `Engine`
// (`src/lib/engine.ts`) dans Node, avec le MÊME Stockfish WASM que l'app (`public/engine/`).
// Partagé par le banc `scripts/bench-bots.mjs` et le harnais E2E `e2e/bots_moves.mjs`.
//
// `Engine` crée un `Worker` : on le remplace par un processus Node qui exécute le build WASM
// lite mono-thread et relaie l'UCI ligne à ligne. Le reste (mutex, parsing des `info`,
// MultiPV) est le code de l'app, sans copie.
import { spawn } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { createInterface } from 'node:readline'
import { fileURLToPath, pathToFileURL } from 'node:url'

export const ROOT = dirname(dirname(fileURLToPath(import.meta.url)))
// Le build de `public/engine/` ne se lance pas tel quel dans Node (package.json en `type: module`,
// le script est CommonJS) : on lance la copie du paquet npm `stockfish`, dont on vérifie qu'elle
// est identique octet pour octet à celle que sert l'app.
export const ENGINE_JS = join(ROOT, 'node_modules', 'stockfish', 'bin', 'stockfish-18-lite-single.js')

function assertSameEngine() {
  for (const ext of ['js', 'wasm']) {
    const app = readFileSync(join(ROOT, 'public', 'engine', `stockfish-18-lite-single.${ext}`))
    const npm = readFileSync(join(ROOT, 'node_modules', 'stockfish', 'bin', `stockfish-18-lite-single.${ext}`))
    if (!app.equals(npm)) throw new Error(`stockfish-18-lite-single.${ext} : la copie npm diffère de public/engine/`)
  }
}

class ProcessWorker {
  constructor() {
    this.onmessage = null
    this.proc = spawn(process.execPath, [ENGINE_JS], { stdio: ['pipe', 'pipe', 'ignore'] })
    this.proc.stdin.on('error', () => {})
    createInterface({ input: this.proc.stdout }).on('line', (line) => this.onmessage?.({ data: line }))
  }
  postMessage(cmd) {
    if (this.proc.exitCode === null && !this.proc.killed) this.proc.stdin.write(`${cmd}\n`)
  }
  terminate() {
    this.proc.kill('SIGKILL')
  }
}

export async function loadApp() {
  assertSameEngine()
  globalThis.location ??= { href: '' } // engine.ts lit `location` au chargement du module
  globalThis.Worker = ProcessWorker
  const { build } = await import('rolldown')
  const dir = mkdtempSync(join(tmpdir(), 'bots-'))
  const file = join(dir, 'app.mjs')
  await build({
    cwd: ROOT,
    input: join(ROOT, 'scripts', 'bench-bots-entry.ts'),
    output: { format: 'esm', file },
    transform: { define: { 'import.meta.env.BASE_URL': '"./"' } },
    logLevel: 'silent',
    write: true,
  })
  try {
    return await import(pathToFileURL(file).href)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

// RNG reproductible (mulberry32), pour qu'un tirage de bot soit rejouable à graine égale.
export function seededRng(seed) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function hashSeed(...parts) {
  let h = 2166136261
  for (const ch of parts.join('|')) h = Math.imul(h ^ ch.charCodeAt(0), 16777619)
  return h >>> 0
}
