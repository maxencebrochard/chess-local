"""QA exhaustive : tous les boutons de l'app, un assert d'effet par bouton.

Usage : npm run test:e2e -- --suite all_buttons
        E2E_ALL_BUTTONS_PROMOTION=1 npm run test:e2e -- --suite all_buttons
"""
import json
import os
from pathlib import Path

import chess

from helpers import BASE, LIVE, PLIES_AT_LEAST, Checker, click_square, desktop_context, mobile_context, wait_js

# Pseudo de la fixture e2e/fixtures/chesscom.json (API chess.com simulée, sauf E2E_LIVE=1).
SETTINGS = {"chesscomUsername": "popeye232"}
# (onglet, texte attendu dans <main>). Analyse n'a pas le même marqueur selon le layout :
# « Options » n'existe que dans la barre d'actions mobile, « Copier PGN » que dans le panneau desktop.
# Les cinq onglets, puis les anciens onglets Analyse, Archive et Stats, atteints par le hub Plus
# (`plus:<clé>` : onglet Plus, puis la carte `data-plus` de cette clé).
NAV = [("Jouer", "Adversaire"), ("Puzzles", "Classement puzzles"), ("Apprendre", "Séance"),
       ("Plus", "Mes données"), ("plus:analyse", {"mobile": "Options", "desktop": "Copier PGN"}),
       ("plus:parties", "Archive"), ("plus:statistiques", "Statistiques"),
       ("plus:reglages", "Profondeur du bilan de partie"), ("plus:donnees", "Dernier export"), ("Accueil", "ChessLocal")]


def marker_for(marker, layout):
    return marker[layout] if isinstance(marker, dict) else marker


def nav_to(page, label):
    """Onglet visible de ce libellé, ou `plus:<clé>` : onglet Plus puis la carte du hub."""
    if label.startswith("plus:"):
        page.locator("nav a[data-nav-tab]", has_text="Plus").locator("visible=true").click()
        page.locator(f"main a[data-plus='{label[5:]}']").click()
    else:
        page.locator("nav a[data-nav-tab]", has_text=label).locator("visible=true").click()

ck = Checker("all_buttons")
check = ck.check


def current_move(page):
    """Texte du coup courant dans la liste, ou None."""
    loc = page.locator("main [data-current='true']")
    return loc.first.inner_text() if loc.count() else None


def selected(btn):
    return "border-accent" in (btn.get_attribute("class") or "")


def resign(page):
    """Abandonner ouvre une feuille de confirmation : on confirme."""
    page.click("button:has-text('Abandonner')")
    page.get_by_role("button", name="Oui, abandonner", exact=True).click()


def promotion_piece(page, fr, tg):
    """Retrouve la promotion lichess par position ; dame pour un autre coup tenté."""
    # Board garde la position avant le coup tant que le sélecteur est ouvert.
    pieces = page.locator("main [data-square] [data-piece]").evaluate_all("""els =>
        Object.fromEntries(els.map(el => [el.closest('[data-square]').dataset.square,
                                        el.dataset.piece]))""")
    puzzles = json.loads((Path(__file__).resolve().parents[1] / "public/puzzles.json").read_text())
    for _, fen, moves, *_ in puzzles:
        moves = moves.split()
        if not any(len(u) == 5 and u[:4] == fr + tg for u in moves[1::2]):
            continue
        board = chess.Board(fen)
        for step, uci in enumerate(moves):
            if step % 2 == 1 and len(uci) == 5 and uci[:4] == fr + tg:
                expected = {chess.square_name(sq): ("w" if pc.color else "b") + pc.symbol().upper()
                            for sq, pc in board.piece_map().items()}
                if pieces == expected:
                    return uci[4]
            board.push_uci(uci)
    return "q"


def suite(p):
    browser = p.chromium.launch(headless=True)

    # ---------- NAV MOBILE : 5 onglets et le hub Plus ----------
    ctx = mobile_context(p, browser, ck, SETTINGS)
    page = ctx.new_page()
    page.goto(f"{BASE}/")
    page.wait_for_timeout(1500)
    for label, marker in NAV:
        nav_to(page, label)
        # Attente bornée du marqueur plutôt qu'un délai fixe : Puzzles charge 16 Mo de puzzles.
        ck.appears(f"[nav mobile] {label}", page, f"main :text('{marker_for(marker, 'mobile')}')", timeout=10000)
    ctx.close()

    # ---------- DESKTOP : le reste ----------
    ctx = desktop_context(browser, ck, SETTINGS, permissions=["clipboard-read", "clipboard-write"],
                          **({"service_workers": "block"} if os.environ.get("E2E_ALL_BUTTONS_PROMOTION") == "1" else {}))
    # Reproduction : limiter le tirage à deux positions distinctes avec d7d8q.
    # Deux puzzles préservent le contrôle « Passer change de puzzle ».
    if os.environ.get("E2E_ALL_BUTTONS_PROMOTION") == "1":
        puzzles = json.loads((Path(__file__).resolve().parents[1] / "public/puzzles.json").read_text())
        forced = [pz for pz in puzzles if pz[0] in ("3kxGz", "43col")]
        assert len(forced) == 2
        ctx.route("**/puzzles.json", lambda route: route.fulfill(json=forced))
        print("[puzzles] tirage forcé : 3kxGz / 43col (d7d8q)", flush=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/")
    page.wait_for_timeout(1500)

    for label, marker in NAV:
        nav_to(page, label)
        ck.appears(f"[nav desktop] {label}", page, f"main :text('{marker_for(marker, 'desktop')}')", timeout=10000)

    # Accueil : carte Problèmes + tuiles + stats
    tiles = [("Problèmes", "Classement puzzles"), ("Séance du jour", "Quelques blocs courts"), ("Analyse", "Stockfish 18"), ("Puzzle Rush", "Survie"),
             ("Archive", "Archive ("), ("chess.com", "Importer depuis"), ("Blitz", "Statistiques")]
    for title, marker in tiles:
        page.locator("nav a", has_text="Accueil").first.click()
        page.wait_for_timeout(400)
        page.locator("main a", has_text=title).first.click()
        # Présence n'importe où dans la page, comme `text=` : `main` est inclus.
        ck.appears(f"[accueil] tuile {title}", page, f":text('{marker}')", timeout=10000, state="attached")

    # ---------- JOUER : setup ----------
    page.locator("nav a", has_text="Jouer").first.click()
    page.wait_for_timeout(500)
    b_local = page.locator("button", has_text="2 joueurs")
    b_local.click(); page.wait_for_timeout(200)
    check("[jouer] mode local sélectionné", selected(b_local))
    check("[jouer] mode local cache les bots", page.locator("text=Adversaire").count() == 0)
    b_coach = page.locator("button", has_text="Entraîneur")
    b_coach.click(); page.wait_for_timeout(200)
    check("[jouer] mode entraîneur sélectionné", selected(b_coach))
    b_bot = page.locator("button", has_text="Contre un bot")
    b_bot.click(); page.wait_for_timeout(200)
    check("[jouer] mode bot resélectionné", selected(b_bot))
    for bot in ["Noa", "Marty", "Léa", "Nina", "Iris", "Viktor", "Sofia", "Arun", "Maximus"]:
        b = page.locator("main button", has_text=bot).first
        b.click(); page.wait_for_timeout(120)
        check(f"[jouer] bot {bot}", selected(b))
    page.locator("main button", has_text="Noa").first.click()
    for col in ["Blancs", "Noirs", "Aléatoire"]:
        b = page.locator("main button", has_text=col).first
        b.click(); page.wait_for_timeout(120)
        check(f"[jouer] couleur {col}", selected(b))
    page.locator("main button", has_text="Blancs").first.click()
    for tcl in ["1 min", "3 min", "3 | 2", "5 min", "10 min", "15 | 10", "30 min", "Illimité"]:
        b = page.get_by_role("button", name=tcl, exact=True)
        b.click(); page.wait_for_timeout(120)
        check(f"[jouer] cadence {tcl}", selected(b))
    check("[jouer] classement affiché", "Mon classement" in page.locator("main").inner_text())
    sw = page.locator("[data-testid=toggle-threat]")
    was = sw.get_attribute("aria-checked")
    sw.click(); page.wait_for_timeout(120)
    check("[jouer] interrupteur « Qu'est-ce qu'il menace ? »", sw.get_attribute("aria-checked") != was)
    sw.click(); page.wait_for_timeout(120)

    # ---------- JOUER : partie vs bot ----------
    page.get_by_role("button", name="Jouer", exact=True).click()
    page.wait_for_timeout(900)
    click_square(page, "e2"); page.wait_for_timeout(200); click_square(page, "e4")
    check("[partie] coup + réponse bot", wait_js(page, PLIES_AT_LEAST, arg=2))
    page.click("main button:has-text('◀')"); page.wait_for_timeout(250)
    check("[partie] ◀", page.locator("main [data-current='true']").count() == 1)
    page.click("main button:has-text('⏮')"); page.wait_for_timeout(250)
    check("[partie] ⏮", page.locator("main [data-current='true']").count() == 1)
    at_first = current_move(page)
    page.click("main button:has-text('▶')"); page.wait_for_timeout(250)
    check("[partie] ▶ avance d'un coup", current_move(page) not in (None, at_first), f"({at_first} -> {current_move(page)})")
    page.click("main button:has-text('⏭')"); page.wait_for_timeout(250)
    last_move = page.locator("main [data-current]").last.inner_text()
    check("[partie] ⏭ (retour live)", current_move(page) == last_move, f"({current_move(page)} / dernier {last_move})")
    page.click("button:has-text('Abandonner')")
    page.wait_for_timeout(300)
    check("[partie] Abandonner → confirmation", page.locator("text=Abandonner la partie ?").is_visible())
    page.get_by_role("button", name="Oui, abandonner", exact=True).click()
    page.wait_for_timeout(1200)
    check("[partie] Oui, abandonner → modale", page.locator("text=gagnent").first.is_visible())
    check("[modale] delta classement", "Classement" in page.locator("body").inner_text())
    page.locator("div.fixed button", has_text="Nouvelle partie").click()
    page.wait_for_timeout(400)
    check("[modale] Nouvelle partie → setup", page.locator("text=Adversaire").is_visible())

    page.get_by_role("button", name="Jouer", exact=True).click()
    page.wait_for_timeout(900)
    click_square(page, "d2"); page.wait_for_timeout(200); click_square(page, "d4")
    # Deux demi-coups au moins : en deçà, l'abandon annule la partie au lieu de la finir.
    check("[partie 2] coup + réponse bot avant l'abandon", wait_js(page, PLIES_AT_LEAST, arg=2))
    resign(page)
    page.wait_for_timeout(1200)
    page.locator("div.fixed button", has_text="Bilan de la partie").click()
    ck.appears("[modale] Bilan de la partie → résumé", page, "text=Démarrer le bilan", timeout=120000)
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(400)

    # ---------- JOUER : 2 joueurs local ----------
    page.locator("nav a", has_text="Jouer").first.click()
    page.wait_for_timeout(500)
    page.locator("button", has_text="2 joueurs").click()
    page.get_by_role("button", name="Illimité", exact=True).click()
    page.get_by_role("button", name="Jouer", exact=True).click()
    page.wait_for_timeout(700)
    click_square(page, "e2"); page.wait_for_timeout(200); click_square(page, "e4")
    page.wait_for_timeout(400)
    click_square(page, "e7"); page.wait_for_timeout(200); click_square(page, "e5")
    page.wait_for_timeout(400)
    check("[local] deux camps jouent", page.locator("main [data-current]").count() == 2)
    resign(page)
    page.wait_for_timeout(900)
    check("[local] abandon", page.locator("text=gagnent").first.is_visible())
    page.locator("div.fixed").click(position={"x": 10, "y": 10})
    page.wait_for_timeout(300)
    check("[modale] clic fond ferme", page.locator("text=gagnent").count() == 0)

    # ---------- PUZZLES ----------
    page.locator("nav a", has_text="Puzzles").first.click()
    ck.appears("[puzzles] page chargée", page, "text=Classement puzzles", timeout=15000)
    page.wait_for_timeout(1500)
    body_before = page.locator("[id^='chessboard-']").first.inner_html()
    page.click("button:has-text('Indice')")
    page.wait_for_timeout(400)
    hinted = page.evaluate("""() => [...document.querySelectorAll('[data-square] *')]
        .some(n => getComputedStyle(n).backgroundColor.includes('255, 255, 51'))""")
    check("[puzzles] Indice surligne", hinted)
    page.click("button:has-text('Passer')")
    page.wait_for_timeout(1500)
    body_after = page.locator("[id^='chessboard-']").first.inner_html()
    check("[puzzles] Passer change de puzzle", body_before != body_after)
    promotions = 0
    for _ in range(10):
        if page.locator("text=Raté").count() or page.locator("text=Résolu").count():
            break
        page.click("button:has-text('Indice')")
        page.wait_for_timeout(250)
        fr = page.evaluate("""() => {
          const els=[...document.querySelectorAll('[data-square]')];
          const has=(r,f)=>[r,...r.querySelectorAll('*')].some(f);
          return els.find(e=>has(e,n=>getComputedStyle(n).backgroundColor.includes('255, 255, 51')))?.getAttribute('data-square') ?? null;
        }""")
        if not fr:
            break
        click_square(page, fr); page.wait_for_timeout(250)
        tg = page.evaluate("""() => {
          const els=[...document.querySelectorAll('[data-square]')];
          const has=(r,f)=>[r,...r.querySelectorAll('*')].some(f);
          return els.find(e=>has(e,n=>getComputedStyle(n).background.includes('rgba(0, 0, 0, 0.34)')))?.getAttribute('data-square') ?? null;
        }""")
        if not tg:
            break
        click_square(page, tg); page.wait_for_timeout(800)
        queen = page.get_by_role("button", name="Dame", exact=True)
        if queen.is_visible():
            piece = promotion_piece(page, fr, tg)
            label = {"q": "Dame", "r": "Tour", "b": "Fou", "n": "Cavalier"}[piece]
            page.get_by_role("button", name=label, exact=True).click()
            queen.wait_for(state="hidden")
            check(f"[puzzles] promotion {fr}{tg}{piece} ferme le sélecteur", not queen.is_visible())
            promotions += 1
            # Même délai de réponse adverse que pour un coup sans promotion.
            page.wait_for_timeout(800)
    finished = page.locator("text=Raté").count() or page.locator("text=Résolu").count()
    check("[puzzles] terminé", bool(finished))
    if os.environ.get("E2E_ALL_BUTTONS_PROMOTION") == "1":
        check("[puzzles] promotion forcée jouée et puzzle résolu",
              promotions > 0 and page.locator("text=Résolu").is_visible())
    if page.locator("button:has-text('Réessayer')").count():
        page.click("button:has-text('Réessayer')")
        page.wait_for_timeout(600)
        check("[puzzles] Réessayer relance", page.locator("text=Trouve le meilleur coup").is_visible())
        page.click("button:has-text('Passer')")
    else:
        page.click("button:has-text('Suivant')")
    page.wait_for_timeout(1500)
    check("[puzzles] Suivant/Passer → nouveau", page.locator("text=Trouve le meilleur coup").is_visible())

    # ---------- RUSH ----------
    page.goto(f"{BASE}/#/rush")
    page.wait_for_timeout(800)
    for mode, marker in [("3 minutes", "2:5"), ("5 minutes", "4:5"), ("Survie", "résolus")]:
        page.locator("main button", has_text=mode).click()
        page.wait_for_timeout(1600)
        ok = page.locator(f"text={marker}").count() > 0 or page.locator("text=résolus").is_visible()
        check(f"[rush] démarrage {mode}", ok)
        page.click("main button:has-text('✕'), main button:has-text('Arrêter')")
        page.wait_for_timeout(600)
        check(f"[rush] Arrêter ({mode})", page.locator("text=Terminé").count() > 0 or page.locator("text=record").count() > 0)
        if mode != "Survie":
            page.click("button:has-text('Menu')")
            page.wait_for_timeout(400)
            check(f"[rush] Menu ({mode})", page.locator("text=Puzzle Rush").first.is_visible())
    page.click("button:has-text('Rejouer')")
    page.wait_for_timeout(1200)
    check("[rush] Rejouer relance", page.locator("text=résolus").is_visible())
    page.click("main button:has-text('✕'), main button:has-text('Arrêter')")
    page.wait_for_timeout(400)
    page.click("button:has-text('Menu')")

    # ---------- ANALYSE classique (desktop) ----------
    nav_to(page, "plus:analyse")
    page.wait_for_timeout(2500)
    page.locator("main button:has-text('e4')").last.click()
    page.wait_for_timeout(500)
    check("[analyse] explorer joue e4", page.locator("main [data-current]").count() >= 1)
    click_square(page, "e7"); page.wait_for_timeout(200); click_square(page, "e5")
    page.wait_for_timeout(500)
    check("[analyse] coup au board", page.locator("main [data-current]").count() >= 2)
    lines_before = page.locator("main .space-y-1").count()
    page.locator("main button.h-6.w-11").first.click()
    page.wait_for_timeout(500)
    check("[analyse] toggle moteur OFF", page.locator("main .space-y-1").count() < max(lines_before, 1))
    page.locator("main button.h-6.w-11").first.click()
    page.wait_for_timeout(1500)
    check("[analyse] toggle moteur ON", page.locator("main .space-y-1").count() >= 1)
    page.get_by_role("button", name="PGN", exact=True).click()
    page.fill("textarea", "n'importe quoi")
    page.click("button:has-text('Charger')")
    page.wait_for_timeout(300)
    check("[analyse] PGN invalide → erreur", page.locator("text=Format non reconnu").is_visible())
    page.locator("div.fixed").click(position={"x": 10, "y": 10})
    page.wait_for_timeout(300)
    check("[analyse] fond ferme la modale", page.locator("textarea").count() == 0)
    page.click("button:has-text('Copier PGN')")
    clip = page.evaluate("() => navigator.clipboard.readText()")
    check("[analyse] Copier PGN", "1. e4 e5" in clip, f"({clip[:30]})")
    page.click("button:has-text('chess.com')")
    page.wait_for_timeout(500)
    check("[analyse] bouton chess.com", "import" in page.url)

    # ---------- IMPORT ----------
    # SEC-3 : rien ne part vers chess.com sans action, la liste ne s'affiche qu'après « Voir mes parties ».
    page.get_by_role("button", name="Voir mes parties").click()
    ck.appears("[import] liste affichée", page, "main button:has-text('contre ')", timeout=30000)
    check("[import] liste chargée", page.locator("main button", has_text="contre ").count() >= 5)
    if not LIVE:
        # Sans ça, le check passerait aussi contre l'API réelle : on veut la preuve que c'est la fixture.
        check("[import] ce sont les parties de la fixture", page.locator("main button", has_text="BotGolf").count() == 1)
    page.click("summary")
    page.wait_for_timeout(300)
    check("[import] details Raccourci s'ouvre", page.locator("text=Raccourcis").is_visible())
    page.fill("input[placeholder*='colle un lien']", "https://www.chess.com/game/live/999999999999")
    page.get_by_role("button", name="Bilan", exact=True).click()
    ck.appears("[import] lien introuvable → erreur propre", page, "text=introuvable", timeout=30000, state="attached")

    # ---------- ARCHIVE ----------
    nav_to(page, "plus:parties")
    page.wait_for_timeout(600)
    rows = page.locator("main a", has_text="Analyser").count()
    check("[archive] parties listées", rows >= 2, f"({rows})")
    with page.expect_download() as dl:
        page.click("button:has-text('Exporter tout')")
    check("[archive] export PGN téléchargé", dl.value.suggested_filename.endswith(".pgn"))
    page.locator("main a", has_text="Analyser").first.click()
    # Analyse est une page paresseuse : attendre son contenu plutôt qu'un délai fixe.
    ck.appears("[archive] Analyser ouvre la partie (coup courant présent)", page, "main [data-current]", timeout=10000, state="attached")
    check("[archive] Analyser ouvre la partie", "analyse" in page.url)
    nav_to(page, "plus:parties")
    page.wait_for_timeout(600)
    before = page.locator("main a", has_text="Analyser").count()
    page.locator("main button:has-text('✕')").first.click()
    page.wait_for_timeout(500)
    # Suppression différée (ANA-24) : la ligne devient une barre « Annuler » ; l'effacement en base
    # est prouvé par test_archive_import.py.
    check("[archive] ✕ retire la ligne (suppression différée)", page.locator("main a", has_text="Analyser").count() == before - 1)
    page.locator("main a", has_text="Bilan").first.click()
    ck.appears("[archive] Bilan lance le review", page, "text=Démarrer le bilan", timeout=120000)
    page.click("header button:has-text('✕')")

    # ---------- STATS, puis RÉGLAGES (page extraite de Stats au lot 3) ----------
    nav_to(page, "plus:statistiques")
    ck.appears("[stats] statistiques affichées", page, "[data-testid=threat-stats]")
    nav_to(page, "plus:reglages")
    ck.appears("[réglages] page ouverte depuis le hub", page, "main h1:text-is('Réglages')")
    page.locator("button[title='Bois']").click()
    page.wait_for_timeout(300)
    check("[réglages] thème Bois", '"themeId":"brown"' in page.evaluate("() => localStorage.getItem('chess-local-settings')"))
    page.locator("button[title='Vert']").click()
    for name, label in (("Afficher les coups légaux", "coups légaux"), ("Sons", "sons")):
        t = page.get_by_role("switch", name=name, exact=True)
        was_on = t.get_attribute("aria-checked") == "true"
        t.click(); page.wait_for_timeout(200)
        check(f"[réglages] toggle {label}", (t.get_attribute("aria-checked") == "true") != was_on)
        t.click()
    for depth, key in [("Rapide", "fast"), ("Profond", "deep"), ("Équilibré", "balanced")]:
        page.get_by_role("button", name=depth, exact=True).click()
        page.wait_for_timeout(200)
        check(f"[réglages] profondeur {depth}", f'"reviewDepth":"{key}"' in page.evaluate("() => localStorage.getItem('chess-local-settings')"))

    ctx.close()
    browser.close()


ck.run(suite)
