"""Accueil + Stats : état peuplé, justesse des chiffres, CTA, réglages, persistance, thème partout."""
import json
import os
import sys

QA = "e2e/qa"
os.environ.setdefault("SHOTS", f"{QA}/global/shots")
sys.path.insert(0, QA)
sys.path.insert(0, f"{QA}/global")
from qa_helpers import *  # noqa
from seed import seed, dump_counts, EXPECTED

fails = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        fails.append(name)


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.on("requestfailed", lambda r: logs.append(f"REQFAILED {r.url[:100]}"))
    page.goto(f"{BASE}/#/")
    page.wait_for_timeout(1200)
    seed(page)
    print("stores:", dump_counts(page))
    page.reload()
    page.wait_for_timeout(1300)
    shot(page, "home_populated_393x852")
    txt = page.locator("main").inner_text()
    print("HOME TEXT:", txt.replace("\n", " | "))
    check("home: 8 résolus", "8 résolus" in txt)
    check("home: classement puzzles 1034", "classement 1034" in txt)
    check("home: rapide 781 / blitz 868 / bullet 803", all(v in txt for v in ["781", "868", "803"]))
    check("home: archive 10 parties", "10 parties" in txt)
    check("home: classement Illimité (822) visible quelque part", "822" in txt)

    # CTA
    for label, expected in [("Problèmes", "#/puzzles"), ("Rapide", "#/stats"), ("Blitz", "#/stats"), ("Bullet", "#/stats"), ("Analyse", "#/analyse"),
                            ("Puzzle Rush", "#/rush"), ("Archive", "#/archive"), ("chess.com", "#/import")]:
        page.goto(f"{BASE}/#/")
        page.wait_for_timeout(700)
        page.locator("main a", has_text=label).first.tap()
        page.wait_for_timeout(700)
        check(f"home CTA {label} -> {expected}", page.evaluate("location.hash").startswith(expected), page.evaluate("location.hash"))
    page.goto(f"{BASE}/#/")
    page.wait_for_timeout(700)
    page.get_by_role("button", name="Jouer", exact=True).tap()
    page.wait_for_timeout(700)
    check("home CTA Jouer -> #/jouer", page.evaluate("location.hash") == "#/jouer")

    # ---------- STATS ----------
    page.goto(f"{BASE}/#/stats")
    page.wait_for_timeout(1300)
    shot(page, "stats_populated_393x852_top")
    txt = page.locator("main").inner_text()
    print("STATS TEXT:", txt.replace("\n", " | ")[:900])
    check("stats: 3 gagnées", f"{EXPECTED['wins']} gagnées" in txt)
    check("stats: 2 nulles", f"{EXPECTED['draws']} nulles" in txt)
    check("stats: 2 perdues", f"{EXPECTED['losses']} perdues" in txt)
    check("stats: 8 résolus / 12 tentés (67 %)", "8 résolus / 12 tentés" in txt and "67" in txt)
    check("stats: singulier '1 partie' (bullet)", "1 partie" in txt and "1 parties" not in txt, "-> " + ("'1 parties' affiché" if "1 parties" in txt else "ok"))
    check("stats: classement Illimité affiché", "Illimité" in txt or "822" in txt)
    check("stats: records Puzzle Rush affichés", "Rush" in txt)
    check("stats: domaines Apprendre affichés", "850" in txt or "905" in txt)
    bar = page.evaluate("""() => { const b = document.querySelector('main .h-2.rounded-full'); if (!b) return null; const W = b.getBoundingClientRect().width; return [...b.children].map(c => +(c.getBoundingClientRect().width / W * 100).toFixed(1)) }""")
    print("barre V/N/D (%):", bar)
    check("stats: barre V/N/D = 42.9/28.6/28.6", bar is not None and abs(bar[0] - 42.9) < 0.5 and abs(bar[1] - 28.6) < 0.5)
    hfull = page.evaluate("document.querySelector('main').scrollHeight - document.querySelector('main').clientHeight")
    page.set_viewport_size({"width": 393, "height": 852 + hfull})
    page.wait_for_timeout(300)
    shot(page, "stats_populated_393_full")
    page.set_viewport_size({"width": 393, "height": 852})

    # ---------- RÉGLAGES + persistance ----------
    page.locator("button[title='Améthyste']").tap()
    toggles = page.locator("main button.h-6.w-11")
    toggles.nth(0).tap()  # coups légaux -> off
    toggles.nth(1).tap()  # sons -> on
    page.get_by_role("button", name="Profond", exact=True).tap()
    page.wait_for_timeout(300)
    ls = json.loads(page.evaluate("localStorage.getItem('chess-local-settings')"))
    print("settings après clics:", ls)
    check("réglages écrits", ls["state"]["themeId"] == "purple" and ls["state"]["showLegalMoves"] is False and ls["state"]["playSounds"] is True and ls["state"]["reviewDepth"] == "deep")
    page.reload()
    page.wait_for_timeout(1200)
    ls2 = json.loads(page.evaluate("localStorage.getItem('chess-local-settings')"))
    check("réglages persistés après reload", ls2["state"] == ls["state"], str(ls2["state"]))
    ui = page.evaluate("""() => ({ theme: [...document.querySelectorAll('main button[title]')].filter(b => b.className.includes('border-accent')).map(b => b.title),
        toggles: [...document.querySelectorAll('main button.h-6.w-11')].map(b => b.className.includes('bg-accent')),
        depth: [...document.querySelectorAll('main button')].filter(b => b.className.includes('bg-accent/10')).map(b => b.innerText) })""")
    print("UI après reload:", ui)
    check("UI reflète les réglages après reload", ui == {"theme": ["Améthyste"], "toggles": [False, True], "depth": ["Profond"]})
    # pseudo chess.com : où est-il éditable ?
    check("stats: pseudo chess.com éditable dans Réglages", page.locator("main input[type=text], main input:not([type])").count() > 0)
    check("stats: version/build affiché dans Réglages", "build" in page.locator("main").inner_text().lower())
    # remets les sons à off pour la suite (pas d'audio en headless, mais propre)
    page.locator("main button.h-6.w-11").nth(1).tap()

    # ---------- THÈME APPLIQUÉ PARTOUT (améthyste : dark #8877b7 = rgb(136, 119, 183)) ----------
    DARK = "rgb(136, 119, 183)"
    sqbg = """() => { const e = document.querySelector("[data-square='a1']"); return e ? getComputedStyle(e).backgroundColor : null }"""
    sqbg_last = """() => { const all = document.querySelectorAll("[data-square='a1']"); const e = all[all.length - 1]; return e ? getComputedStyle(e).backgroundColor + ' (n=' + all.length + ')' : null }"""
    page.goto(f"{BASE}/#/puzzles"); page.wait_for_timeout(2500)
    check("thème: puzzles", page.evaluate(sqbg) == DARK, str(page.evaluate(sqbg)))
    shot(page, "theme_purple_puzzles")
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(1500)
    check("thème: analyse", page.evaluate(sqbg) == DARK, str(page.evaluate(sqbg)))
    page.goto(f"{BASE}/#/rush"); page.wait_for_timeout(800)
    page.locator("main button", has_text="Survie").tap(); page.wait_for_timeout(2500)
    check("thème: rush", page.evaluate(sqbg) == DARK, str(page.evaluate(sqbg)))
    page.goto(f"{BASE}/#/jouer"); page.wait_for_timeout(1000)
    page.get_by_role("button", name="Jouer", exact=True).tap(); page.wait_for_timeout(1500)
    check("thème: jouer", page.evaluate(sqbg) == DARK, str(page.evaluate(sqbg)))
    page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(1000)
    page.locator("main button", has_text="Finales").first.tap(); page.wait_for_timeout(2500)
    check("thème: apprendre (exercice)", page.evaluate(sqbg) == DARK, str(page.evaluate(sqbg)))
    if page.locator("button[title='Voir le cours']").count():
        page.locator("button[title='Voir le cours']").tap(); page.wait_for_timeout(800)
        v = page.evaluate(sqbg_last)
        check("thème: diagramme de cours", v is not None and v.startswith(DARK), str(v))
        shot(page, "theme_purple_course")
    else:
        print("   (pas de bouton cours sur cet item)")
    print("logs:", logs)
    browser.close()

print("\nFAILS:", fails)
