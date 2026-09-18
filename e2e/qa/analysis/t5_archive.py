"""Passe 5 : archive (état vide, création de parties, liste, Analyser/Bilan, export, suppression)."""
import os, sys
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *


def play_and_resign(page, color, tc, first):
    page.goto(f"{BASE}/#/"); page.wait_for_timeout(400)
    page.goto(f"{BASE}/#/jouer"); page.wait_for_timeout(800)
    page.get_by_role("button", name="Noa").click()
    page.get_by_role("button", name=color).click()
    page.get_by_role("button", name=tc, exact=True).click()
    page.get_by_role("button", name="Jouer", exact=True).click(); page.wait_for_timeout(1500)
    if color == "♚ Noirs":
        page.wait_for_timeout(2500)
    tap_move(page, *first); page.wait_for_timeout(2500)
    page.locator("button:visible", has_text="Abandonner").first.click(); page.wait_for_timeout(1500)
    shot(page, f"t5_gameover_{tc.replace(' ', '').replace('|', '-')}")


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/archive"); page.wait_for_timeout(1000)
    shot(page, "t5_00_empty")
    print("état vide:", page.locator("main").inner_text().replace("\n", " | "))

    play_and_resign(page, "♔ Blancs", "10 min", ("e2", "e4"))
    play_and_resign(page, "♚ Noirs", "3 | 2", ("e7", "e5"))
    # partie locale
    page.goto(f"{BASE}/#/"); page.wait_for_timeout(400)
    page.goto(f"{BASE}/#/jouer"); page.wait_for_timeout(800)
    page.locator("button", has_text="2 joueurs").first.click() if page.locator("button", has_text="2 joueurs").count() else None
    page.get_by_role("button", name="Jouer", exact=True).click(); page.wait_for_timeout(1200)
    tap_move(page, "e2", "e4"); tap_move(page, "e7", "e5")
    page.locator("button:visible", has_text="Abandonner").first.click(); page.wait_for_timeout(1500)

    page.goto(f"{BASE}/#/archive"); page.wait_for_timeout(1200)
    shot(page, "t5_01_list")
    rows = page.locator("main .space-y-1 > div")
    print("nb lignes:", rows.count(), "overflow_x:", overflow_x(page))
    for i in range(rows.count()):
        r = rows.nth(i)
        print(f"  ligne {i}: {r.inner_text()!r} h={round(r.bounding_box()['height'])}")
    # cibles tactiles
    for sel in ("a:has-text('Bilan')", "a:has-text('Analyser')", "button:has-text('✕')"):
        bb = page.locator(f"main {sel}").first.bounding_box()
        print("cible", sel, {k: round(v) for k, v in bb.items()})

    # Export global
    with page.expect_download() as dl:
        page.locator("main button", has_text="Exporter tout").click()
    path = dl.value.path()
    content = open(path).read()
    print("EXPORT PGN:\n" + content)

    # Analyser (Revoir)
    page.locator("main a", has_text="Analyser").nth(1).click(); page.wait_for_timeout(2500)
    print("Analyser: hash", page.evaluate("location.hash"), "orientation (a1 en haut ?):",
          page.evaluate("() => {const a=document.querySelector(\"[data-square='a1']\").getBoundingClientRect(); const h=document.querySelector(\"[data-square='h8']\").getBoundingClientRect(); return a.top < h.top ? 'noirs en bas' : 'blancs en bas'}"))
    shot(page, "t5_02_analyser_black_game")
    page.go_back(); page.wait_for_timeout(800)
    print("retour arrière -> hash", page.evaluate("location.hash"))

    # Bilan
    page.goto(f"{BASE}/#/archive"); page.wait_for_timeout(1000)
    page.locator("main a", has_text="Bilan").nth(1).click()
    page.wait_for_selector("text=Démarrer le bilan", timeout=120000); page.wait_for_timeout(300)
    shot(page, "t5_03_bilan_black_game")
    print("résumé noms:", page.evaluate("() => [...document.querySelectorAll('.fixed .grid')][0].innerText.replace(/\\n+/g,' | ')"))
    page.locator("button", has_text="Démarrer le bilan").click(); page.wait_for_timeout(600)
    print("guidé 1er coup bulle:", page.locator(".fixed .bg-white").first.inner_text().replace("\n", " | "))
    shot(page, "t5_04_guided_black_game")
    # mistakes enregistrées ?
    mist = page.evaluate("""() => new Promise(res => {const r=indexedDB.open('chess-local'); r.onsuccess=()=>{const db=r.result; const tx=db.transaction('mistakes'); const q=tx.objectStore('mistakes').getAll(); q.onsuccess=()=>res(q.result)}})""")
    print("mistakes:", mist)

    # Suppression sans confirmation ?
    page.goto(f"{BASE}/#/archive"); page.wait_for_timeout(1000)
    n0 = page.locator("main a", has_text="Analyser").count()
    page.locator("main button", has_text="✕").first.click(); page.wait_for_timeout(500)
    n1 = page.locator("main a", has_text="Analyser").count()
    print("suppression:", n0, "->", n1, "| confirmation/annuler visible:", page.locator("text=/Annuler|Confirmer|Supprimer/").count())
    shot(page, "t5_05_after_delete")
    print("LOGS", logs)
    browser.close()
