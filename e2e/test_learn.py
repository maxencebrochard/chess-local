"""E2E « Apprendre » : page, séances par domaine, exercices, Elo, mes erreurs, sauvegarde.

Usage : npm run test:e2e -- --suite learn
"""
import json
import re

from helpers import BASE, SHOTS, Checker, click_square as sq, mobile_context, overflow_x

# Bouton du domaine Finales (et pas la carte « Cours de finales »).
FINALES = re.compile(r"^\W*Finales$")

PGN = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#"
ck = Checker("learn")
check = ck.check

# Témoin posé avant le code de l'app : main.tsx doit demander le stockage persistant au
# démarrage, sinon iOS peut purger IndexedDB (parties, classements, progrès).
SPY_PERSIST = """
if (navigator.storage && navigator.storage.persist) {
  const original = navigator.storage.persist.bind(navigator.storage)
  navigator.storage.persist = () => { window.__persistRequested = true; return original() }
}
"""


# LEARN-10 : `puzzles.json` remplacé par un mat en 1 portant tous les thèmes (même méthode que
# test_continuation) : quel que soit le thème tiré, la séance Tactiques sert ce puzzle.
# Amorce ...Nc3, puis Ra8#. Un coup du roi (g1f1) est faux.
MATE_IN_1 = ["L10", "6k1/5ppp/8/8/4n3/8/5PPP/R5K1 b - - 0 1", "e4c3 a1a8"]
THEMES = (
    "fork pin skewer discoveredAttack mateIn1 mateIn2 mateIn3 backRankMate hangingPiece sacrifice "
    "deflection attraction promotion trappedPiece intermezzo defensiveMove rookEndgame pawnEndgame "
    "zugzwang exposedKing discoveredCheck advancedPawn kingsideAttack quietMove"
)

# Géométrie de la barre de verdict, lue sans dépendre de ses classes : le libellé est le span
# qui contient « Réussi » ou « Raté », la barre est son parent. Les lignes de texte sont comptées
# par les rectangles du texte (Range), donc un « ! » rejeté seul à la ligne compte pour deux.
VERDICT_GEOM = r"""() => {
  const label = [...document.querySelectorAll('main span')].find((s) => /^(✓ Réussi|✗ Raté)/.test(s.textContent.trim()))
  if (!label) return null
  let bar = label.parentElement
  while (bar && !bar.querySelector('button')) bar = bar.parentElement
  const lines = (el) => {
    const r = document.createRange()
    r.selectNodeContents(el)
    return new Set([...r.getClientRects()].filter((q) => q.width > 0).map((q) => Math.round(q.top))).size
  }
  const delta = [...bar.querySelectorAll('span')].find((s) => /^\(?[+-]\d+\)?$/.test(s.textContent.trim()))
  const next = [...bar.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Suivant')
  const b = bar.getBoundingClientRect(), n = next.getBoundingClientRect(), l = label.getBoundingClientRect()
  return {
    text: label.textContent.trim(), labelLines: lines(label),
    delta: delta ? delta.textContent.trim() : null, deltaLines: delta ? lines(delta) : 0,
    barH: Math.round(b.height), left: Math.round(l.left), right: Math.round(window.innerWidth - n.right),
  }
}"""


def verdict_bar(p, browser, standalone):
    """LEARN-10 : à 393 px, verdict et delta sur une ligne chacun, barre compacte, marges symétriques."""
    tag = f"verdict {'852' if standalone else '660'}"
    ctx = mobile_context(p, browser, ck, standalone=standalone, service_workers="block")
    body = json.dumps([[MATE_IN_1[0], MATE_IN_1[1], MATE_IN_1[2], 1000, THEMES]])
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=body))
    page = ctx.new_page()
    for outcome, (frm, to) in (("réussi", ("a1", "a8")), ("raté", ("g1", "f1"))):
        page.goto(f"{BASE}/#/apprendre")
        page.wait_for_timeout(1200)
        page.locator("main button", has_text="Tactiques").click()
        if not ck.appears(f"[{tag}] {outcome} : leçon", page, "button:has-text(\"C'est parti\")", timeout=20000):
            break
        page.get_by_role("button", name="C'est parti").click()
        page.wait_for_timeout(1500)  # amorce ...Nc3 jouée
        sq(page, frm)
        page.wait_for_timeout(200)
        sq(page, to)
        ck.appears(f"[{tag}] {outcome} : verdict affiché", page, "text=Suivant", timeout=8000)
        page.wait_for_timeout(600)
        g = page.evaluate(VERDICT_GEOM)
        if not check(f"[{tag}] {outcome} : barre de verdict trouvée", g is not None):
            break
        check(f"[{tag}] {outcome} : libellé « {g['text']} » sur une seule ligne", g["labelLines"] == 1, f"({g['labelLines']} lignes)")
        check(f"[{tag}] {outcome} : delta d'Elo affiché sur une ligne", g["delta"] is not None and g["deltaLines"] == 1, f"({g['delta']}, {g['deltaLines']} lignes)")
        # Une seule rangée : la hauteur est celle du bouton Suivant (52 px) plus les marges de 8 px.
        check(f"[{tag}] {outcome} : barre sur une rangée (≤ 68 px)", g["barH"] <= 68, f"({g['barH']} px)")
        check(f"[{tag}] {outcome} : marges symétriques de 12 px", abs(g["left"] - 12) <= 1 and abs(g["right"] - 12) <= 1, f"(gauche {g['left']}, droite {g['right']})")
        check(f"[{tag}] {outcome} : aucun débordement horizontal", overflow_x(page) == 0)
        page.screenshot(path=f"{SHOTS}/learn_verdict_{outcome}_{'852' if standalone else '660'}.png")
        page.click("header button:has-text('✕')")
        page.wait_for_timeout(400)
    ctx.close()


def suite(p):
    browser = p.chromium.launch(headless=True)
    verdict_bar(p, browser, standalone=True)
    verdict_bar(p, browser, standalone=False)
    ctx = mobile_context(p, browser, ck)
    ctx.add_init_script(SPY_PERSIST)
    page = ctx.new_page()

    # --- Page Apprendre ---
    page.goto(f"{BASE}/#/apprendre")
    page.wait_for_timeout(1500)
    check("[learn] onglet nav Apprendre", page.locator("nav a", has_text="Apprendre").last.is_visible())
    check("[learn] 4 pastilles Elo", page.locator("main .grid > div").count() >= 4)
    check("[learn] CTA Séance", page.get_by_role("button", name="Séance", exact=True).is_visible())
    check("[learn] Mes erreurs grisé (vide)", not page.locator("button", has_text="Mes erreurs").is_enabled())
    page.screenshot(path=f"{SHOTS}/learn_home.png")

    # --- Séance Finales (leçon -> cours -> jeu) ---
    page.locator("main button", has_text=FINALES).click()
    page.wait_for_timeout(1200)
    check("[learn] leçon finale affichée", page.locator(".bg-white").first.is_visible())
    page.screenshot(path=f"{SHOTS}/learn_lesson.png")
    # Cours détaillé depuis la leçon
    page.click("text=Voir le cours complet")
    page.wait_for_timeout(500)
    check("[cours] feuille ouverte", page.locator("text=À retenir").is_visible())
    check("[cours] contenu structuré", page.locator("h2:has-text('📚')").is_visible())
    page.screenshot(path=f"{SHOTS}/learn_course.png")
    page.click("text=Retour à l'exercice")
    page.wait_for_timeout(300)
    check("[cours] fermeture -> leçon intacte", page.locator(".bg-white").first.is_visible())
    page.get_by_role("button", name="C'est parti").click()
    page.wait_for_timeout(800)
    check("[learn] objectif affiché", page.locator("text=Objectif").is_visible())
    check("[learn] board finale", page.locator("[id^='chessboard-']").first.is_visible())
    # Bouton ? dans le header (ne doit jamais chevaucher le board)
    q_btn = page.locator("header button", has_text="?")
    q_box = q_btn.bounding_box()
    board_box = page.locator("[id^='chessboard-']").first.bounding_box()
    overlaps = not (q_box["x"] + q_box["width"] < board_box["x"] or q_box["x"] > board_box["x"] + board_box["width"]
                    or q_box["y"] + q_box["height"] < board_box["y"] or q_box["y"] > board_box["y"] + board_box["height"])
    check("[cours] ? ne chevauche pas le board", not overlaps)
    q_btn.click()
    page.wait_for_timeout(400)
    check("[cours] ? pendant l'exercice", page.locator("text=À retenir").is_visible())
    page.click("text=Retour à l'exercice")
    page.wait_for_timeout(300)
    check("[cours] retour exercice intact", page.locator("[id^='chessboard-']").first.is_visible())
    page.screenshot(path=f"{SHOTS}/learn_endgame.png")
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(400)

    # --- Séance Tactiques (3 puzzles, on rate le 1er exprès via un coup légal quelconque) ---
    page.locator("main button", has_text="Tactiques").click()
    page.wait_for_timeout(2500)
    check("[learn] leçon tactique (thème)", page.locator(".bg-white").first.is_visible())
    page.get_by_role("button", name="C'est parti").click()
    page.wait_for_timeout(1800)
    check("[learn] puzzle affiché", page.locator("[id^='chessboard-']").first.is_visible())
    page.screenshot(path=f"{SHOTS}/learn_tactic.png")
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(400)

    # --- Séance Ouvertures : drill, bon coup accepté, mauvais corrigé ---
    page.locator("main button", has_text="Ouvertures").click()
    page.wait_for_timeout(1500)
    page.get_by_role("button", name="C'est parti").click()
    page.wait_for_timeout(1200)
    check("[learn] drill affiché", page.locator("text=premiers coups").is_visible())
    # Mauvais coup volontaire : a2a3 (aucune ligne du répertoire classique ne commence par a3)
    sq(page, "a2"); page.wait_for_timeout(150); sq(page, "a3")
    page.wait_for_timeout(600)
    corrected = page.locator("text=Pas la ligne").count() > 0
    check("[learn] mauvais coup corrigé", corrected)
    page.screenshot(path=f"{SHOTS}/learn_opening.png")
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(400)

    # --- CTA Séance auto ---
    page.get_by_role("button", name="Séance", exact=True).click()
    page.wait_for_timeout(2500)
    check("[learn] séance auto démarre (leçon)", page.locator(".bg-white").first.is_visible())
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(400)

    # --- Mes erreurs : bilan d'une partie avec gaffes -> stock alimenté -> jouable ---
    page.goto(f"{BASE}/#/analyse")
    page.wait_for_timeout(1500)
    page.locator("main button", has_text="Options").click()
    page.wait_for_timeout(300)
    page.click("text=Importer PGN ou FEN")
    page.fill("textarea", PGN)
    page.click("button:has-text('Charger')")
    page.wait_for_timeout(400)
    page.get_by_role("button", name="★ Bilan").click()
    ck.appears("[bilan] résumé affiché", page, "text=Démarrer le bilan", timeout=180000)
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(600)
    page.goto(f"{BASE}/#/apprendre")
    page.wait_for_timeout(1200)
    mistakes_btn = page.locator("button", has_text="Mes erreurs")
    check("[learn] Mes erreurs alimenté par le bilan", mistakes_btn.is_enabled())
    mistakes_btn.click()
    page.wait_for_timeout(1200)
    page.get_by_role("button", name="C'est parti").click()
    page.wait_for_timeout(600)
    check("[learn] exercice erreur affiché", page.locator("text=Trouve mieux").is_visible())
    page.screenshot(path=f"{SHOTS}/learn_mistake.png")
    # Jouer un coup quelconque -> verdict -> Réessayer / Analyser
    # Jouer n'importe quel coup légal : sélectionner une pièce puis un point de destination.
    played = False
    for f in "abcdefgh":
        for r in "12345678":
            page.locator(f"[data-square='{f}{r}']").click()
            page.wait_for_timeout(60)
            tg = page.evaluate("""() => {
              const els=[...document.querySelectorAll('[data-square]')];
              const has=(root,pred)=>[root,...root.querySelectorAll('*')].some(pred);
              return els.find(e=>has(e,n=>getComputedStyle(n).background.includes('rgba(0, 0, 0, 0.34)')))?.getAttribute('data-square') ?? null;
            }""")
            if tg:
                page.locator(f"[data-square='{tg}']").click()
                played = True
                break
        if played:
            break
    page.wait_for_timeout(12000)  # vérification moteur éventuelle
    verdict = page.locator("text=Réussi").count() > 0 or page.locator("text=Raté").count() > 0
    check("[learn] verdict après coup", verdict)
    check("[learn] bouton Réessayer", page.locator("button", has_text="Réessayer").is_visible())
    check("[learn] bouton Analyser", page.locator("button", has_text="Analyser").is_visible())
    page.locator("button", has_text="Réessayer").click()
    page.wait_for_timeout(600)
    check("[learn] Réessayer relance l'exercice", page.locator("text=Trouve mieux").is_visible())
    # Rejouer un coup pour revenir au verdict, puis Analyser -> Retour -> exercice restauré
    header_before = page.locator("header h1").inner_text()
    played = False
    for f in "abcdefgh":
        for r in "12345678":
            page.locator(f"[data-square='{f}{r}']").click()
            page.wait_for_timeout(50)
            tg = page.evaluate("""() => {
              const els=[...document.querySelectorAll('[data-square]')];
              const has=(root,pred)=>[root,...root.querySelectorAll('*')].some(pred);
              return els.find(e=>has(e,n=>getComputedStyle(n).background.includes('rgba(0, 0, 0, 0.34)')))?.getAttribute('data-square') ?? null;
            }""")
            if tg:
                page.locator(f"[data-square='{tg}']").click()
                played = True
                break
        if played:
            break
    page.wait_for_timeout(2000)
    page.locator("button", has_text="Analyser").click()
    page.wait_for_timeout(1200)
    check("[analyse] Analyser ouvre /analyse", "#/analyse" in page.url or page.evaluate("() => location.hash") == "#/analyse")
    back_btn = page.locator("button", has_text="Retour à l'exercice")
    check("[analyse] bouton retour visible", back_btn.is_visible())
    # Partie contre le moteur depuis cette analyse puis retour : l'analyse rouverte garde son
    # bouton de retour vers l'exercice.
    page.locator("main button", has_text="Options").click()
    page.locator("button", has_text="Jouer contre le moteur").locator("visible=true").click()
    ck.appears("[analyse] partie contre le moteur", page, "[data-testid='position-game']")
    page.get_by_role("button", name="Retour").click()
    ck.appears("[analyse] retour de la partie : bouton retour à l'exercice", page, "button:has-text(\"Retour à l'exercice\")")
    back_btn.click()
    page.wait_for_timeout(800)
    check("[learn] retour restaure la séance", page.evaluate("() => location.hash") == "#/apprendre")
    check("[learn] compteur d'item restauré", page.locator("header h1").inner_text() == header_before)
    page.click("header button:has-text('✕')")


    # --- Anti-saut : le board de /analyse ne bouge pas quand les lignes moteur arrivent ---
    page.goto(f"{BASE}/#/analyse")
    page.wait_for_timeout(600)
    y_before = page.evaluate("() => document.querySelector(\"[id^='chessboard-']\")?.getBoundingClientRect().top")
    page.wait_for_timeout(4000)
    y_after = page.evaluate("() => document.querySelector(\"[id^='chessboard-']\")?.getBoundingClientRect().top")
    check("[anti-saut] board stable sur /analyse", y_before is not None and y_before == y_after, f"({y_before} -> {y_after})")

    # --- Sauvegarde (Stats) ---
    page.goto(f"{BASE}/#/stats")
    page.wait_for_timeout(800)
    check("[backup] boutons présents", page.locator("button", has_text="Exporter tout").is_visible()
          and page.locator("button", has_text="Restaurer").is_visible())
    check("[backup] storage.persist demandé au démarrage", page.evaluate("() => window.__persistRequested === true"))

    ctx.close()
    browser.close()


ck.run(suite)
