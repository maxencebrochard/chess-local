"""E2E de la chasse aux bugs Q4 : un scénario utilisateur par bug reproduit, rouge avant son correctif.

- reset : « Réinitialiser l'app » efface aussi la partie de Jouer en cours, la séance de puzzle et
  les préférences de Mats éclair (elles survivaient : la partie reprenait après « Tout effacer »).
- brillant : un vrai sacrifice (Fxh7+ du coup du roi grec) est classé Brillant (jamais atteint).
- promotion : une promotion sur une case défendue ne sacrifie qu'un pion, elle n'est pas Brillante
  (la dame promue comptait comme une pièce donnée).
- repetition : le camp gagnant qui provoque la triple répétition reçoit « Gain manqué », et la courbe
  du bilan finit à 50 % (le coup n'était pas sanctionné, la courbe restait sur l'avantage).
- repetition_continuee : la même répétition non réclamée, suivie d'autres coups, n'est pas une nulle :
  ni Gain manqué ni courbe à 50 %, et les positions suivantes sont évaluées.
- coup_force : un seul coup légal n'est pas un « Très bon » coup.
- liste_noirs : sur ordinateur, quand les Noirs ont le trait au départ, la liste des coups laisse la
  case blanche vide et dessine le premier coup en figurine noire.
- eval_mat_noir : sur ordinateur, le « # » de la barre d'éval reste lisible quand les Noirs ont maté.
- variante : une ligne modifiée dans l'analyse d'une partie de l'Archive n'écrit plus ses fautes au
  nom de cette partie (clé `game:<id>`, libellé de la partie).
- date_pgn : l'en-tête [Date] d'une partie finie à 0 h 30 (heure de Paris) porte le jour local.
- finale_fuite : quitter Apprendre pendant la réflexion de Stockfish dans une finale ne recrée pas de
  worker après le démontage.

`BUG_CASE=<nom>[,<nom>...]` ne lance que ces scénarios (preuves par mutation, mise au point).

Usage : npm run test:e2e -- --suite bug_hunt   (aussi en `npm run test:e2e:dev`, StrictMode)
"""
import os
import re

import chess

from helpers import BASE, HOLD_BESTMOVE, Checker, desktop_context, mobile_context, piece_on, shot, tap_move, wait_js, open_learn_session

ck = Checker("bug_hunt")
check = ck.check
ONLY = set(filter(None, os.environ.get("BUG_CASE", "").split(","))) or None

# Workers vivants : constructeur et terminate() comptés, pour voir un moteur Stockfish orphelin.
WORKER_SPY = """(() => {
  const Native = window.Worker
  window.__workersLive = 0
  window.__workersMade = 0
  window.Worker = class extends Native {
    constructor(...a) { super(...a); window.__workersLive++; window.__workersMade++; this.__dead = false }
    terminate() { if (!this.__dead) { this.__dead = true; window.__workersLive-- } return super.terminate() }
  }
})()"""

IDB = """([store]) => new Promise((res, rej) => {
  const r = indexedDB.open('chess-local')
  r.onsuccess = () => {
    const db = r.result
    if (!db.objectStoreNames.contains(store)) { db.close(); res([]); return }
    const q = db.transaction(store).objectStore(store).getAll()
    q.onsuccess = () => { db.close(); res(q.result) }
    q.onerror = () => { db.close(); rej(q.error) }
  }
  r.onerror = () => rej(r.error)
})"""

ADD_GAME = """(game) => new Promise((res, rej) => {
  const r = indexedDB.open('chess-local')
  r.onsuccess = () => {
    const db = r.result
    const tx = db.transaction('games', 'readwrite')
    const q = tx.objectStore('games').add(game)
    tx.oncomplete = () => { db.close(); res(q.result) }
    tx.onerror = () => { db.close(); rej(tx.error) }
  }
  r.onerror = () => rej(r.error)
})"""

# Tallies du résumé du bilan : {libellé: [blancs, noirs]}.
TALLIES = """() => {
  const out = {}
  for (const row of document.querySelectorAll('.fixed .grid')) {
    const s = row.querySelectorAll(':scope > span')
    if (s.length !== 4) continue
    out[s[0].textContent.trim()] = [+s[1].textContent, +s[3].textContent]
  }
  return out
}"""

GREEK_GIFT = """[FEN "rnbq1rk1/pppn1ppp/4p3/3pP3/1b1P4/2NB1N2/PPP2PPP/R1BQK2R w KQ - 0 7"]
[SetUp "1"]

7. Bxh7+ Kxh7 8. Ng5+ *"""

# Les Blancs, une dame de plus, tournent en rond : 5. Dd3 est la troisième occurrence de la même
# position (le départ, dame en d1, n'est jamais revu : c'est bien ce coup qui fait la nulle).
REPETITION = """[FEN "6k1/5ppp/8/8/8/8/5PPP/3Q2K1 w - - 0 1"]
[SetUp "1"]

1. Qd3 Kh8 2. Qd2 Kg8 3. Qd3 Kh8 4. Qd2 Kg8 5. Qd3 *"""

# La même répétition, non réclamée : la partie continue et les Blancs gardent leur dame de plus.
REPETITION_CONTINUED = REPETITION.replace("5. Qd3 *", "5. Qd3 Kh8 6. h3 Kg8 *")

# Noirs au trait, en échec, un seul coup légal (Rd7), position équilibrée (vérifié avec python-chess
# et Stockfish 18 natif, profondeur 10 : -0,07 pour les Noirs).
FORCED = """[FEN "rnbq1b1r/4pppp/p1p1kn2/p2pQ3/2PP3P/RP3P2/3NP1P1/2B1KBNR b K - 5 15"]
[SetUp "1"]

15... Kd7 *"""

# 1. b8=D+ est le seul bon coup (Cxb8 Te8#), sur une case que le cavalier d7 défend : Stockfish 18
# natif, profondeur 10, +3,95 contre +0,35 pour le deuxième coup, +3,58 après (python-chess).
PROMOTION = """[FEN "6k1/1P1n1ppp/8/8/8/8/2q2PPP/4R1K1 w - - 0 1"]
[SetUp "1"]

1. b8=Q+ *"""

FOOLS_MATE_FEN = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"


def wanted(name):
    return ONLY is None or name in ONLY


def open_analysis(ctx):
    page = ctx.new_page()
    page.goto(f"{BASE}/#/analyse")
    ck.appears("[analyse] échiquier affiché", page, "[data-square='e4']", timeout=30000)
    page.wait_for_timeout(800)
    return page


def load_text(page, text):
    options = page.locator("main button:visible", has_text="Options")
    if options.count():  # mobile : barre d'actions, puis feuille Options
        options.first.click()
        page.locator("button:visible", has_text="Importer PGN ou FEN").click()
    else:  # ordinateur : bouton « PGN » de la colonne de droite
        page.get_by_role("button", name="PGN", exact=True).click()
    page.wait_for_selector("textarea", timeout=5000)
    page.fill("textarea", text)
    page.locator("button:visible", has_text="Charger").click()
    page.wait_for_timeout(600)


def run_review(page, tag):
    page.locator("main button:visible", has_text="Bilan").first.click()
    return ck.appears(f"[{tag}] bilan calculé (résumé affiché)", page, "text=Démarrer le bilan", timeout=240000)


def graph_pcts(page):
    """Win% blanc de chaque point de la courbe du résumé, position initiale comprise (y = 32 - pct * 0,32 dans le SVG)."""
    d = page.evaluate("() => [...document.querySelectorAll('svg.cursor-pointer path')].find((p) => p.getBoundingClientRect().width > 0)?.getAttribute('d') ?? ''")
    pts = re.findall(r"L(-?[\d.]+),(-?[\d.]+)", d)
    return [round((32 - float(y)) / 0.32, 1) for _, y in pts[:-1]]  # le dernier L est le coin bas droit de l'aire


def graph_last_pct(page):
    pcts = graph_pcts(page)
    return pcts[-1] if len(pcts) >= 2 else None


def case_reset(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    # Une séance de puzzle, une préférence de Mats éclair, puis une partie contre un bot.
    page.goto(f"{BASE}/#/puzzles")
    ck.appears("[reset] puzzle affiché", page, "[data-square='e4']", timeout=30000)
    page.wait_for_timeout(1500)
    page.evaluate("() => localStorage.setItem('chess-local-mats', JSON.stringify({ cadence: { 'chrono-kq': '3min' }, showNet: false }))")
    page.goto(f"{BASE}/#/jouer")
    ck.appears("[reset] écran de configuration", page, "text=Adversaire", timeout=20000)
    page.locator("main button", has_text="Contre un bot").first.click()
    page.locator("main button", has_text="Noa").first.click()
    page.locator("main button", has_text="Blancs").first.click()
    page.get_by_role("button", name="Illimité", exact=True).click()
    page.get_by_role("button", name="Jouer", exact=True).click()
    ck.appears("[reset] partie lancée", page, "[data-square='e2']", timeout=15000)
    tap_move(page, "e2", "e4")
    page.wait_for_timeout(2500)
    keys = page.evaluate("() => ['chess-local-play-game', 'chess-local-puzzle-session', 'chess-local-mats'].filter((k) => localStorage.getItem(k) !== null)")
    check("[reset] avant : partie, séance de puzzle et préférences de Mats enregistrées", len(keys) == 3, f"({keys})")

    page.goto(f"{BASE}/#/donnees")
    page.click("[data-testid=reset-btn]")
    ck.appears("[reset] première confirmation", page, "[data-testid=reset-sheet]")
    page.click("[data-testid=reset-confirm]")
    ck.appears("[reset] deuxième confirmation", page, "[data-testid=reset-final-sheet]")
    page.click("[data-testid=reset-final-confirm]")
    ck.appears("[reset] l'app redémarre sur l'accueil", page, "main :text('Problèmes')", timeout=20000)
    left = page.evaluate("() => ['chess-local-play-game', 'chess-local-puzzle-session', 'chess-local-mats'].filter((k) => localStorage.getItem(k) !== null)")
    check("[reset] après « Tout effacer » : aucune de ces clés ne reste", left == [], f"({left})")
    page.goto(f"{BASE}/#/jouer")
    configured = ck.appears("[reset] Jouer s'ouvre sur la configuration, pas sur l'ancienne partie", page, "text=Adversaire", timeout=10000)
    if not configured:
        shot(page, "bug_hunt_reset_jouer")
    ctx.close()


def case_brillant(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = open_analysis(ctx)
    load_text(page, GREEK_GIFT)
    if run_review(page, "brillant"):
        t = page.evaluate(TALLIES)
        check("[brillant] Fxh7+ (sacrifice du fou sur h7) compté Brillant chez les Blancs", t.get("Brillant", [0, 0])[0] >= 1, f"({t})")
        shot(page, "bug_hunt_brillant")
        page.set_viewport_size({"width": 393, "height": 660})
        shot(page, "bug_hunt_brillant_393x660")
    ctx.close()


def case_promotion(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = open_analysis(ctx)
    load_text(page, PROMOTION)
    if run_review(page, "promotion"):
        t = page.evaluate(TALLIES)
        best = t.get("Très bon", [0, 0])[0] + t.get("Meilleur", [0, 0])[0]
        check("[promotion] b8=D+ est le meilleur coup du moteur (Très bon ou Meilleur)", best == 1, f"({t})")
        check("[promotion] b8=D+ (seul un pion donné) n'est pas Brillant", t.get("Brillant", [0, 0])[0] == 0, f"({t})")
    ctx.close()


def case_repetition(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = open_analysis(ctx)
    load_text(page, REPETITION)
    if run_review(page, "répétition"):
        t = page.evaluate(TALLIES)
        check("[répétition] 5. Dd3 (triple répétition avec une dame de plus) : Gain manqué", t.get("Gain manqué", [0, 0])[0] >= 1, f"({t})")
        last = graph_last_pct(page)
        check("[répétition] la courbe finit à 50 % (nulle)", last is not None and abs(last - 50) < 1, f"(dernier point : {last} %)")
    ctx.close()


def case_repetition_continuee(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = open_analysis(ctx)
    load_text(page, REPETITION_CONTINUED)
    if run_review(page, "répétition continuée"):
        t = page.evaluate(TALLIES)
        check("[répétition continuée] nulle non réclamée : pas de Gain manqué", t.get("Gain manqué", [0, 0]) == [0, 0], f"({t})")
        pcts = graph_pcts(page)
        check("[répétition continuée] la courbe reste aux Blancs après 5. Dd3", len(pcts) == 13 and pcts[9] > 75, f"({pcts})")
        check("[répétition continuée] les coups suivants sont évalués (dernier point aux Blancs)", len(pcts) == 13 and pcts[-1] > 75, f"({pcts})")
    ctx.close()


def case_coup_force(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = open_analysis(ctx)
    load_text(page, FORCED)
    if run_review(page, "coup forcé"):
        t = page.evaluate(TALLIES)
        check("[coup forcé] Rd7, seul coup légal, n'est pas un « Très bon » coup", t.get("Très bon", [0, 0])[1] == 0, f"({t})")
        check("[coup forcé] il est compté Meilleur", t.get("Meilleur", [0, 0])[1] == 1, f"({t})")
    ctx.close()


def case_liste_noirs(p, browser):
    ctx = desktop_context(browser, ck)
    page = open_analysis(ctx)
    load_text(page, FORCED)
    rows = page.evaluate(
        """() => [...document.querySelectorAll('div.overscroll-contain > div')]
          .filter((r) => r.offsetParent && r.firstElementChild?.textContent.trim() === '1.')
          .map((r) => [...r.children].slice(1).map((c) => c.textContent.trim()))"""
    )
    first = rows[0] if rows else None
    check("[liste noirs] première ligne : case blanche vide, Rd7 en figurine noire", first == ["", "♚d7"], f"({rows})")
    shot(page, "bug_hunt_liste_noirs")
    ctx.close()


def case_eval_mat_noir(p, browser):
    ctx = desktop_context(browser, ck)
    page = open_analysis(ctx)
    load_text(page, FOOLS_MATE_FEN)
    page.wait_for_timeout(800)
    info = page.evaluate(
        """() => {
          const span = [...document.querySelectorAll('main span')].find((s) => s.offsetParent && s.textContent === '#' && s.parentElement.title === '#')
          if (!span) return null
          const canvas = document.createElement('canvas')
          canvas.width = canvas.height = 1
          const ctx = canvas.getContext('2d')
          ctx.fillStyle = getComputedStyle(span).color
          ctx.fillRect(0, 0, 1, 1)
          const rgb = ctx.getImageData(0, 0, 1, 1).data
          return { lum: (rgb[0] + rgb[1] + rgb[2]) / 3 }
        }"""
    )
    # Mat des Noirs : la barre est entièrement sombre (#403d39), le « # » doit être clair.
    check("[éval mat noir] « # » clair sur la barre sombre", info is not None and info["lum"] > 150, f"({info})")
    shot(page, "bug_hunt_eval_mat_noir")
    ctx.close()


def case_variante(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/archive")
    page.wait_for_timeout(1500)
    game_id = page.evaluate(ADD_GAME, {
        "date": 1760000000000, "mode": "bot", "botId": "noa", "playerColor": "w", "timeControl": "illimité",
        "timeClass": "unlimited", "result": "1-0", "termination": "abandon",
        "pgn": '[Event "Partie vs Noa"]\n[Result "1-0"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 1-0',
    })
    page.goto(f"{BASE}/#/analyse?game={game_id}")
    ck.appears("[variante] partie de l'Archive chargée", page, "button[data-current]:visible", timeout=30000)
    page.wait_for_timeout(800)
    # Retour après 2...Cc6 puis une autre suite des Blancs : 3. Fa6 ?? donne le fou.
    page.locator("button[data-current]:visible").nth(3).click()
    page.wait_for_timeout(400)
    tap_move(page, "f1", "a6")
    check("[variante] 3. Fa6 joué dans l'analyse", piece_on(page, "a6") == "wB")
    if run_review(page, "variante"):
        page.wait_for_timeout(1500)
        rows = page.evaluate(IDB, ["mistakes"])
        ba6 = [r for r in rows if r.get("playedSan") == "Ba6"]
        check("[variante] la faute 3. Fa6 de la variante est relevée", len(ba6) == 1, f"({rows})")
        check("[variante] elle n'est pas rattachée à la partie de l'Archive (clé game:<id>)",
              all(r.get("gameKey") != f"game:{game_id}" for r in ba6), f"({ba6})")
        check("[variante] ni à son libellé", all("abandon" not in r.get("gameLabel", "") for r in ba6), f"({ba6})")
    ctx.close()


def case_date_pgn(p, browser):
    # 0 h 30 à Paris le 16 octobre 2026 (UTC+2) : encore le 15 en UTC.
    ctx = mobile_context(p, browser, ck, standalone=True, timezone_id="Europe/Paris")
    page = ctx.new_page()
    page.clock.set_fixed_time("2026-10-15T22:30:00Z")
    page.goto(f"{BASE}/#/jouer")
    ck.appears("[date] écran de configuration", page, "text=Adversaire", timeout=20000)
    page.locator("main button", has_text="2 joueurs").first.click()
    page.get_by_role("button", name="Illimité", exact=True).click()
    page.get_by_role("button", name="Jouer", exact=True).click()
    ck.appears("[date] partie lancée", page, "[data-square='e2']", timeout=15000)
    for frm, to in (("f2", "f3"), ("e7", "e5"), ("g2", "g4"), ("d8", "h4")):
        tap_move(page, frm, to)
    page.wait_for_timeout(1500)
    games = page.evaluate(IDB, ["games"])
    pgn = games[0]["pgn"] if games else ""
    m = re.search(r'\[Date "([^"]+)"\]', pgn)
    check("[date] partie enregistrée", len(games) == 1, f"({len(games)} parties)")
    check("[date] [Date] = jour local (2026.10.16), pas la veille UTC", m is not None and m.group(1) == "2026.10.16", f"({m.group(1) if m else pgn[:120]!r})")
    ctx.close()


def legal_move(page):
    """Un coup légal du camp au trait, lu sur l'échiquier affiché (finale : ni roque ni prise en passant)."""
    board = chess.Board(None)
    for f in "abcdefgh":
        for r in "12345678":
            code = piece_on(page, f + r)
            if code:
                board.set_piece_at(chess.parse_square(f + r), chess.Piece.from_symbol(code[1] if code[0] == "w" else code[1].lower()))
    side_text = page.locator("text=Objectif").first.inner_text()
    board.turn = chess.WHITE if "Blancs" in side_text else chess.BLACK
    # Éviter une prise qui terminerait immédiatement la finale sans recherche moteur.
    for mv in list(board.legal_moves):
        board.push(mv)
        ongoing = not board.is_game_over()
        board.pop()
        if ongoing:
            return chess.square_name(mv.from_square), chess.square_name(mv.to_square)
    raise AssertionError("La finale ne propose aucun coup permettant une réponse du moteur")


def case_finale_fuite(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(WORKER_SPY)
    ctx.add_init_script(HOLD_BESTMOVE)
    page = ctx.new_page()
    open_learn_session(page, "endgame")
    page.wait_for_timeout(1000)
    page.get_by_role("button", name="C'est parti").click()
    if not ck.appears("[finale] exercice affiché", page, "text=Objectif", timeout=15000):
        ctx.close()
        return
    page.wait_for_timeout(2500)  # éval initiale terminée
    frm, to = legal_move(page)
    # Le bestmove de l'éval qui suit le coup est retenu : la page est quittée pendant la réflexion.
    page.evaluate("() => { window.__heldUci = [] }")
    tap_move(page, frm, to)
    if not check("[finale] le moteur réfléchit après le coup", wait_js(page, "() => window.__heldUci.length > 0")):
        ctx.close()
        return
    shot(page, "bug_hunt_finale_393x852")
    # Le ✕ de la séance porte le nom accessible « Quitter la séance » depuis l'audit UI.
    page.get_by_role("button", name="Quitter la séance", exact=True).click()
    page.locator("nav a:visible", has_text="Accueil").click()
    ck.appears("[finale] accueil affiché", page, "main :text('Problèmes')", timeout=10000)
    held = page.evaluate("() => window.__releaseUci()")
    page.wait_for_timeout(3000)
    st = page.evaluate("() => ({ live: window.__workersLive, made: window.__workersMade })")
    check("[finale] recherche retenue pendant le départ", held >= 1, f"({held} bestmove)")
    check("[finale] aucun worker Stockfish vivant après le départ", st["live"] == 0, f"({st})")
    ctx.close()


CASES = [
    ("reset", case_reset), ("brillant", case_brillant), ("promotion", case_promotion), ("repetition", case_repetition),
    ("repetition_continuee", case_repetition_continuee), ("coup_force", case_coup_force),
    ("liste_noirs", case_liste_noirs), ("eval_mat_noir", case_eval_mat_noir), ("variante", case_variante),
    ("date_pgn", case_date_pgn), ("finale_fuite", case_finale_fuite),
]


def suite(p):
    if ONLY and not ONLY <= set(dict(CASES)):
        ck.fail("[suite] BUG_CASE inconnu", f"({sorted(ONLY - set(dict(CASES)))})")
        return
    browser = p.chromium.launch(headless=True)
    for name, fn in CASES:
        if wanted(name):
            print(f"--- {name}", flush=True)
            fn(p, browser)
    browser.close()


ck.run(suite)
