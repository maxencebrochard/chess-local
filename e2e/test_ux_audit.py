"""Audit reproductible des écrans, sans modifier le produit.

npm run test:e2e -- --suite ux_audit
Les captures et mesures restent dans shots/ux-audit/{prod,dev}.
Les écarts visuels sont mesurés, pas approuvés par le succès de la suite.
Chaque route déclarée par l'app (lue dans l'arbre React monté) doit figurer dans la matrice :
UX_AUDIT_FORGET=/convertir prouve qu'une route oubliée fait échouer la suite.
"""
import json
import os
from pathlib import Path
import re
import subprocess

import chess
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from helpers import BASE, SHOTS, Checker, click_square, desktop_context, mobile_context, open_learn_session, open_mistakes_session, overflow_x
from moment_fixtures import GAME_A, GAME_B, SESSIONS as MOMENT_SESSIONS

ck = Checker("ux_audit")
ROOT = Path(__file__).resolve().parents[1]
MODE = "prod" if os.environ.get("E2E_DIST") else "dev"
OUT = Path(SHOTS) / "ux-audit" / MODE
OUT.mkdir(parents=True, exist_ok=True)
ROWS = []
DECLARED = set()
COVERED = set()


def data(name):
    return json.loads((ROOT / "src/data" / name).read_text())


def evidence_path(path):
    """Conserver les destinations SHOTS externes dans l'inventaire exporté."""
    return str(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path.resolve())


# Mat en un après le coup d'amorce, repris du scénario de révision existant.
PUZZLE = [["ux-mate", "6k1/5ppp/8/8/4n3/8/5PPP/R5K1 b - - 0 1", "e4c3 a1a8", 800,
           "backRankMate mate mateIn1 short"]]


def capture(page, fmt, name, marker, selector=False):
    loc = "h1" if marker == "ChessLocal" else marker if selector else f":text({json.dumps(marker, ensure_ascii=False)}):visible"
    if not ck.appears(f"{fmt}/{name} : écran attendu", page, loc, timeout=15000):
        return
    page.evaluate("""async () => {
      await Promise.all(document.getAnimations().filter(a =>
        Number.isFinite(a.effect.getComputedTiming().endTime)).map(a => a.finished.catch(() => {})));
      await Promise.all([...document.images].map(img => img.decode().catch(() => {})));
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    }""")
    metrics = page.evaluate("""() => {
      const main = document.querySelector('main');
      const shown = e => !!(e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden');
      const controls = [...document.querySelectorAll('button,a,input,select,textarea')].filter(shown).map(e => {
        const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
        return {text:(e.getAttribute('aria-label') || e.innerText || e.getAttribute('placeholder') || '').trim(),
          tag:e.tagName,href:e.getAttribute('href'),disabled:!!e.disabled,
          x:r.x,y:r.y,w:r.width,h:r.height,font:s.fontSize,
          inViewport:r.top>=0 && r.bottom<=innerHeight && r.left>=0 && r.right<=innerWidth};
      });
      return {url:location.hash,headings:[...document.querySelectorAll('h1,h2')].filter(shown).map(e=>e.innerText),
        text:document.body.innerText,mainHeight:main.clientHeight,mainScrollHeight:main.scrollHeight,
        controls,nav:[...document.querySelectorAll('nav a')].filter(shown).map(e=>({text:e.innerText,current:e.getAttribute('aria-current'),w:e.getBoundingClientRect().width}))};
    }""")
    metrics.update(format=fmt, name=name, overflowX=overflow_x(page), screenshots=[], scrolls=[])
    # Le body est fixe : full_page ne capture PAS le contenu défilant de main.
    scrollers = page.locator("main, div.overflow-y-auto")
    for i in range(scrollers.count()):
        el = scrollers.nth(i)
        if not el.is_visible():
            continue
        dimensions = el.evaluate("e => ({h:e.clientHeight,total:e.scrollHeight})")
        if dimensions["h"] <= 0:
            continue
        el.evaluate("e => e.scrollTop = 0")
        if i == 0:
            path = OUT / f"{fmt}-{name}.png"
            page.screenshot(path=str(path), scale="css")
            metrics["screenshots"].append(evidence_path(path))
        if dimensions["total"] > dimensions["h"] + 2:
            for n, top in enumerate(range(int(dimensions["h"] * .8), dimensions["total"], max(1, int(dimensions["h"] * .8))), 1):
                el.evaluate("(e,y) => e.scrollTop = y", top)
                path = OUT / f"{fmt}-{name}-scroll{i}-{n}.png"
                page.screenshot(path=str(path), scale="css")
                metrics["screenshots"].append(evidence_path(path))
                metrics["scrolls"].append({"path": evidence_path(path), "scroller": i,
                                          "top": el.evaluate("e => e.scrollTop")})
            el.evaluate("e => e.scrollTop = 0")
    ROWS.append(metrics)
    (OUT / "inventory.json").write_text(json.dumps(ROWS, ensure_ascii=False, indent=2))


def wait_position(page, label, fen):
    """Attendre toutes les pièces, y compris le retrait des pièces de la position initiale."""
    expected = {chess.square_name(sq): ("w" if piece.color else "b") + piece.symbol().upper()
                for sq, piece in chess.Board(fen).piece_map().items()}
    matched = page.wait_for_function("""expected => {
      const board = [...document.querySelectorAll('[data-board]')].find(e => e.getBoundingClientRect().width > 0);
      if (!board) return false;
      const pieces = [...board.querySelectorAll('[data-square] [data-piece]')];
      return pieces.length === Object.keys(expected).length && pieces.every(e =>
        expected[e.closest('[data-square]').dataset.square] === e.dataset.piece);
    }""", arg=expected, timeout=15000)
    # Le même instantané prouve le nombre ET l'emplacement de toutes les pièces.
    # Une seconde lecture peut tomber pendant une animation du plateau.
    ck.check(label, matched.json_value())


def visit(page, fmt, path, name, marker):
    page.goto(f"{BASE}/#{path}")
    capture(page, fmt, name, marker, selector=marker.startswith("["))
    ck.check(f"{fmt}/{name} : URL après rendu", page.url.endswith(f"#{path}"))


# Routes réellement montées : le `<Routes>` d'App.tsx ne devient pas une fibre par `<Route>`
# (react-router les lit par `createRoutesFromChildren`), mais la fibre de `Routes` porte ses
# éléments `<Route>` dans `memoizedProps.children`. Le parcours part d'un nœud DOM rendu et ne
# dépend d'aucun nom de composant : il marche sur le build minifié et quel que soit l'`element`
# (import direct ou chargement à la demande).
DECLARED_ROUTES_JS = """() => {
  const start = document.querySelector('main');
  const key = start && Object.keys(start).find(k => k.startsWith('__reactFiber$'));
  if (!key) return null;
  let root = start[key];
  while (root.return) root = root.return;
  const routeTable = children => {
    const list = (Array.isArray(children) ? children.flat(Infinity) : [children]).filter(c => c && typeof c === 'object');
    return list.length > 0 && list.every(c => c.props && (typeof c.props.path === 'string' || c.props.index)) ? list : null;
  };
  const flatten = (elements, prefix) => elements.flatMap(e => {
    const path = e.props.index ? prefix : (e.props.path.startsWith('/') || !prefix ? e.props.path : `${prefix.replace(/\\/$/, '')}/${e.props.path}`);
    const nested = e.props.children ? routeTable(e.props.children) : null;
    return [path, ...(nested ? flatten(nested, path) : [])];
  });
  const found = new Set();
  const stack = [root];
  while (stack.length) {
    const fiber = stack.pop();
    const table = fiber.memoizedProps && routeTable(fiber.memoizedProps.children);
    if (table) flatten(table, '').forEach(r => found.add(r));
    if (fiber.child) stack.push(fiber.child);
    if (fiber.sibling) stack.push(fiber.sibling);
  }
  return [...found];
}"""


def route_regex(pattern):
    return re.compile("^" + "/".join("[^/]+" if seg.startswith(":") else re.escape(seg) for seg in pattern.split("/")) + "$")


def best_route(path, patterns):
    """Route retenue pour `path`, au classement de react-router : un segment statique l'emporte sur un paramètre."""
    matching = [r for r in patterns if r != "*" and route_regex(r).match(path)]
    return max(matching, key=lambda r: sum(0 if seg.startswith(":") else 1 for seg in r.split("/")), default="*")


def check_route_coverage(page, fmt, visited):
    """Chaque route déclarée doit être photographiée par l'audit : une route ajoutée sans
    extension de la matrice fait échouer la suite."""
    page.goto(f"{BASE}/#/")
    ck.appears(f"{fmt} : accueil rendu avant lecture des routes", page, "main h1", timeout=15000)
    declared = page.evaluate(DECLARED_ROUTES_JS) or []
    # Garde contre un parcours vide ou partiel qui rendrait la comparaison vacuement vraie.
    ck.check(f"{fmt} : table des routes lue dans l'app ({len(declared)} routes)",
             "/" in declared and "*" in declared and len(declared) >= 40, str(declared))
    covered = {best_route(path, declared) for path in visited}
    for route in sorted(declared):
        ck.check(f"{fmt} : route {route} couverte par l'audit", route in covered,
                 "absente de la matrice : ajouter un état à `routes` dans test_ux_audit.py")
    for path in sorted(visited):
        ck.check(f"{fmt} : chemin audité {path} servi par une route déclarée", best_route(path, declared) != "*" or path == "/route-inconnue")
    return declared, covered & set(declared)


def context(p, browser, fmt, height):
    if fmt == "desktop":
        return desktop_context(browser, ck, service_workers="block")
    return mobile_context(p, browser, ck, standalone=True, viewport={"width":393,"height":height}, service_workers="block")


def seed_mistakes(page):
    """Deux positions des suites diagnostic_attaque et defense, datées de la veille."""
    rows = [
        {"id": 1, "color": "w", "fenBefore": "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1", "playedSan": "Kf1", "bestUci": "a1a8"},
        {"id": 2, "color": "b", "fenBefore": "r1bq1rk1/pp3pp1/2n1p2p/3pP1NQ/3P4/2NB4/PP3PPP/R3K2R b KQ - 0 1", "playedSan": "Nb4", "bestUci": "d8g5"},
    ]
    page.evaluate("""rows => new Promise((resolve,reject) => {
      const req=indexedDB.open('chess-local'); req.onerror=()=>reject(req.error);
      req.onsuccess=()=>{const db=req.result; const tx=db.transaction('mistakes','readwrite');
        const yesterday=new Date(); yesterday.setDate(yesterday.getDate()-1); yesterday.setHours(12,0,0,0);
        for(const row of rows) tx.objectStore('mistakes').put({...row,date:+yesterday,cls:'blunder',attempts:0,solved:0,gameKey:'ux',gameLabel:'Partie audit'});
        tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>reject(tx.error);
      };
    })""", rows)


def seed_moments(page):
    """Deux parties analysées (cache `reviews`) et leurs états `critical-moment` (moment_fixtures)."""
    page.evaluate("""data => new Promise((resolve,reject) => {
      const req=indexedDB.open('chess-local'); req.onerror=()=>reject(req.error);
      req.onsuccess=()=>{const db=req.result; const tx=db.transaction(['reviews','learnSessions'],'readwrite');
        for(const r of data.reviews) tx.objectStore('reviews').put(r);
        for(const r of data.sessions) tx.objectStore('learnSessions').put(r);
        tx.oncomplete=()=>{db.close();resolve()};tx.onerror=()=>reject(tx.error);
      };
    })""", {"reviews": [GAME_A, GAME_B], "sessions": MOMENT_SESSIONS})


def suite(p):
    browser = p.chromium.launch(headless=True)
    (OUT / "manifest.json").write_text(json.dumps({
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "mode": MODE, "browser": "Chromium, émulation iPhone, insets natifs nuls",
        "fixtures": ["e2e/fixtures/chesscom.json", "mat en un de test_revision", "deux fautes de diagnostic_attaque et defense"],
    }, ensure_ascii=False, indent=2))
    for fmt, height in [("iphone852", 852), ("iphone660", 660), ("desktop", 900)]:
        ctx = context(p, browser, fmt, height)
        page = ctx.new_page()
        routes = [
            ("/", "accueil", "ChessLocal"), ("/jouer", "jouer", "Adversaire"),
            ("/puzzles", "puzzles", "Classement puzzles"), ("/rush", "rush", "Survie"),
            ("/apprendre", "apprendre", "Séance"), ("/ouvertures", "ouvertures", "Entraîneur d'ouvertures"),
            ("/apprendre/finales", "cours-finales", "Cours de finales"),
            ("/apprendre/roque", "cours-roque", "Démolir le roque"),
            ("/mats", "mats", "Mats éclair"), ("/revision", "revision-vide", "Rien à réviser"),
            ("/attaques-manquees", "attaques-vide", "Rien à rejouer"),
            ("/defenses-ratees", "defenses-vide", "Mes défenses ratées"),
            ("/analyse", "analyse", "[data-board]"), ("/analyse/jouer", "position-vide", "Aucune position"),
            ("/finales", "finales", "Finales jusqu'au bout"), ("/attaque", "attaque", "Entraîneur d'attaque"),
            ("/defense", "defense", "Entraîneur de défense"), ("/archive", "archive-vide", "Aucune partie enregistrée"),
            ("/stats", "stats", "Statistiques"), ("/insights", "insights-vide", "Insights"),
            ("/import", "import", "Importer depuis"),
            ("/plus", "plus", "Outils et progression"),
            ("/reglages", "reglages", "Profondeur du bilan de partie"),
            ("/donnees", "donnees", "Dernier export"),
            ("/repertoire", "repertoire", "Mon répertoire"),
            ("/visualisation", "visualisation", "Calcul et visualisation"),
            ("/moment-critique", "moment-vide", "Aucun moment critique"),
            ("/apprendre/bases", "cours-bases", "Les bases"),
            ("/apprendre/parcours", "parcours", "Parcours d'apprentissage"),
            ("/apprendre/defense", "cours-defense", "Tenir sous l'attaque"),
            # `:text()` trouverait aussi la carte « Mes structures de pions » : le marqueur prouve le bloc `extra`.
            ("/apprendre/structures", "cours-structures", "[data-testid='my-structures-card']"),
            ("/structures", "structures", "[data-testid='structures-summary'], [data-testid='structures-empty']"),
            ("/structures/local:999999@14@iqp", "structures-absent", "[data-testid='structure-missing']"),
            ("/convertir", "convertir", "Convertir l'avantage"),
            ("/finales/chrono", "finales-chrono", "Finales au chrono"),
            ("/seance", "seance-du-jour", "Séance du jour"),
            # Hub guidé d'Apprendre (lot 5).
            ("/apprendre/lecons", "lecons", "[data-testid='defense-card-progress']"),
            ("/apprendre/entrainement", "entrainement", "Quelle compétence travailler"),
            ("/apprendre/mes-parties", "mes-parties", "[data-testid='moments-card']"),
            ("/apprendre/moments-critiques", "moments-vide", "[data-testid='moments-empty']"),
        ]
        for slug in ["tactique", "attaque-defense", "finales", "ouvertures", "strategie"]:
            routes.append((f"/apprendre/entrainement/{slug}", f"groupe-{slug}", "S'entraîner"))
        for path, filename, name in [("/attaque", "attacks.json", "attaque-exercice"),
                                      ("/defense", "defenses.json", "defense-exercice"),
                                      ("/finales", "endgames.json", "finale-exercice"),
                                      ("/convertir", "conversions.json", "convertir-exercice")]:
            item = data(filename)[0]
            routes.append((f"{path}/{item['id']}", name, "Abandonner"))
        for slug, filename in [("finales", "endgameCourse.json"), ("roque", "attackCourse.json"), ("bases", "basicsCourse.json"),
                               ("defense", "defenseCourse.json"), ("structures", "structuresCourse.json")]:
            course = data(filename)
            lid = course["chapters"][0]["lessons"][0]
            routes.append((f"/apprendre/{slug}/{lid}", f"lecon-{slug}", course["lessons"][lid]["title"]))
        step = data("learningPath.json")["levels"][0]["steps"][0]
        routes.append((f"/apprendre/parcours/{step['id']}", "parcours-etape", step["title"]))
        routes.append(("/apprendre/parcours/placement", "parcours-placement", "Test de placement"))
        for path in ["/attaques-manquees", "/defenses-ratees"]:
            routes.append((f"{path}/999999", path[1:]+"-absent", "pas dans ta liste"))
        # Preuve par mutation : `UX_AUDIT_FORGET=/convertir` retire ce chemin de la matrice, la
        # couverture des routes doit alors échouer.
        routes = [r for r in routes if r[0] != os.environ.get("UX_AUDIT_FORGET")]
        for path, name, marker in routes:
            visit(page, fmt, path, name, marker)
        # Repli `*` : une URL inconnue revient à l'accueil.
        page.goto(f"{BASE}/#/route-inconnue")
        try:
            page.wait_for_url(f"{BASE}/#/", timeout=15000)
        except PlaywrightTimeoutError:
            pass
        ck.check(f"{fmt}/route-inconnue : repli vers l'accueil", page.url.endswith("#/"), page.url)
        capture(page, fmt, "route-inconnue", "ChessLocal")
        declared, covered = check_route_coverage(page, fmt, [r[0] for r in routes] + ["/route-inconnue"])
        DECLARED.update(declared)
        COVERED.update(covered)

        # Parcours par l'interface : onglets, puis cours et retour explicite.
        page.goto(f"{BASE}/")
        for label, path in [("Apprendre", "/apprendre"), ("Jouer", "/jouer"), ("Accueil", "/")]:
            page.locator("nav a:visible").filter(has_text=label).click()
            page.wait_for_url(f"**/#{path}")
            ck.check(f"{fmt} : onglet {label}", page.url.endswith("#"+path))
        page.locator("nav a:visible").filter(has_text="Apprendre").click()
        page.get_by_text("Toutes les leçons", exact=True).click()
        page.get_by_text("Cours de finales", exact=True).click()
        ck.appears(f"{fmt} : cours via tuile", page, "h1:text('Cours de finales')")
        page.get_by_role("button", name="Retour à Toutes les leçons").click()
        ck.appears(f"{fmt} : retour à Toutes les leçons", page, "h1:text('Toutes les leçons')")
        page.get_by_role("button", name="Retour à Apprendre").click()
        ck.appears(f"{fmt} : retour au hub", page, "h1:text('Apprendre')")

        for domain, key in [("Finales", "endgame"), ("Tactiques", "tactic"), ("Ouvertures", "opening"), ("Stratégie", "strategy")]:
            page.goto(f"{BASE}/#/")
            open_learn_session(page, key)
            capture(page, fmt, "seance-"+domain.lower(), "C'est parti")
            page.get_by_role("button", name="C'est parti", exact=True).click()
            capture(page, fmt, "exercice-"+domain.lower(), "[data-board]", selector=True)

        page.goto(f"{BASE}/#/jouer")
        page.get_by_role("button", name=re.compile("2 joueurs")).click()
        capture(page, fmt, "jouer-local", "2 joueurs")
        page.get_by_role("button", name=re.compile("Entraîneur")).click()
        capture(page, fmt, "jouer-coach", "Adversaire")
        page.get_by_role("button", name=re.compile("Contre un bot")).click()
        page.get_by_role("button", name="Jouer", exact=True).click()
        capture(page, fmt, "partie", "Abandonner")
        click_square(page, "e2")
        click_square(page, "e4")
        ck.appears(f"{fmt} : coup et réponse du bot", page, "main [data-current] + [data-current]", timeout=20000)
        page.get_by_role("button", name=re.compile("Abandonner")).click()
        capture(page, fmt, "abandon-confirmation", "Oui, abandonner")
        page.get_by_role("button", name="Oui, abandonner", exact=True).click()
        capture(page, fmt, "fin-partie", "Nouvelle partie")
        page.get_by_role("button", name="Bilan de la partie", exact=True).click()
        capture(page, fmt, "bilan-partie", "Précision")
        page.goto(f"{BASE}/#/archive")
        capture(page, fmt, "archive-remplie", "Nina")

        page.goto(f"{BASE}/#/mats?d=chrono-kq")
        capture(page, fmt, "mat-fiche", "[data-board]", selector=True)
        page.get_by_role("button", name="Commencer", exact=True).click()
        capture(page, fmt, "mat-chrono", "[data-board]", selector=True)
        for drill in ["mate-1", "geo-escalier", "motif-damiano"]:
            page.goto(f"{BASE}/#/mats?d={drill}")
            capture(page, fmt, drill+"-fiche", "Commencer")
            page.get_by_role("button", name="Commencer", exact=True).click()
            capture(page, fmt, drill+"-exercice", "[data-board]", selector=True)
        page.goto(f"{BASE}/#/finales/chrono")
        if ck.appears(f"{fmt} : séries des finales au chrono", page, "button[data-serie]", timeout=15000):
            page.locator("button[data-serie]").first.click()
            capture(page, fmt, "finales-chrono-serie", "[data-run='endgame-clock']", selector=True)
        page.goto(f"{BASE}/#/ouvertures")
        page.locator("button").filter(has_text="Sicilienne").first.click()
        capture(page, fmt, "ouverture-fiche", "Variantes")
        page.locator("button[data-mode='next']").click()
        capture(page, fmt, "ouverture-exercice", "[data-board]", selector=True)
        page.goto(f"{BASE}/#/analyse")
        if fmt != "desktop":
            page.get_by_role("button", name=re.compile("Options")).click()
            capture(page, fmt, "analyse-options", "Jouer contre le moteur")
        page.get_by_role("button", name=re.compile("Jouer contre le moteur")).click()
        capture(page, fmt, "position-jeu", "Abandonner")
        page.goto(f"{BASE}/#/analyse")
        if fmt != "desktop":
            page.get_by_role("button", name=re.compile("Options")).click()
            page.get_by_role("button", name="Importer PGN ou FEN", exact=True).click()
        else:
            page.get_by_role("button", name="PGN", exact=True).click()
        capture(page, fmt, "analyse-import", "Importer PGN ou FEN")
        page.locator("textarea").fill("position invalide")
        page.get_by_role("button", name="Charger", exact=True).click()
        capture(page, fmt, "analyse-import-erreur", "Format non reconnu")
        page.goto(f"{BASE}/#/donnees")
        page.get_by_test_id("reset-btn").click()
        capture(page, fmt, "donnees-confirmation", "Réinitialiser l'app ?")
        page.get_by_role("button", name="Annuler", exact=True).click()
        page.goto(f"{BASE}/#/import")
        page.get_by_placeholder("Ton pseudo chess.com").fill("popeye232")
        page.get_by_role("button", name="Voir mes parties", exact=True).click()
        capture(page, fmt, "import-rempli", "Actualiser")
        page.goto(f"{BASE}/#/rush")
        page.get_by_role("button", name=re.compile("Survie")).click()
        capture(page, fmt, "rush-exercice", "[data-board]", selector=True)
        page.get_by_role("button", name="Arrêter", exact=True).click()
        capture(page, fmt, "rush-resultat", "Terminé")

        page.goto(f"{BASE}/#/apprendre/mes-parties")
        ck.appears(f"{fmt} : base initialisée", page, "[data-testid='missed-attacks-card'][data-count='0']")
        seed_mistakes(page)
        seed_moments(page)
        for path, name, marker in [
            ("/", "accueil-revision", "À réviser aujourd'hui"),
            ("/attaques-manquees", "attaques-remplies", "Partie audit"),
            ("/attaques-manquees/1", "attaque-personnelle", "Abandonner"),
            ("/defenses-ratees", "defenses-remplies", "Partie audit"),
            ("/defenses-ratees/2", "defense-personnelle", "Abandonner"),
            ("/revision", "revision-exercice", "[data-board]"),
            ("/apprendre/mes-parties", "mes-parties-remplie", "[data-testid='moments-card'][data-count='2']"),
            ("/apprendre/moments-critiques", "moments-remplis", "[data-testid='moment-item']"),
        ]:
            page.goto(f"{BASE}/#{path}")
            capture(page, fmt, name, marker, selector=marker.startswith("["))
        open_mistakes_session(page)
        capture(page, fmt, "mes-erreurs", "C'est parti")
        page.get_by_role("button", name="C'est parti", exact=True).click()
        capture(page, fmt, "mes-erreurs-exercice", "[data-board]", selector=True)
        # Le diagnostic attaque est un mat en un : preuve d'un vrai verdict utilisateur.
        page.goto(f"{BASE}/#/attaques-manquees/1")
        ck.appears(f"{fmt} : attaque personnelle prête", page, "[data-square='a1'] [data-piece='wR']")
        click_square(page, "a1")
        click_square(page, "a8")
        capture(page, fmt, "attaque-reussie", "Analyser")
        page.get_by_role("button", name=re.compile("Analyser")).click()
        wait_position(page, f"{fmt} : position complète de l'attaque chargée en analyse", "R5k1/5ppp/8/8/8/8/5PPP/6K1 b - - 1 1")
        capture(page, fmt, "analyse-retour", "Retour")
        page.get_by_role("button", name=re.compile("Retour")).first.click()
        ck.appears(f"{fmt} : contexte restauré", page, "[data-square='a8'] [data-piece='wR']")
        if fmt != "desktop":
            for path, name, marker in [("/", "accueil", "ChessLocal"), ("/apprendre", "apprendre", "Séance")]:
                page.goto(f"{BASE}/#{path}")
                page.add_style_tag(content=".pt-safe { padding-top: 71px !important; } .pb-safe { padding-bottom: 34px !important; }")
                capture(page, fmt, name+"-insets-simules", marker)
        else:
            page.goto(f"{BASE}/")
            page.keyboard.press("Tab")
            ck.check("desktop : navigation atteignable au clavier", page.evaluate("document.activeElement.tagName === 'A'"))
            capture(page, fmt, "accueil-focus", "ChessLocal")
        ctx.close()

        loading_ctx = context(p, browser, fmt, height)
        held = []
        loading_ctx.route("**/puzzles.json", lambda route: held.append(route))
        lp = loading_ctx.new_page()
        lp.goto(f"{BASE}/#/puzzles")
        capture(lp, fmt, "puzzles-chargement", "Chargement")
        ck.check(f"{fmt} : requête puzzles retenue", len(held) > 0)
        for route in held:
            route.fulfill(json=PUZZLE)
        capture(lp, fmt, "puzzle-fixture", "Classement puzzles")
        ck.appears(f"{fmt} : amorce terminée", lp, "[data-square='c3'] [data-piece='bN']")
        click_square(lp, "a1")
        click_square(lp, "a8")
        capture(lp, fmt, "puzzle-reussi", "Suivant")
        loading_ctx.unroute("**/puzzles.json")
        loading_ctx.route("**/puzzles.json", lambda route: route.fulfill(status=503, body="Indisponible"))
        lp.evaluate("localStorage.removeItem('chess-local-puzzle-session')")
        lp.reload()
        capture(lp, fmt, "puzzles-erreur", "Puzzles indisponibles")
        loading_ctx.unroute("**/puzzles.json")
        loading_ctx.route("**/puzzles.json", lambda route: route.fulfill(json=PUZZLE))
        lp.get_by_role("button", name="Réessayer", exact=True).click()
        capture(lp, fmt, "puzzles-reprise", "Classement puzzles")
        open_learn_session(lp, "tactic")
        capture(lp, fmt, "seance-fixture", "C'est parti")
        lp.get_by_role("button", name="C'est parti", exact=True).click()
        ck.appears(f"{fmt} : séance prête", lp, "[data-square='c3'] [data-piece='bN']")
        click_square(lp, "a1")
        click_square(lp, "a8")
        capture(lp, fmt, "seance-verdict", "Réussi")
        lp.get_by_role("button", name=re.compile("Analyser")).click()
        wait_position(lp, f"{fmt} : position complète de la séance chargée en analyse", "6k1/5ppp/8/8/8/2n5/5PPP/R5K1 w - - 1 2")
        capture(lp, fmt, "seance-analyse", "Retour à l'exercice")
        lp.get_by_role("button", name=re.compile("Retour à l'exercice")).click()
        ck.appears(f"{fmt} : séance restaurée avec verdict", lp, ":text('Réussi')")
        lp.get_by_role("button", name="Suivant", exact=True).click()
        capture(lp, fmt, "seance-bilan", "Encore une séance")
        loading_ctx.close()
    browser.close()
    ck.check("Les trois formats ont été capturés", {r["format"] for r in ROWS} == {"iphone852", "iphone660", "desktop"})
    (OUT / "routes.json").write_text(json.dumps(sorted(DECLARED), ensure_ascii=False, indent=2))
    print(f"Routes déclarées : {len(DECLARED)} ; couvertes : {len(COVERED)}")
    print(f"Inventaire : {len(ROWS)} états, {sum(len(r['screenshots']) for r in ROWS)} captures ; {OUT}")


ck.run(suite)
