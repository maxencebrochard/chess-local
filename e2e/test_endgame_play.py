"""E2E « Finales jusqu'au bout » : une finale jouée contre Stockfish sans plafond de coups.

1. Accueil Apprendre -> liste des finales (toutes celles de endgames.json) par thème, « Au hasard ».
2. « Mat des deux tours » jouée jusqu'au mat par un second Stockfish dans la page : aucun verdict
   avant le mat, puis « Objectif atteint », résultat noté (liste : « Réussie »).
3. Analyser -> /analyse avec les coups -> « Retour à la finale » restaure la partie terminée.
4. Rejouer, Autre finale, Abandonner (feuille de confirmation), finale à tenir (objectif nulle,
   compteur des 50 coups), nulle proposée (refusée puis acceptée), Indice, Annuler, rechargement.
5. Bouton générique de /analyse : « Jouer contre le moteur » (#/analyse/jouer).
6. Mise en page : 393x852, 393x660 et 1440x900, sans débordement horizontal.

Les positions et les comptes sont lus dans src/data/endgames.json : rien de codé en dur, les
données peuvent changer (lot finales justes).

Usage : npm run test:e2e -- --suite endgame_play
"""
import json
import os
import time

from helpers import BASE, E2E_DIR, Checker, desktop_context, mobile_context, overflow_x, shot, tap_move

ROOT = os.path.dirname(E2E_DIR)
ck = Checker("endgame_play")
check = ck.check

ENDGAMES = json.load(open(os.path.join(ROOT, "src", "data", "endgames.json"), encoding="utf-8"))
# Mat des deux tours : légal avant et après la correction des FEN (lot finales justes), et mené
# au mat en une dizaine de coups.
WIN_ID = "rr-mate"
GAME = "[data-testid='position-game']"

# Second moteur dans la page : même worker que l'app, protocole UCI minimal, un appel à la fois.
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
    const w = new Worker(url)
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

# Lignes learnSessions du domaine des finales libres, lues dans Dexie.
READ_PLAYS = """
() => new Promise((resolve, reject) => {
  const open = indexedDB.open('chess-local')
  open.onerror = () => reject(open.error)
  open.onsuccess = () => {
    const db = open.result
    if (!db.objectStoreNames.contains('learnSessions')) { db.close(); resolve([]); return }
    const all = db.transaction('learnSessions').objectStore('learnSessions').getAll()
    all.onerror = () => { db.close(); reject(all.error) }
    all.onsuccess = () => { db.close(); resolve(all.result.filter((r) => r.domain === 'endgame-play')) }
  }
})
"""


def endgame(eg_id):
    return next(e for e in ENDGAMES if e["id"] == eg_id)


def board_pieces(fen):
    """Case -> pièce ('wK', 'bQ', ...) depuis une FEN."""
    out = {}
    for r, row in enumerate(fen.split(" ")[0].split("/")):
        f = 0
        for ch in row:
            if ch.isdigit():
                f += int(ch)
                continue
            out[f"{'abcdefgh'[f]}{8 - r}"] = ("w" if ch.isupper() else "b") + ch.upper()
            f += 1
    return out


def dom_pieces(page):
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


def game_attr(page, name):
    return page.evaluate(f"() => document.querySelector(\"{GAME}\")?.getAttribute('data-{name}') ?? null")


def fen(page):
    return game_attr(page, "fen")


def status(page):
    return game_attr(page, "status")


def best_move(page, position, depth):
    return page.evaluate(QA_ENGINE, [f"{BASE}/engine/stockfish-18-lite-single.js", position, depth])


def wait_turn(page, color, timeout_s=30):
    """Attend que le trait revienne à `color` (le moteur a répondu) ou la fin de partie."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if status(page) == "over":
            return "over"
        f = fen(page)
        if f and f.split(" ")[1] == color and game_attr(page, "thinking") == "0":
            return "turn"
        page.wait_for_timeout(100)
    return "timeout"


def play(page, uci):
    tap_move(page, uci[:2], uci[2:4], pause=150)
    if len(uci) == 5:
        promo = page.locator("div.absolute.inset-0.z-20 button")
        promo.first.wait_for(timeout=3000)
        promo.nth("qrbn".index(uci[4])).tap()


def drive(page, color, depth, max_moves, tag):
    """Le joueur suit le second Stockfish jusqu'à la fin de partie. Retourne (statut, coups joués,
    verdict vu avant la fin ?)."""
    early = False
    for n in range(max_moves):
        if wait_turn(page, color) != "turn":
            break
        before = fen(page)
        uci = best_move(page, before, depth)
        if not uci or len(uci) < 4:
            ck.fail(f"[{tag}] coup {n + 1} : le worker ne propose rien", f"({uci})")
            return status(page), n, early
        play(page, uci)
        page.wait_for_timeout(150)
        if fen(page) == before:
            ck.fail(f"[{tag}] coup {n + 1} ({uci}) refusé par l'échiquier")
            return status(page), n, early
        if status(page) != "over" and game_attr(page, "verdict") != "none":
            early = True
        if status(page) == "over":
            return "over", n + 1, early
    return status(page), max_moves, early


def open_finale(page, eg_id):
    page.goto(f"{BASE}/#/finales/{eg_id}")
    ok = ck.appears(f"[{eg_id}] partie affichée", page, GAME)
    page.wait_for_timeout(300)
    return ok


def objective_has(page, text):
    return page.locator("[data-testid='objective']", has_text=text).count() == 1


def no_overflow(page, tag):
    check(f"[mise en page] {tag} : pas de débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")


def board_visible(page, tag):
    box = page.locator("[id^='chessboard-']").first.bounding_box()
    vh = page.viewport_size["height"]
    check(f"[mise en page] {tag} : échiquier entier à l'écran", box is not None and box["y"] >= 0 and box["y"] + box["height"] <= vh,
          f"({box and round(box['y'])}..{box and round(box['y'] + box['height'])} / {vh})")


READ_ELO = """
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


def suite(p):
    browser = p.chromium.launch(headless=True)
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(QA_WAIT)
    page = ctx.new_page()

    # --- 1. Entrée et liste ---
    page.goto(f"{BASE}/#/apprendre")
    ck.appears("[entrée] bouton sur l'accueil Apprendre", page, "main button:has-text(\"Jouer une finale jusqu'au bout\")")
    page.locator("main button", has_text="Jouer une finale jusqu'au bout").tap()
    ck.appears("[liste] page des finales", page, "[data-testid='endgame-item']")
    check("[liste] URL #/finales", page.evaluate("() => location.hash") == "#/finales")
    check("[liste] onglet Apprendre allumé", page.locator("nav a[aria-current]", has_text="Apprendre").locator("visible=true").count() == 1)
    items = page.locator("[data-testid='endgame-item']")
    check("[liste] toutes les finales listées", items.count() == len(ENDGAMES), f"({items.count()} / {len(ENDGAMES)})")
    sections = page.locator("[data-testid='endgame-section']").all_inner_texts()
    check("[liste] sections par thème", any("Mats de base" in t for t in sections) and any("Pions" in t for t in sections)
          and any("Tours" in t for t in sections), f"({[t.splitlines()[0] for t in sections]})")
    check("[liste] objectif sur chaque finale", page.locator("[data-testid='endgame-item']", has_text="Gagner").count()
          + page.locator("[data-testid='endgame-item']", has_text="Tenir la nulle").count() == len(ENDGAMES))
    shot(page, "endgame_play_list")
    no_overflow(page, "liste 393x852")
    elo_before = page.evaluate(READ_ELO)
    page.get_by_role("button", name="Au hasard").tap()
    ck.appears("[liste] « Au hasard » ouvre une partie", page, GAME)
    check("[liste] « Au hasard » : URL #/finales/<id>", page.evaluate("() => location.hash").startswith("#/finales/"), f"({page.url})")

    # --- 2. Mat des deux tours jusqu'au bout ---
    mat = endgame(WIN_ID)
    if open_finale(page, WIN_ID):
        check("[mat] objectif « gagner » affiché", objective_has(page, "gagner"))
        check("[mat] échiquier conforme à la FEN", dom_pieces(page) == board_pieces(mat["fen"]))
        check("[mat] en cours", status(page) == "playing")
        shot(page, "endgame_play_mat_start_852")
        board_visible(page, "partie 393x852")
        no_overflow(page, "partie 393x852")
        page.set_viewport_size({"width": 393, "height": 660})
        page.wait_for_timeout(300)
        shot(page, "endgame_play_mat_start_660")
        board_visible(page, "partie 393x660")
        no_overflow(page, "partie 393x660")
        actions_box = page.get_by_role("button", name="Abandonner").bounding_box()
        check("[mise en page] 393x660 : barre d'actions à l'écran", actions_box is not None and actions_box["y"] + actions_box["height"] <= 660,
              f"({actions_box})")
        page.set_viewport_size({"width": 393, "height": 852})
        st, n, early = drive(page, mat["side"], depth=14, max_moves=80, tag="mat")
        check("[mat] partie terminée par le jeu", st == "over", f"({st}, {n} coups)")
        check("[mat] aucun verdict avant la fin", not early)
        check("[mat] plus de 4 coups joués avant le mat", n > 4, f"({n})")
        final = fen(page)
        check("[mat] fin = mat", objective_has(page, "Mat en"))
        check("[mat] verdict « Objectif atteint »", objective_has(page, "Objectif atteint"))
        check("[mat] data-verdict success", game_attr(page, "verdict") == "success")
        shot(page, "endgame_play_mat_mate")
        plays = page.evaluate(READ_PLAYS)
        check("[données] résultat noté dans learnSessions (id + FEN)",
              any(r["itemId"] == WIN_ID and r["success"] == 1 and r.get("fen") == mat["fen"] for r in plays), f"({plays})")
        check("[données] Elo learn-endgame inchangé", page.evaluate(READ_ELO) == elo_before, f"({elo_before} -> {page.evaluate(READ_ELO)})")

        # --- 3. Analyser puis retour ---
        hist_before = page.evaluate("() => history.length")
        page.get_by_role("button", name="Analyser").tap()
        ck.appears("[analyse] /analyse ouvert", page, "button:has-text('Retour à la finale')")
        moves_shown = page.locator("main [data-current]").count()
        check("[analyse] coups de la partie chargés", moves_shown >= n, f"({moves_shown} >= {n})")
        page.locator("button", has_text="Retour à la finale").tap()
        ck.appears("[analyse] retour à la partie", page, GAME)
        page.wait_for_timeout(400)
        check("[analyse] partie terminée restaurée", status(page) == "over" and fen(page) == final)
        check("[analyse] aller-retour sans empiler l'historique", page.evaluate("() => history.length") == hist_before,
              f"({hist_before} -> {page.evaluate('() => history.length')})")
        check("[analyse] verdict restauré", objective_has(page, "Objectif atteint"))

        # --- 4a. Annuler après la fin, puis Rejouer ---
        page.get_by_role("button", name="Annuler").tap()
        page.wait_for_timeout(400)
        check("[annuler après fin] la partie reprend", status(page) == "playing" and fen(page) != final)
        check("[annuler après fin] marquée « avec aide »", page.locator("text=avec aide").count() >= 1)
        page.get_by_role("button", name="Recommencer").tap()
        page.wait_for_timeout(500)
        check("[recommencer] position de départ", fen(page) == mat["fen"] and status(page) == "playing", f"({fen(page)})")
        check("[recommencer] plus d'aide", page.locator("text=avec aide").count() == 0)
        plays = page.evaluate(READ_PLAYS)
        check("[données] une seule ligne par tentative", len([r for r in plays if r["itemId"] == WIN_ID]) == 1, f"({len(plays)})")

        # Liste : la finale gagnée est marquée
        page.goto(f"{BASE}/#/finales")
        ck.appears("[liste] retour à la liste", page, "[data-testid='endgame-item']")
        check("[liste] « Réussie » sur la finale gagnée",
              page.locator(f"[data-testid='endgame-item'][data-id='{WIN_ID}']", has_text="Réussie").count() == 1)

    # --- 4b. Abandonner (confirmation), Autre finale ---
    if open_finale(page, WIN_ID):
        page.get_by_role("button", name="Abandonner").tap()
        ck.appears("[abandon] feuille de confirmation", page, "[data-testid='resign-sheet']")
        page.locator("[data-testid='resign-cancel']").tap()
        page.wait_for_timeout(200)
        check("[abandon] annuler garde la partie", status(page) == "playing")
        page.get_by_role("button", name="Abandonner").tap()
        page.locator("[data-testid='resign-confirm']").tap()
        page.wait_for_timeout(400)
        check("[abandon] partie terminée", status(page) == "over")
        check("[abandon] « Objectif manqué »", objective_has(page, "Objectif manqué"))
        check("[abandon] motif affiché", objective_has(page, "abandonné"))
        shot(page, "endgame_play_resign")
        page.get_by_role("button", name="Rejouer").tap()
        page.wait_for_timeout(400)
        check("[rejouer] position de départ", fen(page) == mat["fen"] and status(page) == "playing", f"({fen(page)})")
        page.get_by_role("button", name="Abandonner").tap()
        page.locator("[data-testid='resign-confirm']").tap()
        page.wait_for_timeout(300)
        page.get_by_role("button", name="Autre finale").tap()
        page.wait_for_timeout(600)
        h = page.evaluate("() => location.hash")
        check("[autre] une autre finale est ouverte", h.startswith("#/finales/") and h != f"#/finales/{WIN_ID}" and status(page) == "playing", f"({h})")

    # --- 4c. Finale à tenir : objectif nulle, compteur 50 coups, pas de nulle proposable ---
    hold = next((e for e in ENDGAMES if e["objective"] == "draw"), None)
    if hold and open_finale(page, hold["id"]):
        check("[nulle] objectif « tenir la nulle »", objective_has(page, "tenir la nulle"))
        check("[nulle] compteur des 50 coups", page.locator("text=/50 coups : \\d+\\/50/").count() >= 1)
        check("[nulle] pas de nulle proposable quand l'objectif est la nulle", page.get_by_role("button", name="Nulle").count() == 0)
        shot(page, "endgame_play_hold")

    # --- 4d. Nulle proposée par le joueur gagnant : Stockfish accepte, objectif gain manqué ---
    if open_finale(page, WIN_ID):
        page.get_by_role("button", name="Nulle").tap()
        ck.appears("[nulle] Stockfish perdant accepte", page, f"{GAME}[data-status='over']", timeout=20000)
        check("[nulle] acceptée = objectif gain manqué", objective_has(page, "Objectif manqué"))
        check("[nulle] motif « acceptée »", objective_has(page, "acceptée"))

    # --- 5. Bouton générique depuis /analyse (position où Stockfish gagne) ---
    page.goto(f"{BASE}/#/analyse")
    ck.appears("[générique] analyse ouverte", page, "main button:has-text('Options')")
    page.locator("main button", has_text="Options").tap()
    page.locator("button", has_text="Importer PGN ou FEN").tap()
    lost = "4k3/8/8/8/8/8/3q4/K7 w - - 0 1"
    page.fill("textarea", lost)
    page.click("button:has-text('Charger')")
    page.wait_for_timeout(400)
    page.locator("main button", has_text="Options").tap()
    page.locator("button", has_text="Jouer contre le moteur").locator("visible=true").tap()
    ck.appears("[générique] partie depuis la position", page, GAME)
    check("[générique] URL #/analyse/jouer", page.evaluate("() => location.hash") == "#/analyse/jouer")
    check("[générique] même position", fen(page) == lost, f"({fen(page)})")
    check("[générique] onglet Analyse allumé", page.locator("nav a[aria-current]", has_text="Analyse").locator("visible=true").count() == 1)
    check("[générique] pas d'objectif, partie libre", page.locator("[data-testid='objective']", has_text="Objectif").count() == 0)
    page.get_by_role("button", name="Nulle").tap()
    ck.appears("[nulle] refus affiché", page, "text=Stockfish refuse la nulle", timeout=20000)
    check("[nulle] refus : la partie continue", status(page) == "playing")
    play(page, best_move(page, lost, 1))
    check("[générique] coup joué puis réponse du moteur", wait_turn(page, "w") in ("turn", "over"))
    shot(page, "endgame_play_generic")
    page.get_by_role("button", name="Abandonner").tap()
    page.locator("[data-testid='resign-confirm']").tap()
    page.wait_for_timeout(300)
    check("[générique] abandon = « Défaite »", objective_has(page, "Défaite"))
    page.get_by_role("button", name="Analyser").tap()
    ck.appears("[générique] analyse avec retour à la partie", page, "button:has-text('Retour à la partie')")
    page.locator("button", has_text="Retour à la partie").tap()
    ck.appears("[générique] partie restaurée", page, f"{GAME}[data-status='over']")
    page.get_by_role("button", name="Retour").tap()
    ck.appears("[générique] retour à l'analyse", page, "main button:has-text('Options')")
    for _ in range(30):
        if dom_pieces(page) == board_pieces(lost):
            break
        page.wait_for_timeout(100)
    check("[générique] l'analyse d'origine est rouverte", dom_pieces(page) == board_pieces(lost), f"({dom_pieces(page)})")

    # --- 4e. Indice, rechargement, Annuler ---
    if open_finale(page, WIN_ID):
        start = fen(page)
        page.get_by_role("button", name="Indice").tap()
        ck.appears("[indice] flèche affichée", page, "[id^='chessboard-'] marker[id*='arrowhead']", timeout=20000, state="attached")
        check("[indice] partie marquée « avec aide »", page.locator("text=avec aide").count() >= 1)
        wait_turn(page, mat["side"])
        play(page, best_move(page, start, 8))
        check("[annuler] coup joué, flèche effacée", fen(page) != start and page.locator("[id^='chessboard-'] marker[id*='arrowhead']").count() == 0)
        check("[annuler] moteur a répondu", wait_turn(page, mat["side"]) == "turn")
        after_two = fen(page)
        page.reload()
        ck.appears("[rechargement] partie toujours là", page, GAME)
        page.wait_for_timeout(400)
        check("[rechargement] coups conservés", fen(page) == after_two, f"({fen(page)})")
        check("[rechargement] aide conservée", page.locator("text=avec aide").count() >= 1)
        page.get_by_role("button", name="Annuler").tap()
        page.wait_for_timeout(400)
        check("[annuler] retour deux demi-coups en arrière", fen(page) == start, f"({fen(page)})")
        play(page, best_move(page, start, 8))
        check("[en cours] coup joué", fen(page) != start, f"({fen(page)})")
        check("[en cours] moteur a répondu", wait_turn(page, mat["side"]) == "turn")
        stored = page.evaluate("() => localStorage.getItem('chess-local-position-game-v1')")
        page.goto(f"{BASE}/#/finales")
        if not ck.appears("[liste] badge « En cours »", page, f"[data-testid='endgame-item'][data-id='{WIN_ID}']:has-text('En cours')", timeout=5000):
            print("partie persistée :", stored)

    ctx.close()

    # --- 6. Desktop ---
    ctx = desktop_context(browser, ck)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/finales")
    ck.appears("[desktop] liste", page, "[data-testid='endgame-item']")
    shot(page, "endgame_play_list_desktop")
    page.goto(f"{BASE}/#/finales/lucena")
    ck.appears("[desktop] partie", page, GAME)
    page.wait_for_timeout(500)
    board_visible(page, "partie 1440x900")
    shot(page, "endgame_play_desktop")
    page.goto(f"{BASE}/#/analyse")
    ck.appears("[desktop] bouton générique sur /analyse", page, "main button:has-text('Jouer contre le moteur')")
    ctx.close()
    browser.close()


ck.run(suite)
