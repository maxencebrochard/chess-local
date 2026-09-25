"""T05d : quel geste fait fuir un board détaché ? 8 itérations par scénario."""
import sys
from pz import *
def nxt(page, prev):
    page.locator("main button").filter(has_text="Suivant").or_(page.locator("main button").filter(has_text="Passer")).first.tap()
    z = wait_puzzle(page, not_id=prev); page.wait_for_timeout(700); return z
with sync_playwright() as p:
    for scen in ("select_only", "wrong_move", "first_move_only", "solve"):
        browser, ctx, page, logs = open_mobile(p, standalone=True)
        page.goto(f"{BASE}/#/puzzles")
        page.wait_for_selector("text=Classement puzzles", timeout=30000)
        page.wait_for_timeout(1000)
        n0 = heap_mb(page)
        pz = wait_puzzle(page)
        for i in range(8):
            wait_placement(page, pz, 1)
            if scen == "select_only":
                tap_square(page, pz["moves"][1][:2]); page.wait_for_timeout(200)
            elif scen == "wrong_move":
                w = wrong_move(pz, 1); tap_move(page, w[:2], w[2:4]); page.wait_for_timeout(300)
            elif scen == "first_move_only":
                play_uci(page, pz["moves"][1]); page.wait_for_timeout(600)
            else:
                solve(page, pz); page.wait_for_timeout(400)
            pz = nxt(page, pz["id"])
        n1 = heap_mb(page)
        print(f"{scen:16s} noeuds {n0[1]} -> {n1[1]}  listeners {n0[2]} -> {n1[2]}  (+{(n1[1]-n0[1])/8:.0f} noeuds/puzzle)")
        browser.close()
