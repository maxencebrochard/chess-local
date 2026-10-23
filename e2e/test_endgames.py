"""E2E finales d'Apprendre : données justes et verdict lu sur l'échiquier, pas sur l'évaluation.

1. `node scripts/check-learn-data.mjs` : positions légales, objectifs cohérents, flèches et coups
   cités jouables, textes en français (endgames.json, courses.json, strategy.json).
2. « Mat roi + dame » : trois va-et-vient de dame ne donnent PAS « Réussi », la barre d'éval ne
   reste pas à « 0,00 » sans coup joué.
3. « Mat roi + dame » : un vrai mat donne « Réussi » avec son motif, et la barre affiche « M<n> ».
4. « L'opposition de base » : les meilleurs coups mènent à la promotion et au « Réussi », jamais « Raté ».

Le joueur est piloté par un second worker Stockfish créé dans la page (le même WASM que l'app),
sur une FEN reconstruite depuis le DOM : aucune dépendance à python-chess ni à un Stockfish natif.
Il reçoit toute la partie (`position fen <départ> moves ...`, réponses du bot déduites de l'échiquier) :
sur la seule position courante, il ne voit pas les répétitions, et sa navette de roi gagnante finissait
par une nulle par répétition quand le bot, à durée fixe, répondait autrement sous charge.

Usage : npm run test:e2e -- --suite endgames
"""
import json
import os
import subprocess
import time

from helpers import BASE, E2E_DIR, Checker, drag_piece, mobile_context, shot, tap_move

ROOT = os.path.dirname(E2E_DIR)
ck = Checker("endgames")
check = ck.check

ENDGAMES = json.load(open(os.path.join(ROOT, "src", "data", "endgames.json"), encoding="utf-8"))
DEFAULT_ELO = 800  # classement initial de learn-endgame (DEFAULT_RATING de db.ts)
POOL_SPAN = 300  # buildSession('endgame') : near(ENDGAMES, difficulté, elo, 300) puis pick()

# Math.random servi depuis une file : vide, retour au vrai hasard. Permet de choisir la finale servie.
RND_INIT = """
window.__rndQ = []
const __origRnd = Math.random
Math.random = () => (window.__rndQ && window.__rndQ.length) ? window.__rndQ.shift() : __origRnd()
"""

# Second moteur dans la page : même worker que l'app, protocole UCI minimal, un appel à la fois.
QA_ENGINE = """
async ([url, position, depth]) => {
  if (!window.__qaWorker) {
    const w = new Worker(url)
    window.__qaLines = []
    w.onmessage = (e) => window.__qaLines.push(String(e.data))
    window.__qaWorker = w
    w.postMessage('uci')
    await window.__qaWait((l) => l === 'uciok')
  }
  const w = window.__qaWorker
  window.__qaLines.length = 0
  w.postMessage(position)
  w.postMessage('go depth ' + depth)
  const bm = await window.__qaWait((l) => l.startsWith('bestmove'))
  return bm.split(' ')[1]
}
"""
QA_WAIT = """
window.__qaWait = (pred) => new Promise((resolve) => {
  const t = setInterval(() => {
    const i = window.__qaLines.findIndex(pred)
    if (i >= 0) { clearInterval(t); resolve(window.__qaLines[i]) }
  }, 5)
})
"""


# Classement learn-endgame lu dans Dexie, comme buildSession (getRating : absent = DEFAULT_RATING).
READ_RATING = """
() => new Promise((resolve, reject) => {
  const open = indexedDB.open('chess-local')
  open.onerror = () => reject(open.error)
  open.onsuccess = () => {
    const db = open.result
    if (!db.objectStoreNames.contains('ratings')) { db.close(); resolve(null); return }
    const get = db.transaction('ratings').objectStore('ratings').get('learn-endgame')
    get.onerror = () => { db.close(); reject(get.error) }
    get.onsuccess = () => { db.close(); resolve(get.result ? get.result.value : null) }
  }
})
"""


def rnd_for(eg_id, elo):
    """Valeur de Math.random qui fait tomber pick() sur cette finale dans le vivier à cet Elo."""
    pool = [e["id"] for e in ENDGAMES if abs(e["difficulty"] - elo) <= POOL_SPAN]
    if eg_id not in pool:
        raise RuntimeError(f"{eg_id} n'est pas dans le vivier à {elo} Elo : {pool}")
    return (pool.index(eg_id) + 0.5) / len(pool)


def endgame(eg_id):
    return next(e for e in ENDGAMES if e["id"] == eg_id)


def pieces(page):
    """Case -> pièce ('wK', 'bQ', ...) du premier échiquier de la page."""
    return page.evaluate(
        """() => {
          const out = {}
          const board = document.querySelector("[id^='chessboard-']")
          if (!board) return out
          board.querySelectorAll('[data-square]').forEach((sq) => {
            const p = sq.querySelector('[data-piece]')
            if (p) out[sq.getAttribute('data-square')] = p.getAttribute('data-piece')
          })
          return out
        }"""
    )


def fen_from(pcs, turn):
    """FEN de la position affichée (pas de roque ni de prise en passant dans ces finales)."""
    rows = []
    for rank in "87654321":
        row = ""
        empty = 0
        for file in "abcdefgh":
            p = pcs.get(f"{file}{rank}")
            if p:
                if empty:
                    row += str(empty)
                    empty = 0
                row += p[1].upper() if p[0] == "w" else p[1].lower()
            else:
                empty += 1
        if empty:
            row += str(empty)
        rows.append(row)
    return f"{'/'.join(rows)} {turn} - - 0 1"


def best_move(page, fen, depth, moves=()):
    position = f"position fen {fen}" + (f" moves {' '.join(moves)}" if moves else "")
    return page.evaluate(QA_ENGINE, [f"{BASE}/engine/stockfish-18-lite-single.js", position, depth])


def move_between(before, after, color):
    """Coup UCI de `color` qui mène de `before` à `after` (cases -> pièces), ou None. Ces finales
    n'ont ni roque ni prise en passant : une case quittée, une case atteinte, promotion comprise."""
    left = [sq for sq, pc in before.items() if pc[0] == color and after.get(sq) != pc]
    reached = [sq for sq, pc in after.items() if pc[0] == color and before.get(sq) != pc]
    if len(left) != 1 or len(reached) != 1:
        return None
    promo = after[reached[0]][1].lower() if before[left[0]][1] == "P" and after[reached[0]][1] != "P" else ""
    return left[0] + reached[0] + promo


def verdict(page):
    if page.locator("text=✓ Réussi").count():
        return "success"
    if page.locator("text=✗ Raté").count():
        return "fail"
    return None


def eval_label(page):
    return page.evaluate("() => document.querySelector('div.h-7 span')?.innerText ?? null")


def start_endgame(page, eg_id):
    """Ouvre Apprendre, force la finale servie, vérifie l'item lu dans sessionStorage, lance le jeu."""
    page.goto(f"{BASE}/#/apprendre/entrainement/finales")
    ck.appears("[séance] groupe Finales d'Apprendre", page, "main [data-session=endgame]")
    elo = page.evaluate(READ_RATING)
    # La même valeur plusieurs fois : la séance s'ouvre sur #/apprendre (lot 5), et les clés des
    # deux navigations (aller, puis state effacé au montage) puisent aussi dans Math.random avant
    # le tirage de la finale. La file est vidée une fois la leçon affichée.
    page.evaluate("(x) => { window.__rndQ = Array(6).fill(x) }", rnd_for(eg_id, DEFAULT_ELO if elo is None else elo))
    page.locator("main [data-session=endgame]").tap()
    ck.appears(f"[séance] leçon {eg_id}", page, "text=C'est parti")
    page.evaluate("() => { window.__rndQ = [] }")
    raw = page.evaluate("() => sessionStorage.getItem('learn-session-v1')")
    served = None
    try:
        served = json.loads(raw)["session"]["items"][0]["endgame"]["id"]
    except Exception:
        pass
    if not check(f"[séance] finale servie = {eg_id}", served == eg_id, f"(servie : {served})"):
        return False
    page.get_by_role("button", name="C'est parti").tap()
    ck.appears("[séance] échiquier affiché", page, "[id^='chessboard-']")
    page.wait_for_timeout(400)
    return True


def play(page, uci, how):
    """Joue un coup au tap ou au drag tactile, dialogue de promotion compris."""
    frm, to = uci[:2], uci[2:4]
    if how == "drag":
        drag_piece(page, frm, to)
    else:
        tap_move(page, frm, to, pause=180)
    if len(uci) == 5:
        idx = "qrbn".index(uci[4])
        promo = page.locator("div.absolute.inset-0.z-20 button")
        try:
            promo.first.wait_for(timeout=3000)
            promo.nth(idx).tap()
        except Exception:
            pass


def wait_reply(page, before, uci, color, timeout_s=30):
    """Après mon coup : attend que le bot ait répondu, ou qu'un verdict tombe.
    Retourne 'move', 'verdict', 'rejected' (mon coup n'a pas été appliqué) ou 'timeout'."""
    frm, to = uci[:2], uci[2:4]
    expected = dict(before)
    expected.pop(frm, None)
    expected[to] = f"{color}{uci[4].upper()}" if len(uci) == 5 else before[frm]
    deadline = time.time() + timeout_s
    applied = False
    while time.time() < deadline:
        now = pieces(page)
        if now == expected:
            applied = True  # mon coup est là, le bot n'a pas encore joué
        elif applied or (now != before and now.get(to, "").startswith(color) and frm not in now):
            # l'échiquier a changé au-delà de mon coup : le bot a répondu
            return "move"
        v = verdict(page)
        if v:
            return "verdict"
        page.wait_for_timeout(120)
    return "rejected" if not applied else "timeout"


def drive(page, eg, depth, max_moves, tag):
    """Le joueur suit le worker en page jusqu'au verdict. Retourne (verdict, étiquettes d'éval vues)."""
    color = eg["side"]
    labels = []
    trace = []

    def result():
        v = verdict(page)
        if v != "success":
            print(f"[diagnostic {tag}] {json.dumps(trace, ensure_ascii=False)}", flush=True)
            # Le diagnostic ne doit jamais interrompre la suite.
            try:
                print(f"[diagnostic {tag}] écran final : {page.locator('main').inner_text(timeout=2000)}", flush=True)
            except Exception as e:
                print(f"[diagnostic {tag}] écran final illisible : {e}", flush=True)
        return v, labels

    start = pieces(page)
    start_fen = fen_from(start, color)
    moves = []
    for n in range(max_moves):
        before = pieces(page)
        uci = best_move(page, start_fen, depth, moves)
        # Garder le parcours exact : les réponses du bot à durée fixe varient sous charge.
        trace.append({"avant": fen_from(before, color), "proposé": uci})
        if not uci or len(uci) < 4 or not before.get(uci[:2], "").startswith(color):
            ck.fail(f"[{tag}] coup {n + 1} : le worker ne propose rien de jouable", f"({uci})")
            return result()
        play(page, uci, "drag" if n % 2 else "tap")
        outcome = wait_reply(page, before, uci, color)
        labels.append(eval_label(page))
        trace[-1].update({"réponse": outcome, "éval": labels[-1]})
        if outcome == "rejected":
            ck.fail(f"[{tag}] coup {n + 1} ({uci}) refusé par l'échiquier")
            return result()
        if outcome == "timeout":
            ck.fail(f"[{tag}] coup {n + 1} ({uci}) : ni réponse du bot ni verdict en 30 s")
            return result()
        if outcome == "verdict":
            page.wait_for_timeout(600)
            return result()
        mine = dict(before)
        mine.pop(uci[:2], None)
        mine[uci[2:4]] = f"{color}{uci[4].upper()}" if len(uci) == 5 else before[uci[:2]]
        reply = move_between(mine, pieces(page), "b" if color == "w" else "w")
        if not reply:
            ck.fail(f"[{tag}] coup {n + 1} : réponse du bot illisible sur l'échiquier")
            return result()
        moves += [uci, reply]
        trace[-1]["bot"] = reply
    return result()


def suite(p):
    # --- 1. Données : script Node, exécutable seul par le gate ---
    res = subprocess.run(["node", "scripts/check-learn-data.mjs"], cwd=ROOT, capture_output=True, text=True)
    out = (res.stdout + res.stderr).strip()
    print(out if len(out) < 4000 else out[-4000:], flush=True)
    check("[données] check-learn-data.mjs passe", res.returncode == 0, f"(code {res.returncode})")

    browser = p.chromium.launch(headless=True)
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(RND_INIT)
    ctx.add_init_script(QA_WAIT)
    page = ctx.new_page()

    # --- 2. Roi + dame : la navette ne vaut pas un mat ---
    kq = endgame("kq-mate")
    if start_endgame(page, "kq-mate"):
        label0 = None
        for _ in range(40):
            label0 = eval_label(page)
            if label0 not in (None, "0,00"):
                break
            page.wait_for_timeout(250)
        check("[éval] évaluée dès l'affichage, sans coup joué", label0 not in (None, "0,00"), f"({label0})")
        shot(page, "endgames_kq_start")
        queen = next((sq for sq, pc in pieces(page).items() if pc == "wQ"), None)
        check("[navette] dame trouvée sur l'échiquier", queen is not None, f"({queen})")
        shuttle = [f"{queen}c2", f"c2{queen}"] * 3 if queen and queen != "c2" else []
        for n, uci in enumerate(shuttle):
            before = pieces(page)
            play(page, uci, "drag" if n % 2 else "tap")
            outcome = wait_reply(page, before, uci, "w")
            check(f"[navette] coup {n + 1} ({uci}) appliqué et bot a répondu", outcome in ("move", "verdict"), f"({outcome})")
            if outcome == "verdict":
                break
        page.wait_for_timeout(1500)
        v = verdict(page)
        check("[navette] trois va-et-vient ne donnent PAS « Réussi »", v != "success", f"(verdict : {v})")
        shot(page, "endgames_kq_shuffle")
    page.locator("header button", has_text="✕").tap()
    page.wait_for_timeout(400)

    # --- 3. Roi + dame : un vrai mat donne Réussi, avec son motif ---
    if start_endgame(page, "kq-mate"):
        v, labels = drive(page, kq, depth=16, max_moves=30, tag="mat")
        check("[mat] verdict « Réussi » sur le mat", v == "success", f"(verdict : {v}, {len(labels)} coups)")
        check("[mat] motif « Mat » affiché", page.locator("text=Mat !").count() > 0)
        check("[éval] étiquette M<n> vue avant le mat", any(l and l.startswith("M") for l in labels), f"({labels[-4:]})")
        shot(page, "endgames_kq_mate_852")
        page.set_viewport_size({"width": 393, "height": 660})
        page.wait_for_timeout(300)
        shot(page, "endgames_kq_mate_660")
        page.set_viewport_size({"width": 393, "height": 852})
    page.locator("header button", has_text="✕").tap()
    page.wait_for_timeout(400)

    # --- 4. Opposition de base : les meilleurs coups gagnent ---
    opp = endgame("kp-opposition-1")
    if start_endgame(page, "kp-opposition-1"):
        v, labels = drive(page, opp, depth=20, max_moves=40, tag="opposition")
        check("[opposition] les meilleurs coups donnent « Réussi »", v == "success", f"(verdict : {v}, {len(labels)} coups)")
        check("[opposition] jamais « Raté »", v != "fail")
        check("[opposition] motif « promu » affiché", page.locator("text=promu").count() > 0)
        shot(page, "endgames_opposition_end")

    ctx.close()
    browser.close()


ck.run(suite)
