// Wrapper UCI autour du worker Stockfish 18 lite (WASM mono-thread).
// Un Engine = un worker. Toutes les opérations publiques sont sérialisées par
// un mutex (chaîne de promesses) : deux `go` sans `stop` intermédiaire
// corrompent le moteur WASM (trap `unreachable`).

export interface EngineLine {
  multipv: number
  depth: number
  scoreCp: number | null // centipawns, point de vue du trait
  scoreMate: number | null
  pv: string[] // coups UCI
}

export interface SearchResult {
  bestMove: string
  lines: EngineLine[]
}

const DEBUG_UCI = location.href.includes('debug-uci')

export class Engine {
  private worker: Worker
  private ready: Promise<void>
  private listeners = new Set<(line: string) => void>()
  private queue: Promise<unknown> = Promise.resolve()
  private searchId = 0
  private searching = false
  onLines: ((lines: EngineLine[]) => void) | null = null
  private currentLines: EngineLine[] = []

  constructor() {
    this.worker = new Worker(`${import.meta.env.BASE_URL}engine/stockfish-18-lite-single.js`)
    this.worker.onmessage = (e: MessageEvent) => {
      const line = typeof e.data === 'string' ? e.data : ''
      if (DEBUG_UCI && !line.startsWith('info')) console.log('[uci<]', line)
      for (const l of this.listeners) l(line)
    }
    this.ready = this.initUci()
  }

  private send(cmd: string) {
    if (DEBUG_UCI) console.log('[uci>]', cmd)
    this.worker.postMessage(cmd)
  }

  private waitFor(predicate: (line: string) => boolean): Promise<string> {
    return new Promise((resolve) => {
      const listener = (line: string) => {
        if (predicate(line)) {
          this.listeners.delete(listener)
          resolve(line)
        }
      }
      this.listeners.add(listener)
    })
  }

  private async initUci() {
    const uciok = this.waitFor((l) => l === 'uciok')
    this.send('uci')
    await uciok
    const ok = this.waitFor((l) => l === 'readyok')
    this.send('isready')
    await ok
  }

  // Sérialise les opérations : jamais deux commandes de recherche entrelacées.
  private exclusive<T>(fn: () => Promise<T>): Promise<T> {
    const run = this.queue.then(fn)
    this.queue = run.catch(() => undefined)
    return run
  }

  // Arrête la recherche en cours s'il y en a une. À appeler sous mutex uniquement.
  private async ensureIdle() {
    if (!this.searching) return
    const done = this.waitFor((l) => l.startsWith('bestmove'))
    this.send('stop')
    await Promise.race([done, new Promise((r) => setTimeout(r, 2000))])
    this.searching = false
  }

  private attachInfoListener(): () => void {
    const id = ++this.searchId
    this.currentLines = []
    const infoListener = (line: string) => {
      if (id !== this.searchId) return
      const parsed = parseInfo(line)
      if (!parsed) return
      this.currentLines[parsed.multipv - 1] = parsed
      this.onLines?.(this.currentLines.filter(Boolean))
    }
    this.listeners.add(infoListener)
    return () => this.listeners.delete(infoListener)
  }

  setOptions(options: Record<string, string | number | boolean>): Promise<void> {
    return this.exclusive(async () => {
      await this.ready
      await this.ensureIdle()
      for (const [name, value] of Object.entries(options)) {
        this.send(`setoption name ${name} value ${value}`)
      }
      const ok = this.waitFor((l) => l === 'readyok')
      this.send('isready')
      await ok
    })
  }

  // Recherche bloquante ; résout sur bestmove. onLines reçoit les lignes au fil de l'eau.
  search(opts: { fen: string; depth?: number; movetimeMs?: number; multipv?: number }): Promise<SearchResult> {
    return this.exclusive(async () => {
      await this.ready
      await this.ensureIdle()
      const detach = this.attachInfoListener()
      if (opts.multipv) this.send(`setoption name MultiPV value ${opts.multipv}`)
      this.send(`position fen ${opts.fen}`)
      const done = this.waitFor((l) => l.startsWith('bestmove'))
      this.searching = true
      if (opts.movetimeMs) this.send(`go movetime ${opts.movetimeMs}`)
      else this.send(`go depth ${opts.depth ?? 16}`)
      const bestLine = await done
      this.searching = false
      detach()
      return { bestMove: bestLine.split(' ')[1], lines: this.currentLines.filter(Boolean) }
    })
  }

  // Recherche infinie pour l'analyse live ; s'arrête au prochain stop()/search().
  startInfinite(fen: string, multipv: number): Promise<void> {
    return this.exclusive(async () => {
      await this.ready
      await this.ensureIdle()
      this.attachInfoListener()
      this.send(`setoption name MultiPV value ${multipv}`)
      this.send(`position fen ${fen}`)
      this.searching = true
      this.send('go infinite')
    })
  }

  stop(): Promise<void> {
    this.searchId++ // invalide les callbacks onLines de la recherche en cours
    return this.exclusive(() => this.ensureIdle())
  }

  quit() {
    this.searchId++
    void this.exclusive(async () => {
      this.send('quit')
      this.worker.terminate()
    })
  }
}

function parseInfo(line: string): EngineLine | null {
  if (!line.startsWith('info ') || !line.includes(' pv ')) return null
  const depth = matchNum(line, 'depth')
  if (depth === null) return null
  const multipv = matchNum(line, 'multipv') ?? 1
  const cp = matchNum(line, 'score cp')
  const mate = matchNum(line, 'score mate')
  const pvIndex = line.indexOf(' pv ')
  const pv = line.slice(pvIndex + 4).trim().split(' ')
  return { multipv, depth, scoreCp: cp, scoreMate: mate, pv }
}

function matchNum(line: string, key: string): number | null {
  const m = line.match(new RegExp(`\\b${key} (-?\\d+)`))
  return m ? +m[1] : null
}
