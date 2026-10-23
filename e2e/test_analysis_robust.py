"""E2E Analyse robuste : écrans blancs, bilans faux et moteur qui ne s'arrête pas (lot L3).

Couvre ANA-1 (PGN avec en-tête FEN), ANA-2, ANA-3 et CP-2 (bilan jamais invalidé quand la ligne
change), CP-4 (partie à 0 coup), ANA-9 (« Mes erreurs » : couleur et libellé), ANA-10 (moteur coupé
= `stop` UCI réel), PERF-1 (recherche live bornée), PERF-2 (page cachée = `stop`), CP-6 (lignes de
l'ancienne position avec le signe du nouveau trait : barre qui passe en blanc pendant le recalcul
d'un mat ou d'un avantage noir), CP-7 (bilan lancé après le démontage), ANA-18 (import vide),
ANA-31 (`?game=` inconnu) et ANA-5 (nom d'ouverture long).

Usage : npm run test:e2e -- --suite analysis_robust
"""
import re
import time

from helpers import BASE, Checker, mobile_context, overflow_x, piece_on, shot, tap_move

ck = Checker("analysis_robust")
check = ck.check


PGN_FEN = (
    '[SetUp "1"]\n'
    '[FEN "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"]\n\n'
    "3... Nf6 4. Ng5 d5"
)
# Nom d'ouverture long (espagnole fermée) : très fréquent sur les parties chess.com.
PGN_LONG_OPENING = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 10. d4 Nbd7"
PGN_SHORT = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#"
# Fautes des DEUX camps : 2.Ba6 donne un fou (blancs), 3...g6 donne la tour (noirs).
PGN_BOTH_ERR = "1. e4 e5 2. Ba6 Nxa6 3. Qh5 g6 4. Qxe5+ Qe7 5. Qxh8"
# Milieu de partie dense (attaque anglaise) : la profondeur 22 met plus de 10 s à venir, donc la
# recherche live est encore en cours quand on coupe le moteur.
PGN_DENSE = (
    "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Be3 e5 7. Nb3 Be6 8. f3 Be7 9. Qd2 O-O "
    "10. O-O-O Nbd7 11. g4 b5 12. g5 b4 13. Ne2 Ne8 14. f4 a5 15. f5 a4 16. Nbd4 exd4 17. Nxd4 b3 "
    "18. Kb1 bxc2+ 19. Nxc2 Bb3 20. axb3 axb3 21. Na3 Ne5"
)
# Blancs largement gagnants (+6) à chaque position : un libellé négatif ne peut venir que d'une
# ligne de l'ancienne position affichée avec le signe du nouveau trait.
PGN_PLUS6 = "1. e4 e5 2. Nf3 Qg5 3. Nxg5 Nc6 4. d4 Nf6 5. d5 Nb8 6. Nc3 h6"
# Mat forcé pour les Noirs (deux tours contre roi) à chaque position du parcours.
PGN_BLACK_MATE = '[SetUp "1"]\n[FEN "r5k1/1r6/8/8/4K3/8/8/8 b - - 0 1"]\n\n1... Rb4+ 2. Kd3 Ra3+ 3. Kc2'
# Blancs une dame de moins dès le 6e demi-coup : avantage noir massif mais pas de mat.
PGN_BLACK_UP = "1. e4 e5 2. Qg4 Nf6 3. Nf3 Nxg4 4. d4 Nc6 5. d5 Nb8 6. Nc3 h6"
# 48 demi-coups sans théorie : en profondeur `deep`, le bilan reste ouvert assez longtemps pour agir.
PGN_MEDIUM = (
    "1. c4 g6 2. d3 f5 3. e3 e6 4. Qh5 Nf6 5. Kd2 Ng8 6. Na3 Bb4+ 7. Kc2 a5 8. e4 Ke7 9. e5 Nh6 "
    "10. Nb1 Qf8 11. Qd1 c6 12. Ne2 a4 13. Bd2 Ra5 14. Be3 Rxe5 15. Bc1 Bd6 16. g4 Rc5 17. a3 f4 "
    "18. Nd4 Na6 19. Rg1 Qd8 20. Nxc6+ Kf7 21. Nxd8+ Ke7 22. f3 Rb5 23. Nf7 Nf5 24. Nd8 Rg8"
)
ENGINE_LINE = "main [data-engine-line]:visible"
# Mat en 1 de chaque camp, au trait (…♜a8# et ♖a8#) : la ligne principale annonce un mat.
FEN_BLACK_M1 = "6K1/8/6k1/8/8/8/8/r7 b - - 0 1"
FEN_WHITE_M1 = "6k1/8/6K1/8/8/8/8/R7 w - - 0 1"
# Lignes moteur visibles (zone compacte mobile), lues sans dépendre du balisage : texte et
# hauteur de chaque ligne, hauteur de la zone qui les contient.
ENGINE_LINES_JS = """() => {
  const visible = (sel) => [...document.querySelectorAll(sel)].filter((e) => e.offsetParent)
  // Balisage d'avant le correctif : les lignes étaient des <p class="truncate"> sans attribut.
  const rows = visible('main [data-engine-line]').length ? visible('main [data-engine-line]') : visible('main p.truncate')
  return {
    rows: rows.map((e) => ({ text: e.innerText.replace(/\\s+/g, ' ').trim(), h: Math.round(e.getBoundingClientRect().height) })),
    zoneH: rows.length ? Math.round(rows[0].parentElement.getBoundingClientRect().height) : null,
  }
}"""


def open_analysis(ctx, query="", hash_query=""):
    """Nouvelle page par scénario : un écran blanc ne doit pas contaminer le suivant."""
    page = ctx.new_page()
    page.goto(f"{BASE}/{query}#/analyse{hash_query}")
    page.wait_for_selector("[data-square='e4']", timeout=30000)
    page.wait_for_timeout(800)
    return page


def open_import(page):
    page.locator("main button:visible", has_text="Options").click()
    page.locator("button:visible", has_text="Importer PGN ou FEN").click()
    page.wait_for_selector("textarea", timeout=5000)


def load_text(page, text):
    open_import(page)
    page.fill("textarea", text)
    page.locator("button:visible", has_text="Charger").click()
    page.wait_for_timeout(600)


def chips(page):
    """Nombre de demi-coups dans la bande visible (mobile) ou la bande du bilan guidé."""
    return page.locator("button[data-current]:visible").count()


def bilan_btn(page):
    return page.locator("main button:visible", has_text="Bilan").first


def root_len(page):
    return page.evaluate("() => document.getElementById('root').innerHTML.length")


def review_shown(page):
    """Le bilan est plaqué sur la vue principale : graphe d'éval et carte de précision."""
    return page.locator("main svg.cursor-pointer").count() > 0 or page.locator("text=Précision Blancs").count() > 0


def settle_review(page, timeout=600000):
    """Attend que le bilan en vol soit réglé : annulé (bouton Bilan réactivé) ou affiché (résumé).
    Flux unique : sans le correctif c'est le résumé périmé qui arrive, avec lui c'est l'annulation."""
    page.wait_for_function(
        """() => {
          const summary = [...document.querySelectorAll('button')].some((b) => b.textContent.includes('Démarrer le bilan'))
          const bilan = [...document.querySelectorAll('main button')].find((b) => b.offsetParent && b.textContent.includes('Bilan'))
          return summary || (bilan && !bilan.disabled)
        }""",
        timeout=timeout,
    )
    return page.locator("button:visible", has_text="Démarrer le bilan").count() > 0


def tally_sums(page):
    """Somme des classes du résumé, par camp : doit valoir le nombre de demi-coups de chaque camp."""
    return page.evaluate(
        """() => {
          let w = 0, b = 0
          for (const row of document.querySelectorAll('.fixed .grid')) {
            const s = row.querySelectorAll(':scope > span')
            if (s.length !== 4) continue
            w += +s[1].textContent
            b += +s[3].textContent
          }
          return [w, b]
        }"""
    )


def watch_uci(page):
    """Trafic UCI journalisé par `?debug-uci` : commandes envoyées (`[uci>]`) et réponses hors `info`."""
    log = {"sent": [], "recv": []}

    def on_console(m):
        if m.text.startswith("[uci>] "):
            log["sent"].append(m.text[len("[uci>] "):])
        elif m.text.startswith("[uci<] "):
            log["recv"].append(m.text[len("[uci<] "):])

    page.on("console", on_console)
    return log


# Journal UCI tenu dans la page, au niveau du worker : commandes envoyées et profondeur des lignes
# `info` reçues (que `?debug-uci` ne journalise pas), dans l'ordre exact où l'app les voit.
# Un journal par worker : en StrictMode (dev), le premier moteur est quitté au démontage simulé
# pendant que le second démarre, et son `go infinite` peut même partir après celui du second.
# `window.__uciLogs` : un journal par worker qui a lancé une recherche infinie.
UCI_DEPTH_SPY = """(() => {
  const Native = window.Worker
  const logs = []
  window.__uciLogs = () => logs.filter((l) => l.goAt)
  window.Worker = class extends Native {
    constructor(...a) {
      super(...a)
      this.__log = { sent: [], depth: 0, stopped: false, depthAtStop: null, times: [], goAt: 0, dead: false }
      logs.push(this.__log)
      this.addEventListener('message', (e) => {
        const log = this.__log
        const m = typeof e.data === 'string' && /^info .*\\bdepth (\\d+)\\b.* pv /.exec(e.data)
        if (m && +m[1] > log.depth) {
          log.depth = +m[1]
          log.times.push([+m[1], Math.round(performance.now() - log.goAt)])
        }
      })
    }
    postMessage(cmd, ...rest) {
      const log = this.__log
      if (typeof cmd === 'string') {
        log.sent.push(cmd)
        if (cmd === 'go infinite') Object.assign(log, { depth: 0, stopped: false, depthAtStop: null, times: [], goAt: performance.now() })
        if (cmd === 'stop' && !log.stopped) Object.assign(log, { stopped: true, depthAtStop: log.depth })
        if (cmd === 'quit') log.dead = true
      }
      return super.postMessage(cmd, ...rest)
    }
    terminate() {
      this.__log.dead = true
      return super.terminate()
    }
  }
})()"""
LIVE_DEPTH = 22  # src/pages/Analysis.tsx
# Une nouvelle profondeur arrive en moins d'une seconde au repos (21 → 22 : 0,6 s, profondeur 22
# atteinte en 4 s) ; 60 s sans progrès est un moteur bloqué, pas une machine lente.
STALL_S = 60


def wait_live_self_stop(page):
    """Attend le `stop` de la recherche live tant que le moteur progresse.

    Réussite : un worker reçoit `stop` à la profondeur cible. Échec : un worker en recherche (ni
    stoppé ni quitté) atteint la profondeur cible + 2 (la recherche ne s'arrête pas d'elle-même),
    ou aucune nouvelle profondeur pendant STALL_S secondes. Un worker stoppé plus tôt sans être
    relancé (StrictMode : celui du premier montage) n'est ni une réussite ni un échec."""
    best, since = -1, time.time()
    while True:
        logs = page.evaluate("() => window.__uciLogs()")
        done = [lg for lg in logs if lg["stopped"] and lg["depthAtStop"] >= LIVE_DEPTH]
        if done:
            return {"ok": True, "profondeur au stop": done[0]["depthAtStop"], "ms par profondeur": done[0]["times"][-4:]}
        running = [lg for lg in logs if not lg["stopped"] and not lg["dead"]]
        over = [lg["depth"] for lg in running if lg["depth"] >= LIVE_DEPTH + 2]
        if over:
            return {"ok": False, "profondeur sans stop": over[0]}
        depth = max((lg["depth"] for lg in running), default=-1)
        if depth > best:
            best, since = depth, time.time()
        elif time.time() - since > STALL_S:
            return {"ok": False, "bloqué à la profondeur": best, "secondes": round(time.time() - since),
                    "journaux": [(lg["sent"][-3:], lg["depthAtStop"]) for lg in logs]}
        page.wait_for_timeout(200)


def wait_until(page, predicate, timeout_ms):
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if predicate():
            return True
        page.wait_for_timeout(200)
    return predicate()


def idb(page, script, arg=None):
    """Accès IndexedDB brut à la base Dexie `chess-local` (déjà créée par l'app)."""
    return page.evaluate(
        """([body, arg]) => new Promise((resolve, reject) => {
          const req = indexedDB.open('chess-local')
          req.onerror = () => reject(req.error)
          req.onsuccess = () => {
            const db = req.result
            if (!db.objectStoreNames.contains('games')) { db.close(); reject(new Error('base non initialisée')); return }
            new Function('db', 'arg', 'resolve', 'reject', body)(db, arg, (v) => { db.close(); resolve(v) }, reject)
          }
        })""",
        [script, arg],
    )


def seed_game(ctx, game):
    page = ctx.new_page()
    page.goto(f"{BASE}/#/archive")
    # Dexie crée la base au premier accès : attendre la table plutôt qu'une durée fixe. Jamais
    # d'`open` avant que la base existe, il en créerait une vide en version 1.
    wait_until(page, lambda: page.evaluate("""() => indexedDB.databases().then((list) => list.some((d) => d.name === 'chess-local')
      && new Promise((res) => {
        const r = indexedDB.open('chess-local')
        r.onsuccess = () => { const ok = r.result.objectStoreNames.contains('games'); r.result.close(); res(ok) }
        r.onerror = () => res(false)
      }))"""), 30000)
    game_id = idb(
        page,
        "const tx = db.transaction('games', 'readwrite'); const r = tx.objectStore('games').add(arg);"
        "tx.oncomplete = () => resolve(r.result); tx.onerror = () => reject(tx.error)",
        game,
    )
    page.close()
    return game_id


def no_workers(page, timeout_ms=15000):
    """Plus aucun worker dans la page, attendu sans durée fixe. `quit()` laisse finir la recherche
    en vol (mutex) avant de terminer le worker : quelques secondes sous charge. Un worker orphelin,
    lui, ne disparaît jamais et échoue à l'échéance."""
    return wait_until(page, lambda: len(page.workers) == 0, timeout_ms)


# Chunk de la page Archive : build de production (`assets/Archive-<hash>.js`) ou serveur de dev.
ARCHIVE_CHUNK = re.compile(r"/(assets/Archive-[^/]*\.js|src/pages/Archive\.tsx)(\?.*)?$")


# Quitter l'analyse au moment exact où elle lit la partie (`?game=`) dans Dexie : un toucher sur
# l'onglet Archive placé dans la fenêtre de la course, au lieu d'espérer que la charge l'y mette.
# Le clic part en microtâche, avant toute réponse d'IndexedDB (qui arrive dans une tâche).
LEAVE_ON_GAME_READ = """(() => {
  if (!location.hash.includes('game=')) return
  let armed = true
  const get = IDBObjectStore.prototype.get
  IDBObjectStore.prototype.get = function (...a) {
    if (armed && this.name === 'games') {
      armed = false
      queueMicrotask(() => [...document.querySelectorAll('nav a')].filter((e) => e.textContent.includes('Archive')).at(-1).click())
    }
    return get.apply(this, a)
  }
})()"""


LEAVE_ON_REVIEW = """(() => {
  window.__leftOnReview = false
  const post = Worker.prototype.postMessage
  Worker.prototype.postMessage = function (cmd, ...rest) {
    const r = post.call(this, cmd, ...rest)
    if (!window.__leftOnReview && typeof cmd === 'string' && cmd.startsWith('go depth')) {
      window.__leftOnReview = true
      queueMicrotask(() => [...document.querySelectorAll('nav a')].filter((e) => e.textContent.includes('Archive')).at(-1).click())
    }
    return r
  }
})()"""


def cp7_slow_chunk(p, browser, game):
    """CP-7 déterministe : partie quittée pendant sa lecture, chunk d'Archive lente (première
    visite, appareil chargé).

    La navigation de l'app est une transition : tant que la page suivante n'est pas chargée,
    Analyse reste montée. Sa lecture Dexie (`?game=`) se termine pendant ce temps ; avant le
    correctif, son nettoyage d'URL (`setParams`, relatif à la route d'Analyse) ramenait l'utilisateur
    sur #/analyse et le bilan différé démarrait un moteur. La chunk est retenue, puis libérée.
    Service worker bloqué : il servirait la chunk depuis son précache, hors de portée de `route`."""
    ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block")
    game_id = seed_game(ctx, game)
    held = []
    ctx.route(ARCHIVE_CHUNK, lambda route: held.append(route))  # `route` désactive aussi le cache HTTP
    ctx.add_init_script(LEAVE_ON_GAME_READ)
    page = ctx.new_page()
    uci = watch_uci(page)
    page.goto(f"{BASE}/?debug-uci#/analyse?game={game_id}&review=1")
    check("[cp7 chunk lente] chunk d'Archive demandée au toucher", wait_until(page, lambda: bool(held), 30000), f"({len(held)})")
    # Durée de la chunk lente simulée, pas une attente d'assertion : la lecture Dexie, déjà partie
    # au toucher, et le bilan différé de 300 ms ont largement le temps de se dérouler.
    page.wait_for_timeout(2000)
    hash_ = page.evaluate("location.hash")
    check("[cp7 chunk lente] la navigation vers l'Archive n'est pas annulée par le chargement de la partie",
          hash_ == "#/archive", f"(hash {hash_})")
    # L'analyse live de la position initiale (`go infinite`) tourne tant qu'Analyse est montée ; le
    # bilan, lui (`go depth`), ne doit pas partir pour une page quittée.
    check("[cp7 chunk lente] aucun bilan lancé pour une page quittée", not any(c.startswith("go depth") for c in uci["sent"]),
          f"({[c for c in uci['sent'] if c.startswith('go')]})")
    for route in held:
        route.continue_()
    ctx.unroute(ARCHIVE_CHUNK)
    ck.appears("[cp7 chunk lente] Archive affichée", page, "main h1:has-text('Archive')", timeout=30000)
    check("[cp7 chunk lente] aucun worker Stockfish orphelin", no_workers(page),
          f"({len(page.workers)} worker(s), hash {page.evaluate('location.hash')})")
    ctx.close()


def eval_label(page):
    return page.locator("main .bg-neutral-800:visible span").first.inner_text()


def start_bar_sampler(page):
    """Relève la barre d'éval mobile (`HEvalBar`) à chaque mutation DOM et à chaque frame.

    Le MutationObserver capte un état qui ne vit qu'un commit React (une frame rAF peut le rater) ;
    la largeur lue est la cible inline du remplissage blanc, pas la valeur animée."""
    page.evaluate(
        """() => {
          const bar = document.querySelector('main .h-7.bg-neutral-800')
          window.__frames = []
          const read = () => {
            // Relu à chaque relevé : une barre remontée ne doit pas laisser lire un nœud détaché figé.
            const bar = document.querySelector('main .h-7.bg-neutral-800')
            if (!bar) return
            const fill = bar.querySelector('div')
            const label = bar.querySelector('span').textContent
            window.__frames.push({ share: parseFloat(fill.style.width), label })
          }
          window.__obs = new MutationObserver(read)
          window.__obs.observe(bar, { attributes: true, characterData: true, childList: true, subtree: true })
          window.__sampling = true
          const tick = () => { read(); if (window.__sampling) requestAnimationFrame(tick) }
          requestAnimationFrame(tick)
        }"""
    )


def stop_bar_sampler(page):
    return page.evaluate("() => { window.__sampling = false; window.__obs.disconnect(); return window.__frames }")


def toggle_engine(page, expect_label):
    page.locator("main button:visible", has_text="Options").click()
    page.locator("button:visible", has_text=f"Moteur : {expect_label}").click()
    page.locator("button:visible", has_text="Fermer").click()


def suite(p):
    browser = p.chromium.launch(headless=True)
    ctx = mobile_context(p, browser, ck, standalone=True)

    # ---------- ANA-1 : PGN avec en-tête FEN ----------
    page = open_analysis(ctx)
    load_text(page, PGN_FEN)
    check("[ana1] l'app reste montée après l'import", root_len(page) > 1000, f"(root {root_len(page)} car.)")
    check("[ana1] 3 demi-coups chargés depuis la position custom", chips(page) == 3, f"({chips(page)})")
    check("[ana1] position finale affichée (Cf6, d5)", piece_on(page, "f6") == "bN" and piece_on(page, "d5") == "bP",
          f"(f6={piece_on(page, 'f6')}, d5={piece_on(page, 'd5')})")
    if chips(page) == 3:
        bilan_btn(page).click()
        ck.appears("[ana1] le bilan d'une partie à départ custom aboutit", page, "button:has-text('Démarrer le bilan')", timeout=120000)
    page.close()

    # ---------- ANA-18 : import vide ----------
    page = open_analysis(ctx)
    tap_move(page, "e2", "e4")
    tap_move(page, "e7", "e5")
    check("[ana18] deux coups joués", chips(page) == 2, f"({chips(page)})")
    open_import(page)
    charger = page.locator("button:visible", has_text="Charger")
    check("[ana18] Charger désactivé champ vide", charger.is_disabled())
    page.fill("textarea", "   \n ")
    check("[ana18] Charger désactivé avec des espaces", charger.is_disabled())
    page.fill("textarea", '[White "Alice"]\n[Black "Bob"]\n\n*')
    if not charger.is_disabled():
        charger.click()
        page.wait_for_timeout(400)
    check("[ana18] PGN sans coup refusé : modale ouverte avec un message", page.locator("textarea").count() == 1 and page.locator("p.text-red-400").is_visible())
    page.touchscreen.tap(196, 40)  # hors de la modale
    page.wait_for_timeout(400)
    check("[ana18] la partie en cours est intacte", chips(page) == 2, f"({chips(page)})")
    page.close()

    # ---------- ANA-5 : nom d'ouverture long ----------
    for label, standalone in (("852", True), ("660", False)):
        c5 = ctx if standalone else mobile_context(p, browser, ck)
        page = open_analysis(c5)
        load_text(page, PGN_LONG_OPENING)
        geo = page.evaluate(
            """() => {
              const board = document.querySelector("[data-square='a1']").closest('.boardbox, .w-full').getBoundingClientRect()
              const banner = [...document.querySelectorAll('main div.truncate')].find((d) => d.offsetParent && /espagnole|Ruy|Hors/.test(d.textContent))
              const m = document.querySelector('main')
              return { x: board.x, w: board.width, banner: banner ? banner.getBoundingClientRect().width : -1,
                       text: banner ? banner.textContent : '', mainOverflow: m.scrollWidth - m.clientWidth }
            }"""
        )
        check(f"[ana5-{label}] bandeau d'ouverture présent et long", len(geo["text"]) > 30, f"({geo['text']!r})")
        check(f"[ana5-{label}] échiquier dans l'écran (x >= 0)", geo["x"] >= 0, f"(x={geo['x']})")
        check(f"[ana5-{label}] échiquier centré", abs(geo["x"] - (393 - geo["w"]) / 2) <= 1, f"(x={geo['x']}, w={geo['w']})")
        check(f"[ana5-{label}] bandeau pas plus large que l'échiquier", 0 < geo["banner"] <= geo["w"] + 1, f"({geo['banner']} vs {geo['w']})")
        check(f"[ana5-{label}] aucun débordement horizontal", geo["mainOverflow"] <= 0 and overflow_x(page) <= 0,
              f"(main {geo['mainOverflow']}, page {overflow_x(page)})")
        shot(page, f"l3_ana5_{label}")
        page.close()
        if not standalone:
            c5.close()

    # ---------- ANA-31 : ?game=<id inconnu> ----------
    page = open_analysis(ctx, hash_query="?game=99999&review=1")
    ck.appears("[ana31] message « partie introuvable »", page, "[role='alert']:has-text('introuvable')", timeout=8000)
    shot(page, "l3_ana31_toast")
    page.wait_for_timeout(300)
    check("[ana31] URL nettoyée", page.evaluate("location.hash") == "#/analyse", f"({page.evaluate('location.hash')})")
    page.close()

    # ---------- CP-4 : partie archivée sans aucun coup (abandon immédiat), bilan demandé ----------
    empty_id = seed_game(ctx, {"date": 1758100000000, "mode": "bot", "botId": "noa", "playerColor": "w", "timeControl": "5+0",
                               "timeClass": "blitz", "pgn": '[Event "Partie vs Noa"]\n[Result "0-1"]\n\n0-1', "result": "0-1", "termination": "abandon"})
    page = ctx.new_page()
    page.goto(f"{BASE}/#/analyse?game={empty_id}&review=1")
    page.wait_for_selector("[data-square='e4']", timeout=30000)
    ck.appears("[cp4] message « partie vide »", page, "[role='alert']:has-text('vide')", timeout=8000)
    page.wait_for_timeout(1500)
    start = page.locator("button:visible", has_text="Démarrer le bilan")
    check("[cp4] aucun résumé de bilan pour une partie sans coup", start.count() == 0, f"({start.count()} bouton(s))")
    if start.count():
        start.first.click()  # sans correctif : pageerror « reading 'san' » et écran blanc
        page.wait_for_timeout(600)
    check("[cp4] l'app reste montée", root_len(page) > 1000, f"(root {root_len(page)} car.)")
    check("[cp4] URL nettoyée", page.evaluate("location.hash") == "#/analyse", f"({page.evaluate('location.hash')})")
    page.close()

    # ---------- PERF-1 : la recherche live s'arrête d'elle-même à la profondeur cible ----------
    page = ctx.new_page()
    page.add_init_script(UCI_DEPTH_SPY)
    uci = watch_uci(page)
    page.goto(f"{BASE}/?debug-uci#/analyse")
    page.wait_for_selector("[data-square='e4']", timeout=30000)
    ck.appears("[perf1] lignes moteur affichées", page, ENGINE_LINE, timeout=30000)
    check("[perf1] recherche infinie lancée", "go infinite" in uci["sent"], f"({uci['sent'][-3:]})")
    # Atteindre la profondeur 22 en MultiPV 3 prend de quelques secondes à plusieurs minutes selon la
    # charge de la machine : on attend le moteur tant qu'il progresse, sans échéance murale. Le check
    # reste décidable : un moteur qui dépasse la cible sans `stop` (correctif absent) atteint la
    # profondeur cible + 2 et échoue aussitôt ; un moteur qui ne progresse plus échoue au bout de
    # STALL_S. Tout est relevé dans la page (journal de chaque worker) : même ordre que l'app.
    outcome = wait_live_self_stop(page)
    check("[perf1] `stop` envoyé sans aucune action de l'utilisateur, à la profondeur cible", outcome["ok"], f"({outcome})")
    n_go = sum(c.startswith("go") for c in uci["sent"])
    page.wait_for_timeout(2000)
    check("[perf1] aucune relance après l'arrêt", sum(c.startswith("go") for c in uci["sent"]) == n_go, f"({uci['sent'][-4:]})")
    check("[perf1] `bestmove` reçu (le moteur est vraiment au repos)",
          wait_until(page, lambda: any(r.startswith("bestmove") for r in uci["recv"]), 15000), f"({uci['recv'][-3:]})")
    check("[perf1] les lignes restent affichées après l'arrêt", page.locator(ENGINE_LINE).count() >= 1)
    page.close()

    # ---------- ANA-10 : « Moteur : désactivé » arrête vraiment Stockfish ; PERF-2 : page cachée ----------
    page = ctx.new_page()
    uci = watch_uci(page)
    page.goto(f"{BASE}/?debug-uci#/analyse")
    page.wait_for_selector("[data-square='e4']", timeout=30000)
    page.wait_for_timeout(500)
    load_text(page, PGN_DENSE)
    ck.appears("[ana10] lignes moteur affichées sur le milieu de partie", page, ENGINE_LINE, timeout=30000)
    sent = uci["sent"]
    last_go = max((i for i, c in enumerate(sent) if c == "go infinite"), default=len(sent))
    # Garde : la recherche live doit être encore en cours au moment de la coupure, sinon le check suivant ne prouve rien.
    check("[ana10] recherche live encore en cours avant la coupure", last_go < len(sent) and "stop" not in sent[last_go + 1:], f"({sent[-4:]})")
    mark = len(sent)
    toggle_engine(page, "activé")
    page.wait_for_timeout(1500)
    after = uci["sent"][mark:]
    check("[ana10] commande UCI `stop` envoyée à la coupure", "stop" in after, f"(après coupure : {after})")
    check("[ana10] aucun `go` après la coupure", not any(c.startswith("go") for c in after), f"({after})")
    labels = []
    for _ in range(4):
        labels.append(eval_label(page))
        page.wait_for_timeout(700)
    check("[ana10] la barre d'éval ne bouge plus", len(set(labels)) == 1, f"({labels})")
    mark = len(uci["sent"])
    tap_move(page, "h2", "h3")
    page.wait_for_timeout(1200)
    check("[ana10] coup joué moteur coupé : toujours aucun `go`", chips(page) == 43 and not any(c.startswith("go") for c in uci["sent"][mark:]),
          f"({chips(page)} coups, {uci['sent'][mark:]})")
    toggle_engine(page, "désactivé")
    ck.appears("[ana10] moteur réactivé : les lignes reviennent", page, ENGINE_LINE, timeout=30000)
    check("[ana10] moteur réactivé : `go infinite` renvoyé", "go infinite" in uci["sent"][mark:], f"({uci['sent'][mark:]})")

    mark = len(uci["sent"])
    page.evaluate(
        """() => {
          const proto = Document.prototype
          window.__vis = { hidden: Object.getOwnPropertyDescriptor(proto, 'hidden'), state: Object.getOwnPropertyDescriptor(proto, 'visibilityState') }
          Object.defineProperty(proto, 'hidden', { get: () => true, configurable: true })
          Object.defineProperty(proto, 'visibilityState', { get: () => 'hidden', configurable: true })
          document.dispatchEvent(new Event('visibilitychange'))
        }"""
    )
    page.wait_for_timeout(1500)
    after = uci["sent"][mark:]
    check("[perf2] page cachée : `stop` envoyé", "stop" in after, f"({after})")
    check("[perf2] page cachée : aucun `go`", not any(c.startswith("go") for c in after), f"({after})")
    mark = len(uci["sent"])
    page.evaluate(
        """() => {
          Object.defineProperty(Document.prototype, 'hidden', window.__vis.hidden)
          Object.defineProperty(Document.prototype, 'visibilityState', window.__vis.state)
          document.dispatchEvent(new Event('visibilitychange'))
        }"""
    )
    check("[perf2] page de nouveau visible : recherche relancée", wait_until(page, lambda: "go infinite" in uci["sent"][mark:], 5000), f"({uci['sent'][mark:]})")
    page.close()

    # ---------- CP-6 : jamais une ligne de l'ancienne position avec le signe du nouveau trait ----------
    page = open_analysis(ctx)
    load_text(page, PGN_PLUS6)
    ck.appears("[cp6] lignes moteur affichées", page, ENGINE_LINE, timeout=30000)
    page.wait_for_timeout(2500)
    page.evaluate(
        """() => {
          window.__labels = []
          window.__sampling = true
          const tick = () => {
            const el = document.querySelector('main .bg-neutral-800 span')
            if (el) window.__labels.push(el.textContent)
            if (window.__sampling) requestAnimationFrame(tick)
          }
          requestAnimationFrame(tick)
        }"""
    )
    for _ in range(3):
        page.locator("main button:visible", has_text="Précédent").click()
        page.wait_for_timeout(700)
        page.locator("main button:visible", has_text="Suivant").click()
        page.wait_for_timeout(700)
    labels = page.evaluate("() => { window.__sampling = false; return window.__labels }")
    positive = [l for l in labels if l.startswith("+") and float(l[1:].replace(",", ".")) >= 3]
    negative = [l for l in labels if l.startswith("-")]
    # Seuil de relevés aligné sur CP-6 bis : sous charge, Chromium ne peint qu'environ 7 images par
    # seconde pendant la recherche infinie (57 à 79 relevés sur les 6 navigations), 60 échouait au hasard.
    check("[cp6] échantillonnage utile (des évals à +3 ou plus relevées)", len(labels) > 30 and len(positive) > 10, f"({len(labels)} frames, {len(positive)} positives)")
    check("[cp6] aucun libellé de signe inversé pendant 6 navigations", not negative, f"({sorted(set(negative))} sur {len(labels)} frames)")
    page.close()

    # ---------- CP-6 bis : avantage noir (mat et matériel), le bug vu sur iPhone ----------
    # « La barre passe en blanc le temps que l'ordinateur réévalue, puis repasse en noir. »
    # Chaque position du parcours est gagnante pour les Noirs : un remplissage blanc > 50 % ou un
    # libellé positif ne peut venir que d'une éval de l'ancienne position avec le signe du nouveau trait.
    for tag, text, steps in (("cp6-mat", PGN_BLACK_MATE, 4), ("cp6-noir", PGN_BLACK_UP, 5)):
        page = open_analysis(ctx)
        load_text(page, text)
        ck.appears(f"[{tag}] lignes moteur affichées", page, ENGINE_LINE, timeout=30000)
        page.wait_for_timeout(1500)
        start_bar_sampler(page)
        for _ in range(steps):  # positions jamais analysées : recalcul à chaque pas
            page.locator("main button:visible", has_text="Précédent").click()
            page.wait_for_timeout(700)
        for _ in range(2):  # allers-retours sur des positions déjà analysées
            for btn in ("Suivant", "Précédent"):
                for _ in range(steps):
                    page.locator("main button:visible", has_text=btn).click()
                    page.wait_for_timeout(350)
        frames = stop_bar_sampler(page)
        black = [f for f in frames if f["share"] < 50]
        inverted = [f for f in frames if f["share"] > 50 or f["label"].startswith("+")]
        check(f"[{tag}] échantillonnage utile (barre côté noir relevée)", len(frames) > 30 and len(black) > 10,
              f"({len(frames)} relevés, {len(black)} côté noir)")
        check(f"[{tag}] la barre ne passe jamais côté blanc pendant le recalcul", not inverted,
              f"({len(inverted)} relevés inversés sur {len(frames)} : {inverted[:4]})")
        # Retomber au neutre pendant le recalcul (« M4 » puis « 0,00 » puis « M4 ») est le même saut, à moitié.
        neutral = [f for f in frames if f["label"] == "0,00" or f["share"] == 50]
        check(f"[{tag}] la barre ne retombe jamais au neutre pendant le recalcul", not neutral,
              f"({len(neutral)} relevés neutres sur {len(frames)})")
        page.close()

    # ---------- Lignes moteur : typographie d'un mat (« -M1 », pas « (M1 (adv.)) ») ----------
    for tag, fen, score, move in (("lignes-noir", FEN_BLACK_M1, "-M1", "1… ♜a8#"), ("lignes-blanc", FEN_WHITE_M1, "M1", "1. ♖a8#")):
        page = open_analysis(ctx)
        load_text(page, fen)
        got = wait_until(page, lambda: any("M1" in r["text"] for r in page.evaluate(ENGINE_LINES_JS)["rows"]), 30000)
        info = page.evaluate(ENGINE_LINES_JS)
        first = info["rows"][0]["text"] if info["rows"] else ""
        check(f"[{tag}] ligne principale « {score} » en tête", got and (first == score or first.startswith(score + " ")), f"({first!r})")
        check(f"[{tag}] ni parenthèses ni « adv. »", got and "(" not in first and "adv" not in first, f"({first!r})")
        check(f"[{tag}] coups numérotés en figurines (« {move} »)", move in first, f"({first!r})")
        check(f"[{tag}] zone de 38 px, lignes de 17 px (l'échiquier ne bouge pas)",
              info["zoneH"] == 38 and all(r["h"] == 17 for r in info["rows"]), f"(zone {info['zoneH']}, lignes {[r['h'] for r in info['rows']]})")
        shot(page, f"analysis_lignes_{tag}")
        page.close()

    # ---------- ANA-9 : « Mes erreurs » = fautes du joueur, avec le libellé de la partie ----------
    # Table `mistakes` partagée avec les scénarios précédents (le bilan d'ANA-1 y écrit sous
    # « Partie analysée ») : vidée avant, pour ne lire que les fautes de la partie semée.
    page = ctx.new_page()
    page.goto(f"{BASE}/#/archive")
    page.wait_for_timeout(1500)
    idb(page, "const tx = db.transaction('mistakes', 'readwrite'); tx.objectStore('mistakes').clear();"
              "tx.oncomplete = () => resolve(true); tx.onerror = () => reject(tx.error)")
    page.close()
    game = {"date": 1758200000000, "mode": "bot", "botId": "noa", "playerColor": "b", "timeControl": "5+0",
            "timeClass": "blitz", "pgn": PGN_BOTH_ERR, "result": "1-0", "termination": "abandon"}
    game_id = seed_game(ctx, game)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/analyse?game={game_id}&review=1")
    if ck.appears("[ana9] bilan lancé depuis l'archive", page, "button:has-text('Démarrer le bilan')", timeout=180000):
        page.wait_for_timeout(1500)  # écritures Dexie de recordMistakes
        rows = idb(
            page,
            "const r = db.transaction('mistakes').objectStore('mistakes').getAll(); r.onsuccess = () => resolve(r.result); r.onerror = () => reject(r.error)",
        )
        brief = [(r["fenBefore"].split(" ")[1], r["playedSan"], r["cls"], r["gameLabel"]) for r in rows]
        check("[ana9] la faute du joueur (noirs) est enregistrée", any(t == "b" for t, *_ in brief), f"({brief})")
        check("[ana9] aucune faute de l'adversaire (blancs) dans Mes erreurs", all(t == "b" for t, *_ in brief), f"({brief})")
        check("[ana9] libellé de la partie conservé", bool(brief) and all(lbl == "5+0 · 1-0 abandon" for *_, lbl in brief), f"({brief})")
    page.close()

    # ---------- CP-7 : quitter la page avant le lancement différé du bilan ----------
    page = ctx.new_page()
    # Quitter pendant le bilan, recherche en vol : le toucher part de la page au premier `go depth`.
    # Depuis Python, il arrivait soit avant le montage d'Analyse (aucun moteur, check vide), soit
    # après la fin du bilan, dont le résumé recouvre la navigation (clic intercepté sous charge).
    page.add_init_script(LEAVE_ON_REVIEW)
    page.goto(f"{BASE}/#/analyse?game={game_id}&review=1")
    check("[cp7] Analyse quittée pendant le bilan", wait_until(page, lambda: page.evaluate("window.__leftOnReview") is True, 60000))
    ck.appears("[cp7] Archive affichée après avoir quitté pendant le lancement du bilan", page, "main h1:has-text('Archive')", timeout=30000)
    check("[cp7] aucun worker Stockfish orphelin après avoir quitté pendant le lancement du bilan", no_workers(page),
          f"({len(page.workers)} worker(s), hash {page.evaluate('location.hash')})")
    page.close()
    cp7_slow_chunk(p, browser, game)

    # ---------- CP-2 : coup ajouté en bout de ligne après un bilan, puis Bilan > Démarrer ----------
    page = open_analysis(ctx)
    load_text(page, "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6")
    bilan_btn(page).click()
    if ck.appears("[cp2] premier bilan", page, "button:has-text('Démarrer le bilan')", timeout=120000):
        page.locator("button:visible", has_text="✕").click()
        page.locator("button[data-current]:visible").last.click()
        page.wait_for_timeout(400)
        check("[cp2] bilan visible avant le coup ajouté", review_shown(page))
        tap_move(page, "b5", "a4")
        check("[cp2] 7e demi-coup ajouté", chips(page) == 7, f"({chips(page)})")
        check("[cp2] le bilan de 6 demi-coups n'est plus plaqué sur la ligne de 7", not review_shown(page))
        bilan_btn(page).click()
        if ck.appears("[cp2] bilan de la nouvelle ligne", page, "button:has-text('Démarrer le bilan')", timeout=120000):
            sums = tally_sums(page)
            check("[cp2] le bilan couvre les 7 demi-coups", sums == [4, 3], f"({sums})")
            page.locator("button:visible", has_text="Démarrer le bilan").click()
            page.wait_for_timeout(800)
            check("[cp2] la vue guidée s'affiche (pas d'écran blanc)", root_len(page) > 1000 and chips(page) == 7,
                  f"(root {root_len(page)} car., {chips(page)} coups)")
    page.close()
    ctx.close()

    # ---------- ANA-2 / ANA-3 : un bilan en vol est invalidé dès que la ligne change ----------
    deep = mobile_context(p, browser, ck, settings={"reviewDepth": "deep"}, standalone=True)

    # ANA-2 : coup joué pendant le calcul, puis tap sur le graphe.
    page = open_analysis(deep)
    load_text(page, PGN_MEDIUM)
    check("[ana2] 48 demi-coups chargés", chips(page) == 48, f"({chips(page)})")
    bilan_btn(page).click()
    page.wait_for_timeout(1200)
    page.locator("button[data-current]:visible").nth(9).click()
    page.wait_for_timeout(400)
    check("[ana2] bilan en cours au moment de jouer", bilan_btn(page).is_disabled())
    tap_move(page, "a2", "a3")
    check("[ana2] variante jouée : ligne tronquée à 11 demi-coups", chips(page) == 11, f"({chips(page)})")
    check("[ana2] bouton Bilan réactivé tout de suite", wait_until(page, lambda: not bilan_btn(page).is_disabled(), 3000))
    stale = settle_review(page)
    check("[ana2] le bilan de l'ancienne ligne ne s'affiche jamais", not stale)
    if not stale:
        bilan_btn(page).click()
    if ck.appears("[ana2] résumé du bilan", page, "button:has-text('Démarrer le bilan')", timeout=300000):
        sums = tally_sums(page)
        check("[ana2] le bilan affiché est celui des 11 demi-coups", sums == [6, 5], f"({sums})")
        shot(page, "l3_ana2_summary")
        g = page.locator(".fixed svg.cursor-pointer").first.bounding_box()
        page.touchscreen.tap(g["x"] + g["width"] * 0.9, g["y"] + g["height"] / 2)
        page.wait_for_timeout(1000)
        check("[ana2] tap sur le graphe : vue guidée, pas d'écran blanc", root_len(page) > 1000 and chips(page) == 11,
              f"(root {root_len(page)} car., {chips(page)} coups)")
        shot(page, "l3_ana2_after_graph_tap")
    page.close()

    # ANA-3 : réimport pendant le calcul.
    page = deep.new_page()
    uci = watch_uci(page)
    page.goto(f"{BASE}/?debug-uci#/analyse")
    page.wait_for_selector("[data-square='e4']", timeout=30000)
    page.wait_for_timeout(800)
    load_text(page, PGN_MEDIUM)
    bilan_btn(page).click()
    page.wait_for_timeout(1500)
    check("[ana3] bilan en cours au moment du réimport", bilan_btn(page).is_disabled() and any(c.startswith("go depth") for c in uci["sent"]), f"({uci['sent'][-3:]})")
    load_text(page, PGN_SHORT)
    check("[ana3] partie courte chargée", chips(page) == 14, f"({chips(page)})")
    check("[ana3] bouton Bilan de nouveau disponible tout de suite", wait_until(page, lambda: not bilan_btn(page).is_disabled(), 3000))
    page.wait_for_timeout(2500)  # au plus une recherche en vol s'achève (le mutex ne s'interrompt pas)
    n1 = sum(c.startswith("go depth") for c in uci["sent"])
    page.wait_for_timeout(5000)
    n2 = sum(c.startswith("go depth") for c in uci["sent"])
    check("[ana3] l'ancien bilan ne lance plus de recherche", n1 == n2, f"({n1} -> {n2} `go depth`)")
    stale = settle_review(page)
    check("[ana3] l'ancien bilan ne s'affiche pas sur la nouvelle partie", not stale)
    if not stale:
        bilan_btn(page).click()
    if ck.appears("[ana3] résumé du bilan", page, "button:has-text('Démarrer le bilan')", timeout=300000):
        sums = tally_sums(page)
        check("[ana3] le bilan affiché est celui de la partie courte (7 + 7)", sums == [7, 7], f"({sums})")
        shot(page, "l3_ana3_summary")
    page.close()
    deep.close()
    browser.close()


ck.run(suite)
