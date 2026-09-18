import os, sys
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *
with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    uci = []
    page.on("console", lambda m: uci.append(m.text) if m.text.startswith("[uci") else None)
    page.goto(f"{BASE}/?debug-uci#/analyse"); page.wait_for_timeout(2500)
    tap_move(page, "e2", "e4"); page.wait_for_timeout(1500)
    print("UCI avant OFF (journal actif ?):", len(uci), uci[-4:])
    n = len(uci)
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Moteur").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Fermer").click(); page.wait_for_timeout(3000)
    print("UCI après OFF:", uci[n:])
    tap_move(page, "e7", "e5"); page.wait_for_timeout(1500)
    print("UCI après un coup moteur OFF:", uci[n:])
    browser.close()
