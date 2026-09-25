"""T09 : sons (playSounds=true) : quels fichiers sont demandés à chaque étape ?"""
from pz import *
with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, settings={"playSounds": True}, standalone=True)
    reqs = []
    page.on("request", lambda r: reqs.append(r.url.split("/")[-1]) if "/sounds/" in r.url else None)
    page.add_init_script("""window.__played = []; const S = AudioBufferSourceNode.prototype.start; AudioBufferSourceNode.prototype.start = function(...a){ window.__played.push(Math.round(this.buffer.duration*1000)); return S.apply(this, a) }""")
    page.goto(f"{BASE}/#/puzzles")
    page.wait_for_selector("text=Classement puzzles", timeout=30000)
    pz = wait_puzzle(page); assert wait_placement(page, pz, 1); page.wait_for_timeout(400)
    print("après amorce : fichiers", reqs, "sons joués (durées ms):", page.evaluate("window.__played"))
    w = wrong_move(pz, 1); tap_move(page, w[:2], w[2:4]); page.wait_for_timeout(600)
    print("après coup faux : fichiers", reqs, "joués:", page.evaluate("window.__played"))
    page.locator("main button", has_text="Suivant").tap()
    pz2 = wait_puzzle(page, not_id=pz["id"]); solve(page, pz2); page.wait_for_timeout(700)
    print("après résolution : fichiers", reqs, "joués:", page.evaluate("window.__played"))
    print("LOGS:", set(l[:120] for l in logs))
    browser.close()
