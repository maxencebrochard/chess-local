"""Pièces et sons (F10).

Sons. Chromium headless joue l'audio sans geste ; iOS non : l'init script `WEBKIT_AUDIO` de
helpers émule la politique de WebKit (contexte `suspended` hors geste, `__background(mode)` pour
l'arrière-plan) et journalise chaque son joué avec son audibilité. Les seeds E2E coupent les
sons : ils sont rallumés ici.

Pièces : jeu par défaut « celtique » sur Jouer, Analyse, Puzzles et le sélecteur de promotion,
images réellement servies sous le sous-chemin, choix « Chessnut » dans Réglages appliqué partout
et persistant au rechargement.
"""
import json
import sys

try:
    import chess
except ImportError:
    sys.exit("python-chess manquant : pip install -r e2e/requirements.txt")

from helpers import BASE, WEBKIT_AUDIO, Checker, desktop_context, drag_piece, fmt_sounds, mobile_context, shot, sound_log, sounds_heard, tap_move

ck = Checker("pieces_sons")
check = ck.check

SOUND_ON = {"playSounds": True}


def ctx_with_audio(p, browser, settings, **kw):
    # Service worker bloqué : les routes de la suite (puzzles.json) doivent voir les requêtes.
    ctx = mobile_context(p, browser, ck, settings=settings, standalone=True, service_workers="block", **kw)
    ctx.add_init_script(WEBKIT_AUDIO)
    return ctx


def wait_sounds(page, start, n, timeout=15000):
    waited = 0
    while waited < timeout:
        if len([e for e in sound_log(page)[start:] if e["name"] != "(muet)"]) >= n:
            break
        page.wait_for_timeout(100)
        waited += 100
    return sounds_heard(page, start)


def expect_exact(name, entries, expected):
    got = [(e["name"], e["audible"]) for e in entries]
    want = [(n, True) for n in expected]
    return check(name, got == want, f"(attendu {expected}, obtenu {fmt_sounds(entries)})")


# ---------- Jouer ----------

def goto_play(page):
    page.goto(f"{BASE}/#/jouer")
    return ck.appears("[jouer] écran de configuration", page, "text=Adversaire", timeout=20000)


def start_game(page, color="Blancs"):
    page.locator("main button", has_text="Contre un bot").first.click()
    page.wait_for_timeout(100)
    page.locator("main button", has_text="Noa").first.click()
    page.locator("main button", has_text=color).first.click()
    page.get_by_role("button", name="Illimité", exact=True).click()
    page.get_by_role("button", name="Jouer", exact=True).click()
    return ck.appears(f"[jouer] partie lancée ({color})", page, "[data-square='e2']", timeout=15000)


def plies(page):
    return page.locator("main [data-current]").count()


def wait_plies(page, n, timeout=15000):
    waited = 0
    while plies(page) < n and waited < timeout:
        page.wait_for_timeout(100)
        waited += 100
    return plies(page) >= n


def resign(page):
    page.locator("main button", has_text="🏳").first.click()
    page.wait_for_timeout(300)
    btn = page.get_by_role("button", name="Oui, abandonner", exact=True)
    if btn.count() > 0:
        btn.first.click()
    page.wait_for_timeout(300)


BOT_SOUNDS = {"move-opponent", "capture", "move-check", "castle", "promote"}


def bot_reply(name, page, start):
    """Le son qui suit mon coup (entrée `start`, sons entendus seulement) est celui du bot."""
    entries = wait_sounds(page, start, 2)[1:]
    ok = len(entries) == 1 and entries[0]["name"] in BOT_SOUNDS and entries[0]["audible"]
    return check(name, ok, f"(obtenu {fmt_sounds(entries)})")


def play_white_suite(p, browser):
    ctx = ctx_with_audio(p, browser, SOUND_ON)
    page = ctx.new_page()
    if not goto_play(page):
        ctx.close()
        return
    n = len(sound_log(page))
    if not start_game(page, "Blancs"):
        ctx.close()
        return
    expect_exact("[jouer] début de partie : son game-start entendu", sounds_heard(page, n), ["game-start"])

    n = len(sound_log(page))
    drag_piece(page, "e2", "e4")
    # Premier son après le drag : le mien ; le bot peut répondre très vite, son coup est jugé ensuite.
    expect_exact("[jouer] mon coup (drag tactile) : move-self entendu", wait_sounds(page, n, 1, timeout=3000)[:1], ["move-self"])
    wait_plies(page, 2)
    bot_reply("[jouer] coup du bot : son adverse entendu", page, n)

    n = len(sound_log(page))
    drag_piece(page, "d2", "d5")  # pion : deux cases interdites
    expect_exact("[jouer] coup illégal lâché : son illegal", sounds_heard(page, n), ["illegal"])
    check("[jouer] coup illégal refusé (toujours 2 demi-coups)", plies(page) == 2, f"({plies(page)})")

    # Arrière-plan, contexte muet mais `running` : le coup suivant doit s'entendre.
    # d2-d4 est toujours légal et calme après 1.e4 et n'importe quelle réponse noire.
    page.evaluate("() => window.__background('zombie')")
    n = len(sound_log(page))
    drag_piece(page, "d2", "d4")
    entries = wait_sounds(page, n, 1)
    check("[jouer] après arrière-plan (contexte muet) : mon coup s'entend",
          len(entries) >= 1 and entries[0]["audible"] and entries[0]["name"] == "move-self", f"({fmt_sounds(entries)})")
    wait_plies(page, 4)
    page.wait_for_timeout(400)  # fin de l'animation du coup du bot : l'échiquier affiché est à jour

    # Arrière-plan, contexte `interrupted` : idem, avec un coup calme choisi sur la position réelle.
    page.evaluate("() => window.__background('interrupted')")
    n = len(sound_log(page))
    uci = quiet_white_move(page)
    drag_piece(page, uci[:2], uci[2:4])
    entries = wait_sounds(page, n, 1)
    check("[jouer] après arrière-plan (contexte interrompu) : mon coup s'entend",
          len(entries) >= 1 and entries[0]["audible"] and entries[0]["name"] == "move-self", f"({uci} : {fmt_sounds(entries)})")
    wait_plies(page, 6)
    page.wait_for_timeout(300)

    n = len(sound_log(page))
    resign(page)
    entries = sounds_heard(page, n)
    expect_exact("[jouer] abandon : son game-end entendu", entries, ["game-end"])
    shot(page, "f10_jouer_fin_852")
    ctx.close()


def play_black_suite(p, browser):
    """Noirs : le premier son est le coup du bot, déclenché hors geste (après la réflexion)."""
    ctx = ctx_with_audio(p, browser, SOUND_ON)
    page = ctx.new_page()
    if goto_play(page):
        n = len(sound_log(page))
        if start_game(page, "Noirs"):
            entries = wait_sounds(page, n, 2)
            ok = len(entries) == 2 and entries[0]["name"] == "game-start" and entries[1]["name"] in BOT_SOUNDS and all(e["audible"] for e in entries)
            check("[jouer noirs] game-start puis 1er coup du bot entendus", ok, f"({fmt_sounds(entries)})")
    ctx.close()


def sound_off_suite(p, browser):
    ctx = ctx_with_audio(p, browser, {"playSounds": False})
    page = ctx.new_page()
    if goto_play(page) and start_game(page, "Blancs"):
        drag_piece(page, "e2", "e4")
        wait_plies(page, 2)
        drag_piece(page, "d2", "d5")
        page.wait_for_timeout(500)
        entries = sound_log(page)
        check("[sons coupés] aucun son démarré, pas même le déverrouillage", entries == [], f"({fmt_sounds(entries)})")
    ctx.close()


# ---------- Analyse : navigation coup par coup ----------

NAV_FEN = "8/1P6/p7/8/2k5/8/8/R3K2R w KQ - 0 1"
NAV_PGN = f'[FEN "{NAV_FEN}"]\n[SetUp "1"]\n\n1. Rxa6 Kc5 2. O-O Kc4 3. b8=Q Kc3 4. Qb3+ *'
NAV_EXPECTED = ["capture", "move-opponent", "castle", "move-opponent", "promote", "move-opponent", "move-check"]
# Position hors théorie (un départ théorique classerait tout 📖) : 1. Td7?? laisse Te1#. Le bilan
# guidé s'ouvre sur ce premier coup, une gaffe, donc « Réessayer » est proposé d'emblée.
RETRY_PGN = '[FEN "4r1k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"]\n[SetUp "1"]\n\n1. Rd7 Re1# *'


def load_pgn(page, pgn, label):
    page.locator("main button:visible", has_text="Options").click()
    page.locator("button:visible", has_text="Importer PGN ou FEN").click()
    if not ck.appears(f"{label} : zone d'import ouverte", page, "textarea", timeout=5000):
        return False
    page.fill("textarea", pgn)
    page.locator("button:visible", has_text="Charger").click()
    page.wait_for_timeout(800)
    return True


def analysis_suite(p, browser):
    ctx = ctx_with_audio(p, browser, SOUND_ON)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/analyse")
    if not ck.appears("[analyse] page chargée", page, "[data-square='e4']", timeout=30000):
        ctx.close()
        return
    if not load_pgn(page, NAV_PGN, "[analyse] navigation"):
        ctx.close()
        return
    prev = page.locator("main button:visible", has_text="Précédent").first
    nxt = page.locator("main button:visible", has_text="Suivant").first
    n = len(sound_log(page))
    for _ in range(7):
        prev.tap()
        page.wait_for_timeout(120)
    entries = sounds_heard(page, n)
    check("[analyse] reculer coup par coup reste muet", entries == [], f"({fmt_sounds(entries)})")
    got = []
    for _ in NAV_EXPECTED:
        n = len(sound_log(page))
        nxt.tap()
        entries = sounds_heard(page, n, settle=250)
        got.append(entries[0]["name"] if len(entries) == 1 and entries[0]["audible"] else fmt_sounds(entries))
    check("[analyse] avancer coup par coup : bon son à chaque coup (prise, roque, promotion, échec)", got == NAV_EXPECTED,
          f"(attendu {NAV_EXPECTED}, obtenu {got})")

    # Réessayer du bilan guidé : l'entrée (position avant la gaffe) et la sortie (position après)
    # sont des sauts de position, donc muets ; le coup suivant sonne de nouveau.
    if not load_pgn(page, RETRY_PGN, "[analyse] réessai"):
        ctx.close()
        return
    page.locator("main button:visible", has_text="Bilan").first.click()
    if ck.appears("[analyse] réessai : résumé du bilan", page, "button:has-text('Démarrer le bilan')", timeout=120000):
        page.locator("button:visible", has_text="Démarrer le bilan").click()
        if ck.appears("[analyse] réessai : bilan guidé ouvert", page, "button:has-text('Réessayer')", timeout=10000):
            page.wait_for_timeout(300)
            retry = page.locator("button:visible", has_text="Réessayer")
            enabled = retry.is_enabled()
            check("[analyse] réessai : Réessayer proposé sur la gaffe 1. Td7", enabled)
            if enabled:
                n = len(sound_log(page))
                retry.tap()
                entries = sounds_heard(page, n)
                check("[analyse] réessai : entrée dans Réessayer (position avant la gaffe), muette", entries == [], f"({fmt_sounds(entries)})")
                n = len(sound_log(page))
                page.get_by_role("button", name="Quitter", exact=True).tap()
                entries = sounds_heard(page, n)
                check("[analyse] réessai : Quitter est muet (pas de son du coup fautif)", entries == [], f"({fmt_sounds(entries)})")
                n = len(sound_log(page))
                page.locator("button:visible", has_text="Suivant").tap()
                expect_exact("[analyse] réessai : Suivant après Quitter, le mat sonne", sounds_heard(page, n), ["move-check"])
    ctx.close()


# ---------- Puzzles ----------

MATE1 = ["004yJ", "r4rk1/1bp2ppp/p1q1pn2/2P5/8/3B1N2/P1P1QPPP/R4RK1 w - - 0 16", "f3e5 c6g2", 737, "mate mateIn1 oneMove"]
PROMO = ["0LaM6", "2rR3k/1p2P1pP/6B1/4n3/8/8/7P/7K b - - 2 37", "c8d8 e7d8q", 799, "advancedPawn mate mateIn1 oneMove promotion"]


def board_after(pz, n):
    b = chess.Board(pz[1])
    for uci in pz[2].split()[:n]:
        b.push_uci(uci)
    return b


def wrong_move(pz):
    b = board_after(pz, 1)
    expected = pz[2].split()[1]
    for m in b.legal_moves:
        if m.uci() == expected or m.promotion:
            continue
        b.push(m)
        mate = b.is_checkmate()
        b.pop()
        if not mate:
            return m.uci()
    raise RuntimeError("aucun coup faux")


def puzzle_page(p, browser, puzzles, settings=SOUND_ON):
    ctx = ctx_with_audio(p, browser, settings)
    body = json.dumps(puzzles)
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=body))
    page = ctx.new_page()
    # Arrivée par l'onglet, comme sur l'iPhone : ce tap est le geste qui déverrouille l'audio,
    # avant l'amorce jouée automatiquement.
    page.goto(f"{BASE}/#/")
    if not ck.appears("[puzzles] accueil et navigation chargés", page, "nav[aria-label='Navigation principale'] a:visible", timeout=30000):
        return ctx, page, False
    page.locator("nav[aria-label='Navigation principale'] a:visible", has_text="Puzzles").first.tap()
    ok = ck.appears("[puzzles] page chargée", page, "text=Classement puzzles", timeout=30000)
    return ctx, page, ok


DOM_FEN_JS = """() => {
  const rows = []
  for (let r = 8; r >= 1; r--) {
    let row = '', empty = 0
    for (const f of 'abcdefgh') {
      const el = document.querySelector(`[data-square='${f}${r}'] [data-piece]`)
      const pc = el ? el.getAttribute('data-piece') : null
      if (!pc) { empty++; continue }
      if (empty) { row += empty; empty = 0 }
      row += pc[0] === 'w' ? pc[1] : pc[1].toLowerCase()
    }
    if (empty) row += empty
    rows.push(row)
  }
  return rows.join('/')
}"""


def dom_board_fen(page):
    """Placement des pièces lu sur l'échiquier affiché (partie « pièces » d'un FEN)."""
    return page.evaluate(DOM_FEN_JS)


def quiet_white_move(page):
    """Un coup blanc légal sans prise, échec, roque ni promotion, choisi sur la position affichée :
    la réponse du bot est imprévisible (Noa joue presque au hasard) et le roi blanc peut être en
    échec, donc un coup fixé d'avance serait tantôt illégal."""
    b = chess.Board(dom_board_fen(page) + " w - - 0 1")
    for m in b.legal_moves:
        if b.is_capture(m) or m.promotion or b.is_castling(m) or b.gives_check(m):
            continue
        return m.uci()
    raise RuntimeError("aucun coup calme")


def wait_ply_played(page, pz, n, timeout=8000):
    target = board_after(pz, n).board_fen()
    waited = 0
    while waited < timeout:
        if dom_board_fen(page) == target:
            return True
        page.wait_for_timeout(100)
        waited += 100
    return False


def puzzles_suite(p, browser):
    # Raté : l'amorce adverse sonne, puis le coup faux donne fail.
    ctx, page, ok = puzzle_page(p, browser, [MATE1])
    if ok:
        n = len(sound_log(page))
        played = wait_ply_played(page, MATE1, 1)
        entries = sounds_heard(page, n)
        check("[puzzles] amorce adverse jouée", played)
        expect_exact("[puzzles] amorce : son du coup adverse", entries, ["move-opponent"])
        w = wrong_move(MATE1)
        n = len(sound_log(page))
        tap_move(page, w[:2], w[2:4], pause=150)
        entries = sounds_heard(page, n, settle=600)
        expect_exact("[puzzles] coup faux : le seul son est fail (coup faux muet, puis repris muet)", entries, ["fail"])
    ctx.close()

    # Réussi : mat en 1, son d'échec du coup puis success.
    ctx, page, ok = puzzle_page(p, browser, [MATE1])
    if ok and wait_ply_played(page, MATE1, 1):
        page.wait_for_timeout(300)
        sol = MATE1[2].split()[1]
        n = len(sound_log(page))
        tap_move(page, sol[:2], sol[2:4], pause=150)
        entries = sounds_heard(page, n, settle=600)
        expect_exact("[puzzles] solution : verdict success puis son du coup mat (échec), une fois chacun", entries, ["success", "move-check"])
    ctx.close()


# ---------- Apprendre : un seul verdict ----------

# Mat en 1 portant tous les thèmes : quel que soit le thème tiré, la séance Tactiques le sert.
LEARN_M1 = ["L10", "6k1/5ppp/8/8/4n3/8/5PPP/R5K1 b - - 0 1", "e4c3 a1a8", 1000,
            "fork pin skewer discoveredAttack mateIn1 mateIn2 mateIn3 backRankMate hangingPiece sacrifice "
            "deflection attraction promotion trappedPiece intermezzo defensiveMove rookEndgame pawnEndgame "
            "zugzwang exposedKing discoveredCheck advancedPawn kingsideAttack quietMove"]


def learn_suite(p, browser):
    ctx = ctx_with_audio(p, browser, SOUND_ON)
    body = json.dumps([LEARN_M1])
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=body))
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre")
    page.wait_for_timeout(1200)
    page.locator("main button", has_text="Tactiques").click()
    if ck.appears("[apprendre] leçon tactique", page, "button:has-text(\"C'est parti\")", timeout=20000):
        n = len(sound_log(page))
        page.get_by_role("button", name="C'est parti").click()
        page.wait_for_timeout(1500)  # amorce ...Nc3 jouée
        entries = sounds_heard(page, n)
        expect_exact("[apprendre] amorce adverse : son du coup adverse", entries, ["move-opponent"])
        n = len(sound_log(page))
        tap_move(page, "a1", "a8", pause=200)
        entries = sounds_heard(page, n, settle=800)
        expect_exact("[apprendre] mat trouvé : un seul success, et le son du coup", entries, ["success", "move-check"])
    ctx.close()


# ---------- Volume ----------

def volume_suite(p, browser):
    ctx = ctx_with_audio(p, browser, SOUND_ON)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/stats")
    slider = page.locator("input[aria-label='Volume des sons']")
    if ck.appears("[volume] curseur présent sous Sons", page, "input[aria-label='Volume des sons']", timeout=15000):
        slider.scroll_into_view_if_needed()
        slider.fill("40")
        n = len(sound_log(page))
        slider.focus()
        page.keyboard.press("ArrowLeft")  # 35 %, aperçu au relâcher de la touche
        entries = sounds_heard(page, n, settle=600)
        expect_exact("[volume] aperçu au relâcher : son d'un coup", entries, ["move-self"])
        gain = page.evaluate("() => window.__gain")
        check("[volume] son joué au volume réglé (0,35)", gain is not None and abs(gain - 0.35) < 1e-6, f"({gain})")
        stored = page.evaluate("() => JSON.parse(localStorage.getItem('chess-local-settings')).state.soundVolume")
        check("[volume] volume mémorisé", stored is not None and abs(stored - 0.35) < 1e-6, f"({stored})")
        shot(page, "f10_reglages_volume_852")
    ctx.close()


# ---------- Pièces ----------

PIECE_IMGS_JS = """() => [...document.querySelectorAll('[data-piece] img')].map((i) => i.getAttribute('src'))"""


def piece_srcs(page):
    return page.evaluate(PIECE_IMGS_JS)


def all_from(srcs, set_id):
    return len(srcs) > 0 and all(f"pieces/{set_id}/" in s for s in srcs)


def images_served(page):
    """Chaque image de pièce répond 200 et se décode (servie sous le sous-chemin de l'app)."""
    return page.evaluate("""async () => {
      const imgs = [...document.querySelectorAll('[data-piece] img')]
      const out = []
      for (const i of imgs.slice(0, 6)) {
        const r = await fetch(i.src)
        let decoded = true
        try { await i.decode() } catch { decoded = false }
        out.push({ src: i.src, status: r.status, type: r.headers.get('content-type'), decoded })
      }
      return out
    }""")


def square_has_drawing(page, square):
    """L'image de la pièce est réellement peinte : une fois dessinée sur un canvas, une part
    notable de ses pixels est opaque (une image vide ou cassée n'en a aucun)."""
    return page.evaluate("""async (sq) => {
      const img = document.querySelector(`[data-square='${sq}'] [data-piece] img`)
      if (!img) return 0
      await img.decode()
      const c = document.createElement('canvas')
      c.width = c.height = 64
      const g = c.getContext('2d')
      g.drawImage(img, 0, 0, 64, 64)
      const d = g.getImageData(0, 0, 64, 64).data
      let opaque = 0
      for (let i = 3; i < d.length; i += 4) if (d[i] > 200) opaque++
      return opaque / (64 * 64)
    }""", square) > 0.2


def pieces_suite(p, browser):
    ctx = ctx_with_audio(p, browser, {})
    page = ctx.new_page()
    if goto_play(page) and start_game(page, "Blancs"):
        srcs = piece_srcs(page)
        check("[pièces] Jouer : 32 pièces du jeu par défaut « celtique »", len(srcs) == 32 and all_from(srcs, "celtique"), f"({len(srcs)} : {srcs[:2]})")
        served = images_served(page)
        check("[pièces] images servies (200, svg, décodées) sous le sous-chemin de l'app",
              len(served) > 0 and all(s["status"] == 200 and "svg" in (s["type"] or "") and s["decoded"] and BASE in s["src"] for s in served), f"({served[:2]})")
        check("[pièces] la case e1 montre un roi dessiné", square_has_drawing(page, "e1"))
        shot(page, "f10_jouer_celtique_852")

    # Réglages : choix de Chessnut, avec aperçu.
    page.goto(f"{BASE}/#/stats")
    if ck.appears("[pièces] réglage « Pièces » présent", page, "[data-piece-set='chessnut']", timeout=15000):
        page.locator("[data-piece-set='chessnut']").scroll_into_view_if_needed()
        shot(page, "f10_reglages_pieces_852")
        previews = page.evaluate("() => [...document.querySelectorAll('[data-piece-set] img')].map((i) => i.getAttribute('src'))")
        check("[pièces] aperçus des jeux dans les Réglages", any("pieces/chessnut/" in s for s in previews) and any("pieces/fantasy/" in s for s in previews), f"({previews[:4]})")
        page.locator("[data-piece-set='chessnut']").tap()
        page.wait_for_timeout(200)
        checked = page.locator("[data-piece-set='chessnut']").get_attribute("aria-checked")
        check("[pièces] Chessnut sélectionné", checked == "true", f"({checked})")
        stored = page.evaluate("() => JSON.parse(localStorage.getItem('chess-local-settings')).state.pieceSet")
        check("[pièces] choix mémorisé dans les réglages", stored == "chessnut", f"({stored})")
        # Second rang de la grille (Spatial, Classique) : aperçus rendus eux aussi.
        page.locator("[data-piece-set='classique']").scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        tiles = page.evaluate("() => [...document.querySelectorAll('[data-piece-set]')].map((t) => t.querySelectorAll('img, svg').length)")
        check("[pièces] chaque vignette montre ses deux pièces (cavalier blanc, dame noire)", tiles == [2] * 5, f"({tiles})")
        shot(page, "f10_reglages_pieces_bas_852")

    page.goto(f"{BASE}/#/analyse")
    if ck.appears("[pièces] Analyse chargée", page, "[data-square='e4']", timeout=30000):
        page.wait_for_timeout(300)
        srcs = piece_srcs(page)
        check("[pièces] Analyse : pièces Chessnut", len(srcs) == 32 and all_from(srcs, "chessnut"), f"({len(srcs)} : {srcs[:2]})")
        page.reload()
        if ck.appears("[pièces] Analyse rechargée", page, "[data-square='e4']", timeout=30000):
            page.wait_for_timeout(300)
            srcs = piece_srcs(page)
            check("[pièces] Chessnut toujours là après rechargement", all_from(srcs, "chessnut"), f"({srcs[:2]})")
    ctx.close()

    # Puzzles et sélecteur de promotion, avec le jeu par défaut.
    ctx, page, ok = puzzle_page(p, browser, [PROMO], settings={})
    if ok and wait_ply_played(page, PROMO, 1):
        srcs = piece_srcs(page)
        check("[pièces] Puzzles : pièces « celtique »", all_from(srcs, "celtique"), f"({srcs[:2]})")
        tap_move(page, "e7", "d8", pause=200)
        imgs = page.evaluate("() => [...document.querySelectorAll('button[aria-label] img')].map((i) => i.getAttribute('src'))")
        promo = [s for s in imgs if "pieces/" in s]
        check("[pièces] sélecteur de promotion : 4 pièces blanches du jeu choisi",
              len(promo) == 4 and all("pieces/celtique/w" in s for s in promo), f"({promo})")
        shot(page, "f10_promotion_852")
    ctx.close()

    # Onglet Safari 393x660 : l'échiquier tient entier avec ses pièces.
    ctx = mobile_context(p, browser, ck, settings={}, standalone=False, service_workers="block")
    page = ctx.new_page()
    if goto_play(page) and start_game(page, "Blancs"):
        check("[pièces] 393x660 : pièces « celtique »", all_from(piece_srcs(page), "celtique"))
        shot(page, "f10_jouer_celtique_660")
    ctx.close()

    # Desktop 1440x900 : rendu de l'échiquier.
    ctx = desktop_context(browser, ck, settings={})
    page = ctx.new_page()
    if goto_play(page) and start_game(page, "Blancs"):
        check("[pièces] desktop : pièces « celtique »", all_from(piece_srcs(page), "celtique"))
        shot(page, "f10_jouer_celtique_1440")
    ctx.close()


def course_audio_suite(p, browser):
    for course, lesson, expected in [
        ("finales", "mat-deux-tours", ["move-self", "move-opponent"]),
        ("roque", "grec-schema", ["move-check", "capture"]),
    ]:
        ctx = ctx_with_audio(p, browser, {**SOUND_ON, "pieceSet": "chessnut"})
        page = ctx.new_page()
        page.goto(f"{BASE}/#/apprendre/{course}/{lesson}")
        page.locator("[data-square='a1']").click()
        expect_exact(f"[{course}] diagramme muet", sounds_heard(page, 0), [])
        check(f"[{course}] pièces Chessnut", all_from(piece_srcs(page), "chessnut"))
        page.get_by_role("button", name="Continuer", exact=True).click()
        n = len(sound_log(page))
        # Aucun délai artificiel après Continuer : le pilote doit attendre le nouveau plateau.
        if course == "finales":
            tap_move(page, "a1", "a4")
        else:
            page.get_by_role("button", name="💡 Solution").click()
        expect_exact(f"[{course}] coup puis réponse", wait_sounds(page, n, 2), expected)
        n = len(sound_log(page))
        page.get_by_role("button", name="← Précédent").click()
        expect_exact(f"[{course}] retour au diagramme muet", sounds_heard(page, n), [])
        shot(page, f"f10_diagramme_{course}")
        ctx.close()


def suite(p):
    browser = p.chromium.launch(headless=True)
    try:
        play_white_suite(p, browser)
        play_black_suite(p, browser)
        sound_off_suite(p, browser)
        analysis_suite(p, browser)
        puzzles_suite(p, browser)
        learn_suite(p, browser)
        volume_suite(p, browser)
        pieces_suite(p, browser)
        course_audio_suite(p, browser)
    finally:
        browser.close()


ck.run(suite)
