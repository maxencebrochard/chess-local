"""Vérifie si la double sauvegarde de fin de partie existe aussi sur le build de prod (sans StrictMode dev)."""
import os
os.environ["BASE"] = "https://maxencebrochard.github.io/chess-local"
from common import *

IDB = """() => new Promise(res => { const r = indexedDB.open('chess-local'); r.onsuccess = () => { const db = r.result; const tx = db.transaction(['games']); let out; tx.objectStore('games').getAll().onsuccess = e => out = e.target.result.map(g => [g.id, g.result, g.termination]); tx.oncomplete = () => res(out) } })"""
with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/jouer"); page.wait_for_selector("text=Cadence", timeout=30000)
    build = None
    setup(page, mode="local", tc="Illimité")
    for a, b in [("f2", "f3"), ("e7", "e5"), ("g2", "g4"), ("d8", "h4")]:
        tap_move(page, a, b)
    page.wait_for_selector("div.fixed", timeout=8000); page.wait_for_timeout(800)
    print("PROD modale:", page.locator("div.fixed").inner_text().replace("\n", " | "))
    print("PROD parties en base après 1 partie:", page.evaluate(IDB))
    browser.close()
