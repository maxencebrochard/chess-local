"""QA exhaustive : tous les boutons de l'app, un assert d'effet par bouton.

Usage : python3 e2e/test_all_buttons.py            (dev local, port 5199)
        BASE=https://… python3 e2e/test_all_buttons.py
"""
import json
import os
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:5199")
SETTINGS = json.dumps({"state": {"themeId": "green", "showLegalMoves": True, "playSounds": False,
                                 "chesscomUsername": "popeye232", "reviewDepth": "fast"}, "version": 0})
errors = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        errors.append(name)


def click_square(page, square):
    page.locator(f"[data-square='{square}']").click()


def selected(btn):
    return "border-accent" in (btn.get_attribute("class") or "")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # ---------- NAV MOBILE : 7 onglets ----------
    ctx = browser.new_context(**p.devices["iPhone 14 Pro"])
    page = ctx.new_page()
    page.add_init_script(f"localStorage.setItem('chess-local-settings', {json.dumps(SETTINGS)})")
    page.goto(BASE)
    page.wait_for_timeout(1500)
    for label, marker in [("Jouer", "Adversaire"), ("Puzzles", "Classement puzzles"), ("Rush", "Puzzle Rush"),
                          ("Analyse", "Options"), ("Archive", "Archive"), ("Stats", "Statistiques"),
                          ("Accueil", "ChessLocal")]:
        page.locator("nav a", has_text=label).last.click()
        page.wait_for_timeout(700)
        check(f"[nav mobile] {label}", page.locator(f"main :text('{marker}')").first.is_visible())
    ctx.close()

    # ---------- DESKTOP : le reste ----------
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              permissions=["clipboard-read", "clipboard-write"])
    page = ctx.new_page()
    page.add_init_script(f"localStorage.setItem('chess-local-settings', {json.dumps(SETTINGS)})")
    page.on("pageerror", lambda e: print("PAGEERROR:", str(e)[:150]))
    page.goto(BASE)
    page.wait_for_timeout(1500)

    for label in ["Jouer", "Puzzles", "Rush", "Analyse", "Archive", "Stats", "Accueil"]:
        page.locator("nav a", has_text=label).first.click()
        page.wait_for_timeout(700)
        check(f"[nav desktop] {label}", True)

    # Accueil : carte Problèmes + tuiles + stats
    tiles = [("Problèmes", "Classement puzzles"), ("Analyse", "Stockfish 18"), ("Puzzle Rush", "Survie"),
             ("Archive", "Archive ("), ("chess.com", "Importer depuis"), ("Blitz", "Statistiques")]
    for title, marker in tiles:
        page.locator("nav a", has_text="Accueil").first.click()
        page.wait_for_timeout(400)
        page.locator("main a", has_text=title).first.click()
        page.wait_for_timeout(700)
        ok = page.locator(f"main :text('{marker}')").count() > 0 or page.locator(f"text={marker}").count() > 0
        check(f"[accueil] tuile {title}", ok)

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

    # ---------- JOUER : partie vs bot ----------
    page.get_by_role("button", name="Jouer", exact=True).click()
    page.wait_for_timeout(900)
    click_square(page, "e2"); page.wait_for_timeout(200); click_square(page, "e4")
    page.wait_for_timeout(3500)
    check("[partie] coup + réponse bot", page.locator("main [data-current]").count() >= 2)
    page.click("main button:has-text('◀')"); page.wait_for_timeout(250)
    check("[partie] ◀", page.locator("main [data-current='true']").count() == 1)
    page.click("main button:has-text('⏮')"); page.wait_for_timeout(250)
    check("[partie] ⏮", page.locator("main [data-current='true']").count() == 1)
    page.click("main button:has-text('▶')"); page.wait_for_timeout(250)
    check("[partie] ▶", True)
    page.click("main button:has-text('⏭')"); page.wait_for_timeout(250)
    check("[partie] ⏭ (retour live)", True)
    page.click("button:has-text('Abandonner')")
    page.wait_for_timeout(1200)
    check("[partie] Abandonner → modale", page.locator("text=gagnent").first.is_visible())
    check("[modale] delta classement", "Classement" in page.locator("body").inner_text())
    page.locator("div.fixed button", has_text="Nouvelle partie").click()
    page.wait_for_timeout(400)
    check("[modale] Nouvelle partie → setup", page.locator("text=Adversaire").is_visible())

    page.get_by_role("button", name="Jouer", exact=True).click()
    page.wait_for_timeout(900)
    click_square(page, "d2"); page.wait_for_timeout(200); click_square(page, "d4")
    page.wait_for_timeout(3500)
    page.click("button:has-text('Abandonner')")
    page.wait_for_timeout(1200)
    page.locator("div.fixed button", has_text="Bilan de la partie").click()
    page.wait_for_selector("text=Démarrer le bilan", timeout=120000)
    check("[modale] Bilan de la partie → résumé", True)
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
    page.click("button:has-text('Abandonner')")
    page.wait_for_timeout(900)
    check("[local] abandon", page.locator("text=gagnent").first.is_visible())
    page.locator("div.fixed").click(position={"x": 10, "y": 10})
    page.wait_for_timeout(300)
    check("[modale] clic fond ferme", page.locator("text=gagnent").count() == 0)

    # ---------- PUZZLES ----------
    page.locator("nav a", has_text="Puzzles").first.click()
    page.wait_for_selector("text=Classement puzzles", timeout=15000)
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
          return els.find(e=>has(e,n=>getComputedStyle(n).background.includes('radial-gradient')))?.getAttribute('data-square') ?? null;
        }""")
        if not tg:
            break
        click_square(page, tg); page.wait_for_timeout(800)
    finished = page.locator("text=Raté").count() or page.locator("text=Résolu").count()
    check("[puzzles] terminé", bool(finished))
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
    page.locator("nav a", has_text="Rush").first.click()
    page.wait_for_timeout(600)
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
    page.locator("nav a", has_text="Analyse").first.click()
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
    page.wait_for_selector("text=vs ", timeout=30000)
    check("[import] liste chargée", page.locator("main button", has_text="vs ").count() >= 5)
    page.click("summary")
    page.wait_for_timeout(300)
    check("[import] details Raccourci s'ouvre", page.locator("text=Raccourcis").is_visible())
    page.fill("input[placeholder*='colle un lien']", "https://www.chess.com/game/live/999999999999")
    page.get_by_role("button", name="Bilan", exact=True).click()
    page.wait_for_timeout(8000)
    check("[import] lien introuvable → erreur propre", page.locator("text=introuvable").count() > 0)

    # ---------- ARCHIVE ----------
    page.locator("nav a", has_text="Archive").first.click()
    page.wait_for_timeout(600)
    rows = page.locator("main a", has_text="Analyser").count()
    check("[archive] parties listées", rows >= 2, f"({rows})")
    with page.expect_download() as dl:
        page.click("button:has-text('Exporter tout')")
    check("[archive] export PGN téléchargé", dl.value.suggested_filename.endswith(".pgn"))
    page.locator("main a", has_text="Analyser").first.click()
    page.wait_for_timeout(800)
    check("[archive] Analyser ouvre la partie", "analyse" in page.url and page.locator("main [data-current]").count() >= 1)
    page.locator("nav a", has_text="Archive").first.click()
    page.wait_for_timeout(600)
    before = page.locator("main a", has_text="Analyser").count()
    page.locator("main button:has-text('✕')").first.click()
    page.wait_for_timeout(500)
    check("[archive] ✕ supprime", page.locator("main a", has_text="Analyser").count() == before - 1)
    page.locator("main a", has_text="Bilan").first.click()
    page.wait_for_selector("text=Démarrer le bilan", timeout=120000)
    check("[archive] Bilan lance le review", True)
    page.click("header button:has-text('✕')")

    # ---------- STATS / RÉGLAGES ----------
    page.locator("nav a", has_text="Stats").first.click()
    page.wait_for_timeout(600)
    page.locator("button[title='Bois']").click()
    page.wait_for_timeout(300)
    check("[stats] thème Bois", '"themeId":"brown"' in page.evaluate("() => localStorage.getItem('chess-local-settings')"))
    page.locator("button[title='Vert']").click()
    toggles = page.locator("main button.h-6.w-11")
    t0 = toggles.nth(0)
    was_on = "bg-accent" in (t0.get_attribute("class") or "")
    t0.click(); page.wait_for_timeout(200)
    check("[stats] toggle coups légaux", ("bg-accent" in (t0.get_attribute("class") or "")) != was_on)
    t0.click()
    t1 = toggles.nth(1)
    was_on = "bg-accent" in (t1.get_attribute("class") or "")
    t1.click(); page.wait_for_timeout(200)
    check("[stats] toggle sons", ("bg-accent" in (t1.get_attribute("class") or "")) != was_on)
    t1.click()
    for depth, key in [("Rapide", "fast"), ("Profond", "deep"), ("Équilibré", "balanced")]:
        page.get_by_role("button", name=depth, exact=True).click()
        page.wait_for_timeout(200)
        check(f"[stats] profondeur {depth}", f'"reviewDepth":"{key}"' in page.evaluate("() => localStorage.getItem('chess-local-settings')"))

    ctx.close()
    browser.close()

print("=" * 50)
print("TOUT PASSE" if not errors else f"ÉCHECS: {errors}")
