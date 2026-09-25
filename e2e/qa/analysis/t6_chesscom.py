"""Passe 6 : import chess.com (réseau réel)."""
import os, sys, time, json
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *

USER = sys.argv[1] if len(sys.argv) > 1 else " Hikaru "


def orient(page):
    return page.evaluate("() => {const a=document.querySelector(\"[data-square='a1']\").getBoundingClientRect(); const h=document.querySelector(\"[data-square='h8']\").getBoundingClientRect(); return a.top < h.top ? 'noirs en bas' : 'blancs en bas'}")


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    reqs = []
    game_urls = []
    page.on("request", lambda r: reqs.append(r.url) if "api.chess.com" in r.url else None)

    def on_resp(r):
        if "api.chess.com" in r.url:
            print("   API", r.status, r.url)
            if "/games/20" in r.url and r.status == 200:
                try:
                    d = r.json()
                    game_urls.extend([g["url"] for g in d["games"][-5:]])
                except Exception as e:
                    print("   json err", e)
    page.on("response", on_resp)

    page.goto(f"{BASE}/#/import"); page.wait_for_timeout(1200)
    shot(page, "t6_00_empty")
    btn = page.get_by_role("button", name="Connecter")
    print("champ vide -> Connecter désactivé:", btn.is_disabled())
    inp = page.locator("input").first
    print("attributs input:", inp.evaluate("e => ({autocap: e.getAttribute('autocapitalize'), autocorrect: e.getAttribute('autocorrect'), spell: e.getAttribute('spellcheck'), enterkeyhint: e.getAttribute('enterkeyhint'), type: e.type, fontSize: getComputedStyle(e).fontSize})"))
    inp.fill("   "); print("espaces seuls -> désactivé:", btn.is_disabled())
    # Entrée clavier
    inp.fill(USER); inp.press("Enter"); page.wait_for_timeout(600)
    print("Entrée dans le champ -> requêtes:", len(reqs), "| Chargement visible:", page.locator("text=Chargement…").count())
    t0 = time.time()
    if not reqs:
        btn.click()
    page.wait_for_timeout(250)
    shot(page, "t6_01_loading")
    print("état de chargement:", page.locator("text=Chargement…").count(), "| bouton pendant chargement:", page.locator("main button").first.inner_text(), "désactivé:", page.locator("main button").first.is_disabled())
    try:
        page.wait_for_selector("main button:has-text('vs ')", timeout=90000)
        print("liste chargée en", round(time.time() - t0, 1), "s ; nb parties:", page.locator("main button:has-text('vs ')").count())
    except Exception:
        print("LISTE NON CHARGÉE après 90 s ; erreur affichée:", page.locator("p.text-red-300").all_inner_texts(), "LOGS", logs)
    shot(page, "t6_02_list")
    print("overflow_x:", overflow_x(page))
    rows = page.locator("main button:has-text('vs ')")
    for i in range(min(4, rows.count())):
        print("   ", rows.nth(i).inner_text().replace("\n", " | "))
    print("pseudo stocké:", page.evaluate("JSON.parse(localStorage.getItem('chess-local-settings')).state.chesscomUsername"))

    # Actualiser avec le même pseudo : refetch ?
    n0 = len(reqs)
    page.get_by_role("button", name="Actualiser").click(); page.wait_for_timeout(2500)
    print("Actualiser (même pseudo) -> nouvelles requêtes:", len(reqs) - n0)

    # Tap sur une partie
    if rows.count():
        first = rows.first.inner_text().replace("\n", " | ")
        rows.first.click()
        page.wait_for_timeout(800)
        shot(page, "t6_03_after_tap")
        page.wait_for_selector("text=Démarrer le bilan", timeout=300000); page.wait_for_timeout(300)
        print("partie tapée:", first)
        print("résumé:", page.evaluate("() => [...document.querySelectorAll('.fixed .grid')][0].innerText.replace(/\\n+/g,' | ')"))
        shot(page, "t6_04_summary")
        page.locator("button", has_text="Démarrer le bilan").click(); page.wait_for_timeout(600)
        print("orientation:", orient(page), "| 1re bulle:", page.locator(".fixed .bg-white").first.inner_text().replace("\n", " | "))
        shot(page, "t6_05_guided")
        mist = page.evaluate("""() => new Promise(res => {const r=indexedDB.open('chess-local'); r.onsuccess=()=>{const db=r.result; const tx=db.transaction('mistakes'); const q=tx.objectStore('mistakes').getAll(); q.onsuccess=()=>res(q.result.map(m => ({label:m.gameLabel, trait:m.fenBefore.split(' ')[1], san:m.playedSan, cls:m.cls})))}})""")
        print("mistakes enregistrées (trait = couleur fautive):", mist)
        # retour : geste back
        page.go_back(); page.wait_for_timeout(1000)
        print("go_back depuis le bilan -> hash:", page.evaluate("location.hash"))

    # Lien collé
    page.goto(f"{BASE}/#/import"); page.wait_for_timeout(1500)
    if game_urls:
        link = game_urls[-1]
        print("lien testé:", link)
        page.wait_for_selector("main button:has-text('vs ')", timeout=90000)
        page.locator("input").nth(1).fill(link)
        page.get_by_role("button", name="Bilan", exact=True).click(); page.wait_for_timeout(500)
        shot(page, "t6_06_link_loading")
        try:
            page.wait_for_url("**/analyse**", timeout=120000)
            print("lien collé -> analyse ok:", page.evaluate("location.hash"))
        except Exception:
            print("lien collé -> pas de navigation ; erreur:", page.locator("p.text-red-300").all_inner_texts())
    print("LOGS", logs)
    browser.close()
