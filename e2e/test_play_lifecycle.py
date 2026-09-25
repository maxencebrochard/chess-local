"""E2E « Jouer », cycle de vie d'une partie contre un bot.

Couvre : navigation dans l'historique sans coup (CP-1, écran blanc), fin de partie pendant la
réflexion du bot et relance immédiate (PLAY-1, BOTS-5), une seule sauvegarde par partie même en
StrictMode (PLAY-9), abandon confirmé et partie annulée sous deux demi-coups (PLAY-10), drapeau
contre un camp sans matériel pour mater (BOTS-4), moteurs libérés à la fin (PERF-3), partie et
configuration restaurées après un changement d'onglet ou un rechargement (PLAY-4).

Les drapeaux utilisent l'horloge simulée de Playwright (`page.clock`) : la pendule de l'app est un
`setInterval` de 100 ms, `run_for` le fait tirer autant de fois que le temps réel l'aurait fait,
sans attendre une minute par scénario.

Usage : npm run test:e2e -- --suite play_lifecycle   (aussi en `npm run test:e2e:dev`, StrictMode)
"""
from helpers import BASE, Checker, mobile_context, shot, tap_move

ck = Checker("play_lifecycle")
check = ck.check

# Lecture directe d'IndexedDB (pas via l'app) : parties et classements tels qu'ils sont stockés.
IDB = """() => new Promise((res, rej) => {
  const r = indexedDB.open('chess-local')
  r.onsuccess = () => {
    const db = r.result
    if (!db.objectStoreNames.contains('games')) { db.close(); res({ games: [], ratings: [] }); return }
    const tx = db.transaction(['games', 'ratings'])
    const out = {}
    tx.objectStore('games').getAll().onsuccess = (e) => { out.games = e.target.result }
    tx.objectStore('ratings').getAll().onsuccess = (e) => { out.ratings = e.target.result }
    tx.oncomplete = () => { db.close(); res(out) }
    tx.onerror = () => { db.close(); rej(tx.error) }
  }
  r.onerror = () => rej(r.error)
})"""

# 2 joueurs local : 32 demi-coups coopératifs après lesquels les Noirs n'ont plus que leur roi et
# le trait est aux Blancs (vérifié avec python-chess : 8/8/2B3k1/4Q3/4P3/8/PPPP1PPP/RNB1K1NR w KQ - 1 17).
# Le drapeau blanc tombe ensuite face à un roi seul : ce doit être une nulle, pas une victoire noire.
FLAG_SEQ = [
    "e2e4", "h7h5", "d1h5", "a7a6", "h5h8", "e7e5", "f1a6", "b7b6", "a6c8", "e8e7", "h8g7", "c7c6",
    "g7f8", "e7f6", "f8f7", "f6g5", "f7g8", "g5h5", "g8d8", "a8a5", "c8d7", "h5g6", "d8b8", "a5a7",
    "d7c6", "a7b7", "b8b7", "b6b5", "b7b5", "g6h6", "b5e5", "h6g6",
]

ARROWS = ["◀", "⏮", "▶", "⏭"]


def goto_play(page):
    page.goto(f"{BASE}/#/jouer")
    return ck.appears("[jouer] écran de configuration", page, "text=Adversaire", timeout=20000)


def setup(page, mode="bot", bot="Noa", color="Blancs", tc="Illimité"):
    """Configure et lance une partie depuis l'écran de configuration."""
    label = {"bot": "Contre un bot", "coach": "Entraîneur", "local": "2 joueurs"}[mode]
    page.locator("main button", has_text=label).first.click()
    page.wait_for_timeout(100)
    if mode != "local":
        page.locator("main button", has_text=bot).first.click()
        page.locator("main button", has_text=color).first.click()
    if mode != "coach":
        page.get_by_role("button", name=tc, exact=True).click()
    page.get_by_role("button", name="Jouer", exact=True).click()
    return ck.appears("[jouer] partie lancée", page, "[data-square='e2']", timeout=15000)


def plies(page):
    """Nombre de demi-coups affichés dans la liste des coups."""
    return page.locator("main [data-current]").count()


def wait_plies(page, n, timeout=15000):
    waited = 0
    while waited < timeout:
        if plies(page) >= n:
            return True
        page.wait_for_timeout(100)
        waited += 100
    return plies(page) >= n


def tap_button(page, text):
    """Tap tactile au centre du bouton de `main` dont le texte est exactement `text`.
    Retourne False s'il n'existe pas (pas d'exception : la suite doit continuer)."""
    box = page.evaluate(
        """(t) => {
          const b = [...document.querySelectorAll('main button')].find((b) => b.innerText.trim() === t)
          if (!b) return null
          const r = b.getBoundingClientRect()
          return [r.x + r.width / 2, r.y + r.height / 2]
        }""",
        text,
    )
    if not box:
        return False
    page.touchscreen.tap(*box)
    page.wait_for_timeout(200)
    return True


def page_alive(page):
    """L'app est toujours rendue : #root non vide et échiquier présent."""
    return page.evaluate("() => (document.getElementById('root')?.innerHTML.length ?? 0) > 0") and page.locator("[data-square='e2']").count() == 1


def arrows_disabled(page):
    return page.evaluate(
        """() => {
          const wanted = ['◀', '⏮', '▶', '⏭']
          const bs = [...document.querySelectorAll('main button')].filter((b) => wanted.includes(b.innerText.trim()))
          return bs.length === 4 && bs.every((b) => b.disabled)
        }"""
    )


def resign(page, confirm_label="Oui, abandonner"):
    """Tape « Abandonner » puis confirme SI la feuille de confirmation existe. Sans le correctif elle
    n'existe pas : le run rouge doit montrer les vrais échecs, pas un délai sur un bouton absent."""
    page.locator("main button", has_text="🏳").first.click()
    page.wait_for_timeout(300)
    btn = page.get_by_role("button", name=confirm_label, exact=True)
    if btn.count() > 0:
        btn.first.click()
    page.wait_for_timeout(300)


def modal_text(page):
    loc = page.locator("div.fixed")
    return loc.first.inner_text() if loc.count() else ""


def clock_texts(page):
    return page.evaluate("() => [...document.querySelectorAll('main .font-mono.text-xl')].map((e) => e.textContent)")


def selected(loc):
    return "border-accent" in (loc.get_attribute("class") or "")


def play_seq(page, seq):
    """Joue une séquence UCI en 2 joueurs local (tap), avec une reprise par coup si le tap est perdu."""
    for i, u in enumerate(seq):
        tap_move(page, u[:2], u[2:4], pause=70)
        if plies(page) < i + 1:
            page.wait_for_timeout(250)
            tap_move(page, u[:2], u[2:4], pause=220)
        if plies(page) < i + 1:
            return i
    return len(seq)


def run_clock(page, ms):
    """Fait tirer la pendule de l'app comme si `ms` s'étaient écoulées. `page.clock.install()` doit
    avoir été appelé AVANT le lancement de la partie : un `setInterval` créé avant l'installation
    reste un vrai minuteur que l'horloge simulée ne pilote pas."""
    page.clock.run_for(ms)
    page.wait_for_timeout(300)


def suite(p):
    browser = p.chromium.launch(headless=True)

    # ---------- CP-1, Blancs : flèches avant tout coup ----------
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    goto_play(page)
    setup(page, bot="Noa", color="Blancs", tc="Illimité")
    for a in ARROWS:
        tap_button(page, a)
    alive = page_alive(page)
    check("[cp1-blancs] page intacte après ◀ ⏮ ▶ ⏭ sans coup", alive)
    check("[cp1-blancs] flèches désactivées sans coup", alive and arrows_disabled(page))
    shot(page, "play_cp1_blancs")
    if alive:
        tap_move(page, "e2", "e4")
    check("[cp1-blancs] un coup est accepté ensuite", alive and wait_plies(page, 1, 3000))
    ctx.close()

    # ---------- CP-1, Noirs : ◀ pendant l'attente du premier coup du bot ----------
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    goto_play(page)
    setup(page, bot="Noa", color="Noirs", tc="Illimité")
    tap_button(page, "◀")
    alive = page_alive(page)
    check("[cp1-noirs] page intacte après ◀ avant le premier coup du bot", alive)
    check("[cp1-noirs] le bot joue son premier coup", alive and wait_plies(page, 1, 15000))
    check("[cp1-noirs] flèches actives dès qu'il y a un coup", alive and page_alive(page) and not arrows_disabled(page))
    ctx.close()

    # ---------- Course : abandon pendant la réflexion de Maximus (partie classée, 3 demi-coups) ----------
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    goto_play(page)
    setup(page, bot="Maximus", color="Blancs", tc="Illimité")
    tap_move(page, "e2", "e4")
    wait_plies(page, 2, 15000)
    tap_move(page, "d2", "d4", pause=80)
    resign(page)
    ck.appears("[course] modale d'abandon", page, "text=Les Noirs gagnent", timeout=5000)
    n_modal = plies(page)
    check("[course] abandon pendant la réflexion (3 demi-coups à la modale)", n_modal == 3, f"({n_modal})")
    page.wait_for_timeout(5000)
    check("[course] aucun coup du bot après l'abandon (5 s)", plies(page) == n_modal, f"({plies(page)})")
    db = page.evaluate(IDB)
    last = db["games"][-1] if db["games"] else None
    pgn_tail = (last or {}).get("pgn", "").rstrip()[-30:]
    check("[course] PGN archivé fidèle au board (2. d4 0-1)", last is not None and pgn_tail.endswith("2. d4 0-1"), f"({pgn_tail!r})")
    check("[perf] aucun worker Stockfish après la fin", len(page.workers) == 0, f"({len(page.workers)})")
    shot(page, "play_course_abandon")

    # ---------- Course : abandon à 1 demi-coup (annulé) puis relance immédiate avec les Noirs ----------
    page.locator("div.fixed button", has_text="Nouvelle partie").click()
    ck.appears("[relance] configuration", page, "text=Adversaire", timeout=5000)
    page.get_by_role("button", name="Jouer", exact=True).click()
    ck.appears("[relance] partie 2 lancée", page, "[data-square='e2']", timeout=10000)
    tap_move(page, "e2", "e4", pause=80)
    resign(page, "Oui, annuler")
    page.locator("div.fixed button", has_text="Nouvelle partie").click()
    page.locator("main button", has_text="Noirs").first.click()
    page.get_by_role("button", name="Jouer", exact=True).click()
    ck.appears("[relance] partie 3 lancée (Noirs)", page, "[data-square='e2']", timeout=10000)
    check("[relance] le bot joue son premier coup avec les Blancs", wait_plies(page, 1, 12000), f"({plies(page)})")
    ctx.close()

    # ---------- Une seule sauvegarde par partie (PLAY-9, StrictMode en dev) ----------
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    goto_play(page)
    setup(page, bot="Noa", color="Blancs", tc="Illimité")
    tap_move(page, "e2", "e4")
    wait_plies(page, 2, 15000)
    resign(page)
    ck.appears("[sauvegarde] modale de fin", page, "text=Les Noirs gagnent", timeout=10000)
    page.wait_for_timeout(800)
    db = page.evaluate(IDB)
    rating = next((r for r in db["ratings"] if r["key"] == "unlimited"), None)
    check("[sauvegarde] une seule ligne games", len(db["games"]) == 1, f"({len(db['games'])})")
    check("[sauvegarde] ratings.unlimited.games == 1", rating is not None and rating["games"] == 1, f"({rating})")
    check("[sauvegarde] playerRatingAfter = Elo enregistré", bool(db["games"]) and rating is not None and db["games"][0].get("playerRatingAfter") == rating["value"])
    check("[sauvegarde] delta de classement dans la modale", "Classement" in modal_text(page))
    ctx.close()

    # ---------- Abandon au coup 0 : partie annulée, ni Elo ni archive ----------
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    goto_play(page)
    setup(page, bot="Noa", color="Blancs", tc="10 min")
    page.locator("main button", has_text="🏳").first.click()
    page.wait_for_timeout(300)
    check("[coup0] feuille « Annuler la partie ? »", page.locator("text=Annuler la partie").count() > 0)
    shot(page, "play_coup0_feuille")
    btn = page.get_by_role("button", name="Oui, annuler", exact=True)
    if btn.count():
        btn.first.click()
    ck.appears("[coup0] modale « Partie annulée »", page, "text=Partie annulée", timeout=5000)
    body = modal_text(page)
    check("[coup0] ni classement ni bilan dans la modale", "Classement" not in body and "Bilan" not in body, f"({body[:80]!r})")
    db = page.evaluate(IDB)
    check("[coup0] aucune partie archivée", len(db["games"]) == 0, f"({len(db['games'])})")
    check("[coup0] aucun Elo touché", not any(r["key"] == "rapid" for r in db["ratings"]), f"({db['ratings']})")
    shot(page, "play_coup0_annulee")
    page.locator("div.fixed button", has_text="Nouvelle partie").click()
    ck.appears("[coup0] retour à la configuration", page, "text=Adversaire", timeout=5000)

    # ---------- Confirmation refusée : la partie continue ----------
    page.get_by_role("button", name="Jouer", exact=True).click()
    ck.appears("[continuer] partie lancée", page, "[data-square='e2']", timeout=10000)
    page.locator("main button", has_text="🏳").first.click()
    page.wait_for_timeout(300)
    cont = page.get_by_role("button", name="Continuer la partie", exact=True)
    check("[continuer] bouton « Continuer la partie »", cont.count() > 0)
    if cont.count():
        cont.first.click()
        page.wait_for_timeout(300)
    check("[continuer] aucune fin de partie", page.locator("div.fixed").count() == 0)
    tap_move(page, "e2", "e4")
    check("[continuer] la partie continue (coup accepté)", wait_plies(page, 1, 3000))
    ctx.close()

    # ---------- Drapeau sous deux demi-coups : annulé, aucun coup ne tombe ensuite ----------
    # Maximus (Blancs) joue son premier coup, puis le joueur (Noirs) laisse tomber son drapeau sans
    # répondre. La recherche du bot est en temps réel : on ne peut pas faire tomber SON drapeau
    # pendant sa réflexion avec l'horloge simulée ; le jeton qui l'en empêche est prouvé par [course].
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    goto_play(page)
    page.clock.install()  # avant le lancement : la pendule doit naître sous l'horloge simulée
    setup(page, bot="Maximus", color="Noirs", tc="1 min")
    run_clock(page, 122_000)  # le coup du bot tombe tôt, puis la pendule noire s'épuise
    ck.appears("[drapeau0] fin de partie", page, "div.fixed", timeout=10000)
    n_modal = plies(page)
    body = modal_text(page)
    check("[drapeau0] partie annulée (moins de deux demi-coups)", "Partie annulée" in body, f"({body[:80]!r})")
    page.wait_for_timeout(2500)  # une recherche réelle encore en vol se termine
    page.clock.run_for(3_000)  # une latence artificielle (minuteur simulé) expire
    page.wait_for_timeout(300)
    check("[drapeau0] aucun coup appliqué après la chute du drapeau", plies(page) == n_modal and n_modal <= 1, f"({n_modal} -> {plies(page)})")
    db = page.evaluate(IDB)
    check("[drapeau0] ni archive ni Elo", len(db["games"]) == 0 and not any(r["key"] == "bullet" for r in db["ratings"]), f"({len(db['games'])}, {db['ratings']})")
    shot(page, "play_drapeau0")
    ctx.close()

    # ---------- Drapeau contre un roi seul : nulle ----------
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    goto_play(page)
    page.clock.install()
    setup(page, mode="local", tc="1 min")
    played = play_seq(page, FLAG_SEQ)
    check("[drapeau] 32 demi-coups joués", played == len(FLAG_SEQ), f"({played})")
    # Roi noir seul, trait aux Blancs : on laisse tomber le drapeau blanc.
    run_clock(page, 61_000)
    ck.appears("[drapeau] fin de partie au temps", page, "div.fixed", timeout=10000)
    body = modal_text(page)
    check("[drapeau] nulle par matériel insuffisant", "Nulle" in body and "matériel insuffisant" in body, f"({body[:80]!r})")
    db = page.evaluate(IDB)
    last = db["games"][-1] if db["games"] else None
    check("[drapeau] result 1/2-1/2 en base", last is not None and last["result"] == "1/2-1/2", f"({(last or {}).get('result')}, {(last or {}).get('termination')})")
    shot(page, "play_drapeau_nulle")
    ctx.close()

    # ---------- Partie et configuration restaurées (PLAY-4), coup courant jouable (CP-3) ----------
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    goto_play(page)
    setup(page, bot="Noa", color="Blancs", tc="10 min")
    tap_move(page, "e2", "e4")
    wait_plies(page, 2, 15000)
    page.wait_for_timeout(1500)  # la pendule blanche descend sous 10:00
    page.locator("nav a", has_text="Archive").last.click()
    page.wait_for_timeout(800)
    page.locator("nav a", has_text="Jouer").last.click()
    page.wait_for_timeout(1000)
    restored = page.locator("[data-square='e2']").count() == 1 and page.locator("text=Adversaire").count() == 0
    check("[restauration] partie en cours affichée (pas la configuration)", restored)
    check("[restauration] 2 demi-coups restaurés", plies(page) == 2, f"({plies(page)})")
    clocks = clock_texts(page)
    check("[restauration] pendules conservées (blanche < 10:00)", len(clocks) == 2 and clocks[1] != "10:00", f"({clocks})")
    shot(page, "play_restauree")
    if restored:
        tap_move(page, "d2", "d4")
    check("[restauration] coup accepté après restauration", restored and wait_plies(page, 3, 3000))
    check("[restauration] le bot répond", restored and wait_plies(page, 4, 15000))
    # CP-3 : taper le coup courant dans la liste revient au direct, le board reste jouable.
    if restored:
        page.locator("main [data-current='true']").first.click()
        page.wait_for_timeout(200)
        tap_move(page, "b1", "c3")
    check("[cp3] coup accepté après un tap sur le coup courant", restored and wait_plies(page, 5, 3000), f"({plies(page)})")
    if restored:
        wait_plies(page, 6, 15000)
    page.reload()
    page.wait_for_timeout(1500)
    check("[restauration] partie restaurée après rechargement", plies(page) == 6, f"({plies(page)})")
    if page.locator("main button", has_text="🏳").count():
        resign(page)
        ck.appears("[restauration] fin de partie", page, "text=Les Noirs gagnent", timeout=10000)
        page.locator("div.fixed button", has_text="Nouvelle partie").click()
    ck.appears("[config] configuration après la partie", page, "text=Adversaire", timeout=5000)
    page.reload()
    ck.appears("[config] configuration après rechargement", page, "text=Adversaire", timeout=10000)
    check("[config] bot, couleur et cadence mémorisés après rechargement",
          selected(page.locator("main button", has_text="Noa").first)
          and selected(page.locator("main button", has_text="Blancs").first)
          and selected(page.get_by_role("button", name="10 min", exact=True)))
    check("[restauration] plus de partie en cours après la fin", page.locator("[data-square='e2']").count() == 0)
    shot(page, "play_config_memorisee")
    ctx.close()

    # ---------- Restauration en mode entraîneur ----------
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    goto_play(page)
    setup(page, mode="coach", bot="Noa", color="Blancs")
    tap_move(page, "e2", "e4")
    wait_plies(page, 2, 20000)
    page.locator("nav a", has_text="Archive").last.click()
    page.wait_for_timeout(800)
    page.locator("nav a", has_text="Jouer").last.click()
    page.wait_for_timeout(1000)
    check("[coach] partie restaurée (barre d'éval, board, 2 demi-coups)",
          page.locator("main .bg-neutral-800").count() >= 1 and page.locator("[data-square='e2']").count() == 1 and plies(page) == 2,
          f"({plies(page)})")
    check("[coach] toujours classée après restauration", page.locator("text=non classée").count() == 0)
    check("[coach] actions du coach disponibles", page.locator("main button", has_text="Indication").count() == 1)
    ctx.close()
    browser.close()


ck.run(suite)
