"""Pendules : bullet 1+0, échantillonnage fin, drapeau, dérive, gel de page (arrière-plan)."""
import time
from common import *

SAMPLER = """() => {
  window.__samples = []
  window.__t0 = performance.now()
  window.__timer = setInterval(() => {
    const els = Array.from(document.querySelectorAll('main .font-mono.text-xl'))
    const modal = !!document.querySelector('div.fixed')
    window.__samples.push([Math.round(performance.now() - window.__t0), els.map(e => e.textContent).join('|'), els.map(e => e.className.includes('bg-red-900') ? 'R' : e.className.includes('bg-neutral-100') ? 'A' : '-').join(''), modal])
    if (modal && window.__samples.length > 5 && window.__samples[window.__samples.length - 5][3]) clearInterval(window.__timer)
  }, 50)
}"""

with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    goto_play(page)
    setup_t = time.time()
    # lance sans attendre 500 ms : on veut le t0 le plus proche du départ
    page.locator("main button", has_text="Noa").first.click()
    page.locator("main button", has_text="1 min").first.click()
    page.get_by_role("button", name="Jouer", exact=True).click()
    page.wait_for_selector("[data-square='e2']")
    page.evaluate(SAMPLER)
    print("pendules départ:", clock_texts(page))
    page.wait_for_timeout(42000)
    shot(page, "clock_low_red")           # < 20 s : rouge
    page.wait_for_timeout(9500)
    shot(page, "clock_tenths")            # < 10 s : dixièmes
    page.wait_for_selector("div.fixed", timeout=30000)
    page.wait_for_timeout(600)
    shot(page, "clock_flag_modal")
    print("MODALE:", page.locator("div.fixed").inner_text().replace("\n", " | "))
    samples = page.evaluate("() => window.__samples")
    # transitions de texte de la pendule blanche (en bas)
    last = None
    trans = []
    for t, txt, cls, modal in samples:
        mine = txt.split("|")[-1] if txt else ""
        if mine != last:
            trans.append((t, mine, cls))
            last = mine
    print("nb transitions:", len(trans))
    print("début:", trans[:3])
    zone = [x for x in trans if x[1].startswith("0:1") or x[1].startswith("0:0")]
    around10 = [x for x in zone if x[1][:4] in ("0:11", "0:10", "0:09")]
    print("autour de 10 s:", around10[:16])
    print("passage au rouge (premier 'R'):", next(((t, txt) for t, txt, cls, m in samples if 'R' in cls), None))
    print("fin:", trans[-8:])
    t_modal = next((t for t, txt, cls, m in samples if m), None)
    t_zero = next((t for t, txt, cls in trans if txt == "0:00"), None)
    print(f"temps mur entre début d'échantillonnage et 0:00 : {t_zero} ms ; modale à {t_modal} ms (attendu ~60000 moins le délai de pose du sampler)")
    neg = [x for x in trans if "-" in x[1]]
    print("temps négatifs:", neg)
    # le bot a-t-il joué ? (il ne doit pas : c'était aux blancs)
    print("demi-coups:", ply_count(page))
    page.touchscreen.tap(196, 30); page.wait_for_timeout(400)
    shot(page, "clock_flag_after_close")
    idb = page.evaluate("""() => new Promise(res => { const r = indexedDB.open('chess-local'); r.onsuccess = () => { const db = r.result; const tx = db.transaction(['ratings','games']); const out = {}; tx.objectStore('ratings').getAll().onsuccess = e => out.ratings = e.target.result; tx.objectStore('games').getAll().onsuccess = e => out.games = e.target.result.map(g => [g.id, g.result, g.termination, g.playerRatingAfter, g.timeClass, g.pgn.slice(-40)]); tx.oncomplete = () => res(out) } })""")
    print("IDB:", idb)

    # ---------- Gel de la page (équivalent PWA iOS en arrière-plan) ----------
    goto_play(page)
    page.locator("main button", has_text="Noa").first.click()
    page.locator("main button", has_text="1 min").first.click()
    page.get_by_role("button", name="Jouer", exact=True).click()
    page.wait_for_selector("[data-square='e2']")
    page.wait_for_timeout(3000)
    before = clock_texts(page)
    cdp = ctx.new_cdp_session(page)
    t0 = time.time()
    cdp.send("Page.setWebLifecycleState", {"state": "frozen"})
    time.sleep(10)
    cdp.send("Page.setWebLifecycleState", {"state": "active"})
    page.wait_for_timeout(300)
    after = clock_texts(page)
    print(f"GEL 10 s : pendules avant {before} -> après {after} (temps mur écoulé {time.time()-t0:.1f}s)")
    print("LOGS:", logs)
    browser.close()
