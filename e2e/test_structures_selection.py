"""Régressions de sélection et de plans des structures."""
import re

from helpers import BASE, Checker, mobile_context
from test_structures import SEED_JS, GAME

ck = Checker("structures_selection")
COLLISION = "1. e4 e6 2. d4 d5 3. e5 f5 4. Nf3 Nh6 5. Bd3 Be7 6. O-O O-O 7. Re1 *"
INVERSE = "1. e3 e5 2. d4 d5 3. Nf3 e4 4. Be2 Nf6 5. O-O Be7 6. b3 O-O 7. Bb2 *"


def suite(p):
    browser = p.chromium.launch(headless=True)
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/structures")
    page.wait_for_selector("[data-testid='structures-summary']")
    games = [dict(id=i, date=1760000000000, mode="bot", botId="iris", playerColor="w",
                  timeControl="5+0", timeClass="blitz", pgn=pgn, result="*", termination="abandon")
             for i, pgn in enumerate([COLLISION, INVERSE], 1)]
    page.evaluate(SEED_JS, [games, []])
    page.reload()
    collision_fen = None
    for sid, game_id, title, hint, plan in [
        ("stonewall", 1, "Stonewall", "Contre le Stonewall", "la case e5 est un trou"),
        ("francaise", 1, "Chaîne française", "Avec la chaîne avancée", "La chaîne d4-e5"),
        ("francaise", 2, "Chaîne française", "Contre la chaîne avancée", "fou de cases noires"),
    ]:
        page.goto(f"{BASE}/#/structures")
        row = page.locator(f"[data-id='{sid}'] [data-key^='local:{game_id}@']")
        row.wait_for()
        key = row.get_attribute("data-key")
        row.click()
        page.wait_for_selector(GAME)
        if game_id == 1:
            fen = page.locator(GAME).get_attribute("data-fen")
            ck.check(f"{sid} demi-coup commun", "@10@" in key)
            if collision_fen is not None:
                ck.check("deux structures, même position", fen == collision_fen)
            collision_fen = fen
        for refresh in (False, True):
            if refresh:
                page.reload()
                page.wait_for_selector(GAME)
            ck.check(f"{sid}/{game_id} titre, rechargement={refresh}", page.locator("h1").inner_text() == title)
            ck.check(f"{sid}/{game_id} camp, rechargement={refresh}", hint in page.locator(GAME).inner_text())
            page.get_by_role("button", name=re.compile(r"^Plan [▴▾]$")).click()
            ck.check(f"{sid}/{game_id} plan, rechargement={refresh}", plan in page.locator(GAME).inner_text())
        ck.check(f"{sid}/{game_id} clé distingue la structure", key.endswith(f"@{sid}"))
    ctx.close()
    browser.close()


if __name__ == "__main__":
    ck.run(suite)
