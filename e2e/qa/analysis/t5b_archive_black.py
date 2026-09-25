"""Passe 5b : partie jouée avec les noirs -> Analyser / Bilan depuis l'archive ; doublons en dev vs prod."""
import os, sys
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *
import qa_helpers

TARGET = sys.argv[1] if len(sys.argv) > 1 else BASE


def orient(page):
    return page.evaluate("() => {const a=document.querySelector(\"[data-square='a1']\").getBoundingClientRect(); const h=document.querySelector(\"[data-square='h8']\").getBoundingClientRect(); return a.top < h.top ? 'noirs en bas' : 'blancs en bas'}")


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{TARGET}/#/jouer"); page.wait_for_timeout(1500)
    page.get_by_role("button", name="Noa").click()
    page.get_by_role("button", name="♚ Noirs").click()
    page.get_by_role("button", name="Jouer", exact=True).click(); page.wait_for_timeout(4000)
    # noirs : on joue quelques coups faibles pour créer des fautes
    for frm, to in (("f7", "f6"), ("a7", "a6"), ("b7", "b5")):
        try:
            tap_move(page, frm, to)
        except Exception as e:
            print("coup impossible", frm, to)
        page.wait_for_timeout(3000)
    ab = page.locator("button:visible:enabled", has_text="Abandonner")
    if ab.count():
        ab.first.click(); page.wait_for_timeout(1500)
    else:
        print("partie déjà terminée:", page.locator("div.fixed").first.inner_text()[:80])
    page.goto(f"{TARGET}/#/archive"); page.wait_for_timeout(1200)
    n = page.locator("main a", has_text="Analyser").count()
    print(f"[{TARGET}] parties en archive après 1 partie jouée:", n)
    if TARGET != BASE:
        browser.close(); sys.exit()
    print(page.locator("main .space-y-1 > div").first.inner_text().replace("\n", " | "))
    page.locator("main a", has_text="Analyser").first.click(); page.wait_for_timeout(2500)
    print("Analyser partie noire -> orientation:", orient(page), "| hash:", page.evaluate("location.hash"))
    shot(page, "t5b_analyser_black")
    page.goto(f"{TARGET}/#/archive"); page.wait_for_timeout(1000)
    page.locator("main a", has_text="Bilan").first.click()
    page.wait_for_selector("text=Démarrer le bilan", timeout=120000); page.wait_for_timeout(300)
    print("résumé:", page.evaluate("() => [...document.querySelectorAll('.fixed .grid')][0].innerText.replace(/\\n+/g,' | ')"))
    shot(page, "t5b_summary_black")
    page.locator("button", has_text="Démarrer le bilan").click(); page.wait_for_timeout(600)
    n = page.locator(".fixed [data-current]").count()
    for i in range(n):
        print(f"  [{i}]", page.locator(".fixed .bg-white").first.inner_text().replace("\n", " | "))
        if i == 0:
            shot(page, "t5b_guided_opponent_move")
            print("   orientation guidé:", orient(page))
        nxt = page.locator(".fixed button", has_text="Suivant")
        if nxt.count(): nxt.click(); page.wait_for_timeout(300)
    mist = page.evaluate("""() => new Promise(res => {const r=indexedDB.open('chess-local'); r.onsuccess=()=>{const db=r.result; const tx=db.transaction('mistakes'); const q=tx.objectStore('mistakes').getAll(); q.onsuccess=()=>res(q.result.map(m => ({label:m.gameLabel, fen:m.fenBefore.split(' ').slice(0,2).join(' '), san:m.playedSan, cls:m.cls})))}})""")
    print("mistakes enregistrées:", mist)
    print("LOGS", logs)
    browser.close()
