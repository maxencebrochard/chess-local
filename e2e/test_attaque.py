"""E2E « Entraîneur d'attaque » (/attaque) : positions d'attaque jouées contre Stockfish bridé.

1. Banque src/data/attacks.json : volume, répartition, légalité, attaquant au trait, catégorie
   recalculée par un code indépendant du générateur, consignes vérifiées sur l'échiquier
   (colonne citée sans pion de l'attaquant, pions de la tempête bien avancés, roque affaibli,
   droits de roque), thème/consigne/plan égaux à scripts/attack_facts.py, garde du fianchetto.
2. Entrée depuis Apprendre, onglet allumé, catégories, niveau du défenseur mémorisé.
3. Options UCI espionnées par instance de worker : le défenseur reçoit UCI_LimitStrength true +
   UCI_Elo choisi avant son premier `go` ; Indice et suivi de l'avantage passent par un moteur
   jamais bridé ; changement de niveau en partie : nouvelle option avant le `go` suivant.
4. Annuler (avec aide), Recommencer (tentative notée abandonnée), rechargement qui reprend la
   partie, autre position qui remplace une tentative en cours (notée abandonnée).
5. Vraie attaque : défenseur à 1320, coups de l'attaquant par un second Stockfish dans la page,
   jusqu'à « Attaque réussie » (bandeau en place, échiquier immobile, retrouvé après rechargement), Conclure, ligne IndexedDB,
   liste « ✓ battu à 1320 ». Puis Plan (calque EngineContinuation), Analyser et retour, Suivante,
   et la même position rouverte depuis la liste après un autre choix de niveau : la partie
   terminée n'est pas reprise, le défenseur est au niveau choisi.
6. Mise en page : 393x852, 393x660 et 1440x900, sans débordement horizontal.

Usage : npm run test:e2e -- --suite attaque
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
import attack_facts  # noqa: E402

ck = Checker("attaque")
check = ck.check

DATA = os.path.join(ROOT, "src", "data", "attacks.json")
ATTACKS = json.load(open(DATA, encoding="utf-8")) if os.path.exists(DATA) else []
GAME = "[data-testid='position-game']"
CATS = ("opposes", "meme", "centre")
SHORT = {"opposes": "Roques opposés", "meme": "Même aile", "centre": "Roi au centre"}  # onglets et têtes de consigne
PREFS = "chess-local-attack"

# Espion UCI : chaque worker numéroté, chaque commande envoyée journalisée, et chaque `bestmove`
# reçu (fin d'une recherche) compté par worker. Le second moteur de la suite passe par le
# constructeur natif : il n'apparaît pas dans le journal.
UCI_SPY = """(() => {
  const Native = window.Worker
  window.__NativeWorker = Native
  window.__uci = []
  window.__bestmoves = []
  let n = 0
  window.Worker = class extends Native {
    constructor(...args) {
      super(...args)
      this.__idx = n++
      this.addEventListener('message', (e) => {
        if (typeof e.data === 'string' && e.data.startsWith('bestmove')) window.__bestmoves.push(this.__idx)
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
() => new Promise((resolve, reject) => {
  const open = indexedDB.open('chess-local')
  open.onerror = () => reject(open.error)
  open.onsuccess = () => {
    const db = open.result
    if (!db.objectStoreNames.contains('learnSessions')) { db.close(); resolve([]); return }
    const all = db.transaction('learnSessions').objectStore('learnSessions').getAll()
    all.onerror = () => { db.close(); reject(all.error) }
    all.onsuccess = () => { db.close(); resolve(all.result.filter((r) => r.domain === 'attack')) }
  }
})
"""


# ---------- 1. Données ----------

def rel(sq, color):
    r = chess.square_rank(sq)
    return r if color == chess.WHITE else 7 - r


def indep_category(board):
    """Catégorie recalculée à partir des seules cases des rois (écrit à part du générateur)."""
    att = board.turn

    def side(sq, color):
        if rel(sq, color) > 1:
            return None
        return {0: "q", 1: "q", 2: "q", 3: "c", 4: "c", 6: "k", 7: "k"}.get(chess.square_file(sq))

    d, a = side(board.king(not att), not att), side(board.king(att), att)
    if d == "c":
        return "centre" if a else None
    if d in ("q", "k") and a in ("q", "k"):
        return "opposes" if d != a else "meme"
    return None


def pawn_files(board, color):
    return {chess.square_file(s) for s in board.pieces(chess.PAWN, color)}


def weakened(board):
    """Roque entamé, vérifié à part : sur une colonne a-c / f-h voisine du roi, pas de pion du
    défenseur devant lui, ou le premier à deux rangées ou plus (sans fou de fianchetto derrière)."""
    att, dfn = board.turn, not board.turn
    k = board.king(dfn)
    kf, kr = chess.square_file(k), rel(k, dfn)
    for f in (kf - 1, kf, kf + 1):
        if f not in (0, 1, 2, 5, 6, 7):
            continue
        ranks = sorted(rel(s, dfn) for s in board.pieces(chess.PAWN, dfn) if chess.square_file(s) == f and rel(s, dfn) > kr)
        if not ranks:
            return True
        if ranks[0] - kr >= 2:
            behind_rank = ranks[0] - 1
            sq = chess.square(f, behind_rank if dfn == chess.WHITE else 7 - behind_rank)
            p = board.piece_at(sq)
            if not (p and p.color == dfn and p.piece_type == chess.BISHOP):
                return True
    return False


def check_data():
    check("[données] banque présente", bool(ATTACKS), f"({DATA})")
    if not ATTACKS:
        return
    counts = {c: sum(1 for a in ATTACKS if a["category"] == c) for c in CATS}
    check("[données] au moins 60 positions", len(ATTACKS) >= 60, f"({len(ATTACKS)})")
    check("[données] au moins 15 par catégorie", min(counts.values()) >= 15, f"({counts})")
    check("[données] ids uniques", len({a["id"] for a in ATTACKS}) == len(ATTACKS))
    check("[données] positions uniques", len({" ".join(a["fen"].split()[:2]) for a in ATTACKS}) == len(ATTACKS))
    bad = {k: [] for k in ("legal", "turn", "cat", "facts", "eval", "material", "file", "storm", "shield", "castle", "head", "kings")}
    for a in ATTACKS:
        b = chess.Board(a["fen"])
        att = b.turn
        if not b.is_valid() or b.is_check():
            bad["legal"].append(a["id"])
        if ("w" if att == chess.WHITE else "b") != a["attacker"]:
            bad["turn"].append(a["id"])
        if indep_category(b) != a["category"]:
            bad["cat"].append(a["id"])
        f = attack_facts.facts(b)
        if (attack_facts.theme(a["category"], f), attack_facts.goal(a["category"], f), attack_facts.plan(b, a["category"], f)) != (a["theme"], a["goal"], a["plan"]):
            bad["facts"].append(a["id"])
        if not (150 <= a["eval"] <= 500):
            bad["eval"].append(a["id"])
        if attack_facts.material(b, att) - attack_facts.material(b, not att) > 1:
            bad["material"].append(a["id"])
        g = a["goal"]
        if not g.startswith(SHORT[a["category"]] + " : "):
            bad["head"].append(a["id"])
        dk = b.king(not att)
        near = {chess.square_file(dk) + d for d in (-1, 0, 1)}
        m = re.search(r"colonne ([a-h])\b", g)
        if m:
            fi = "abcdefgh".index(m.group(1))
            if fi in pawn_files(b, att) or fi not in near:
                bad["file"].append(a["id"])
        m = re.search(r"pousse (?:ton pion|tes pions) ([a-h](?:(?:, | et )[a-h])*)\.", g)
        if m:
            for fl in re.findall(r"[a-h]", m.group(1)):
                fi = "abcdefgh".index(fl)
                if fi not in near or not any(chess.square_file(s) == fi and rel(s, att) >= 3 for s in b.pieces(chess.PAWN, att)):
                    bad["storm"].append(a["id"])
        if "roque affaibli" in g and not weakened(b):
            bad["shield"].append(a["id"])
        rights = a["fen"].split()[2]
        dfn_rights = [c for c in rights if (c.islower() if att == chess.WHITE else c.isupper())]
        if ("avant qu'il roque" in g and not dfn_rights) or ("ne peut plus roquer" in g and dfn_rights):
            bad["castle"].append(a["id"])
        if chess.square_name(dk) not in a["plan"] or (a["category"] != "centre" and chess.square_name(b.king(att)) not in a["plan"]):
            bad["kings"].append(a["id"])
    labels = {
        "legal": "positions légales, pas d'échec au départ",
        "turn": "attaquant au trait",
        "cat": "catégorie recalculée depuis les rois",
        "facts": "thème, consigne et plan égaux à attack_facts.py",
        "eval": "éval de sélection entre +1,5 et +5",
        "material": "pas plus d'un pion d'avance matérielle",
        "file": "colonne citée : sans pion de l'attaquant, voisine du roi adverse",
        "storm": "pions de la tempête : sur leur 4e rangée ou plus, voisins du roi adverse",
        "shield": "« roque affaibli » vérifié sur l'échiquier",
        "castle": "droits de roque conformes à la consigne",
        "head": "consigne commencée par la catégorie",
        "kings": "plan qui cite le roi adverse (et le sien quand les deux sont roqués)",
    }
    for k, label in labels.items():
        check(f"[données] {label}", not bad[k], f"({bad[k][:5]})")
    themes = {a["theme"] for a in ATTACKS}
    check("[données] plusieurs thèmes", len(themes) >= 3, f"({themes})")
    check("[données] chaque catégorie a ses positions avec les Blancs et les Noirs attaquants",
          all({a["attacker"] for a in ATTACKS if a["category"] == c} == {"w", "b"} for c in CATS))
    # Garde du fianchetto : g6 + Fg7 n'est pas un roque affaibli.
    fian = chess.Board("r2q1rk1/pp2ppbp/2np1np1/8/3NP3/2N1BP2/PPPQ2PP/2KR1B1R w - - 0 10")
    check("[données] fianchetto g6/Fg7 : pas de roque affaibli", attack_facts.facts(fian)["shieldAdvanced"] == [])
    check("[données] fianchetto : contrôle indépendant d'accord", not weakened(fian))


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
    """Un coup de l'attaquant (second Stockfish), puis la réponse du défenseur. True si joué."""
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
    """Par worker oracle (celui qui reçoit `go movetime 300`, suivi de l'avantage) : [go envoyés, bestmove reçus]."""
    return page.evaluate("""() => {
      const out = {}
      for (const [i, m] of window.__uci) if (m.startsWith('go movetime 300')) (out[i] ??= [0, 0])[0]++
      for (const i of window.__bestmoves) if (i in out) out[i][1]++
      return out
    }""")


def wait_offer(page, before, timeout_s=5):
    """Après la réponse du défenseur : attend la proposition « Attaque réussie », ou la fin de l'éval
    de l'avantage (bestmove reçu pour un `go movetime 300` postérieur à `before`) puis le rendu qui
    peut la suivre. Retourne data-decisive."""
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


def rows(page):
    return page.evaluate(READ_ROWS)


def open_attack(page, pid):
    page.goto(f"{BASE}/#/attaque/{pid}")
    ok = ck.appears(f"[{pid}] partie affichée", page, GAME)
    page.wait_for_timeout(300)
    return ok


def no_overflow(page, tag):
    check(f"[mise en page] {tag} : pas de débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")


def bar_fits(page, tag):
    w = page.evaluate(f"""() => {{
      const g = document.querySelector("{GAME}")
      const bar = g && g.lastElementChild
      const sub = g && g.querySelector("[data-testid='objective'] p.text-xs")
      return bar ? [bar.scrollWidth - bar.clientWidth, sub ? sub.scrollWidth - sub.clientWidth : 0] : null
    }}""")
    check(f"[mise en page] {tag} : barre d'actions sans débordement", w is not None and w[0] <= 0, f"({w})")
    return w


def board_height(page):
    box = page.locator(".boardbox").first.bounding_box()
    return round(box["height"]) if box else None


# ---------- Suite ----------

def suite(p):
    check_data()
    browser = p.chromium.launch(headless=True)
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(UCI_SPY)
    ctx.add_init_script(QA_WAIT)
    page = ctx.new_page()

    # --- 2. Entrée, liste, niveau ---
    page.goto(f"{BASE}/#/apprendre")
    ck.appears("[entrée] carte sur l'accueil Apprendre", page, "main a:has-text(\"Entraîneur d'attaque\")")
    if page.locator("main a", has_text="Entraîneur d'attaque").count():
        page.locator("main a", has_text="Entraîneur d'attaque").tap()
    ck.appears("[liste] page de l'entraîneur", page, "[data-testid='attack-item']")
    check("[liste] URL #/attaque", page.evaluate("() => location.hash").startswith("#/attaque"), f"({page.url})")
    check("[liste] onglet Apprendre allumé", page.locator("nav a[aria-current]", has_text="Apprendre").locator("visible=true").count() == 1)
    for c in CATS:
        tab = page.locator(f"[role='tab'][data-category='{c}']")
        if tab.count():
            tab.tap()
            page.wait_for_timeout(150)
        n = page.locator("[data-testid='attack-item']").count()
        want = sum(1 for a in ATTACKS if a["category"] == c)
        check(f"[liste] onglet {SHORT[c]} : ses {want} positions", tab.count() == 1 and n == want and n > 0, f"({n})")
    shot(page, "attaque_list_852")
    no_overflow(page, "liste 393x852")

    page.locator("[role='radio'][data-level='1500']").first.tap() if page.locator("[role='radio'][data-level='1500']").count() else ck.fail("[niveau] pastille 1500")
    page.reload()
    ck.appears("[niveau] liste rechargée", page, "[data-testid='defender']")
    check("[niveau] 1500 mémorisé après rechargement",
          page.locator("[role='radio'][data-level='1500'][aria-checked='true']").count() == 1)
    check("[niveau] mémorisé dans localStorage", page.evaluate(f"() => localStorage.getItem('{PREFS}')") == json.dumps({"level": 1500}).replace(" ", ""))

    if not ATTACKS:
        browser.close()
        return

    # --- 3. Options UCI du défenseur et de l'oracle ---
    first = next(a for a in ATTACKS if a["category"] == "opposes")
    color = first["attacker"]
    if open_attack(page, first["id"]):
        check("[partie] consigne affichée", page.locator("[data-testid='objective']", has_text=first["goal"]).count() == 1)
        check("[partie] pas de bouton Nulle", page.get_by_role("button", name="Nulle").count() == 0)
        check("[partie] puce de niveau « 1500 »", "1500" in (page.locator("[data-testid='level-chip']").text_content() or ""))
        check("[partie] ligne moteur « Elo 1500 »", page.locator(GAME, has_text="Elo 1500").count() == 1)
        h0 = board_height(page)
        shot(page, "attaque_game_852")
        no_overflow(page, "partie 393x852")
        bar_fits(page, "partie 393x852")
        page.get_by_role("button", name="Conseils").tap()
        check("[partie] « Conseils ▾ » déplie le plan", page.locator(GAME, has_text=first["plan"][:40]).count() == 1)
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
        # Indice : moteur jamais bridé.
        page.get_by_role("button", name="Indice").tap()
        ck.appears("[indice] flèche affichée", page, "[id^='chessboard-'] marker[id*='arrowhead']", timeout=20000, state="attached")
        ws = workers(uci_log(page))
        hint_w = [i for i, m in ws.items() if "go depth 14" in m]
        check("[uci] Indice calculé par un autre moteur que le défenseur", hint_w and defender and hint_w[0] != defender[0], f"({hint_w} / {defender})")
        check("[uci] le moteur de l'indice n'est jamais bridé",
              hint_w and not any("UCI_LimitStrength value true" in m for m in ws[hint_w[0]]))
        oracle = [i for i, m in ws.items() if "go movetime 300" in m]
        check("[uci] suivi de l'avantage : moteur non bridé", oracle and all(not any("UCI_LimitStrength value true" in m for m in ws[i]) for i in oracle), f"({oracle})")
        check("[partie] Indice : tentative marquée « avec aide »", page.locator(GAME, has_text="avec aide").count() >= 1)

        # Rechargement : la partie reprend.
        fen_before = attr(page, "fen")
        page.reload()
        ck.appears("[reprise] partie après rechargement", page, GAME)
        page.wait_for_timeout(400)
        check("[reprise] même position après rechargement", attr(page, "fen") == fen_before, f"({attr(page, 'fen')})")

        # Changement de niveau en partie : la position repart, nouvelle option avant le go suivant.
        n_rows = len(rows(page))
        page.locator("[data-testid='level-chip']").tap()
        ck.appears("[niveau] feuille de niveau", page, "[data-testid='level-sheet']")
        page.locator("[data-testid='level-sheet'] [role='radio'][data-level='max']").tap()
        page.locator("[data-testid='level-confirm']").tap()
        page.wait_for_timeout(300)
        check("[niveau] la position repart du début", attr(page, "fen") == first["fen"], f"({attr(page, 'fen')})")
        check("[niveau] puce « Max »", "Max" in (page.locator("[data-testid='level-chip']").text_content() or ""))
        r = rows(page)
        check("[niveau] tentative remplacée notée abandonnée", len(r) == n_rows + 1 and r[-1]["outcome"] == "abandon" and r[-1]["defenderElo"] == 1500, f"({r[-1:] })")
        log_len = len(uci_log(page))
        play_best(page, color, 10, "max")
        wait_turn(page, color)
        ws = workers(uci_log(page)[log_len:])
        defender2 = [i for i, m in ws.items() if "go movetime 700" in m]
        check("[uci] pleine force : UCI_LimitStrength false avant le go suivant",
              len(defender2) == 1 and "setoption name UCI_LimitStrength value false" in options_before_first_go(ws[defender2[0]]),
              f"({ {i: options_before_first_go(m) for i, m in ws.items()} })")
        check("[niveau] Max mémorisé", page.evaluate(f"() => localStorage.getItem('{PREFS}')") == '{"level":null}')

        # Annuler : « avec aide ».
        page.get_by_role("button", name="Annuler").tap()
        page.wait_for_timeout(300)
        check("[annuler] coup repris", attr(page, "fen") == first["fen"])
        check("[annuler] tentative « avec aide »", page.locator(GAME, has_text="avec aide").count() >= 1)

        # Recommencer après un coup : tentative notée abandonnée.
        play_best(page, color, 10, "recommencer")
        wait_turn(page, color)
        n_rows = len(rows(page))
        page.get_by_role("button", name="Recommencer").tap()
        page.wait_for_timeout(300)
        r = rows(page)
        check("[recommencer] position de départ", attr(page, "fen") == first["fen"])
        check("[recommencer] tentative notée abandonnée", len(r) == n_rows + 1 and r[-1]["outcome"] == "abandon" and r[-1]["success"] == 0
              and r[-1]["assisted"] is True and r[-1]["defenderElo"] is None, f"({r[-1:]})")

        # Une autre position remplace la tentative en cours : notée abandonnée.
        play_best(page, color, 10, "remplacement")
        wait_turn(page, color)
        other = next(a for a in ATTACKS if a["category"] == "meme")
        n_rows = len(rows(page))
        if open_attack(page, other["id"]):
            check("[remplacement] simple coup d'œil : rien de noté", len(rows(page)) == n_rows)
            play_best(page, other["attacker"], 10, "remplacement")
            page.wait_for_timeout(300)
            r = rows(page)
            check("[remplacement] tentative remplacée notée abandonnée", len(r) == n_rows + 1 and r[-1]["itemId"] == first["id"]
                  and r[-1]["outcome"] == "abandon", f"({r[-1:]})")
            wait_turn(page, other["attacker"])
            page.get_by_role("button", name="Recommencer").tap()

    # --- 5. Vraie attaque jusqu'à la réussite, défenseur à 1320 ---
    page.evaluate(f"() => localStorage.setItem('{PREFS}', JSON.stringify({{ level: 1320 }}))")
    target = max(ATTACKS, key=lambda a: (a["eval"], a["id"]))
    tcolor = target["attacker"]
    if open_attack(page, target["id"]):
        check("[attaque] défenseur Elo 1320", "1320" in (page.locator("[data-testid='level-chip']").text_content() or ""))
        h_start = board_height(page)
        plies = 0
        evals = None  # compteurs de l'oracle avant le dernier coup joué (None : aucun coup encore)
        while plies < 80:
            if attr(page, "status") == "over" or attr(page, "decisive") != "none":
                break
            if wait_turn(page, tcolor) != "turn":
                break
            if evals is not None and wait_offer(page, evals) != "none":
                break
            evals = oracle_evals(page)
            if not play_best(page, tcolor, 12, "attaque"):
                break
            plies += 2
        decisive, status = attr(page, "decisive"), attr(page, "status")
        print(f"[info] attaque {target['id']} : {plies} demi-coups, decisive={decisive}, status={status}, verdict={attr(page, 'verdict')}")
        check("[attaque] réussie avant 80 demi-coups (avantage décisif ou mat)", decisive == "offered" or (status == "over" and attr(page, "verdict") == "success"),
              f"(decisive={decisive}, status={status})")
        if decisive == "offered":
            check("[attaque] bandeau « Attaque réussie » en place", page.locator("[data-testid='objective']", has_text="Attaque réussie").count() == 1)
            check("[attaque] échiquier immobile sous le bandeau", board_height(page) == h_start, f"({board_height(page)} / {h_start})")
            shot(page, "attaque_reussie_852")
            bar_fits(page, "bandeau réussite 393x852")
            page.reload()
            ck.appears("[attaque] rechargement pendant la proposition", page, GAME)
            page.wait_for_timeout(400)
            check("[attaque] proposition retrouvée après rechargement", attr(page, "decisive") == "offered"
                  and page.get_by_role("button", name="Conclure").count() == 1)
            r = rows(page)
            check("[attaque] réussite notée dès l'avantage décisif", r and r[-1]["itemId"] == target["id"] and r[-1]["outcome"] == "decisive"
                  and r[-1]["success"] == 1 and r[-1]["defenderElo"] == 1320 and r[-1]["assisted"] is False, f"({r[-1:]})")
            page.get_by_role("button", name="Conclure").tap()
            page.wait_for_timeout(300)
            check("[attaque] Conclure : partie terminée et gagnée", attr(page, "status") == "over" and attr(page, "verdict") == "success")
            check("[attaque] Conclure : pas d'« Annuler » (fin hors échiquier)", page.get_by_role("button", name="Annuler").count() == 0)
            check("[attaque] une seule ligne pour la tentative", sum(1 for x in rows(page) if x["itemId"] == target["id"] and x["outcome"] != "abandon") == 1)
        elif status == "over":
            r = rows(page)
            check("[attaque] mat noté", r and r[-1]["outcome"] == "mate" and r[-1]["success"] == 1 and r[-1]["defenderElo"] == 1320, f"({r[-1:]})")
        ended = attr(page, "status") == "over"
        shot(page, "attaque_fin_852")
        bar_fits(page, "fin 393x852")
        no_overflow(page, "fin 393x852")

        # Plan : calque EngineContinuation depuis la position de départ.
        plan_btn = page.get_by_role("button", name="Plan", exact=True)
        if plan_btn.count():
            plan_btn.tap()
            ck.appears("[plan] calque du plan de Stockfish", page, "[data-continuation='plan']")
            page.keyboard.press("Escape")
            page.wait_for_timeout(300)
        else:
            ck.fail("[plan] bouton Plan en fin de partie")

        # Analyser puis retour : la partie terminée est restaurée.
        page.get_by_role("button", name="Analyser").tap()
        page.wait_for_timeout(800)
        check("[analyse] ouverte", page.evaluate("() => location.hash").startswith("#/analyse"), f"({page.url})")
        back = page.get_by_role("button", name=re.compile("Retour à l'attaque"))
        if back.count():
            back.first.tap()
            ck.appears("[analyse] retour à l'attaque", page, GAME)
            page.wait_for_timeout(300)
            check("[analyse] partie terminée restaurée", attr(page, "status") == "over" and attr(page, "verdict") == "success")
        else:
            ck.fail("[analyse] bouton « Retour à l'attaque »")

        # Suivante.
        url_before = page.url
        page.get_by_role("button", name="Suivante").tap()
        page.wait_for_timeout(400)
        check("[suivante] autre position", page.url != url_before and "#/attaque/" in page.url, f"({page.url})")

        # Liste : réussie à 1320.
        page.goto(f"{BASE}/#/attaque?c={target['category']}")
        ck.appears("[liste] retour", page, "[data-testid='attack-item']")
        item = page.locator(f"[data-testid='attack-item'][data-id='{target['id']}']")
        check("[liste] position marquée « ✓ battu à 1320 »", item.count() == 1 and "✓ battu à 1320" in (item.text_content() or ""), f"({item.text_content() if item.count() else None})")
        tab = page.locator(f"[role='tab'][data-category='{target['category']}']").text_content() or ""
        check("[liste] onglet : 1 position réussie", re.search(r"(?<!\d)1/\d+", tab) is not None, f"({tab})")

        # Même position rouverte depuis la liste (sans retour d'analyse) après un autre choix de
        # niveau : la partie terminée à 1320 n'est pas reprise, son niveau non plus.
        if ended:
            page.locator("[role='radio'][data-level='2500']").first.tap() if page.locator("[role='radio'][data-level='2500']").count() else ck.fail("[niveau] pastille 2500")
            if open_attack(page, target["id"]):
                chip = page.locator("[data-testid='level-chip']").text_content() or ""
                check("[niveau] position terminée rouverte : puce au niveau choisi « 2500 »", "2500" in chip and "1320" not in chip, f"({chip})")
                check("[niveau] position terminée rouverte : ligne moteur « Elo 2500 »", page.locator(GAME, has_text="Elo 2500").count() == 1)
                check("[niveau] position terminée rouverte : partie repartie du début", attr(page, "status") == "playing" and attr(page, "fen") == target["fen"],
                      f"(status={attr(page, 'status')}, fen={attr(page, 'fen')})")
                stored = page.evaluate("() => JSON.parse(localStorage.getItem('chess-local-position-game-v1') || 'null')")
                check("[niveau] position terminée rouverte : niveau 2500 persisté avec la partie",
                      stored is not None and stored.get("key") == f"attaque:{target['id']}" and stored.get("level") == 2500 and stored.get("end") is None,
                      f"({stored and {k: stored.get(k) for k in ('key', 'level', 'end')}})")

    # --- 6. Mise en page ---
    page.set_viewport_size({"width": 393, "height": 660})
    page.goto(f"{BASE}/#/attaque")
    page.wait_for_timeout(400)
    shot(page, "attaque_list_660")
    no_overflow(page, "liste 393x660")
    if open_attack(page, ATTACKS[0]["id"]):
        shot(page, "attaque_game_660")
        no_overflow(page, "partie 393x660")
        box = page.get_by_role("button", name="Abandonner").bounding_box()
        check("[mise en page] 393x660 : barre d'actions à l'écran", box is not None and box["y"] + box["height"] <= 660)
    ctx.close()

    dctx = desktop_context(browser, ck)
    dctx.add_init_script(UCI_SPY)
    dpage = dctx.new_page()
    dpage.goto(f"{BASE}/#/attaque")
    ck.appears("[desktop] liste", dpage, "[data-testid='attack-item']")
    shot(dpage, "attaque_list_1440")
    no_overflow(dpage, "liste 1440x900")
    check("[desktop] onglet Apprendre allumé (nav latérale)", dpage.locator("nav a[aria-current]", has_text="Apprendre").locator("visible=true").count() == 1)
    if open_attack(dpage, ATTACKS[0]["id"]):
        shot(dpage, "attaque_game_1440")
        no_overflow(dpage, "partie 1440x900")
    browser.close()


ck.run(suite)
