"""Régressions de sélection et de plans des structures."""
import re

from helpers import BASE, Checker, mobile_context, shot
from test_structures import SEED_JS, GAME

ck = Checker("structures_selection")
COLLISION = "1. e4 e6 2. d4 d5 3. e5 f5 4. Nf3 Nh6 5. Bd3 Be7 6. O-O O-O 7. Re1 *"
CARO = "1. e4 c6 2. d4 d5 3. Nc3 dxe4 4. Nxe4 Bf5 5. Ng3 Bg6 6. Nf3 e6 7. Bd3 Nf6 8. O-O Be7 9. Re1 O-O *"
INVERSE = "1. e3 e5 2. d4 d5 3. Nf3 e4 4. Be2 Nf6 5. O-O Be7 6. b3 O-O 7. Bb2 *"


def suite(p):
    browser = p.chromium.launch(headless=True)
    ctx = mobile_context(p, browser, ck, standalone=True)
    chesscom_requests = []
    ctx.on("request", lambda req: chesscom_requests.append(req.url) if "api.chess.com" in req.url else None)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/structures")
    page.wait_for_selector("[data-testid='structures-summary']")
    games = [dict(id=i, date=1760000000000, mode="bot", botId="iris", playerColor="b" if i == 3 else "w",
                  timeControl="5+0", timeClass="blitz", pgn=pgn, result="*", termination="abandon")
             for i, pgn in enumerate([COLLISION, INVERSE, CARO], 1)]
    page.evaluate(SEED_JS, [games, []])
    page.reload()
    sides = page.locator("[data-id='caro-slave'] [data-testid='structure-sides']")
    sides.wait_for()
    ck.check("Caro-Kann : bilan indépendant des coordonnées", sides.inner_text() == "Avec la structure : 1 · contre : 0")
    collision_fen = None
    for sid, game_id, title, hint, plan in [
        ("stonewall", 1, "Stonewall", "Contre le Stonewall", "la case e5 est un trou"),
        ("francaise", 1, "Chaîne française", "Avec la chaîne avancée", "La chaîne d4-e5"),
        ("francaise", 2, "Chaîne française", "Contre la chaîne avancée", "fou de cases noires"),
        ("caro-slave", 3, "Caro-Kann / slave", "Avec le triangle c6-e6", "Le triangle c6-e6"),
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
            if refresh:
                shot(page, f"structures_selection_{sid}_{game_id}")
        ck.check(f"{sid}/{game_id} clé distingue la structure", key.endswith(f"@{sid}"))
    ck.check("Parties déjà chargées : aucun appel chess.com", not chesscom_requests, str(chesscom_requests))
    ctx.close()
    browser.close()


if __name__ == "__main__":
    ck.run(suite)
