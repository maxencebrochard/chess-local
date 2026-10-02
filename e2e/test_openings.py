"""E2E « Entraîneur d'ouvertures » (/ouvertures) : choix d'une famille, trois modes, fautes,
prolongement Stockfish, progression persistée.

Usage : npm run test:e2e -- --suite openings

Les lignes attendues sont recalculées ici depuis src/data/openings.json avec la même règle de
famille que l'app : la suite ne lit jamais le coup attendu dans le DOM, seulement la position
courante (`data-uci` du conteneur du drill) et l'indice une fois demandé (`data-hint`).
"""
import json
import os

from helpers import BASE, Checker, mobile_context, desktop_context, overflow_x, shot, tap_move

ck = Checker("openings")
check = ck.check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "src", "data", "openings.json"), encoding="utf-8") as f:
    OPENINGS = json.load(f)


def family_of(name):
    base = name.split(":")[0].split(",")[0].strip()
    for suffix in (" Accepted", " Declined"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return base


def family_lines(key):
    return [o for o in OPENINGS if family_of(o["name"]) == key]


def leaves(lines):
    ucis = [o["uci"] for o in lines]
    return [o for o in lines if not any(u != o["uci"] and u.startswith(o["uci"] + " ") for u in ucis)]


def children(lines, prefix):
    """Coups théoriques de la famille après la séquence `prefix` (liste UCI)."""
    n = len(prefix)
    out = set()
    for o in lines:
        mv = o["uci"].split(" ")
        if len(mv) > n and mv[:n] == prefix:
            out.add(mv[n])
    return out


# Toutes les séquences de la base lichess : un coup qui y mène est « théorique » quelque part.
BOOK = {" ".join(o["uci"].split(" ")[:n]) for o in OPENINGS for n in range(1, len(o["uci"].split(" ")) + 1)}

SCOTCH = family_lines("Scotch Game")
SCOTCH_LEAVES = leaves(SCOTCH)
GORING = next(o for o in SCOTCH_LEAVES if o["name"] == "Scotch Game: Göring Gambit, Main Line")["uci"].split(" ")
RELFSSON = next(o for o in SCOTCH_LEAVES if o["name"] == "Scotch Game: Relfsson Gambit")["uci"].split(" ")
SICILIAN_LEAVES = leaves(family_lines("Sicilian Defense"))

DRILL = "[data-drill]"


def drill_uci(page):
    v = page.get_attribute(DRILL, "data-uci")
    return v.split(" ") if v else []


def wait_plies(page, n, timeout=15000):
    """Attend que la position du drill compte au moins `n` demi-coups."""
    try:
        page.wait_for_function(
            """(n) => { const d = document.querySelector('[data-drill]');
                        const u = d && d.getAttribute('data-uci'); return (u ? u.split(' ').length : 0) >= n }""",
            arg=n, timeout=timeout,
        )
        return True
    except Exception:
        return False


def play_uci(page, uci):
    tap_move(page, uci[0:2], uci[2:4])


def open_family(page, label):
    page.goto(f"{BASE}/#/ouvertures")
    ok = ck.appears(f"[accueil] carte {label}", page, f"main button:has-text('{label}')", timeout=10000)
    if ok:
        page.locator("main button", has_text=label).first.click()
    return ck.appears(f"[fiche] {label} ouverte", page, f"main h1:has-text('{label}')", timeout=5000)


def pick(page, group_label, option):
    page.get_by_role("group", name=group_label).get_by_role("button", name=option, exact=True).click()
    # Le changement passe par l'URL (navigation en transition) : on attend l'état pressé.
    try:
        page.wait_for_function(
            """([g, o]) => [...document.querySelectorAll(`[role=group][aria-label="${g}"] button`)]
                 .some((b) => b.textContent.trim() === o && b.getAttribute('aria-pressed') === 'true')""",
            arg=[group_label, option], timeout=3000,
        )
    except Exception:
        pass


def pressed(page, group_label, option):
    return page.get_by_role("group", name=group_label).get_by_role("button", name=option, exact=True).get_attribute("aria-pressed") == "true"


def start_variant(page, uci_list):
    sel = f"[data-variant='{' '.join(uci_list)}']"
    if page.locator(sel).count() == 0 or not page.locator(sel).is_visible():
        more = page.locator("button", has_text="Afficher les")
        if more.count():
            more.first.click()
    page.locator(sel).click()
    return ck.appears("[variante] drill ouvert", page, DRILL, timeout=5000)


def play_line(page, line, color, start=0, skip=()):
    """Joue les coups du joueur de `line` à partir de `start`, en attendant les réponses."""
    me = 0 if color == "w" else 1
    for i in range(start, len(line)):
        if i % 2 != me or i in skip:
            continue
        if not wait_plies(page, i):
            return check(f"[variante] réponse adverse avant le demi-coup {i}", False)
        play_uci(page, line[i])
        if not wait_plies(page, i + 1, 5000):
            return check(f"[variante] coup {line[i]} accepté", False, f"(position {drill_uci(page)})")
    return True


def suite(p):
    browser = p.chromium.launch(headless=True)
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()

    # --- Entrée depuis Apprendre ---
    page.goto(f"{BASE}/#/apprendre")
    if ck.appears("[apprendre] carte Entraîneur d'ouvertures", page, "main a:has-text(\"Entraîneur d'ouvertures\")", timeout=10000):
        page.locator("main a", has_text="Entraîneur d'ouvertures").click()
        page.wait_for_timeout(400)
    check("[apprendre] la carte mène à #/ouvertures", page.evaluate("() => location.hash") == "#/ouvertures")
    tab = page.locator("nav a", has_text="Apprendre").last
    check("[nav] onglet Apprendre allumé sur /ouvertures", tab.get_attribute("aria-current") is not None)

    # --- Accueil : populaires et recherche ---
    for label in ("Défense sicilienne", "Défense scandinave", "Partie écossaise", "Gambit dame", "Système de Londres"):
        ck.appears(f"[accueil] populaire {label}", page, f"main button:has-text('{label}')", timeout=5000)
    shot(page, "openings_home")
    check("[accueil] pas de débordement horizontal", overflow_x(page) == 0)
    search = page.get_by_placeholder("Rechercher une ouverture")
    search.fill("scandi")
    page.wait_for_timeout(200)
    names = page.locator("main [data-family]").all_inner_texts()
    check("[recherche] « scandi » : la scandinave en tête (nom de famille avant les variantes)", len(names) >= 1 and "scandinave" in names[0].lower(), f"({names})")
    search.fill("ecossaise")
    page.wait_for_timeout(200)
    names = page.locator("main [data-family]").all_inner_texts()
    check("[recherche] sans accent trouve l'écossaise", any("écossaise" in n.lower() for n in names), f"({names})")
    search.fill("Najdorf")
    page.wait_for_timeout(200)
    names = page.locator("main [data-family]").all_inner_texts()
    check("[recherche] nom de variante anglais trouve la sicilienne", any("sicilienne" in n.lower() for n in names), f"({names})")
    search.fill("")

    # --- Fiche sicilienne : camp Noirs par défaut, nombre de variantes ---
    open_family(page, "Défense sicilienne")
    check("[fiche] sicilienne jouée avec les Noirs par défaut", pressed(page, "Camp", "Noirs"))
    count_text = page.locator("[data-progress]").inner_text()
    check("[fiche] sicilienne : 250 variantes (feuilles lichess)", len(SICILIAN_LEAVES) == 250 and "250 variantes" in count_text, f"({count_text!r}, calcul {len(SICILIAN_LEAVES)})")
    shot(page, "openings_family_sicilian")

    # --- Fiche écossaise ---
    open_family(page, "Partie écossaise")
    check("[fiche] écossaise jouée avec les Blancs par défaut", pressed(page, "Camp", "Blancs"))
    count_text = page.locator("[data-progress]").inner_text()
    check("[fiche] écossaise : 33 variantes (feuilles lichess)", len(SCOTCH_LEAVES) == 33 and "33 variantes" in count_text, f"({count_text!r})")
    check("[fiche] longueur 15 coups par défaut", pressed(page, "Longueur", "15 coups"))
    pick(page, "Longueur", "Théorie seule")
    check("[fiche] longueur Théorie seule sélectionnée", pressed(page, "Longueur", "Théorie seule"))
    shot(page, "openings_family_scotch")
    check("[fiche] pas de débordement horizontal", overflow_x(page) == 0)

    # --- Variante complète : Göring, fautes, coup théorique neutre, fin, réessai ---
    if start_variant(page, GORING):
        title = page.locator("[data-variant-name]").inner_text()
        check("[variante] nom de la variante affiché dès le départ", "Göring" in title, f"({title!r})")
        # Faute volontaire au 2e coup : un coup qui n'existe dans aucune ligne lichess
        # (1.a3 serait neutre : c'est l'ouverture Anderssen).
        play_line(page, GORING[:2], "w")
        wait_plies(page, 2)
        wrong = next(m for m in ("a2a3", "h2h3", "a2a4", "h2h4", "b2b3", "g2g3") if " ".join(GORING[:2] + [m]) not in BOOK)
        play_uci(page, wrong)
        ck.appears("[faute] « Hors théorie » affiché", page, f"{DRILL} >> text=Hors théorie", timeout=3000)
        check("[faute] coup repris", drill_uci(page) == GORING[:2], f"({wrong} : {drill_uci(page)})")
        check("[faute] coup attendu montré (flèche + data-hint)", page.get_attribute(DRILL, "data-hint") == GORING[2], f"({page.get_attribute(DRILL, 'data-hint')})")
        shot(page, "openings_full_fault")
        # Le coup attendu fait avancer, l'adversaire répond.
        play_line(page, GORING, "w", start=2)
        check("[variante] fin atteinte", wait_plies(page, len(GORING)), f"({drill_uci(page)})")
        ck.appears("[fin] carte « À revoir » (1 faute)", page, f"{DRILL} >> text=À revoir", timeout=5000)
        shot(page, "openings_full_end_fault")
        page.locator("button", has_text="Réessayer").click()
        check("[réessai] drill repart de zéro", wait_plies(page, 0) and drill_uci(page) == [])
        # Coup théorique d'une autre branche (4.Cxd4 au lieu de 4.c3) : neutre.
        play_line(page, GORING[:6], "w")
        wait_plies(page, 6)
        other = "f3d4"
        check("[neutre] 4.Cxd4 est bien théorique ici", other in children(SCOTCH, GORING[:6]) and other != GORING[6])
        play_uci(page, other)
        ck.appears("[neutre] message « Coup théorique aussi »", page, f"{DRILL} >> text=Coup théorique aussi", timeout=3000)
        check("[neutre] coup repris", len(drill_uci(page)) == 6)
        shot(page, "openings_full_neutral")
        play_line(page, GORING, "w", start=6)
        ck.appears("[fin] « Variante maîtrisée » sans faute (le neutre ne compte pas)", page, f"{DRILL} >> text=Variante maîtrisée", timeout=5000)
        shot(page, "openings_full_end_ok")
        page.locator("header button", has_text="✕").click()
        page.wait_for_timeout(300)
        badge = page.locator(f"[data-variant='{' '.join(GORING)}']")
        check("[progression] pastille maîtrisée dans la liste", "Maîtrisée" in (badge.inner_text() if badge.count() else ""))
        prog = page.locator("[data-progress]").inner_text()
        check("[progression] compteur 1 maîtrisée", "1 maîtrisée" in prog, f"({prog!r})")
        # Persistance : rechargement.
        page.reload()
        open_family(page, "Partie écossaise")
        prog = page.locator("[data-progress]").inner_text()
        check("[progression] survit au rechargement (IndexedDB)", "1 maîtrisée" in prog, f"({prog!r})")
        rows = page.evaluate("""() => new Promise((res) => {
          const r = indexedDB.open('chess-local'); r.onsuccess = () => {
            const tx = r.result.transaction('learnSessions'); const q = tx.objectStore('learnSessions').getAll();
            q.onsuccess = () => res(q.result.filter((x) => x.domain === 'opening-drill').map((x) => [x.itemId, x.success])) } })""")
        key = "full:w:" + " ".join(GORING)
        check("[persistance] deux tentatives enregistrées dans learnSessions (échec puis succès)",
              [s for k, s in rows if k == key] == [0, 1], f"({rows})")

    # --- Prochain coup ---
    pick(page, "Longueur", "Théorie seule")
    page.locator("main button[data-mode='next']").click()
    if ck.appears("[prochain] drill ouvert", page, DRILL, timeout=5000):
        page.wait_for_timeout(300)
        pos = drill_uci(page)
        cands = children(SCOTCH, pos)
        check("[prochain] position de l'écossaise, trait aux Blancs, avec un coup théorique",
              len(pos) % 2 == 0 and len(pos) >= 5 and len(cands) > 0, f"({pos} -> {cands})")
        shot(page, "openings_next")
        if cands:
            play_uci(page, sorted(cands)[0])
            ck.appears("[prochain] bon coup : « Théorique »", page, f"{DRILL} >> text=✓ Théorique", timeout=3000)
        page.locator("button", has_text="Position suivante").click()
        page.wait_for_timeout(400)
        pos2 = drill_uci(page)
        wrong = next((m for m in ("a2a3", "h2h3", "g2g3", "b2b3") if " ".join(pos2 + [m]) not in BOOK
                      and page.evaluate("(sq) => !!document.querySelector(`[data-square='${sq}'] [data-piece='wP']`)", m[:2])
                      and page.evaluate("(sq) => !document.querySelector(`[data-square='${sq}'] [data-piece]`)", m[2:])), None)
        check("[prochain] un coup légal hors théorie existe", wrong is not None, f"({pos2})")
        if wrong:
            play_uci(page, wrong)
            ck.appears("[prochain] coup faux : « Hors théorie »", page, f"{DRILL} >> text=✗ Hors théorie", timeout=3000)
            check("[prochain] coup faux repris", drill_uci(page) == pos2)
            check("[prochain] coup théorique montré après la faute", page.get_attribute(DRILL, "data-hint") in children(SCOTCH, pos2), f"({page.get_attribute(DRILL, 'data-hint')})")
            shot(page, "openings_next_fault")
        page.locator("header button", has_text="✕").click()
        page.wait_for_timeout(300)

    # --- Suite (5 coups) ---
    page.locator("main button[data-mode='suite']").click()
    if ck.appears("[suite] drill ouvert", page, DRILL, timeout=5000):
        page.wait_for_timeout(300)
        start = drill_uci(page)
        check("[suite] départ dans l'écossaise, trait aux Blancs", len(start) >= 4 and len(start) % 2 == 0, f"({start})")
        # Le joueur trouve ses coups par l'indice : la suite vérifie l'enchaînement, pas la mémoire.
        line = page.get_attribute(DRILL, "data-variant-uci").split(" ")
        expected = sum(1 for i in range(len(start), min(len(start) + 9, len(line))) if i % 2 == 0)
        played = 0
        for _ in range(5):
            n = len(drill_uci(page))
            if page.locator("[data-result]").count():
                break
            page.locator("button", has_text="Indice").click()
            hint = page.get_attribute(DRILL, "data-hint")
            if not hint:
                break
            play_uci(page, hint)
            if not wait_plies(page, n + 1, 5000):
                break
            played += 1
            try:
                page.wait_for_function(
                    """(n) => !!document.querySelector('[data-result]')
                       || (document.querySelector('[data-drill]')?.getAttribute('data-uci') || '').split(' ').length >= n""",
                    arg=n + 2, timeout=5000)
            except Exception:
                pass
        check("[suite] tous les coups demandés joués (5, moins si la théorie s'arrête avant)", played == expected and expected >= 1, f"({played}/{expected})")
        ck.appears("[suite] carte de fin", page, "[data-result]", timeout=5000)
        shot(page, "openings_suite_end")
        page.locator("header button", has_text="✕").click()
        page.wait_for_timeout(300)

    rows = page.evaluate("""() => new Promise((res) => {
      const r = indexedDB.open('chess-local'); r.onsuccess = () => {
        const q = r.result.transaction('learnSessions').objectStore('learnSessions').getAll();
        q.onsuccess = () => res(q.result.filter((x) => x.domain === 'opening-drill').map((x) => x.itemId.split(':')[0])) } })""")
    check("[persistance] « Prochain coup » : une ligne par position (la 1re tentative)", rows.count("next") == 2, f"({rows})")
    check("[persistance] « Suite » enregistrée", rows.count("suite") == 1, f"({rows})")

    # --- ✕ sans jouer : rien n'est enregistré ---
    before = len(rows)
    page.locator("main button[data-mode='full']").click()
    if ck.appears("[abandon] drill ouvert", page, DRILL, timeout=5000):
        page.locator("header button", has_text="✕").click()
        page.wait_for_timeout(300)
        n_rows = page.evaluate("""() => new Promise((res) => { const r = indexedDB.open('chess-local'); r.onsuccess = () => {
          const q = r.result.transaction('learnSessions').objectStore('learnSessions').count(); q.onsuccess = () => res(q.result) } })""")
        check("[abandon] ✕ sans coup joué n'enregistre rien", n_rows == before, f"({n_rows} vs {before})")

    # --- Prolongement Stockfish (10 coups, variante courte) ---
    pick(page, "Longueur", "10 coups")
    if start_variant(page, RELFSSON):
        play_line(page, RELFSSON, "w")
        ck.appears("[stockfish] bandeau de fin de théorie lichess", page, f"{DRILL} >> text=Stockfish", timeout=30000)
        check("[stockfish] l'adversaire répond hors théorie", wait_plies(page, len(RELFSSON) + 1, 30000), f"({drill_uci(page)})")
        shot(page, "openings_engine")
        n = len(drill_uci(page))
        page.locator("button", has_text="Indice").click()
        try:
            page.wait_for_function("() => !!document.querySelector('[data-drill]')?.getAttribute('data-hint')", timeout=30000)
        except Exception:
            pass
        hint = page.get_attribute(DRILL, "data-hint")
        check("[stockfish] l'indice donne le coup de Stockfish", bool(hint) and len(hint) >= 4, f"({hint})")
        if hint:
            play_uci(page, hint)
            check("[stockfish] coup de Stockfish accepté puis réponse adverse", wait_plies(page, n + 2, 30000), f"({drill_uci(page)})")
        check("[stockfish] coups Stockfish marqués ⚙ dans la liste", page.locator("[data-moves] [data-engine]").count() >= 1)
        page.locator("header button", has_text="✕").click()
        page.wait_for_timeout(300)

    pick(page, "Longueur", "Théorie seule")
    page.locator("main button[data-mode='full']").click()
    if ck.appears("[hasard] drill ouvert sur une variante tirée", page, DRILL, timeout=5000):
        first = page.get_attribute(DRILL, "data-variant-uci")
        for _ in range(60):
            if page.locator("[data-result]").count():
                break
            n = len(drill_uci(page))
            page.locator("button", has_text="Indice").click()
            hint = page.get_attribute(DRILL, "data-hint")
            if not hint:
                page.wait_for_timeout(300)
                continue
            play_uci(page, hint)
            wait_plies(page, n + 2, 5000)
        ck.appears("[hasard] fin de variante", page, "[data-result]", timeout=10000)
        page.locator("button", has_text="Variante suivante").click()
        page.wait_for_timeout(500)
        second = page.get_attribute(DRILL, "data-variant-uci")
        check("[hasard] « Variante suivante » tire une autre variante", second != first and drill_uci(page) == [], f"({first!r} -> {second!r})")

    # --- Petit écran : tout le board visible sans défiler ---
    ctx.close()
    ctx = mobile_context(p, browser, ck)
    page = ctx.new_page()
    open_family(page, "Partie écossaise")
    shot(page, "openings_family_660")
    page.locator("main button[data-mode='full']").click()
    if ck.appears("[660] drill ouvert", page, DRILL, timeout=5000):
        page.wait_for_timeout(500)
        box = page.locator(f"{DRILL} [id^='chessboard-']").first.bounding_box()
        check("[660] board entièrement visible", box is not None and box["y"] >= 0 and box["y"] + box["height"] <= 660, f"({box})")
        actions = page.locator("button", has_text="Indice").bounding_box()
        check("[660] actions visibles sans défiler", actions is not None and actions["y"] + actions["height"] <= 660, f"({actions})")
        check("[660] pas de débordement horizontal", overflow_x(page) == 0)
        shot(page, "openings_drill_660")
    ctx.close()

    # --- Desktop ---
    ctx = desktop_context(browser, ck)
    page = ctx.new_page()
    open_family(page, "Partie écossaise")
    shot(page, "openings_family_desktop")
    page.locator("main button[data-mode='full']").click()
    if ck.appears("[desktop] drill ouvert", page, DRILL, timeout=5000):
        page.wait_for_timeout(500)
        shot(page, "openings_drill_desktop")
        box = page.locator(f"{DRILL} [id^='chessboard-']").first.bounding_box()
        check("[desktop] board entièrement visible", box is not None and box["y"] + box["height"] <= 900, f"({box})")
    ctx.close()
    browser.close()


ck.run(suite)
