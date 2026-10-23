"""E2E « Accueil quotidien » (lot 4 du plan UX, docs/ux-refonte.md) : une action prioritaire, la
révision due en ligne secondaire sans double comptage, deux raccourcis, puis la progression.

Deux volets :
- banc Node (src/lib/homePlan.ts bundlé par rolldown) : priorité déterministe (séance en cours,
  partie en cours, séance du jour, séance rapide), révisions déjà comptées par la séance du jour
  (nouvelle séance, séance en cours, séance faite), libellés, début de semaine (lundi local, passage
  à l'heure d'été sous TZ=Europe/Paris) et activité de la semaine ;
- parcours UI (iPhone 14 Pro, base semée nativement après création du schéma, service worker
  bloqué, `puzzles.json` jamais demandé par l'accueil) : profil neuf, dû compris dans la séance,
  dû au-delà de la séance, séance faite puis séance rapide, séance en cours reprise, partie en cours
  reprise, les deux reprises ensemble, compteur de révision indisponible, et les trois formats
  (393x660 PWA avec zones sûres émulées, 393x852, 1440x900) : CTA principal entier au-dessus de la
  nav, aucun débordement horizontal, captures `accueil_*` dans e2e/shots/.

Usage : npm run test:e2e -- --suite accueil
        npm run test:e2e:dev -- --suite accueil      (StrictMode : effets et updaters doublés)
"""
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime

from helpers import BASE, Checker, desktop_context, mobile_context, overflow_x, shot

ck = Checker("accueil")
check = ck.check

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(E2E_DIR)
ROLLDOWN = os.path.join(ROOT, "node_modules", ".bin", "rolldown")
SAFE_TOP, SAFE_BOTTOM = 59, 34

DAY = 86_400_000
TODAY0 = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)


def ago(days=0):
    """Midi il y a `days` jours ; `days=0` : aujourd'hui, une minute après minuit."""
    return TODAY0 + 60_000 if days == 0 else TODAY0 - days * DAY + DAY // 2


# ================================================================== banc Node

BENCH_JS = r"""
const m = await import(process.argv[2])
const out = {}
const seance = (over = {}) => ({ idx: 2, total: 9, kind: 'puzzles', pendingRevisions: ['puzzle:R2'], ...over })
const game = { mode: 'bot', botName: 'Iris', color: 'b', tcLabel: '10 min', plies: 5 }
out.priority = {
  fresh_pending: m.homePrimary({ seance: null, game: null, doneToday: null }).kind,
  fresh: m.homePrimary({ seance: null, game: null, doneToday: false }).kind,
  done: m.homePrimary({ seance: null, game: null, doneToday: true }).kind,
  seance_over_game: m.homePrimary({ seance: seance(), game, doneToday: true }).kind,
  game_over_seance_du_jour: m.homePrimary({ seance: null, game, doneToday: false }).kind,
  game_pending: m.homePrimary({ seance: null, game, doneToday: null }).kind,
}
const due = ['puzzle:R1', 'puzzle:R2', 'mistake:1', 'variant:w:e2e4', 'puzzle:R3', 'mistake:2']
const fresh = ['puzzle:R1', 'mistake:1', 'variant:w:e2e4', 'puzzle:R2']
out.claimed = {
  fresh: m.revisionsInSeance({ due, seance: null, doneToday: false, fresh }),
  done: m.revisionsInSeance({ due, seance: null, doneToday: true, fresh }),
  unknown: m.revisionsInSeance({ due, seance: null, doneToday: null, fresh }),
  resumed: m.revisionsInSeance({ due, seance: seance({ pendingRevisions: ['puzzle:R2', 'mistake:9'] }), doneToday: true, fresh }),
  resumed_none: m.revisionsInSeance({ due, seance: seance({ pendingRevisions: [] }), doneToday: false, fresh }),
}
out.block = [0, 1, 4, 5, 12].map(m.revisionBlockSize)
out.lines = [m.revisionLine(6, 0, '6 puzzles'), m.revisionLine(6, 4, '1 puzzle · 1 faute'), m.revisionLine(2, 2, '1 puzzle · 1 faute'), m.revisionLine(1, 1, '1 faute')]
out.step = m.seanceStepLabel(seance())
out.games = [
  [m.gameTitle(game), m.gameMeta(game)],
  [m.gameTitle({ ...game, botName: null }), m.gameMeta({ ...game, color: 'w', plies: 0 })],
  [m.gameTitle({ ...game, mode: 'coach' }), m.gameMeta({ ...game, mode: 'local', tcLabel: 'Illimité', plies: 40 })],
]
const d = (y, mo, day, h = 12) => new Date(y, mo, day, h).getTime()
const iso = (t) => { const x = new Date(t); return [x.getFullYear(), x.getMonth() + 1, x.getDate(), x.getHours(), x.getMinutes()].join('-') }
out.week = {
  thursday: iso(m.weekStart(d(2026, 9, 22))), // jeudi 22 octobre 2026
  monday: iso(m.weekStart(d(2026, 9, 19, 0))), // lundi 0 h
  sunday: iso(m.weekStart(d(2026, 9, 25, 23))), // dimanche 23 h
  dst: iso(m.weekStart(d(2026, 2, 29, 12))), // dimanche 29 mars 2026, jour du passage à l'heure d'été
}
out.summary = [
  m.weekSummary({ seances: 0, puzzles: 0, games: 0 }),
  m.weekSummary({ seances: 1, puzzles: 12, games: 0 }),
  m.weekSummary({ seances: 3, puzzles: 1, games: 2 }),
]
console.log(JSON.stringify(out))
"""

# homePlan.ts n'exporte pas revisionBlockSize : le banc l'importe de seance.ts, même bundle.
ENTRY_TS = "export * from './homePlan'\nexport { revisionBlockSize } from './seance'\n"


def node_bench():
    with tempfile.TemporaryDirectory() as d:
        entry = os.path.join(ROOT, "src", "lib", f".accueil-entry-{os.getpid()}.ts")
        bundle = os.path.join(d, "home.mjs")
        try:
            with open(entry, "w", encoding="utf-8") as f:
                f.write(ENTRY_TS)
            r = subprocess.run([ROLLDOWN, entry, "--format", "esm", "--file", bundle], cwd=ROOT, capture_output=True, text=True, timeout=120)
        finally:
            os.remove(entry)
        if r.returncode != 0:
            ck.fail("[banc] bundle rolldown de homePlan.ts", (r.stderr or r.stdout)[-300:])
            return None
        script = os.path.join(d, "bench.mjs")
        with open(script, "w", encoding="utf-8") as f:
            f.write(BENCH_JS)
        r = subprocess.run(["node", script, "file://" + bundle], cwd=ROOT, capture_output=True, text=True, timeout=120, env={**os.environ, "TZ": "Europe/Paris"})
    if r.returncode != 0:
        ck.fail("[banc] homePlan.ts sous Node", r.stderr.strip()[-400:])
        return None
    return json.loads(r.stdout.strip().splitlines()[-1])


def part_bench():
    out = node_bench()
    if out is None:
        return
    pr = out["priority"]
    check("[priorité] profil neuf, série pas encore lue : carte en attente", pr["fresh_pending"] == "pending", f"({pr})")
    check("[priorité] sans reprise : séance du jour", pr["fresh"] == "seance", f"({pr})")
    check("[priorité] séance du jour faite : séance rapide", pr["done"] == "quick", f"({pr})")
    check("[priorité] séance en cours avant partie en cours", pr["seance_over_game"] == "resume-seance", f"({pr})")
    check("[priorité] partie en cours avant séance du jour", pr["game_over_seance_du_jour"] == "resume-game", f"({pr})")
    check("[priorité] reprise de partie sans attendre la série", pr["game_pending"] == "resume-game", f"({pr})")
    cl = out["claimed"]
    check("[double comptage] nouvelle séance : les révisions qu'elle reprendrait, dans l'ordre de la file",
          cl["fresh"] == ["puzzle:R1", "puzzle:R2", "mistake:1", "variant:w:e2e4"], f"({cl['fresh']})")
    check("[double comptage] séance faite : aucune révision comptée par la séance", cl["done"] == [], f"({cl['done']})")
    check("[double comptage] série inconnue : aucune", cl["unknown"] == [], f"({cl['unknown']})")
    check("[double comptage] séance en cours : ses révisions non jugées et encore dues seulement", cl["resumed"] == ["puzzle:R2"], f"({cl['resumed']})")
    check("[double comptage] séance en cours sans révision restante : aucune", cl["resumed_none"] == [], f"({cl['resumed_none']})")
    check("[double comptage] règle de seance.ts : 4 révisions au plus", out["block"] == [0, 1, 4, 4, 4], f"({out['block']})")
    check("[libellés] ligne de révision", out["lines"] == ["6 puzzles", "4 dans ta séance du jour, en plus : 1 puzzle · 1 faute", "Toutes dans ta séance du jour : 1 puzzle · 1 faute", "Dans ta séance du jour : 1 faute"], f"({out['lines']})")
    check("[libellés] étape de la séance en cours", out["step"] == "Étape 3 sur 9 · Puzzles à ton niveau", f"({out['step']!r})")
    check("[libellés] parties en cours", out["games"] == [
        ["Partie contre Iris", "10 min · coup 3 · tu as les Noirs"],
        ["Partie contre un bot", "10 min · coup 1 · tu as les Blancs"],
        ["Partie avec le coach", "Illimité · coup 21"],
    ], f"({out['games']})")
    wk = out["week"]
    check("[semaine] jeudi : lundi 0 h de la même semaine", wk["thursday"] == "2026-10-19-0-0", f"({wk})")
    check("[semaine] lundi 0 h : lui-même", wk["monday"] == "2026-10-19-0-0", f"({wk})")
    check("[semaine] dimanche soir : lundi précédent", wk["sunday"] == "2026-10-19-0-0", f"({wk})")
    check("[semaine] jour du passage à l'heure d'été : lundi 23 mars 0 h", wk["dst"] == "2026-3-23-0-0", f"({wk})")
    check("[semaine] activité", out["summary"] == [
        "Rien encore cette semaine : ton bilan se remplit en jouant",
        "Cette semaine : 1 séance · 12 puzzles réussis",
        "Cette semaine : 3 séances · 1 puzzle réussi · 2 parties",
    ], f"({out['summary']})")


# ================================================================== base semée

TABLES = sorted(["games", "ratings", "puzzleAttempts", "rushScores", "mistakes", "learnSessions", "reviews"])
OPEN_DB = """
() => new Promise((res, rej) => {
  const r = indexedDB.open('chess-local')
  r.onsuccess = () => res(r.result)
  r.onerror = () => rej(r.error)
})
"""
MISTAKE_FEN = "3q2k1/5ppp/8/8/8/8/5PPP/3Q2K1 w - - 0 1"
# Fichiers du compteur de révision (import dynamique de Home.tsx) : chunk du build, module du serveur de dev.
REVISION_CHUNK = re.compile(r"/(assets/revision-[^/]*\.js|src/lib/revision\.ts)(\?.*)?$")


def wait_schema(page, tries=40):
    for _ in range(tries):
        tables = page.evaluate(
            """() => new Promise((res) => {
              indexedDB.databases().then((list) => {
                if (!list.some((d) => d.name === 'chess-local')) return res(0)
                const r = indexedDB.open('chess-local')
                r.onsuccess = () => { const t = Array.from(r.result.objectStoreNames).sort(); r.result.close(); res(t) }
                r.onerror = () => res(-1)
              })
            })"""
        )
        if tables == TABLES:
            return True
        page.wait_for_timeout(250)
    return False


def seed_db(page, data):
    page.evaluate(
        "async (data) => {"
        f"  const db = await ({OPEN_DB})()"
        """
          const tx = db.transaction(Object.keys(data), 'readwrite')
          for (const [t, rows] of Object.entries(data)) for (const r of rows) tx.objectStore(t).put(r)
          await new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = () => rej(tx.error); tx.onabort = () => rej(tx.error) })
          db.close()
        }""",
        data,
    )


def ls(i, domain, item, date, ok, **extra):
    return {"id": i, "date": date, "domain": domain, "itemId": item, "success": 1 if ok else 0, "ratingAfter": None, **extra}


def failed_puzzles(n):
    return [{"id": i + 1, "puzzleId": f"R{i + 1}", "date": ago(5), "success": False, "puzzleRating": 820, "ratingAfter": 790} for i in range(n)]


MISTAKE = {"id": 1, "date": ago(10), "gameLabel": "Partie 1", "fenBefore": MISTAKE_FEN, "playedSan": "h3", "bestUci": "d1d8", "cls": "blunder", "attempts": 0, "solved": 0}
# Partie de Jouer en cours, au format de lib/playSession.ts (Play.tsx la reprend à son montage).
STORED_GAME = {"mode": "bot", "botId": "iris", "botName": "Iris", "playerColor": "w", "tcLabel": "10 min",
               "sans": ["e4", "e5", "Nf3", "Nc6"], "clocks": {"w": 590000, "b": 595000}, "unrated": False, "lastWhiteCp": 30}


def context(p, browser, fmt="660", puzzles_requests=None):
    """Contexte iPhone (660 : PWA 393x660 avec zones sûres émulées ; 852 : PWA 393x852) ou desktop.
    `puzzles.json` répond 404 (la séance s'en passe) et chaque demande est notée : l'accueil ne doit
    jamais le charger."""
    if fmt == "desktop":
        ctx = desktop_context(browser, ck, service_workers="block")
    else:
        ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block",
                             **({"viewport": {"width": 393, "height": 660}} if fmt == "660" else {}))

    def puzzles(route):
        if puzzles_requests is not None:
            puzzles_requests.append(route.request.url)
        route.fulfill(status=404, body="absent")
    ctx.route("**/puzzles.json", puzzles)
    page = ctx.new_page()
    if fmt == "660":
        page.context.new_cdp_session(page).send("Emulation.setSafeAreaInsetsOverride", {"insets": {"top": SAFE_TOP, "bottom": SAFE_BOTTOM}})
    return ctx, page


def seeded(p, browser, data, fmt="660", game=None, puzzles_requests=None):
    ctx, page = context(p, browser, fmt, puzzles_requests)
    page.goto(f"{BASE}/#/archive")
    ck.appears("[seed] Archive chargée (base ouverte)", page, "main h1:has-text('Archive')", timeout=15000)
    if check("[seed] schéma courant créé par l'app", wait_schema(page)) and data:
        seed_db(page, data)
    if game is not None:
        page.evaluate("(g) => localStorage.setItem('chess-local-play-game', JSON.stringify({ ...g, savedAt: Date.now() }))", game)
    return ctx, page


def open_home(page, tag):
    page.goto(f"{BASE}/#/")
    ok = ck.appears(f"[{tag}] accueil prêt (révision et série lues)", page, "[data-testid=home][data-review-ready]", timeout=15000, state="attached")
    page.wait_for_timeout(150)
    return ok


def primary(page):
    return page.locator("[data-testid=home]").get_attribute("data-home-primary")


def text_of(page, selector):
    loc = page.locator(selector)
    return loc.first.inner_text().strip() if loc.count() else ""


def card_text(page):
    return text_of(page, "[data-home-card]")


def cta(page):
    return page.locator("[data-home-cta]")


def visible_cta(page, tag):
    """CTA principal entier dans la zone utile : sous la zone sûre haute, au-dessus de la nav basse."""
    box = cta(page).bounding_box()
    m = page.evaluate("""() => {
      const nav = [...document.querySelectorAll('nav')].find((n) => n.getBoundingClientRect().width > 0)
      const r = nav ? nav.getBoundingClientRect() : null
      const mobile = r && r.width > r.height
      return { navTop: mobile ? r.top : innerHeight, vh: innerHeight }
    }""")
    ok = box is not None and box["y"] >= 0 and box["y"] + box["height"] <= m["navTop"] + 0.5 and box["height"] >= 44
    check(f"[{tag}] CTA principal entier au-dessus de la nav, sans défiler", ok, f"(cta {box}, nav à {m['navTop']})")


def review_badge(page):
    loc = page.locator("[data-testid=home-revision] [data-review-count]")
    return loc.inner_text().strip() if loc.count() else None


def in_seance(page):
    loc = page.locator("[data-testid=home-revision]")
    return loc.get_attribute("data-review-in-seance") if loc.count() else None


def no_double_count(page, tag, total, claimed):
    """Quantité de révision affichée une seule fois : pastille = total dû ; la carte de séance nomme sa
    part (« Commence par k ») et la ligne de révision la même part, jamais un total ajouté."""
    main = page.locator("main").inner_text()
    k = re.search(r"Commence par (\d+) révision", main)
    shown_k = int(k.group(1)) if k else 0
    check(f"[{tag}] pastille = {total} dus", review_badge(page) == str(total), f"({review_badge(page)!r})")
    check(f"[{tag}] part de la séance = {claimed}, nommée sur la carte et sur la ligne", shown_k == claimed and in_seance(page) == str(claimed),
          f"(carte {shown_k}, ligne {in_seance(page)!r})")
    check(f"[{tag}] une seule pastille de quantité sur l'accueil", page.locator("main [data-review-count]").count() == 1)


def glued(page, tag, selector):
    """Coupures interdites dans les lignes de l'accueil : jamais « · » en début de ligne, jamais un nombre
    séparé du mot qui le suit (« 2 / puzzles »). La largeur du bloc est forcée de 100 à 360 px par pas
    de 2 px, pour amener une fin de ligne sur chaque espace, puis rétablie."""
    bad = page.evaluate("""(sel) => {
      const root = document.querySelector(sel)
      if (!root) return ['bloc absent']
      const top = (node, i) => { const r = document.createRange(); r.setStart(node, i); r.setEnd(node, i + 1); return r.getClientRects()[0]?.top }
      // Caractères d'un même texte rendu, dans l'ordre, avec leur nœud (le texte traverse des spans).
      const chars = []
      const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
      for (let n = walk.nextNode(); n; n = walk.nextNode()) for (let i = 0; i < n.data.length; i++) chars.push([n, i, n.data[i]])
      // Paires à garder sur une même ligne : mot avant « · » et « · », chiffre final d'un nombre et mot suivant.
      const pairs = []
      chars.forEach(([, , c], k) => {
        if (c === '·' && k >= 2) pairs.push([k - 2, k])
        if (/\d/.test(c) && chars[k + 1]?.[2] === ' ' && chars[k + 2] && /\S/.test(chars[k + 2][2]) && chars[k + 2][2] !== '·') pairs.push([k, k + 2])
      })
      const old = root.style.width
      const found = new Set()
      for (let w = 100; w <= 360; w += 2) {
        root.style.width = w + 'px'
        for (const [a, b] of pairs) {
          const ta = top(chars[a][0], chars[a][1]), tb = top(chars[b][0], chars[b][1])
          if (ta !== undefined && tb !== undefined && Math.abs(ta - tb) > 2)
            found.add(`${w}px : « ${chars.slice(Math.max(0, a - 6), b + 4).map((x) => x[2]).join('')} »`)
        }
      }
      root.style.width = old
      return pairs.length ? [...found].slice(0, 5) : ['aucun « · » ni nombre à contrôler']
    }""", selector)
    check(f"[{tag}] {selector} : ni « · » en début de ligne ni nombre séparé de son mot, à toute largeur", bad == [], f"({bad})")


# ================================================================== parcours

def part_new_profile(p, browser):
    requests = []
    ctx, page = seeded(p, browser, None, puzzles_requests=requests)
    if open_home(page, "neuf"):
        check("[neuf] carte principale : séance du jour", primary(page) == "seance", f"({primary(page)})")
        text = card_text(page)
        check("[neuf] explication brève de la séance", "Ta séance du jour" in text and "enchaînés sans avoir à choisir" in text, f"({text!r})")
        check("[neuf] CTA « Commencer »", cta(page).inner_text().strip() == "Commencer")
        check("[neuf] aucune série ni révision due annoncée", "🔥" not in text and "Commence par" not in text, f"({text!r})")
        check("[neuf] aucune ligne de révision", page.locator("[data-testid=home-revision]").count() == 0)
        main = page.locator("main").inner_text()
        check("[neuf] aucun classement présenté comme acquis (800 par défaut)", "800" not in main, f"({main[:200]!r})")
        check("[neuf] raccourcis Jouer et Puzzles", page.locator("[data-testid=home-play]").get_attribute("href") == "#/jouer"
              and page.locator("[data-testid=home-puzzles]").get_attribute("href") == "#/puzzles")
        ck.appears("[neuf] progression : bilan vide expliqué", page, "[data-testid=home-bilan]:has-text('Rien encore cette semaine')", timeout=5000)
        check("[neuf] « Voir mon bilan » mène à Mon bilan", page.locator("[data-testid=home-bilan]").get_attribute("href") == "#/insights")
        if ck.appears("[neuf] parcours : progression lue", page, "[data-testid=home][data-path-ready]", timeout=10000, state="attached"):
            prog = page.locator("[data-testid=home-path-progress]").inner_text().strip()
            check("[neuf] parcours : 0 étape validée sur le total", re.fullmatch(r"0/\d+", prog) is not None, f"({prog!r})")
        visible_cta(page, "neuf 660")
        check("[neuf] aucun débordement horizontal", overflow_x(page) <= 0)
        check("[neuf] l'accueil ne demande jamais puzzles.json", requests == [], f"({requests})")
        shot(page, "accueil_neuf_660")
        hist = page.evaluate("() => history.length")
        cta(page).click()
        ck.appears("[neuf] Commencer ouvre la séance du jour", page, "[data-seance-intro]", timeout=20000)
        check("[neuf] descente empilée vers #/seance", page.evaluate("() => location.hash") == "#/seance" and page.evaluate("() => history.length") == hist + 1)
    ctx.close()


def part_due(p, browser):
    # Deux dus (faute J-10, puzzle raté J-5), séances hier et avant-hier : la séance les reprend tous.
    data = {"puzzleAttempts": failed_puzzles(1), "mistakes": [MISTAKE],
            "learnSessions": [ls(1, "seance", "puzzles+attack", ago(1), True, score=5), ls(2, "seance", "puzzles+endgame", ago(2), True, score=4)]}
    requests = []
    ctx, page = seeded(p, browser, data, puzzles_requests=requests)
    if open_home(page, "dû inclus"):
        check("[dû inclus] carte : séance du jour", primary(page) == "seance", f"({primary(page)})")
        status = text_of(page, "[data-home-card] [data-seance-status]")
        check("[dû inclus] statut « Commence par 2 révisions dues · 🔥 2 jours »", status == "Commence par 2 révisions dues · 🔥 2 jours", f"({status!r})")
        no_double_count(page, "dû inclus", 2, 2)
        row = text_of(page, "[data-testid=home-revision]")
        check("[dû inclus] ligne : « Toutes dans ta séance du jour : 1 puzzle · 1 erreur »", "Toutes dans ta séance du jour : 1 puzzle · 1 erreur" in row, f"({row!r})")
        check("[dû inclus] pastille neutre (rien en plus de la séance)",
              "bg-amber-400" not in (page.locator("[data-testid=home-revision] [data-review-count]").get_attribute("class") or ""))
        check("[dû inclus] l'accueil ne demande jamais puzzles.json", requests == [], f"({requests})")
        glued(page, "dû inclus", "[data-testid=home-revision] .ui-card-description")
        glued(page, "dû inclus", "[data-home-card] [data-seance-status]")
        shot(page, "accueil_du_inclus_660")
        hist = page.evaluate("() => history.length")
        page.locator("[data-testid=home-revision]").click()
        ck.appears("[dû inclus] la ligne ouvre la révision", page, "main h1", timeout=10000)
        check("[dû inclus] descente empilée vers #/revision", page.evaluate("() => location.hash") == "#/revision" and page.evaluate("() => history.length") == hist + 1)
    ctx.close()

    # Six puzzles ratés : la séance en reprend quatre, la ligne annonce les deux autres.
    ctx, page = seeded(p, browser, {"puzzleAttempts": failed_puzzles(6)}, fmt="852")
    if open_home(page, "dû au-delà"):
        no_double_count(page, "dû au-delà", 6, 4)
        row = text_of(page, "[data-testid=home-revision]")
        check("[dû au-delà] ligne : « 4 dans ta séance du jour, en plus : 2 puzzles »", "4 dans ta séance du jour, en plus : 2 puzzles" in row, f"({row!r})")
        check("[dû au-delà] pastille ambrée (il reste à réviser hors séance)",
              "bg-amber-400" in (page.locator("[data-testid=home-revision] [data-review-count]").get_attribute("class") or ""))
        glued(page, "dû au-delà", "[data-testid=home-revision] .ui-card-description")
        shot(page, "accueil_du_au_dela_852")
    ctx.close()


def part_done_today(p, browser):
    data = {"puzzleAttempts": failed_puzzles(2), "learnSessions": [ls(1, "seance", "revision+puzzles", ago(0), True, score=6), ls(2, "seance", "puzzles", ago(1), True, score=4)]}
    ctx, page = seeded(p, browser, data)
    if open_home(page, "faite"):
        check("[faite] carte : séance rapide", primary(page) == "quick", f"({primary(page)})")
        status = text_of(page, "[data-seance-status]")
        check("[faite] statut « ✓ Faite aujourd'hui · 🔥 2 jours »", status == "✓ Faite aujourd'hui · 🔥 2 jours", f"({status!r})")
        check("[faite] CTA « Séance rapide »", cta(page).inner_text().strip() == "Séance rapide")
        no_double_count(page, "faite", 2, 0)
        row = text_of(page, "[data-testid=home-revision]")
        check("[faite] ligne : types des dus", "2 puzzles" in row, f"({row!r})")
        tile = page.locator("[data-seance-tile]")
        check("[faite] ligne « Refaire une séance du jour » vers #/seance", tile.count() == 1 and "Refaire une séance du jour" in tile.inner_text() and tile.get_attribute("href") == "#/seance")
        ck.appears("[faite] activité de la semaine (séance du jour comprise)", page, "[data-testid=home-bilan]:has-text('Cette semaine')", timeout=5000)
        visible_cta(page, "faite 660")
        glued(page, "faite", "[data-home-card] [data-seance-status]")
        shot(page, "accueil_faite_660")
        cta(page).click()
        ck.appears("[faite] séance rapide lancée dans Apprendre", page, "[aria-label='Quitter la séance']", timeout=20000)
        check("[faite] Apprendre, state consommé", page.evaluate("() => location.hash") == "#/apprendre" and page.evaluate("() => history.state?.usr ?? null") is None)
    ctx.close()


def learn_rows(page):
    return page.evaluate(
        "async () => {"
        f"  const db = await ({OPEN_DB})()"
        """
          const rows = await new Promise((res, rej) => {
            const r = db.transaction('learnSessions').objectStore('learnSessions').getAll()
            r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error)
          })
          db.close()
          return rows.filter((r) => r.domain !== 'seance')
        }"""
    )


def part_quick_pending(p, browser):
    """« Séance rapide » alors qu'un résultat d'Apprendre attend son enregistrement (écriture refusée
    puis onglet Accueil) : la séance en attente est reprise telle quelle, jamais remplacée."""
    data = {"learnSessions": [ls(1, "seance", "puzzles", ago(0), True, score=4)]}
    ctx, page = seeded(p, browser, data)
    if not open_home(page, "attente") or not check("[attente] carte : séance rapide", primary(page) == "quick", f"({primary(page)})"):
        ctx.close()
        return
    cta(page).click()
    if not ck.appears("[attente] séance d'Apprendre lancée", page, "[aria-label='Quitter la séance']", timeout=20000):
        ctx.close()
        return
    saved = page.evaluate("""() => {
      const s = JSON.parse(sessionStorage.getItem('learn-session-v1'))
      s.pendingResult = true
      s.phase = 'play'
      sessionStorage.setItem('learn-session-v1', JSON.stringify(s))
      return s
    }""")
    before = learn_rows(page)
    if open_home(page, "attente") and check("[attente] retour à l'accueil : séance rapide", primary(page) == "quick", f"({primary(page)})"):
        cta(page).click()
        if ck.appears("[attente] résultat en attente repris", page, "[data-testid=learn-save]:has-text('Ton résultat est conservé')", timeout=10000):
            stored = page.evaluate("() => JSON.parse(sessionStorage.getItem('learn-session-v1'))")
            check("[attente] même séance conservée", stored["session"] == saved["session"] and stored["itemIdx"] == saved["itemIdx"] and stored.get("pendingResult") is True)
            check("[attente] rien d'écrit avant l'enregistrement", learn_rows(page) == before)
            page.get_by_role("button", name="Enregistrer le résultat", exact=True).click()
            ck.appears("[attente] résultat enregistré", page, "[data-exercise-verdict]:has-text('Réussi')", timeout=10000)
            rows = learn_rows(page)
            check("[attente] une seule ligne écrite, réussie, du domaine de la séance",
                  len(rows) == len(before) + 1 and rows[-1]["domain"] == saved["session"]["domain"] and rows[-1]["success"] == 1, f"({rows})")
    ctx.close()


def part_resume_seance(p, browser):
    ctx, page = seeded(p, browser, {"mistakes": [MISTAKE]}, game=STORED_GAME)
    page.goto(f"{BASE}/#/seance")
    if ck.appears("[reprise] accueil de séance", page, "[data-seance-intro] button:has-text('Commencer')", timeout=30000):
        page.locator("[data-seance-intro] button", has_text="Commencer").click()
        ck.appears("[reprise] première étape", page, "[data-seance-item]", timeout=15000)
        page.get_by_label("Quitter la séance").click()
    if open_home(page, "reprise"):
        check("[reprise] séance en cours avant partie en cours", primary(page) == "resume-seance", f"({primary(page)})")
        text = card_text(page)
        check("[reprise] étape et type affichés", re.search(r"Étape 1 sur \d+ · Révision", text) is not None, f"({text!r})")
        status = text_of(page, "[data-home-card] [data-seance-status]")
        check("[reprise] statut « Étape 1 sur N · Révision »", re.fullmatch(r"Étape 1 sur \d+ · Révision", status) is not None, f"({status!r})")
        bar = page.locator("[data-home-card] [role=progressbar]")
        check("[reprise] progression réelle de la séance", bar.count() == 1 and bar.get_attribute("aria-valuenow") == "0" and int(bar.get_attribute("aria-valuemax") or 0) >= 2)
        check("[reprise] CTA « Reprendre la séance »", cta(page).inner_text().strip() == "Reprendre la séance")
        check("[reprise] la faute due est comptée dans la séance en cours", in_seance(page) == "1" and review_badge(page) == "1", f"({in_seance(page)!r}, {review_badge(page)!r})")
        check("[reprise] raccourci Jouer : « Partie en cours »", "Partie en cours" in page.locator("[data-testid=home-play]").inner_text())
        visible_cta(page, "reprise 660")
        glued(page, "séance en cours", "[data-home-card] [data-seance-status]")
        shot(page, "accueil_reprise_seance_660")
        cta(page).click()
        ck.appears("[reprise] la séance reprend à son étape", page, "[data-seance-item]", timeout=15000)
    ctx.close()


def part_resume_game(p, browser):
    ctx, page = seeded(p, browser, None, game=STORED_GAME)
    if open_home(page, "partie"):
        check("[partie] carte : partie en cours", primary(page) == "resume-game", f"({primary(page)})")
        text = card_text(page)
        check("[partie] adversaire, cadence, coup et camp", "Partie contre Iris" in text and "10 min · coup 3 · tu as les Blancs" in text, f"({text!r})")
        check("[partie] CTA « Reprendre la partie »", cta(page).inner_text().strip() == "Reprendre la partie")
        tile = page.locator("[data-seance-tile]")
        check("[partie] séance du jour en ligne secondaire", tile.count() == 1 and tile.get_attribute("href") == "#/seance")
        check("[partie] raccourci Jouer sans doublon de reprise", "Partie en cours" not in page.locator("[data-testid=home-play]").inner_text())
        visible_cta(page, "partie 660")
        glued(page, "partie", "[data-home-card] h2 + p")
        shot(page, "accueil_reprise_partie_660")
        hist = page.evaluate("() => history.length")
        cta(page).click()
        ck.appears("[partie] Jouer reprend la partie (échiquier, pas la configuration)", page, "[id^='chessboard-']", timeout=20000)
        check("[partie] onglet Jouer en replace", page.evaluate("() => location.hash") == "#/jouer" and page.evaluate("() => history.length") == hist)
        check("[partie] coups rejoués", page.evaluate("() => JSON.parse(localStorage.getItem('chess-local-play-game') || 'null')?.sans?.length") == 4)
    ctx.close()

    # Instantané expiré (plus de 24 h) : Play ne le reprendrait pas, l'accueil non plus.
    ctx, page = seeded(p, browser, None)
    page.evaluate("(g) => localStorage.setItem('chess-local-play-game', JSON.stringify({ ...g, savedAt: Date.now() - 25 * 3600000 }))", STORED_GAME)
    if open_home(page, "partie expirée"):
        check("[partie expirée] pas de reprise proposée", primary(page) == "seance", f"({primary(page)})")
    ctx.close()


def part_unavailable(p, browser):
    ctx, page = seeded(p, browser, {"puzzleAttempts": failed_puzzles(2)})
    blocked = []

    def abort(route):
        blocked.append(route.request.url)
        route.abort()
    page.route(REVISION_CHUNK, abort)
    page.goto(f"{BASE}/#/")
    if ck.appears("[indisponible] accueil prêt, compteur indisponible", page, "[data-testid=home][data-review-ready=unavailable]", timeout=20000, state="attached"):
        check("[indisponible] la chunk du compteur a bien été refusée", len(blocked) >= 1, f"({blocked})")
        check("[indisponible] carte et CTA présents", primary(page) == "seance" and cta(page).is_visible())
        check("[indisponible] aucune ligne de révision ni compte inventé", page.locator("[data-testid=home-revision]").count() == 0 and "Commence par" not in card_text(page))
        visible_cta(page, "indisponible 660")
        shot(page, "accueil_indisponible_660")
    page.unroute(REVISION_CHUNK)
    ctx.close()


def part_formats(p, browser):
    data = {"puzzleAttempts": failed_puzzles(6), "learnSessions": [ls(1, "seance", "puzzles", ago(1), True, score=4)],
            "games": [{"id": 1, "date": ago(0), "mode": "bot", "botId": "noa", "playerColor": "w", "timeControl": "10+0", "timeClass": "rapid", "pgn": "1. e4 e5", "result": "1-0"}]}
    for fmt in ("660", "852", "desktop"):
        ctx, page = seeded(p, browser, data, fmt=fmt)
        if open_home(page, fmt):
            ck.appears(f"[{fmt}] parcours lu", page, "[data-testid=home][data-path-ready]", timeout=10000, state="attached")
            visible_cta(page, fmt)
            check(f"[{fmt}] aucun débordement horizontal", overflow_x(page) <= 0, f"({overflow_x(page)} px)")
            small = page.evaluate("""() => [...document.querySelectorAll('main a, main button')]
              .filter((e) => e.offsetParent !== null)
              .map((e) => { const r = e.getBoundingClientRect(); return [e.innerText.split('\\n')[0], Math.round(r.width), Math.round(r.height)] })
              .filter(([, w, h]) => w < 44 || h < 44)""")
            check(f"[{fmt}] cibles de 44 px au moins", small == [], f"({small})")
            # Ordre du plan : action principale, révision, raccourcis, puis progression.
            order = page.evaluate("""() => ['[data-home-cta]', '[data-testid=home-revision]', '[data-testid=home-play]', '[data-testid=home-path]', '[data-testid=home-bilan]']
              .map((s) => document.querySelector(s)?.getBoundingClientRect().top ?? -1)""")
            check(f"[{fmt}] ordre : séance, révision, raccourcis, progression", all(t >= 0 for t in order) and order == sorted(order), f"({order})")
            shot(page, f"accueil_{fmt}")
            main = page.locator("main")
            if main.evaluate("e => e.scrollHeight > e.clientHeight"):
                main.evaluate("e => e.scrollTop = e.scrollHeight")
                page.wait_for_timeout(200)
                shot(page, f"accueil_{fmt}_bas")
        ctx.close()


def suite(p):
    part_bench()
    browser = p.chromium.launch()
    part_new_profile(p, browser)
    part_due(p, browser)
    part_done_today(p, browser)
    part_quick_pending(p, browser)
    part_resume_seance(p, browser)
    part_resume_game(p, browser)
    part_unavailable(p, browser)
    part_formats(p, browser)
    browser.close()


if __name__ == "__main__":
    ck.run(suite)
