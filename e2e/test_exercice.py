"""E2E « Exercice commun » (lots 7 et 8 de docs/ux-refonte.md) : en-tête, scène et zone de
décision partagés par la séance d'Apprendre, la révision espacée, les parties contre Stockfish
(PositionGame) et les lignes des cours, aux trois formats de référence (393x660 PWA avec zones
sûres émulées, 393x852, 1440x900). Sur desktop, la zone est à droite de l'échiquier (deux colonnes).

Pour une séance Tactiques (mat en 1 servi par une route), Mes erreurs (une faute semée) et la
révision (une faute et un puzzle dus) :
- en-tête sous la zone sûre, progression de la série, croix nommée ;
- échiquier entier et zone de décision visibles sans défiler, au-dessus de la zone sûre basse ;
- échiquier immobile au pixel près : en jeu, pendant la vérification Stockfish, au verdict,
  après Réessayer, après l'aller-retour vers l'analyse ;
- verdict « ✓ Réussi » ou « ✗ À revoir » avec une explication non coupée, action principale
  Réessayer après un échec et Suivant après une réussite, cibles de 44 px ;
- « Pourquoi ? » sur une faute, qui ouvre la réfutation ;
- Réessayer sans nouvelle écriture en base (ratings, learnSessions, puzzleAttempts, mistakes) ;
- Analyser puis retour : même item, même verdict, même explication, même échéance.

Pour une partie contre Stockfish (finale « Mat roi + dame ») :
- objectif dans la zone, adversaire dans la bande au-dessus, échiquier immobile au coup, à la
  réponse de Stockfish, au verdict et après Rejouer ;
- reprise après rechargement depuis `chess-local-position-game-v1` ;
- abandon : issue neutre « ◐ Objectif manqué », explication, Rejouer en principal, une seule
  ligne `endgame-play`, et Rejouer sans aucune écriture ;
- Quitter (✕) vers la liste des finales ; changement d'activité : une attaque entamée puis
  remplacée par une finale est notée abandonnée une fois (`recordReplaced`).

Pour une ligne de cours (« Le mat des deux tours », étape 2) : consigne dans la zone, coup juste
hors méthode au ton neutre, Solution au ton réussi, échiquier immobile, texte jamais coupé.

Usage : npm run test:e2e -- --suite exercice
"""
import json
import os

import chess

from helpers import BASE, SHOTS, Checker, click_square as sq, desktop_context, mobile_context, open_learn_session, open_mistakes_session, overflow_x

ck = Checker("exercice")
check = ck.check

SAFE_TOP, SAFE_BOTTOM = 59, 34
DAY = 86_400_000

# Mat en 1 portant tous les thèmes : toute séance Tactiques le sert. Amorce ...Nc3, puis Ra8#.
MATE_FEN = "6k1/5ppp/8/8/4n3/8/5PPP/R5K1 b - - 0 1"
THEMES = ("fork pin skewer discoveredAttack mateIn1 mateIn2 mateIn3 backRankMate hangingPiece sacrifice deflection attraction "
          "promotion trappedPiece intermezzo defensiveMove rookEndgame pawnEndgame zugzwang exposedKing discoveredCheck "
          "advancedPawn kingsideAttack quietMove")
PUZZLES = json.dumps([["L10", MATE_FEN, "e4c3 a1a8", 1000, THEMES]])

# Faute semée : ...h3 au lieu de Dxd8#. Le meilleur coup conclut sans moteur ; Rf1 est jugé par
# Stockfish (perte de la dame) : « À revoir ».
MISTAKE_FEN = "3q2k1/5ppp/8/8/8/8/5PPP/3Q2K1 w - - 0 1"

TABLES = sorted(["games", "ratings", "puzzleAttempts", "rushScores", "mistakes", "learnSessions", "reviews"])
OPEN_DB = """
() => new Promise((res, rej) => {
  const r = indexedDB.open('chess-local')
  r.onsuccess = () => {
    const db = r.result
    if (JSON.stringify(Array.from(db.objectStoreNames).sort()) !== JSON.stringify(TABLES)) { db.close(); rej(new Error('schéma absent')); return }
    res(db)
  }
  r.onerror = () => rej(r.error)
})
""".replace("TABLES", json.dumps(TABLES))

# Instantané des tables qu'un verdict peut écrire : un réessai ne doit rien y changer.
SNAPSHOT = "async () => {" f"  const db = await ({OPEN_DB})()" """
  const all = (t) => new Promise((res, rej) => { const q = db.transaction(t).objectStore(t).getAll(); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error) })
  const out = {}
  for (const t of ['ratings', 'learnSessions', 'puzzleAttempts', 'mistakes']) out[t] = JSON.stringify(await all(t))
  db.close()
  return out
}"""

GEOM = r"""() => {
  const rect = (el) => { if (!el) return null; const b = el.getBoundingClientRect(); return { top: b.top, bottom: b.bottom, left: b.left, right: b.right, width: b.width, height: b.height } }
  const zone = document.querySelector('[data-exercise-feedback]')
  const lines = (el) => {
    if (!el) return 0
    const r = document.createRange(); r.selectNodeContents(el)
    return new Set([...r.getClientRects()].filter((q) => q.width > 0).map((q) => Math.round(q.top))).size
  }
  const verdict = document.querySelector('[data-exercise-verdict]')
  const reason = document.querySelector('[data-exercise-reason]')
  const buttons = zone ? [...zone.querySelectorAll('button')] : []
  const primary = zone?.querySelector('.ui-cta')
  return {
    board: rect(document.querySelector('[data-exercise-board]')),
    header: rect(document.querySelector('[data-exercise-header]')),
    zone: rect(zone), kind: zone?.dataset.exerciseFeedback ?? null,
    verdict: verdict?.textContent.trim() ?? null, verdictLines: lines(verdict),
    reason: reason?.textContent.trim() ?? null,
    reasonClipped: reason ? reason.scrollHeight > reason.clientHeight + 1 : false,
    primary: primary?.textContent.trim() ?? null,
    labels: buttons.map((b) => b.textContent.trim()),
    small: buttons.filter((b) => { const q = b.getBoundingClientRect(); return q.width < 44 || q.height < 44 }).map((b) => b.textContent.trim()),
    zoneOverflow: zone ? zone.scrollHeight > zone.clientHeight + 1 || [...zone.querySelectorAll('[data-exercise-actions]')].some((r) => r.scrollWidth > r.clientWidth + 1) : true,
    // Libellé plus large que son bouton (le pseudo-élément qui agrandit la cible ne compte pas).
    clippedLabels: zone ? [...zone.querySelectorAll('button')].filter((b) => { const r = document.createRange(); r.selectNodeContents(b); return r.getBoundingClientRect().width > b.getBoundingClientRect().width + 1 }).map((b) => b.textContent.trim()) : [],
    title: document.querySelector('[data-exercise-header] h1')?.textContent ?? null,
    progress: document.querySelector('[data-exercise-header] [role=progressbar]')?.getAttribute('aria-valuenow') ?? null,
    note: document.querySelector('[data-exercise-note]')?.textContent.trim() ?? null,
    vh: innerHeight, vw: innerWidth,
  }
}"""


def formats(p, browser):
    def m660():
        return mobile_context(p, browser, ck, standalone=True, viewport={"width": 393, "height": 660}, service_workers="block"), True

    def m852():
        return mobile_context(p, browser, ck, standalone=True, service_workers="block"), False

    def desk():
        return desktop_context(browser, ck, service_workers="block"), False

    return [("393x660", m660), ("393x852", m852), ("1440x900", desk)]


def new_page(ctx, safe):
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=PUZZLES))
    page = ctx.new_page()
    if safe:
        page.context.new_cdp_session(page).send("Emulation.setSafeAreaInsetsOverride", {"insets": {"top": SAFE_TOP, "bottom": SAFE_BOTTOM}})
    return page


def wait_schema(page, tries=60):
    for _ in range(tries):
        tables = page.evaluate("""() => new Promise((res) => {
          indexedDB.databases().then((list) => {
            if (!list.some((d) => d.name === 'chess-local')) return res(0)
            const r = indexedDB.open('chess-local')
            r.onsuccess = () => { const t = Array.from(r.result.objectStoreNames).sort(); r.result.close(); res(t) }
            r.onerror = () => res(-1)
          })
        })""")
        if tables == TABLES:
            return True
        page.wait_for_timeout(250)
    return False


def seed(page, data):
    page.evaluate("async (data) => {" f"  const db = await ({OPEN_DB})()" """
      const tx = db.transaction(Object.keys(data), 'readwrite')
      for (const [t, rows] of Object.entries(data)) for (const r of rows) tx.objectStore(t).put(r)
      await new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = () => rej(tx.error) })
      db.close()
    }""", data)


def mistake_row(now, days):
    return {"id": 1, "date": now - days * DAY, "gameLabel": "Partie test", "fenBefore": MISTAKE_FEN, "playedSan": "h3",
            "bestUci": "d1d8", "cls": "blunder", "attempts": 0, "solved": 0}


def geom(page):
    return page.evaluate(GEOM)


def settle(page, ms=900):
    # Fin du flash du coup faux (600 ms) et d'une transition éventuelle, puis deux images.
    page.wait_for_timeout(ms)
    page.evaluate("() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))")


def layout_checks(tag, page, g, safe):
    if not check(f"{tag} : scène trouvée", g["board"] is not None and g["zone"] is not None and g["header"] is not None):
        return False
    top = SAFE_TOP if safe else 0
    bottom = g["vh"] - (SAFE_BOTTOM if safe else 0)
    check(f"{tag} : en-tête sous la zone sûre", g["header"]["top"] >= top, f"({g['header']['top']} < {top})")
    check(f"{tag} : échiquier carré", abs(g["board"]["width"] - g["board"]["height"]) <= 1, f"({g['board']['width']}x{g['board']['height']})")
    check(f"{tag} : zone de décision visible sans défiler", g["zone"]["bottom"] <= bottom + 0.5, f"(bas {g['zone']['bottom']:.1f} > {bottom})")
    if g["vw"] >= 1024:
        # Deux colonnes : zone à droite de l'échiquier, en haut de sa colonne, échiquier entier visible.
        check(f"{tag} : zone à droite de l'échiquier", g["zone"]["left"] >= g["board"]["right"] + 16, f"(zone {g['zone']['left']:.1f}, échiquier jusqu'à {g['board']['right']:.1f})")
        check(f"{tag} : zone en haut de la colonne de droite", g["zone"]["top"] <= g["board"]["top"] + 0.5 and g["board"]["top"] - g["zone"]["top"] <= 40,
              f"(zone {g['zone']['top']:.1f}, échiquier {g['board']['top']:.1f})")
        check(f"{tag} : échiquier entier visible", g["board"]["bottom"] <= g["vh"] + 0.5, f"({g['board']['bottom']:.1f})")
        check(f"{tag} : échiquier d'au moins 600 px", g["board"]["width"] >= 600, f"({g['board']['width']})")
    else:
        check(f"{tag} : zone alignée sur l'échiquier", abs(g["zone"]["left"] - g["board"]["left"]) < 0.5 and abs(g["zone"]["right"] - g["board"]["right"]) < 0.5,
              f"(zone {g['zone']['left']:.1f}-{g['zone']['right']:.1f}, échiquier {g['board']['left']:.1f}-{g['board']['right']:.1f})")
    check(f"{tag} : contenu de la zone non coupé", not g["zoneOverflow"] and not g["clippedLabels"], f"({g['clippedLabels']})")
    check(f"{tag} : aucun débordement horizontal", overflow_x(page) == 0)
    if g["vw"] <= 400 and not safe:
        check(f"{tag} : échiquier pleine largeur (marges de 6 px)", abs(g["board"]["width"] - (g["vw"] - 12)) <= 1, f"({g['board']['width']})")
    return True


def verdict_checks(tag, g, ok):
    if ok:
        check(f"{tag} : verdict « ✓ Réussi »", g["kind"] == "success" and g["verdict"] == "✓ Réussi", f"({g['kind']}, {g['verdict']!r})")
        check(f"{tag} : action principale Suivant", g["primary"] == "Suivant", f"({g['primary']!r})")
    else:
        check(f"{tag} : verdict « ✗ À revoir »", g["kind"] == "review" and g["verdict"] == "✗ À revoir", f"({g['kind']}, {g['verdict']!r})")
        check(f"{tag} : action principale Réessayer", g["primary"] == "Réessayer", f"({g['primary']!r})")
    check(f"{tag} : verdict sur une ligne", g["verdictLines"] == 1, f"({g['verdictLines']})")
    check(f"{tag} : explication présente et non coupée", bool(g["reason"]) and len(g["reason"]) > 10 and not g["reasonClipped"], f"({g['reason']!r})")
    check(f"{tag} : Analyser et Suivant/Réessayer présents", any("Analyser" in x for x in g["labels"]) and any("Suivant" in x for x in g["labels"]) and any("Réessayer" in x for x in g["labels"]), f"({g['labels']})")
    check(f"{tag} : cibles de 44 px", not g["small"], f"({g['small']})")


def game_verdict_checks(tag, g, kind, label, primary):
    """Verdict d'une partie : ton, symbole et titre de l'écran, explication, action principale."""
    check(f"{tag} : ton « {kind} »", g["kind"] == kind, f"({g['kind']})")
    check(f"{tag} : verdict « {label} »", g["verdict"] == label, f"({g['verdict']!r})")
    check(f"{tag} : verdict sur une ligne", g["verdictLines"] == 1, f"({g['verdictLines']})")
    check(f"{tag} : explication présente et non coupée", bool(g["reason"]) and len(g["reason"]) > 5 and not g["reasonClipped"], f"({g['reason']!r})")
    check(f"{tag} : action principale « {primary} »", g["primary"] == primary, f"({g['primary']!r})")
    check(f"{tag} : Analyser présent", any("Analyser" in x for x in g["labels"]), f"({g['labels']})")
    check(f"{tag} : cibles de 44 px", not g["small"], f"({g['small']})")


def same_board(tag, a, b):
    check(f"{tag} : échiquier immobile", a is not None and b is not None and a == b, f"({a} -> {b})")


def click_button(page, label):
    page.locator("[data-exercise-feedback] button", has_text=label).first.click()


# ---------------------------------------------------------------- séance Tactiques
def tactic(page, fmt, safe):
    tag = f"[{fmt} tactique]"
    open_learn_session(page, "tactic")
    if not ck.appears(f"{tag} leçon", page, "button:has-text(\"C'est parti\")", timeout=20000):
        return
    page.get_by_role("button", name="C'est parti").click()
    if not ck.appears(f"{tag} consigne", page, "[data-exercise-feedback=prompt]"):
        return
    settle(page, 1300)  # amorce ...Nc3 jouée
    g0 = geom(page)
    if not layout_checks(f"{tag} en jeu", page, g0, safe):
        return
    check(f"{tag} : consigne avec le trait", "trait aux Blancs" in page.locator("[data-exercise-prompt]").inner_text())
    check(f"{tag} : titre et position « 1/1 »", "Tactiques" in (g0["title"] or "") and "1/1" in (g0["title"] or ""), f"({g0['title']!r})")
    check(f"{tag} : progression à 0 avant le verdict", g0["progress"] == "0", f"({g0['progress']})")
    page.screenshot(path=f"{SHOTS}/exercice_tactique_jeu_{fmt}.png")

    sq(page, "g1"); page.wait_for_timeout(150); sq(page, "f1")
    if not ck.appears(f"{tag} verdict après le coup faux", page, "[data-exercise-feedback=review]", timeout=8000):
        return
    settle(page)
    g1 = geom(page)
    same_board(f"{tag} verdict À revoir", g0["board"], g1["board"])
    check(f"{tag} : zone de même hauteur", g0["zone"]["height"] == g1["zone"]["height"], f"({g0['zone']['height']} -> {g1['zone']['height']})")
    layout_checks(f"{tag} À revoir", page, g1, safe)
    verdict_checks(f"{tag} À revoir", g1, ok=False)
    check(f"{tag} : variation de classement affichée", (g1["note"] or "").startswith("Classement -"), f"({g1['note']!r})")
    check(f"{tag} : progression à 1 après le verdict", g1["progress"] == "1", f"({g1['progress']})")
    check(f"{tag} : pas de « Pourquoi ? » sur un puzzle", not any("Pourquoi" in x for x in g1["labels"]))
    page.screenshot(path=f"{SHOTS}/exercice_tactique_a_revoir_{fmt}.png")

    before = page.evaluate(SNAPSHOT)
    click_button(page, "Réessayer")
    if not ck.appears(f"{tag} réessai : consigne", page, "[data-exercise-feedback=prompt]"):
        return
    settle(page, 1300)
    same_board(f"{tag} réessai", g0["board"], geom(page)["board"])
    sq(page, "a1"); page.wait_for_timeout(150); sq(page, "a8")
    if not ck.appears(f"{tag} réessai réussi", page, "[data-exercise-feedback=success]", timeout=8000):
        return
    settle(page)
    g2 = geom(page)
    same_board(f"{tag} verdict Réussi", g0["board"], g2["board"])
    verdict_checks(f"{tag} Réussi", g2, ok=True)
    after = page.evaluate(SNAPSHOT)
    changed = [t for t in before if before[t] != after[t]]
    check(f"{tag} : réessai sans nouvelle écriture en base", not changed, f"({changed})")
    check(f"{tag} : réessai sans variation de classement affichée", g2["note"] == g1["note"], f"({g1['note']!r} -> {g2['note']!r})")
    page.screenshot(path=f"{SHOTS}/exercice_tactique_reussi_{fmt}.png")

    click_button(page, "Analyser")
    if ck.appears(f"{tag} analyse ouverte", page, "button:has-text(\"Retour à l'exercice\")", timeout=15000):
        page.locator("button", has_text="Retour à l'exercice").click()
        if ck.appears(f"{tag} séance restaurée", page, "[data-exercise-feedback=success]", timeout=15000):
            settle(page)
            g3 = geom(page)
            same_board(f"{tag} après l'analyse", g0["board"], g3["board"])
            check(f"{tag} : même item, même verdict, même explication", (g3["title"], g3["verdict"], g3["reason"]) == (g2["title"], g2["verdict"], g2["reason"]),
                  f"({g3['title']!r}, {g3['verdict']!r}, {g3['reason']!r})")
    page.locator("[data-exercise-header] button[aria-label='Quitter la séance']").click()
    page.wait_for_timeout(300)


# ---------------------------------------------------------------- finale et ouverture (en jeu)
def endgame_opening(page, fmt, safe):
    tag = f"[{fmt} finale]"
    open_learn_session(page, "endgame")
    if ck.appears(f"{tag} leçon", page, "button:has-text(\"C'est parti\")", timeout=20000):
        page.get_by_role("button", name="C'est parti").click()
        if ck.appears(f"{tag} consigne", page, "[data-exercise-prompt]:has-text('Objectif')"):
            settle(page, 1500)  # barre d'éval renseignée
            g = geom(page)
            layout_checks(f"{tag} en jeu", page, g, safe)
            bar = page.evaluate("() => { const b = document.querySelector('.exercise-above')?.getBoundingClientRect(); return b ? [b.left, b.right, b.bottom] : null }")
            check(f"{tag} : barre d'éval alignée sur l'échiquier, au-dessus", bar is not None and abs(bar[0] - g["board"]["left"]) < 0.5
                  and abs(bar[1] - g["board"]["right"]) < 0.5 and bar[2] <= g["board"]["top"] + 0.5, f"({bar})")
            page.screenshot(path=f"{SHOTS}/exercice_finale_{fmt}.png")
        page.locator("[data-exercise-header] button[aria-label='Quitter la séance']").click()
        page.wait_for_timeout(300)

    tag = f"[{fmt} ouverture]"
    open_learn_session(page, "opening")
    if ck.appears(f"{tag} leçon", page, "button:has-text(\"C'est parti\")", timeout=20000):
        page.get_by_role("button", name="C'est parti").click()
        if ck.appears(f"{tag} consigne", page, "[data-exercise-prompt]:has-text('premiers coups')"):
            settle(page, 600)
            g0 = geom(page)
            layout_checks(f"{tag} en jeu", page, g0, safe)
            # Mauvais coup : la correction s'ajoute à la consigne, dans la zone réservée.
            sq(page, "a2"); page.wait_for_timeout(150); sq(page, "a3")
            if ck.appears(f"{tag} correction affichée", page, "[data-exercise-prompt]:has-text('Pas la ligne')", timeout=5000):
                settle(page, 300)
                g1 = geom(page)
                same_board(f"{tag} correction", g0["board"], g1["board"])
                check(f"{tag} : correction non coupée", not g1["zoneOverflow"])
                page.screenshot(path=f"{SHOTS}/exercice_ouverture_correction_{fmt}.png")
        page.locator("[data-exercise-header] button[aria-label='Quitter la séance']").click()
        page.wait_for_timeout(300)


# ---------------------------------------------------------------- Mes erreurs
def mistakes(page, fmt, safe):
    tag = f"[{fmt} faute]"
    open_mistakes_session(page)
    if not ck.appears(f"{tag} leçon", page, "button:has-text(\"C'est parti\")", timeout=20000):
        return
    page.get_by_role("button", name="C'est parti").click()
    if not ck.appears(f"{tag} consigne", page, "[data-exercise-prompt]:has-text('Trouve mieux')"):
        return
    settle(page, 500)
    g0 = geom(page)
    if not layout_checks(f"{tag} en jeu", page, g0, safe):
        return
    # Coup jugé par Stockfish : la consigne annonce la vérification à la même place.
    sq(page, "g1"); page.wait_for_timeout(150); sq(page, "f1")
    if ck.appears(f"{tag} vérification annoncée dans la zone", page, "[data-exercise-prompt]:has-text('Je vérifie')", timeout=5000):
        same_board(f"{tag} pendant la vérification", g0["board"], geom(page)["board"])
    if not ck.appears(f"{tag} verdict Stockfish", page, "[data-exercise-feedback=review]", timeout=60000):
        return
    settle(page, 300)
    g1 = geom(page)
    same_board(f"{tag} verdict À revoir", g0["board"], g1["board"])
    layout_checks(f"{tag} À revoir", page, g1, safe)
    verdict_checks(f"{tag} À revoir", g1, ok=False)
    check(f"{tag} : « Pourquoi ? » proposé", any(x.endswith("Pourquoi ?") for x in g1["labels"]), f"({g1['labels']})")
    page.screenshot(path=f"{SHOTS}/exercice_faute_a_revoir_{fmt}.png")
    click_button(page, "Pourquoi")
    if ck.appears(f"{tag} réfutation ouverte", page, "[aria-label='Pourquoi ce coup est une faute']", timeout=10000):
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        check(f"{tag} : Échap ferme la réfutation", page.locator("dialog[open][aria-label='Pourquoi ce coup est une faute']").count() == 0)
        ck.appears(f"{tag} réfutation fermée, verdict intact", page, "[data-exercise-feedback=review]", timeout=5000)

    before = page.evaluate(SNAPSHOT)
    click_button(page, "Réessayer")
    if not ck.appears(f"{tag} réessai", page, "[data-exercise-prompt]:has-text('Trouve mieux')"):
        return
    sq(page, "d1"); page.wait_for_timeout(150); sq(page, "d8")
    if not ck.appears(f"{tag} meilleur coup : Réussi", page, "[data-exercise-feedback=success]", timeout=10000):
        return
    settle(page, 300)
    g2 = geom(page)
    same_board(f"{tag} verdict Réussi", g0["board"], g2["board"])
    verdict_checks(f"{tag} Réussi", g2, ok=True)
    check(f"{tag} : explication du meilleur coup", "coup de Stockfish" in (g2["reason"] or ""), f"({g2['reason']!r})")
    after = page.evaluate(SNAPSHOT)
    changed = [t for t in ("ratings", "learnSessions", "puzzleAttempts") if before[t] != after[t]]
    check(f"{tag} : réessai sans nouvelle écriture de résultat", not changed, f"({changed})")
    m0, m1 = json.loads(before["mistakes"])[0], json.loads(after["mistakes"])[0]
    check(f"{tag} : réessai sans tentative de plus", m1["attempts"] == m0["attempts"] == 1, f"({m0['attempts']} -> {m1['attempts']})")
    page.screenshot(path=f"{SHOTS}/exercice_faute_reussi_{fmt}.png")
    page.locator("[data-exercise-header] button[aria-label='Quitter la séance']").click()
    page.wait_for_timeout(300)


# ---------------------------------------------------------------- révision espacée
def revision(page, fmt, safe):
    tag = f"[{fmt} révision]"
    page.goto(f"{BASE}/#/revision")
    if not ck.appears(f"{tag} faute due en premier", page, "[data-review-item=mistake] [data-exercise-prompt]", timeout=20000):
        return
    settle(page, 500)
    g0 = geom(page)
    if not layout_checks(f"{tag} en jeu", page, g0, safe):
        return
    check(f"{tag} : titre « Révision 1/2 »", "Révision" in (g0["title"] or "") and "1/2" in (g0["title"] or ""), f"({g0['title']!r})")
    check(f"{tag} : ligne d'état dans la consigne", "Raté il y a" in page.locator("[data-exercise-prompt]").inner_text())
    sq(page, "g1"); page.wait_for_timeout(150); sq(page, "f1")
    if ck.appears(f"{tag} vérification annoncée dans la zone", page, "[data-exercise-prompt]:has-text('Je vérifie')", timeout=5000):
        same_board(f"{tag} pendant la vérification", g0["board"], geom(page)["board"])
    if not ck.appears(f"{tag} verdict Stockfish", page, "[data-exercise-feedback=review]", timeout=60000):
        return
    settle(page, 300)
    g1 = geom(page)
    same_board(f"{tag} verdict À revoir", g0["board"], g1["board"])
    layout_checks(f"{tag} À revoir", page, g1, safe)
    verdict_checks(f"{tag} À revoir", g1, ok=False)
    check(f"{tag} : échéance « Revient demain »", g1["note"] == "Revient demain", f"({g1['note']!r})")
    check(f"{tag} : « Pourquoi ? » proposé", any("Pourquoi" in x for x in g1["labels"]), f"({g1['labels']})")
    page.screenshot(path=f"{SHOTS}/exercice_revision_a_revoir_{fmt}.png")

    page.wait_for_timeout(500)  # écriture asynchrone du premier verdict (recordReview)
    before = page.evaluate(SNAPSHOT)
    click_button(page, "Réessayer")
    if ck.appears(f"{tag} réessai", page, "[data-exercise-prompt]:has-text('Trouve mieux')"):
        sq(page, "d1"); page.wait_for_timeout(150); sq(page, "d8")
        if ck.appears(f"{tag} réessai réussi", page, "[data-exercise-feedback=success]", timeout=10000):
            settle(page, 300)
            g2 = geom(page)
            same_board(f"{tag} réessai réussi", g0["board"], g2["board"])
            check(f"{tag} : l'échéance du premier essai reste affichée", g2["note"] == "Revient demain", f"({g2['note']!r})")
            # L'écriture du premier verdict est asynchrone : laisser la chaîne se terminer.
            page.wait_for_timeout(500)
            after = page.evaluate(SNAPSHOT)
            changed = [t for t in before if before[t] != after[t]]
            check(f"{tag} : réessai sans nouvelle écriture en base", not changed, f"({changed})")

    click_button(page, "Analyser")
    if ck.appears(f"{tag} analyse ouverte", page, "button:has-text('Retour à la révision')", timeout=15000):
        page.locator("button", has_text="Retour à la révision").click()
        if ck.appears(f"{tag} séance restaurée", page, "[data-review-item=mistake] [data-exercise-feedback=success]", timeout=15000):
            settle(page, 300)
            g3 = geom(page)
            same_board(f"{tag} après l'analyse", g0["board"], g3["board"])
            check(f"{tag} : même item, verdict, explication et échéance", (g3["title"], g3["verdict"], g3["reason"], g3["note"]) == (g2["title"], g2["verdict"], g2["reason"], g2["note"]),
                  f"({g3['title']!r}, {g3['verdict']!r}, {g3['reason']!r}, {g3['note']!r})")

    click_button(page, "Suivant")
    if not ck.appears(f"{tag} puzzle dû", page, "[data-review-item=puzzle] [data-exercise-prompt]", timeout=10000):
        return
    check(f"{tag} : la consigne ne livre pas le thème", "Mat" not in page.locator("[data-exercise-prompt]").inner_text())
    settle(page, 1300)
    p0 = geom(page)
    same_board(f"{tag} même scène d'un item à l'autre", g0["board"], p0["board"])
    sq(page, "a1"); page.wait_for_timeout(150); sq(page, "a8")
    if ck.appears(f"{tag} puzzle réussi", page, "[data-exercise-feedback=success]", timeout=8000):
        settle(page)
        p1 = geom(page)
        same_board(f"{tag} verdict du puzzle", p0["board"], p1["board"])
        verdict_checks(f"{tag} puzzle", p1, ok=True)
        check(f"{tag} : thème dans l'explication après le verdict", "Mat en 1" in (p1["reason"] or ""), f"({p1['reason']!r})")
        check(f"{tag} : échéance du puzzle", p1["note"] == "Revient dans 3 jours", f"({p1['note']!r})")
        page.screenshot(path=f"{SHOTS}/exercice_revision_puzzle_{fmt}.png")


# ---------------------------------------------------------------- partie contre Stockfish (PositionGame)
GAME = "[data-testid=position-game]"
KQ_FEN = "8/8/8/4k3/8/8/3Q4/4K3 w - - 0 1"
STORE_KEY = "chess-local-position-game-v1"
ROWS = "async (domain) => {" f"  const db = await ({OPEN_DB})()" """
  const rows = await new Promise((res, rej) => { const q = db.transaction('learnSessions').objectStore('learnSessions').getAll(); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error) })
  db.close()
  return rows.filter((r) => r.domain === domain)
}"""


def game_attr(page, name):
    return page.evaluate(f"() => document.querySelector('{GAME}')?.getAttribute('data-{name}') ?? null")


def wait_my_turn(page, color, timeout=30000):
    """Trait au joueur, moteur au repos (ou partie finie) : True si atteint."""
    try:
        page.wait_for_function(f"""(c) => {{ const g = document.querySelector('{GAME}')
          return g && (g.dataset.status === 'over' || (g.dataset.fen.split(' ')[1] === c && g.dataset.thinking === '0')) }}""", arg=color, timeout=timeout)
        return True
    except Exception:
        return False


def play_uci(page, uci):
    sq(page, uci[:2]); page.wait_for_timeout(150); sq(page, uci[2:4])


def first_legal(fen):
    return next(iter(chess.Board(fen).legal_moves)).uci()


def position_game(page, fmt, safe):
    tag = f"[{fmt} partie]"
    page.goto(f"{BASE}/#/finales/kq-mate")
    if not ck.appears(f"{tag} partie affichée", page, f"{GAME} [data-exercise-feedback=prompt]", timeout=20000):
        return
    wait_my_turn(page, "w")
    settle(page, 400)
    g0 = geom(page)
    if not layout_checks(f"{tag} en jeu", page, g0, safe):
        return
    check(f"{tag} : titre de la finale, sans compteur hors série", (g0["title"] or "").strip() == "Mat roi + dame" and g0["progress"] is None, f"({g0['title']!r}, {g0['progress']})")
    check(f"{tag} : objectif dans la zone", "Objectif : gagner" in page.locator("[data-exercise-prompt]").inner_text())
    check(f"{tag} : ✕ nommé « Retour »", page.locator("[data-exercise-header] button[aria-label='Retour']").count() == 1)
    above = page.evaluate("() => { const b = document.querySelector('.exercise-above')?.getBoundingClientRect(); return b ? [b.left, b.right, b.bottom] : null }")
    check(f"{tag} : adversaire dans la bande au-dessus de l'échiquier", above is not None and abs(above[0] - g0["board"]["left"]) < 0.5
          and above[2] <= g0["board"]["top"] + 0.5 and "Stockfish 18" in page.locator(".exercise-above").inner_text(), f"({above})")
    labels = page.locator("[data-exercise-feedback=prompt] button").all_inner_texts()
    check(f"{tag} : actions de jeu dans la zone", all(any(n in x for x in labels) for n in ("Abandonner", "Nulle", "Indice", "Annuler", "Recommencer")), f"({labels})")
    page.screenshot(path=f"{SHOTS}/exercice_partie_jeu_{fmt}.png")

    play_uci(page, "d2d3")
    if ck.appears(f"{tag} Stockfish réfléchit", page, f"{GAME}[data-thinking='1']", timeout=5000):
        same_board(f"{tag} pendant la réflexion", g0["board"], geom(page)["board"])
    check(f"{tag} réponse de Stockfish", wait_my_turn(page, "w"))
    settle(page, 300)
    same_board(f"{tag} après la réponse", g0["board"], geom(page)["board"])
    fen = game_attr(page, "fen")
    stored = page.evaluate(f"() => JSON.parse(localStorage.getItem('{STORE_KEY}') || 'null')")
    check(f"{tag} : partie persistée (deux demi-coups)", stored is not None and stored.get("key") == "finale:kq-mate" and len(stored.get("uci", [])) == 2, f"({stored})")

    page.reload()
    if ck.appears(f"{tag} reprise après rechargement", page, f"{GAME}[data-fen='{fen}']", timeout=20000):
        wait_my_turn(page, "w")
        settle(page, 300)
        same_board(f"{tag} après le rechargement", g0["board"], geom(page)["board"])

    before = len(page.evaluate(ROWS, "endgame-play"))
    page.locator("[data-exercise-feedback] button", has_text="Abandonner").click()
    page.locator("[data-testid=resign-confirm]").click()
    if not ck.appears(f"{tag} verdict après l'abandon", page, f"{GAME} [data-exercise-feedback=neutral]", timeout=8000):
        return
    settle(page, 400)
    g1 = geom(page)
    same_board(f"{tag} verdict neutre", g0["board"], g1["board"])
    check(f"{tag} : zone de même hauteur", g0["zone"]["height"] == g1["zone"]["height"], f"({g0['zone']['height']} -> {g1['zone']['height']})")
    layout_checks(f"{tag} abandon", page, g1, safe)
    game_verdict_checks(f"{tag} abandon", g1, "neutral", "◐ Objectif manqué", "Rejouer")
    check(f"{tag} : explication de l'abandon", g1["reason"] == "Tu as abandonné.", f"({g1['reason']!r})")
    check(f"{tag} : « Autre finale » en secondaire", any("Autre finale" in x for x in g1["labels"]), f"({g1['labels']})")
    check(f"{tag} : jugement de l'objectif inchangé (échec)", game_attr(page, "verdict") == "fail" and game_attr(page, "tone") == "neutral")
    page.wait_for_timeout(300)
    after = page.evaluate(ROWS, "endgame-play")
    check(f"{tag} : une ligne endgame-play ratée", len(after) == before + 1 and after[-1]["success"] == 0, f"({before} -> {len(after)})")
    page.screenshot(path=f"{SHOTS}/exercice_partie_abandon_{fmt}.png")

    snap = page.evaluate(SNAPSHOT)
    page.locator("[data-exercise-feedback] .ui-cta", has_text="Rejouer").click()
    if ck.appears(f"{tag} Rejouer : nouvelle partie", page, f"{GAME}[data-status=playing] [data-exercise-feedback=prompt]", timeout=8000):
        settle(page, 300)
        g2 = geom(page)
        same_board(f"{tag} après Rejouer", g0["board"], g2["board"])
        check(f"{tag} : Rejouer repart de la position de départ", game_attr(page, "fen") == KQ_FEN)
        page.wait_for_timeout(300)
        changed = [t for t, v in page.evaluate(SNAPSHOT).items() if snap[t] != v]
        check(f"{tag} : Rejouer sans écriture en base", not changed, f"({changed})")

    page.locator("[data-exercise-header] button[aria-label='Retour']").click()
    ck.appears(f"{tag} Quitter : liste des finales", page, "main h1:has-text('Finales')", timeout=10000)
    check(f"{tag} : Quitter ramène à #/finales", page.evaluate("() => location.hash") == "#/finales", f"({page.evaluate('() => location.hash')})")


def replaced_attempt(page, fmt):
    """Une attaque entamée puis remplacée par une finale : notée abandonnée une seule fois."""
    tag = f"[{fmt} changement d'activité]"
    attacks = json.load(open(os.path.join(os.path.dirname(__file__), "..", "src", "data", "attacks.json")))
    pos = attacks[0]
    page.goto(f"{BASE}/#/attaque/{pos['id']}")
    if not ck.appears(f"{tag} attaque affichée", page, f"{GAME} [data-exercise-feedback=prompt]", timeout=20000):
        return
    color = pos["fen"].split(" ")[1]
    wait_my_turn(page, color)
    before = len(page.evaluate(ROWS, "attack"))
    play_uci(page, first_legal(pos["fen"]))
    check(f"{tag} réponse du défenseur", wait_my_turn(page, color, 45000))
    page.goto(f"{BASE}/#/finales/kq-mate")
    if not ck.appears(f"{tag} finale affichée", page, f"{GAME} [data-exercise-feedback=prompt]", timeout=20000):
        return
    check(f"{tag} : un simple coup d'œil ne note rien", len(page.evaluate(ROWS, "attack")) == before)
    wait_my_turn(page, "w")
    play_uci(page, "d2d3")
    page.wait_for_timeout(800)
    rows = page.evaluate(ROWS, "attack")
    check(f"{tag} : attaque notée abandonnée une fois", len(rows) == before + 1 and rows[-1].get("outcome") == "abandon" and rows[-1].get("itemId") == pos["id"],
          f"({before} -> {len(rows)}, {rows[-1] if rows else None})")
    wait_my_turn(page, "w")
    play_uci(page, first_legal(game_attr(page, "fen")))
    page.wait_for_timeout(800)
    check(f"{tag} : pas de seconde note", len(page.evaluate(ROWS, "attack")) == before + 1)


# ---------------------------------------------------------------- ligne d'un cours
def course_line(page, fmt, safe):
    tag = f"[{fmt} cours]"
    page.goto(f"{BASE}/#/apprendre/finales/mat-deux-tours?etape=2")
    if not ck.appears(f"{tag} ligne affichée", page, "[data-exercise-feedback=prompt] [data-testid=line-feedback]", timeout=20000):
        return
    settle(page, 400)
    # Position dans le contenu du défileur : un clic de Playwright peut faire défiler la leçon.
    r = lambda sel: page.evaluate(f"""() => {{ const e = document.querySelector("{sel}"); if (!e) return null; const b = e.getBoundingClientRect()
      let s = e.parentElement; while (s && !/(auto|scroll)/.test(getComputedStyle(s).overflowY)) s = s.parentElement
      return [b.left, b.top + (s ? s.scrollTop : 0), b.width, b.height] }}""")  # noqa: E731
    b0 = r("[data-board]")
    head = r("[data-exercise-header]")
    check(f"{tag} : en-tête sous la zone sûre", head is not None and head[1] >= (SAFE_TOP if safe else 0), f"({head})")
    check(f"{tag} : compteur « 2/3 » dans le titre", page.locator("[data-exercise-header] h1 [data-testid=lesson-step]").inner_text() == "2/3")
    check(f"{tag} : aucun débordement horizontal", overflow_x(page) == 0)
    # Coup juste mais hors méthode (toute la position « garde » le gain) : ton neutre.
    play_uci(page, "e1e2")
    if ck.appears(f"{tag} coup hors méthode : ton neutre", page, "[data-exercise-feedback=neutral] [data-exercise-verdict]", timeout=5000):
        check(f"{tag} : verdict neutre « ◐ ♔e2 »", page.locator("[data-exercise-verdict]").inner_text().strip() == "◐ ♔e2", f"({page.locator('[data-exercise-verdict]').inner_text()!r})")
        same_board(f"{tag} coup neutre", b0, r("[data-board]"))
        page.screenshot(path=f"{SHOTS}/exercice_cours_neutre_{fmt}.png")
    page.wait_for_timeout(900)  # coup repris
    page.get_by_role("button", name="💡 Solution").click()
    if ck.appears(f"{tag} Solution : ton réussi", page, "[data-exercise-feedback=success] [data-exercise-verdict]", timeout=5000):
        settle(page, 900)  # réponse adverse
        same_board(f"{tag} coup trouvé", b0, r("[data-board]"))
        clipped = page.evaluate("() => { const e = document.querySelector('[data-exercise-reason]'); return e ? e.scrollHeight > e.clientHeight + 1 : true }")
        check(f"{tag} : explication jamais coupée", not clipped)
        check(f"{tag} : réponse adverse dans la zone", "répondent" in page.locator("[data-exercise-feedback=success]").inner_text())
        page.screenshot(path=f"{SHOTS}/exercice_cours_reussi_{fmt}.png")
    if fmt == "1440x900":
        zone = r("[data-exercise-feedback]")
        check(f"{tag} : desktop, retour à droite de l'échiquier", zone is not None and zone[0] >= b0[0] + b0[2] + 16, f"({zone}, {b0})")


def suite(p):
    browser = p.chromium.launch(headless=True)
    for fmt, make in formats(p, browser):
        ctx, safe = make()
        page = new_page(ctx, safe)
        page.goto(f"{BASE}/#/apprendre")
        if not check(f"[{fmt}] schéma créé", wait_schema(page)):
            ctx.close()
            continue
        now = page.evaluate("() => Date.now()")
        seed(page, {"mistakes": [mistake_row(now, 0)]})
        tactic(page, fmt, safe)
        endgame_opening(page, fmt, safe)
        mistakes(page, fmt, safe)
        ctx.close()

        ctx, safe = make()
        page = new_page(ctx, safe)
        page.goto(f"{BASE}/#/")
        if check(f"[{fmt}] schéma créé (révision)", wait_schema(page)):
            now = page.evaluate("() => Date.now()")
            seed(page, {
                "mistakes": [mistake_row(now, 10)],
                "puzzleAttempts": [{"id": 1, "puzzleId": "L10", "date": now - 5 * DAY, "success": False, "puzzleRating": 1000, "ratingAfter": 900}],
            })
            revision(page, fmt, safe)
        ctx.close()

        ctx, safe = make()
        page = new_page(ctx, safe)
        page.goto(f"{BASE}/#/finales")
        if check(f"[{fmt}] schéma créé (partie)", wait_schema(page)):
            position_game(page, fmt, safe)
            course_line(page, fmt, safe)
            if fmt == "393x852":
                replaced_attempt(page, fmt)
        ctx.close()
    browser.close()


ck.run(suite)
