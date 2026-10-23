"""E2E « Convertir l'avantage » (/convertir) : positions gagnantes à gagner contre Stockfish bridé.

1. Banque src/data/conversions.json : volume, répartition, légalité, joueur au trait, éval de
   sélection, catégorie recalculée par un code indépendant du générateur, faits cités vérifiés sur
   l'échiquier par un code indépendant (pions passés, pions isolés, tour en 7e, roi à activer,
   paire de fous, matériel du thème), thème/consigne/plan égaux à scripts/conversion_facts.py.
2. Entrée depuis Apprendre, onglet allumé, catégories, hasard, niveau mémorisé à part de celui de
   l'entraîneur d'attaque.
3. Options UCI espionnées : défenseur bridé (UCI_LimitStrength + UCI_Elo avant son premier `go`),
   Indice et suivi de l'avantage par un moteur jamais bridé, pas de bouton Nulle, Conseils.
4. Rechargement qui reprend, changement de niveau (abandon noté), Recommencer (abandon noté),
   tentatives écrasées entre entraîneurs : attaque -> conversion et conversion -> attaque, chacune
   notée abandonnée dans son domaine.
5. Vraie conversion : défenseur à 1320, coups du joueur par un second Stockfish dans la page,
   jusqu'à « Avantage converti » (ou mat), ligne IndexedDB `conversion`, Conclure et son motif,
   liste « ✓ battu à 1320 ».
6. Mise en page : 393x852, 393x660 et 1440x900, sans débordement horizontal.

Usage : npm run test:e2e -- --suite convertir
"""
import json
import os
import re
import sys
import time

import chess

from helpers import BASE, E2E_DIR, Checker, desktop_context, mobile_context, overflow_x, shot, tap_move

ROOT = os.path.dirname(E2E_DIR)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import conversion_facts  # noqa: E402

ck = Checker("convertir")
check = ck.check

DATA = os.path.join(ROOT, "src", "data", "conversions.json")
BANK = json.load(open(DATA, encoding="utf-8")) if os.path.exists(DATA) else []
PUZZLES = {x[0]: x for x in json.load(open(os.path.join(ROOT, "public", "puzzles.json"), encoding="utf-8"))}
ATTACKS = json.load(open(os.path.join(ROOT, "src", "data", "attacks.json"), encoding="utf-8"))
GAME = "[data-testid='position-game']"
ITEM = "[data-testid='conversion-item']"
CATS = ("finale", "materiel", "positionnel")
LABEL = {"finale": "Finale", "materiel": "Matériel", "positionnel": "Positionnel"}
PREFS = "chess-local-conversion"
ATTACK_PREFS = "chess-local-attack"
DECISIVE_CP = 800

# Espion UCI : chaque worker numéroté, chaque commande envoyée journalisée, chaque `bestmove`
# reçu compté par worker. Le moteur du joueur (second Stockfish de la suite) passe par le
# constructeur natif : il n'apparaît pas dans le journal.
UCI_SPY = """(() => {
  const Native = window.Worker
  window.__NativeWorker = Native
  window.__uci = []
  window.__bestmoves = []
  window.__scores = []
  let n = 0
  window.Worker = class extends Native {
    constructor(...args) {
      super(...args)
      this.__idx = n++
      this.addEventListener('message', (e) => {
        if (typeof e.data !== 'string') return
        if (e.data.startsWith('bestmove')) window.__bestmoves.push(this.__idx)
        const m = e.data.match(/ score (cp|mate) (-?\\d+)/)
        if (m) window.__scores.push([this.__idx, m[1], +m[2]])
      })
    }
    postMessage(msg, ...rest) {
      if (typeof msg === 'string') window.__uci.push([this.__idx, msg])
      return super.postMessage(msg, ...rest)
    }
  }
})()"""
QA_WAIT = """
window.__qaWait = (pred) => new Promise((resolve) => {
  const t = setInterval(() => {
    const i = window.__qaLines.findIndex(pred)
    if (i >= 0) { clearInterval(t); resolve(window.__qaLines[i]) }
  }, 5)
})
"""
QA_ENGINE = """
async ([url, fen, depth]) => {
  if (!window.__qaWorker) {
    const w = new window.__NativeWorker(url)
    window.__qaLines = []
    w.onmessage = (e) => window.__qaLines.push(String(e.data))
    window.__qaWorker = w
    w.postMessage('uci')
    await window.__qaWait((l) => l === 'uciok')
  }
  const w = window.__qaWorker
  window.__qaLines.length = 0
  w.postMessage('position fen ' + fen)
  w.postMessage('go depth ' + depth)
  const bm = await window.__qaWait((l) => l.startsWith('bestmove'))
  return bm.split(' ')[1]
}
"""
READ_ROWS = """
(domain) => new Promise((resolve, reject) => {
  const open = indexedDB.open('chess-local')
  open.onerror = () => reject(open.error)
  open.onsuccess = () => {
    const db = open.result
    if (!db.objectStoreNames.contains('learnSessions')) { db.close(); resolve([]); return }
    const all = db.transaction('learnSessions').objectStore('learnSessions').getAll()
    all.onerror = () => { db.close(); reject(all.error) }
    all.onsuccess = () => { db.close(); resolve(all.result.filter((r) => r.domain === domain)) }
  }
})
"""


# ---------- 1. Données (contrôles écrits à part du générateur) ----------

VAL = {"p": 1, "n": 3, "b": 3, "r": 5, "q": 9, "k": 0}


def rel(sq, color):
    r = chess.square_rank(sq)
    return r if color == chess.WHITE else 7 - r


def counts(board, color):
    out = {k: 0 for k in VAL}
    for p in board.piece_map().values():
        if p.color == color:
            out[p.symbol().lower()] += 1
    return out


def points(board, color):
    return sum(VAL[k] * n for k, n in counts(board, color).items())


def indep_category(board):
    pl = board.turn
    minor_major = sum(n for c in (chess.WHITE, chess.BLACK) for k, n in counts(board, c).items() if k in "nbrq")
    if minor_major <= 4:
        return "finale"
    return "materiel" if points(board, pl) > points(board, not pl) else "positionnel"


def is_passed(board, name, color):
    sq = chess.parse_square(name)
    p = board.piece_at(sq)
    if not p or p.piece_type != chess.PAWN or p.color != color:
        return False
    f = chess.square_file(sq)
    for o in board.pieces(chess.PAWN, not color):
        if abs(chess.square_file(o) - f) <= 1 and rel(o, color) > rel(sq, color):
            return False
    return True


def is_isolated(board, name, color):
    sq = chess.parse_square(name)
    p = board.piece_at(sq)
    if not p or p.piece_type != chess.PAWN or p.color != color:
        return False
    f = chess.square_file(sq)
    return not any(abs(chess.square_file(o) - f) == 1 for o in board.pieces(chess.PAWN, color))


def material_theme_ok(board, th):
    pl = board.turn
    a, b = counts(board, pl), counts(board, not pl)
    d = {k: a[k] - b[k] for k in "pnbrq"}
    pieces = {k: v for k, v in d.items() if k != "p" and v}
    if th == "Pion de plus":
        return not pieces and d["p"] == 1
    if th.endswith(" pions de plus"):
        return not pieces and d["p"] >= 2
    if th == "Qualité de plus":
        return pieces in ({"r": 1, "b": -1}, {"r": 1, "n": -1})
    if th == "Pièce de plus":
        return pieces in ({"b": 1}, {"n": 1})
    if th == "Tour de plus":
        return pieces == {"r": 1}
    if th == "Dame de plus":
        return pieces == {"q": 1}
    if th == "Plus de matériel":
        return points(board, pl) > points(board, not pl)
    return None  # pas un thème matériel


def check_data():
    check("[données] banque présente", bool(BANK), f"({DATA})")
    if not BANK:
        return
    by = {c: [e for e in BANK if e["category"] == c] for c in CATS}
    check("[données] au moins 45 positions", len(BANK) >= 45, f"({len(BANK)})")
    check("[données] au moins 12 par catégorie", min(len(v) for v in by.values()) >= 12, f"({ {c: len(v) for c, v in by.items()} })")
    check("[données] ids uniques", len({e["id"] for e in BANK}) == len(BANK))
    check("[données] positions uniques", len({" ".join(e["fen"].split()[:2]) for e in BANK}) == len(BANK))
    check("[données] un puzzle d'origine par position", len({e["source"]["puzzle"] for e in BANK}) == len(BANK))
    keys = ("source", "majority", "legal", "turn", "eval", "cat", "facts", "units", "head", "passed", "isolated", "rook7", "king", "bishops", "material", "plan")
    bad = {k: [] for k in keys}
    for e in BANK:
        b = chess.Board(e["fen"])
        pl = b.turn
        # Provenance : position du puzzle lichess, sa solution, puis les coups ajoutés (nombre
        # impair : le camp qui a joué la solution retrouve le trait).
        src = PUZZLES.get(e["source"]["puzzle"])
        try:
            r = chess.Board(src[1])
            for m in src[2].split() + e["source"]["uci"]:
                r.push_uci(m)
            replay_ok = r.fen() == e["fen"] and len(e["source"]["uci"]) % 2 == 1 and "advantage" in src[4].split()
        except Exception:
            replay_ok = False
        if not replay_ok:
            bad["source"].append(e["id"])
        m = re.search(r"À l'aile (dame|roi), tes pions occupent (\w+) colonnes contre (\w+)", e["plan"])
        if m:
            files = range(0, 4) if m.group(1) == "dame" else range(4, 8)
            nums = {"une": 1, "deux": 2, "trois": 3, "quatre": 4}
            mine_f = {chess.square_file(s) for s in b.pieces(chess.PAWN, pl) if chess.square_file(s) in files}
            his_f = {chess.square_file(s) for s in b.pieces(chess.PAWN, not pl) if chess.square_file(s) in files}
            if (len(mine_f), len(his_f)) != (nums.get(m.group(2)), nums.get(m.group(3))) or not len(mine_f) > len(his_f) >= 1:
                bad["majority"].append(e["id"])
        if not b.is_valid() or b.is_check() or b.is_game_over():
            bad["legal"].append(e["id"])
        if ("w" if pl == chess.WHITE else "b") != e["player"]:
            bad["turn"].append(e["id"])
        if not (200 <= e["eval"] <= 450):
            bad["eval"].append(e["id"])
        if indep_category(b) != e["category"]:
            bad["cat"].append(e["id"])
        cat = conversion_facts.category(b)
        f = conversion_facts.facts(b)
        if (conversion_facts.theme(cat, f), conversion_facts.goal(cat, f), conversion_facts.plan(b, cat, f)) != (e["theme"], e["goal"], e["plan"]):
            bad["facts"].append(e["id"])
        if sum(1 for p in b.piece_map().values() if p.piece_type != chess.KING) < 7:
            bad["units"].append(e["id"])
        if not e["goal"].startswith(e["theme"] + " : "):
            bad["head"].append(e["id"])
        text = e["goal"] + " " + e["plan"]
        # Pions passés cités (« pion passé d5 », « Ton pion d5 est passé », « Tes pions a4 et b5 sont passés »).
        mine = re.findall(r"pion passé ([a-h][1-8])", e["goal"])
        m = re.search(r"(?:Ton|Tes) pions? ((?:[a-h][1-8](?:, | et )?)+) (?:est|sont) passés?", e["plan"])
        mine += re.findall(r"[a-h][1-8]", m.group(1)) if m else []
        his = re.findall(r"[a-h][1-8]", (re.search(r"Attention à (?:son pion passé en|ses pions passés) ([^:]+):", e["plan"]) or [None, ""])[1])
        if any(not is_passed(b, s, pl) for s in mine) or any(not is_passed(b, s, not pl) for s in his):
            bad["passed"].append(e["id"])
        iso = re.findall(r"pion isolé ([a-h][1-8])", e["goal"])
        m = re.search(r"(?:Son|Ses) pions? ((?:[a-h][1-8](?:, | et )?)+) (?:est|sont) isolés?", e["plan"])
        iso += re.findall(r"[a-h][1-8]", m.group(1)) if m else []
        if any(not is_isolated(b, s, not pl) for s in iso):
            bad["isolated"].append(e["id"])
        for s in re.findall(r"tour en ([a-h][1-8])", text):
            p = b.piece_at(chess.parse_square(s))
            if not p or p.piece_type != chess.ROOK or p.color != pl or rel(chess.parse_square(s), pl) != 6:
                bad["rook7"].append(e["id"])
        m = re.search(r"sors ton roi de ([a-h][1-8])", e["plan"])
        if (m and (m.group(1) != chess.square_name(b.king(pl)) or rel(b.king(pl), pl) > 1)) or ("active ton roi" in e["goal"] and not m):
            bad["king"].append(e["id"])
        shade = {(chess.square_file(s) + chess.square_rank(s)) % 2 for s in b.pieces(chess.BISHOP, pl)}
        if "paire de fous" in text and len(shade) != 2:
            bad["bishops"].append(e["id"])
        ok = material_theme_ok(b, e["theme"])
        if ok is False or (e["category"] == "materiel" and ok is None):
            bad["material"].append(e["id"])
        n_sent = len(re.findall(r"[.!?](?:\s|$)", e["plan"]))
        if not 2 <= n_sent <= 5:
            bad["plan"].append(e["id"])
    labels = {
        "source": "provenance : puzzle « advantage » + solution + coups ajoutés (impairs) = la FEN",
        "majority": "majorité citée vérifiée en colonnes",
        "legal": "positions légales, pas d'échec ni de fin au départ",
        "turn": "joueur au trait",
        "eval": "éval de sélection entre +2 et +4,5",
        "cat": "catégorie recalculée depuis le matériel",
        "facts": "thème, consigne et plan égaux à conversion_facts.py",
        "units": "au moins 7 pions et pièces hors rois",
        "head": "consigne commencée par le thème",
        "passed": "pions passés cités vérifiés sur l'échiquier",
        "isolated": "pions isolés cités vérifiés sur l'échiquier",
        "rook7": "tour citée sur la 7e rangée du joueur",
        "king": "roi à activer : sa case, sur ses deux premières rangées",
        "bishops": "paire de fous vérifiée",
        "material": "thème matériel conforme aux pièces",
        "plan": "plan de deux à cinq phrases",
    }
    for k, label in labels.items():
        check(f"[données] {label}", not bad[k], f"({bad[k][:5]})")
    check("[données] plusieurs thèmes", len({e["theme"] for e in BANK}) >= 4, f"({ {e['theme'] for e in BANK} })")
    check("[données] chaque catégorie a des positions avec les Blancs et les Noirs",
          all({e["player"] for e in v} == {"w", "b"} for v in by.values()))
    # Contrôles des faits sur des positions connues (le générateur ne peut pas les biaiser).
    b = chess.Board("8/5k2/8/3P4/8/8/5K2/8 w - - 0 1")
    check("[données] faits : pion d5 passé, roi f2 à activer",
          conversion_facts.facts(b)["passed"] == ["d5"] and conversion_facts.facts(b)["kingBack"])
    b = chess.Board("6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1")
    check("[données] faits : tour de plus, pas de pion passé",
          conversion_facts.material_label(conversion_facts.facts(b)) == "Tour de plus" and conversion_facts.facts(b)["passed"] == [])


# ---------- Outils de partie ----------

def attr(page, name):
    return page.evaluate(f"() => document.querySelector(\"{GAME}\")?.getAttribute('data-{name}') ?? null")


def wait_turn(page, color, timeout_s=30):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if attr(page, "status") == "over":
            return "over"
        f = attr(page, "fen")
        if f and f.split(" ")[1] == color and attr(page, "thinking") == "0":
            return "turn"
        page.wait_for_timeout(100)
    return "timeout"


def best_move(page, fen, depth):
    return page.evaluate(QA_ENGINE, [f"{BASE}/engine/stockfish-18-lite-single.js", fen, depth])


def play(page, uci):
    tap_move(page, uci[:2], uci[2:4], pause=150)
    if len(uci) == 5:
        promo = page.locator("div.absolute.inset-0.z-20 button")
        promo.first.wait_for(timeout=3000)
        promo.nth("qrbn".index(uci[4])).tap()


def play_best(page, color, depth, tag):
    """Un coup du joueur (second Stockfish), puis la réponse du défenseur. True si joué."""
    if wait_turn(page, color) != "turn":
        return False
    before = attr(page, "fen")
    uci = best_move(page, before, depth)
    play(page, uci)
    page.wait_for_timeout(150)
    if attr(page, "fen") == before:
        ck.fail(f"[{tag}] coup {uci} refusé par l'échiquier")
        return False
    return True


def uci_log(page):
    return page.evaluate("() => window.__uci")


def workers(log):
    out = {}
    for idx, msg in log:
        out.setdefault(idx, []).append(msg)
    return out


def options_before_first_go(msgs):
    first_go = next((i for i, m in enumerate(msgs) if m.startswith("go ")), len(msgs))
    return [m for m in msgs[:first_go] if m.startswith("setoption")]


def oracle_evals(page):
    """Par worker oracle (celui qui reçoit `go movetime 300`) : [go envoyés, bestmove reçus]."""
    return page.evaluate("""() => {
      const out = {}
      for (const [i, m] of window.__uci) if (m.startsWith('go movetime 300')) (out[i] ??= [0, 0])[0]++
      for (const i of window.__bestmoves) if (i in out) out[i][1]++
      return out
    }""")


def wait_offer(page, before, timeout_s=5):
    """Après la réponse du défenseur : attend la proposition, ou la fin de l'éval de l'avantage puis
    le rendu qui peut la suivre. Retourne data-decisive."""
    deadline = time.time() + timeout_s
    grace = None
    while time.time() < deadline:
        d = attr(page, "decisive")
        if d != "none":
            return d
        if grace is None:
            if any(sent > before.get(i, [0, 0])[0] and got >= sent for i, (sent, got) in oracle_evals(page).items()):
                grace = time.time() + 0.3
        elif time.time() > grace:
            return d
        page.wait_for_timeout(30)
    return attr(page, "decisive")


def last_oracle_score(page):
    """Dernier score (cp ou mate) émis par un worker oracle (`go movetime 300`), point de vue du trait."""
    return page.evaluate("""() => {
      const oracles = new Set(window.__uci.filter(([, m]) => m.startsWith('go movetime 300')).map(([i]) => i))
      const s = window.__scores.filter(([i]) => oracles.has(i))
      return s.length ? s[s.length - 1].slice(1) : null
    }""")


def rows(page, domain="conversion"):
    return page.evaluate(READ_ROWS, domain)


def open_pos(page, pid, route="convertir"):
    page.goto(f"{BASE}/#/{route}/{pid}")
    ok = ck.appears(f"[{pid}] partie affichée", page, GAME)
    page.wait_for_timeout(300)
    return ok


def no_overflow(page, tag):
    check(f"[mise en page] {tag} : pas de débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")


def bar_fits(page, tag):
    w = page.evaluate(f"""() => {{
      const g = document.querySelector("{GAME}")
      const bar = g && g.lastElementChild
      return bar ? bar.scrollWidth - bar.clientWidth : null
    }}""")
    check(f"[mise en page] {tag} : barre d'actions sans débordement", w is not None and w <= 0, f"({w})")


# ---------- Suite ----------

def suite(p):
    check_data()
    browser = p.chromium.launch(headless=True)
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(UCI_SPY)
    ctx.add_init_script(QA_WAIT)
    page = ctx.new_page()

    # --- 2. Entrée, liste, niveau ---
    page.goto(f"{BASE}/#/apprendre/entrainement/attaque-defense")
    card = page.locator("main a", has_text="Convertir l'avantage")
    ck.appears("[entrée] carte dans Apprendre (Attaque et défense)", page, "main a:has-text(\"Convertir l'avantage\")")
    if card.count():
        card.tap()
    ck.appears("[liste] page de l'entraîneur", page, ITEM)
    check("[liste] URL #/convertir", page.evaluate("() => location.hash").startswith("#/convertir"), f"({page.url})")
    check("[liste] onglet Apprendre allumé", page.locator("nav a[aria-current]", has_text="Apprendre").locator("visible=true").count() == 1)
    for c in CATS:
        tab = page.locator(f"[role='tab'][data-category='{c}']")
        if tab.count():
            tab.tap()
            page.wait_for_timeout(150)
        n = page.locator(ITEM).count()
        want = sum(1 for e in BANK if e["category"] == c)
        check(f"[liste] onglet {LABEL[c]} : ses {want} positions", tab.count() == 1 and n == want and n > 0, f"({n})")
    cut = page.evaluate("""() => [...document.querySelectorAll("[role='tab'] span:first-child")].filter((e) => e.scrollWidth > e.clientWidth).map((e) => e.textContent)""")
    check("[liste] libellés des onglets non tronqués (393 px)", page.locator("[role='tab']").count() == 3 and cut == [], f"({cut})")
    shot(page, "convertir_list_852")
    no_overflow(page, "liste 393x852")

    page.get_by_role("button", name="Position au hasard").tap()
    ck.appears("[hasard] partie ouverte", page, GAME)
    random_id = page.url.rsplit("/", 1)[-1]
    check("[hasard] position dans la catégorie affichée", any(e["id"] == random_id and e["category"] == "positionnel" for e in BANK), f"({random_id})")
    page.goto(f"{BASE}/#/convertir")
    ck.appears("[hasard] retour liste", page, "[data-testid='defender']")

    radio = page.locator("[role='radio'][data-level='1500']")
    radio.first.tap() if radio.count() else ck.fail("[niveau] pastille 1500")
    page.reload()
    ck.appears("[niveau] liste rechargée", page, "[data-testid='defender']")
    check("[niveau] 1500 mémorisé après rechargement", page.locator("[role='radio'][data-level='1500'][aria-checked='true']").count() == 1)
    check("[niveau] mémorisé sous sa propre clé", page.evaluate(f"() => localStorage.getItem('{PREFS}')") == '{"level":1500}'
          and page.evaluate(f"() => localStorage.getItem('{ATTACK_PREFS}')") is None)

    if not BANK:
        browser.close()
        return

    # --- 3. Options UCI, consigne, conseils ---
    first = next(e for e in BANK if e["category"] == "materiel")
    color = first["player"]
    if open_pos(page, first["id"]):
        check("[partie] titre = thème", page.locator(f"{GAME} h1").text_content() == first["theme"])
        act = first["goal"].split(" : ", 1)[1]
        check("[partie] consigne affichée sans le thème (déjà en titre)", page.locator("[data-testid='objective']", has_text=act[0].upper() + act[1:]).count() == 1)
        check("[partie] objectif : gagner", page.locator("[data-testid='objective']", has_text="Objectif : gagner").count() == 1)
        check("[partie] pas de bouton Nulle", page.get_by_role("button", name="Nulle").count() == 0)
        check("[partie] puce de niveau « 1500 »", "1500" in (page.locator("[data-testid='level-chip']").text_content() or ""))
        check("[partie] ligne moteur « Elo 1500 »", page.locator(GAME, has_text="Elo 1500").count() == 1)
        shot(page, "convertir_game_852")
        no_overflow(page, "partie 393x852")
        bar_fits(page, "partie 393x852")
        page.get_by_role("button", name="Conseils").tap()
        check("[partie] « Conseils ▾ » déplie le plan", page.locator(GAME, has_text=first["plan"][:40]).count() == 1)
        shot(page, "convertir_conseils_852")
        page.get_by_role("button", name="Conseils").tap()
        play_best(page, color, 10, "options")
        wait_turn(page, color)
        ws = workers(uci_log(page))
        defender = [i for i, m in ws.items() if "go movetime 700" in m]
        check("[uci] un moteur défenseur a joué", len(defender) == 1, f"({list(ws)})")
        if defender:
            opts = options_before_first_go(ws[defender[0]])
            check("[uci] défenseur : UCI_LimitStrength true avant son premier go", "setoption name UCI_LimitStrength value true" in opts, f"({opts})")
            check("[uci] défenseur : UCI_Elo 1500 avant son premier go", "setoption name UCI_Elo value 1500" in opts, f"({opts})")
        page.get_by_role("button", name="Indice").tap()
        ck.appears("[indice] flèche affichée", page, "[id^='chessboard-'] marker[id*='arrowhead']", timeout=20000, state="attached")
        # L'éval de suivi part après la réponse du défenseur, sur le même moteur que l'indice (mutex) :
        # la flèche affichée, elle est forcément envoyée.
        ws = workers(uci_log(page))
        oracle = [i for i, m in ws.items() if "go movetime 300" in m]
        hint_w = [i for i, m in ws.items() if "go depth 14" in m]
        check("[uci] suivi de l'avantage et indice : un même moteur non bridé, distinct du défenseur",
              len(oracle) == 1 and hint_w == oracle and oracle[0] not in defender
              and not any("UCI_LimitStrength value true" in m for m in ws[oracle[0]]), f"({oracle} / {hint_w} / {defender})")
        check("[partie] Indice : tentative marquée « avec aide »", page.locator(GAME, has_text="avec aide").count() >= 1)

        # Rechargement : la partie reprend.
        fen_before = attr(page, "fen")
        page.reload()
        ck.appears("[reprise] partie après rechargement", page, GAME)
        page.wait_for_timeout(400)
        check("[reprise] même position après rechargement", attr(page, "fen") == fen_before, f"({attr(page, 'fen')})")
        check("[reprise] partie persistée sous convertir:<id>", page.evaluate(
            "() => JSON.parse(localStorage.getItem('chess-local-position-game-v1') || 'null')?.key") == f"convertir:{first['id']}")

        # Changement de niveau en partie : la position repart, l'essai est noté abandonné.
        n_rows = len(rows(page))
        page.locator("[data-testid='level-chip']").tap()
        ck.appears("[niveau] feuille de niveau", page, "[data-testid='level-sheet']")
        page.locator("[data-testid='level-sheet'] [role='radio'][data-level='max']").tap()
        page.locator("[data-testid='level-confirm']").tap()
        page.wait_for_timeout(300)
        check("[niveau] la position repart du début", attr(page, "fen") == first["fen"], f"({attr(page, 'fen')})")
        r = rows(page)
        check("[niveau] tentative remplacée notée abandonnée", len(r) == n_rows + 1 and r[-1]["outcome"] == "abandon"
              and r[-1]["defenderElo"] == 1500 and r[-1]["itemId"] == first["id"] and r[-1]["fen"] == first["fen"], f"({r[-1:]})")
        check("[niveau] Max mémorisé", page.evaluate(f"() => localStorage.getItem('{PREFS}')") == '{"level":null}')

        # Recommencer après un coup : tentative notée abandonnée.
        play_best(page, color, 10, "recommencer")
        wait_turn(page, color)
        n_rows = len(rows(page))
        page.get_by_role("button", name="Recommencer").tap()
        page.wait_for_timeout(300)
        r = rows(page)
        check("[recommencer] position de départ", attr(page, "fen") == first["fen"])
        check("[recommencer] tentative notée abandonnée", len(r) == n_rows + 1 and r[-1]["outcome"] == "abandon" and r[-1]["success"] == 0
              and r[-1]["assisted"] is False and r[-1]["defenderElo"] is None, f"({r[-1:]})")

        # Conversion en cours écrasée par une attaque : notée abandonnée dans `conversion`.
        play_best(page, color, 10, "remplacement")
        wait_turn(page, color)
        n_conv = len(rows(page))
        att = ATTACKS[0]
        if open_pos(page, att["id"], "attaque"):
            check("[remplacement] simple coup d'œil : rien de noté", len(rows(page)) == n_conv)
            play_best(page, att["attacker"], 10, "remplacement attaque")
            page.wait_for_timeout(300)
            r = rows(page)
            check("[remplacement] conversion écrasée par une attaque : notée abandonnée",
                  len(r) == n_conv + 1 and r[-1]["itemId"] == first["id"] and r[-1]["outcome"] == "abandon", f"({r[-1:]})")
            wait_turn(page, att["attacker"])
            # Attaque en cours écrasée par une conversion : notée abandonnée dans `attack`.
            n_att = len(rows(page, "attack"))
            if open_pos(page, first["id"]):
                play_best(page, color, 10, "remplacement conversion")
                page.wait_for_timeout(300)
                r = rows(page, "attack")
                check("[remplacement] attaque écrasée par une conversion : notée abandonnée",
                      len(r) == n_att + 1 and r[-1]["itemId"] == att["id"] and r[-1]["outcome"] == "abandon", f"({r[-1:]})")
                wait_turn(page, color)
                page.get_by_role("button", name="Recommencer").tap()

    # --- 5. Vraie conversion jusqu'à la réussite, défenseur à 1320 ---
    page.evaluate(f"() => localStorage.setItem('{PREFS}', JSON.stringify({{ level: 1320 }}))")
    target = max((e for e in BANK if e["category"] == "materiel"), key=lambda e: (e["eval"], e["id"]))
    tcolor = target["player"]
    if open_pos(page, target["id"]):
        check("[conversion] défenseur Elo 1320", "1320" in (page.locator("[data-testid='level-chip']").text_content() or ""))
        plies, evals = 0, None
        while plies < 120:
            if attr(page, "status") == "over" or attr(page, "decisive") != "none":
                break
            if wait_turn(page, tcolor) != "turn":
                break
            if evals is not None and wait_offer(page, evals) != "none":
                break
            evals = oracle_evals(page)
            if not play_best(page, tcolor, 12, "conversion"):
                break
            plies += 2
        decisive, status = attr(page, "decisive"), attr(page, "status")
        print(f"[info] conversion {target['id']} : {plies} demi-coups, decisive={decisive}, status={status}, verdict={attr(page, 'verdict')}")
        check("[conversion] réussie avant 120 demi-coups (avantage décisif ou mat)",
              decisive == "offered" or (status == "over" and attr(page, "verdict") == "success"), f"(decisive={decisive}, status={status})")
        if decisive == "offered":
            score = last_oracle_score(page)
            check(f"[conversion] proposée sur une éval d'au moins +{DECISIVE_CP // 100} (ou mat)",
                  score is not None and ((score[0] == "cp" and score[1] >= DECISIVE_CP) or (score[0] == "mate" and score[1] > 0)), f"({score})")
            check("[conversion] bandeau « Avantage converti »", page.locator("[data-testid='objective']", has_text="Avantage converti").count() == 1)
            shot(page, "convertir_reussie_852")
            bar_fits(page, "bandeau réussite 393x852")
            r = rows(page)
            check("[conversion] réussite notée dès l'avantage décisif", r and r[-1]["itemId"] == target["id"] and r[-1]["outcome"] == "decisive"
                  and r[-1]["success"] == 1 and r[-1]["defenderElo"] == 1320 and r[-1]["assisted"] is False and r[-1]["fen"] == target["fen"], f"({r[-1:]})")
            page.get_by_role("button", name="Conclure").tap()
            page.wait_for_timeout(300)
            check("[conversion] Conclure : partie terminée et gagnée", attr(page, "status") == "over" and attr(page, "verdict") == "success")
            check("[conversion] motif « Avantage décisif tenu »", page.locator("[data-testid='objective']", has_text="Avantage décisif tenu : la partie est gagnée.").count() == 1)
            check("[conversion] une seule ligne pour la tentative", sum(1 for x in rows(page) if x["itemId"] == target["id"] and x["outcome"] != "abandon") == 1)
        elif status == "over":
            r = rows(page)
            check("[conversion] mat noté", r and r[-1]["outcome"] == "mate" and r[-1]["success"] == 1 and r[-1]["defenderElo"] == 1320, f"({r[-1:]})")
        shot(page, "convertir_fin_852")
        bar_fits(page, "fin 393x852")
        no_overflow(page, "fin 393x852")
        check("[fin] bouton Plan", page.get_by_role("button", name="Plan", exact=True).count() == 1)
        page.get_by_role("button", name="Analyser").tap()
        page.wait_for_timeout(800)
        back = page.get_by_role("button", name=re.compile("Retour à la position"))
        if back.count():
            back.first.tap()
            ck.appears("[analyse] retour à la position", page, GAME)
            page.wait_for_timeout(300)
            check("[analyse] partie terminée restaurée", attr(page, "status") == "over" and attr(page, "verdict") == "success")
        else:
            ck.fail("[analyse] bouton « Retour à la position »")
        url_before = page.url
        page.get_by_role("button", name="Suivante").tap()
        page.wait_for_timeout(400)
        check("[suivante] autre position", page.url != url_before and "#/convertir/" in page.url, f"({page.url})")

        page.goto(f"{BASE}/#/convertir?c={target['category']}")
        ck.appears("[liste] retour", page, ITEM)
        item = page.locator(f"{ITEM}[data-id='{target['id']}']")
        check("[liste] position marquée « ✓ battu à 1320 »", item.count() == 1 and "✓ battu à 1320" in (item.text_content() or ""),
              f"({item.text_content() if item.count() else None})")
        tab = page.locator(f"[role='tab'][data-category='{target['category']}']").text_content() or ""
        check("[liste] onglet : 1 position réussie", re.search(r"(?<!\d)1/\d+", tab) is not None, f"({tab})")

    # --- 6. Mise en page ---
    page.set_viewport_size({"width": 393, "height": 660})
    page.goto(f"{BASE}/#/convertir")
    page.wait_for_timeout(400)
    shot(page, "convertir_list_660")
    no_overflow(page, "liste 393x660")
    if open_pos(page, BANK[0]["id"]):
        shot(page, "convertir_game_660")
        no_overflow(page, "partie 393x660")
        box = page.get_by_role("button", name="Abandonner").bounding_box()
        check("[mise en page] 393x660 : barre d'actions à l'écran", box is not None and box["y"] + box["height"] <= 660)
    ctx.close()

    dctx = desktop_context(browser, ck)
    dpage = dctx.new_page()
    dpage.goto(f"{BASE}/#/convertir")
    ck.appears("[desktop] liste", dpage, ITEM)
    shot(dpage, "convertir_list_1440")
    no_overflow(dpage, "liste 1440x900")
    check("[desktop] onglet Apprendre allumé (nav latérale)", dpage.locator("nav a[aria-current]", has_text="Apprendre").locator("visible=true").count() == 1)
    if open_pos(dpage, BANK[-1]["id"]):
        dpage.get_by_role("button", name="Conseils").click()
        shot(dpage, "convertir_game_1440")
        no_overflow(dpage, "partie 1440x900")
    browser.close()


ck.run(suite)
