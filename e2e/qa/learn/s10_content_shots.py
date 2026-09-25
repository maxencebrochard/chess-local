"""Captures de preuve pour les défauts de contenu des cours."""
import sys, json
sys.path.insert(0, 'e2e/qa/learn')
from egdrv import *
with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True); page.add_init_script(RND_INIT)
    for eg_id, elo in (('kq-mate', 800), ('kp-square', 800), ('kp-opposition-1', 800), ('philidor', 1600)):
        open_endgame(page, eg_id, elo)
        page.locator("text=Voir le cours complet").tap(); page.wait_for_timeout(600)
        shot(page, f"s10_course_{eg_id}")
        page.locator("div.fixed.inset-0.z-50 header button").tap(); page.wait_for_timeout(200)
        if eg_id in ('kp-square', 'philidor'):
            go_play(page); page.wait_for_timeout(600); shot(page, f"s10_play_{eg_id}")
        page.goto(f"{BASE}/#/"); page.wait_for_timeout(300)
    # enfilade (thème index 2 sur 20)
    page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(900)
    set_rnd(page, 2.5 / 20); start_domain(page, 'Tactiques')
    print("thème:", get_session(page)['session']['items'][0]['theme'])
    page.locator("text=Voir le cours complet").tap(); page.wait_for_timeout(600)
    shot(page, "s10_course_skewer")
    # un cours sans diagramme (mateIn1 = index 4)
    page.goto(f"{BASE}/#/"); page.wait_for_timeout(300); page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(900)
    set_rnd(page, 4.5 / 20); start_domain(page, 'Tactiques')
    print("thème:", get_session(page)['session']['items'][0]['theme'])
    page.locator("text=Voir le cours complet").tap(); page.wait_for_timeout(600)
    shot(page, "s10_course_mateIn1")
    print("LOGS:", logs[:3])
    browser.close()
