"""E2E cours « Tenir sous l'attaque » (Apprendre) : contrôle hors ligne et ses mutations (règles
communes et règles propres à la défense : tenue vérifiée, menace de mat, « perd », coup marqué « ? »),
carte d'entrée, sommaire, première leçon coup par coup (refus « ne tient pas », indice, flèche, bon
coup joué au doigt, réponse de l'attaquant), « tient aussi », zone grise, toutes les leçons jouables,
progression séparée des autres cours, mise en page 393x852, 393x660, 1440x900.

Usage : npm run test:e2e -- --suite cours_defense
"""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time

import chess

from course_helpers import advance, continue_btn, finish_line, observe_dom, open_lesson, play_solution, wait_piece, wait_ready, wait_rows
from helpers import BASE, Checker, desktop_context, drag_piece, mobile_context, overflow_x, piece_on, shot, tap_move

ck = Checker("cours_defense")
check = ck.check
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "src", "data", "defenseCourse.json")
STAMP = os.path.join(ROOT, "scripts", "defense-course.verified")
# Absent sans la feature : la suite doit alors échouer par ses checks, pas planter au chargement.
RAW = open(DATA, encoding="utf-8").read() if os.path.exists(DATA) else ""
COURSE = json.loads(RAW) if RAW.strip() else {"chapters": [], "lessons": {}}
LESSONS = [lid for ch in COURSE["chapters"] for lid in ch["lessons"]]
N = len(LESSONS)
FIRST = LESSONS[0] if LESSONS else None


def count_lessons(name):
    return sum(len(ch["lessons"]) for ch in json.load(open(os.path.join(ROOT, "src", "data", name), encoding="utf-8"))["chapters"])


FINALES_N = count_lessons("endgameCourse.json")
ROQUE_N = count_lessons("attackCourse.json")

ROWS = """() => new Promise((resolve) => {
  const req = indexedDB.open('chess-local')
  req.onsuccess = () => {
    const tx = req.result.transaction('learnSessions', 'readonly')
    const all = tx.objectStore('learnSessions').getAll()
    all.onsuccess = () => { resolve(all.result.filter((r) => r.domain === 'course').map((r) => r.itemId)); req.result.close() }
  }
})"""

ARROWHEADS = "[id^='chessboard-'] marker[id*='arrowhead']"


def feedback(page):
    return page.locator("[data-testid='line-feedback']").inner_text()


def bubble(page):
    """Texte de l'étape : bulle du coach (diagramme) ou zone de retour commune (ligne, lot 8)."""
    return page.locator(".bg-white, [data-exercise-feedback]").first.inner_text()


def in_viewport(page, locator):
    box = locator.bounding_box()
    vp = page.viewport_size
    return box is not None and box["y"] >= 0 and box["y"] + box["height"] <= vp["height"] + 0.5 and box["x"] >= 0 and box["x"] + box["width"] <= vp["width"] + 0.5


def run_check(json_path=DATA, stamp_path=STAMP):
    res = subprocess.run(["node", "scripts/check-defense-course.mjs", json_path, stamp_path], cwd=ROOT, capture_output=True, text=True)
    return res.returncode, res.stdout + res.stderr


def lines_of(lesson_id):
    return [(i, s) for i, s in enumerate(COURSE["lessons"][lesson_id]["steps"]) if s["kind"] == "line"]


def student_moves(step):
    """[(index, fen avant, coup JSON, uci)] des coups de l'élève d'une ligne."""
    b = chess.Board(step["fen"])
    player = b.turn
    out = []
    for i, m in enumerate(step["moves"]):
        mv = b.parse_san(m["san"])
        if b.turn == player:
            out.append((i, b.fen(), m, mv.uci()))
        b.push(mv)
    return out


def bad_move(fen, m):
    """Un coup légal hors `keeps` et hors `close` : le contrôle exige donc un refus « ne tient pas »."""
    b = chess.Board(fen)
    good = set(m.get("keeps", [])) | set(m.get("close", []))
    for mv in b.legal_moves:
        if mv.uci() not in good and not mv.promotion:
            return mv.uci()
    return None


def find_step(pred):
    """(leçon, index) de la première étape qui vérifie `pred`."""
    for lid in LESSONS:
        for si, s in enumerate(COURSE["lessons"][lid]["steps"]):
            if pred(s):
                return lid, si
    return None, None


# ---------- Mutations du contrôle : chaque copie est retamponnée, le message attendu est exigé ----------
def mutations():
    lesson = COURSE["lessons"][FIRST]
    diag = next(i for i, s in enumerate(lesson["steps"]) if s["kind"] == "diagram")
    line = next(i for i, s in enumerate(lesson["steps"]) if s["kind"] == "line")
    fl, fi = find_step(lambda s: s["kind"] == "diagram" and "fails" in s)
    tl, ti = find_step(lambda s: s["kind"] == "diagram" and "threat" in s)
    check("[mutation] le cours a un diagramme avec fails et un avec threat", fl is not None and tl is not None)
    if fl is None or tl is None:
        return

    def d_first(d):
        return d["lessons"][FIRST]["steps"][diag]

    def mut_fen(d):
        d_first(d)["fen"] = "4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1"  # Noirs en échec, Blancs au trait
    def mut_move(d):
        d["lessons"][FIRST]["steps"][line]["moves"][0]["san"] = "Qxa8"
    def mut_verdict(d):
        s = d_first(d)
        s.pop("claim", None)
        s.pop("fails", None)
        s["text"] = "Ici, la riposte est décisive."
    def mut_dash(d):
        d["lessons"][FIRST]["summary"] += " \u2014 vite"
    def mut_keeps(d):
        d["lessons"][FIRST]["steps"][line]["moves"][0]["keeps"] = ["a7a6"]
    def mut_only(d):
        m = d["lessons"][FIRST]["steps"][line]["moves"][0]
        m["only"] = True
        m["keeps"] = sorted(set(m["keeps"]) | {"a7a6", "a2a3"})
    def mut_absolute(d):
        d["lessons"][FIRST]["keyPoints"][0] = "La défense tient forcément."
    def mut_frozen(d):
        d["lessons"][FIRST + "-bis"] = d["lessons"].pop(FIRST)
        for ch in d["chapters"]:
            ch["lessons"] = [FIRST + "-bis" if x == FIRST else x for x in ch["lessons"]]
    def mut_english(d):
        d["lessons"][FIRST]["steps"][line]["moves"][0]["text"] = "Kg8 garde le roi."
    def mut_result(d):
        d["lessons"][FIRST]["steps"][line]["result"] = "draw"
    def mut_hold_claim(d):
        d_first(d)["claim"] = "hold-x"
    def mut_holds_wrong_claim(d):
        s = d_first(d)
        s.pop("fails", None)
        s["claim"] = "w"
        s["text"] = "Avec le bon coup, la défense tient."
    def mut_threat_false(d):
        s = d["lessons"][tl]["steps"][ti]
        b = chess.Board(s["fen"])
        b.turn = not b.turn
        b.ep_square = None
        quiet = next(m for m in b.legal_moves if not b.gives_check(m))
        s["threat"] = b.san(quiet)
    def mut_mate_unproved(d):
        s = d["lessons"][tl]["steps"][ti]
        s.pop("threat")
        s["eval"] = "+0.10"
        if "failsEval" in s:
            s["failsEval"] = "-3.00"
    def mut_mate_in(d):
        s = d["lessons"][tl]["steps"][ti]
        s["text"] = "L'attaquant menace un mat en 3."
        s["eval"] = "+0.10"
        if "failsEval" in s:
            s["failsEval"] = "-3.00"
    def mut_loses(d):
        s = d["lessons"][fl]["steps"][fi]
        s["failsEval"] = "-1.20"
        s["text"] = s["text"].rstrip(".") + ". Ce coup perd."
    def mut_marked(d):
        s = d_first(d)
        b = chess.Board(s["fen"])
        mv = next(m for m in b.legal_moves if b.san(m) != s.get("fails") and b.piece_at(m.from_square).piece_type == chess.PAWN)
        fr = b.san(mv)
        s["text"] = f"Le coup {fr} ? affaiblit le roi."
    def mut_line_mate(d):
        d["lessons"][FIRST]["steps"][line]["text"] = "Évite le mat."
    cases = [
        ("position illégale (le camp sans le trait est en échec)", mut_fen, "est en échec"),
        ("coup injouable", mut_move, "injouable"),
        ("verdict non tamponné", mut_verdict, "sans claim ni fails"),
        ("tiret cadratin", mut_dash, "tiret cadratin"),
        ("keeps sans le coup", mut_keeps, "keeps absent ou sans le coup"),
        ("only avec plusieurs keeps", mut_only, "only mais"),
        ("formulation absolue", mut_absolute, "formulation absolue"),
        ("id figé renommé", mut_frozen, "supprimée ou renommée"),
        ("notation anglaise", mut_english, "notation anglaise"),
        ("result hors hold, edge, win", mut_result, "result invalide"),
        ("claim hold invalide", mut_hold_claim, "claim invalide"),
        ("« tient » avec un claim w", mut_holds_wrong_claim, "la défense tient"),
        ("threat qui n'est pas mat", mut_threat_false, "n'est pas mat"),
        ("menace de mat sans threat", mut_mate_unproved, "parle de mat sans mat"),
        ("« mat en 3 » avec un simple threat", mut_mate_in, "parle de mat sans mat"),
        ("« perd » sans -2 tamponné", mut_loses, "-2 exigé"),
        ("coup marqué « ? » sans fails", mut_marked, "marqué « ? » sans fails"),
        ("mat dans le texte d'une ligne", mut_line_mate, "parle de mat sans mat"),
    ]
    tmp = tempfile.mkdtemp(prefix="cours-defense-")
    try:
        for label, fn, expected in cases:
            d = json.loads(RAW)
            fn(d)
            text = json.dumps(d, ensure_ascii=False, indent=2) + "\n"
            path = os.path.join(tmp, "course.json")
            stamp = os.path.join(tmp, "course.verified")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            with open(stamp, "w") as f:
                # Même sha du vérificateur que le vrai tampon : seul le contenu diffère.
                f.write(hashlib.sha256(text.encode()).hexdigest() + " " + open(STAMP).read().split()[1] + "\n")
            code, out = run_check(path, stamp)
            check(f"[mutation] {label} : contrôle en échec", code == 1 and expected in out, f"(code {code}, attendu « {expected} » : {out.strip()[-240:]})")
            check(f"[mutation] {label} : tampon accepté (le refus vient de la règle visée)", "a changé depuis" not in out, f"({out.strip()[:160]})")
        # Tampon périmé : le contenu change, le tampon non.
        path = os.path.join(tmp, "course.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(RAW.replace('"title": "', '"title": "x', 1))
        code, out = run_check(path, STAMP)
        check("[mutation] tampon périmé : contrôle en échec", code == 1 and "a changé depuis sa vérification" in out, f"(code {code})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def open_line_at(page, lid, si, ply):
    """Ouvre l'étape `si` de `lid` et joue par « Solution » jusqu'au coup `ply` de l'élève."""
    page.goto(f"{BASE}/#/apprendre/defense/{lid}?etape={si + 1}")
    # Une navigation vers le même hash conserve la ligne React déjà avancée.
    # Chaque scénario commence explicitement au premier coup.
    page.reload()
    ck.appears(f"[{lid}] ligne ouverte", page, f"[data-testid='lesson-step']:has-text('{si + 1}/')")
    for _ in range(ply // 2):
        play_solution(ck, page)
    wait_ready(ck, page)


def suite(p):
    # ---------- Données ----------
    code, out = run_check()
    check("[données] check-defense-course.mjs passe", code == 0, f"({out.strip()[-300:]})")
    check("[données] 6 chapitres, 10 leçons au moins", len(COURSE["chapters"]) >= 6 and N >= 10, f"({len(COURSE['chapters'])} chapitres, {N} leçons)")
    check("[données] contre-attaque au centre enseignée", "contre-attaque-au-centre" in LESSONS)
    results = {s["result"] for lid in LESSONS for _, s in lines_of(lid)}
    check("[données] des lignes où la défense tient (hold)", "hold" in results, f"({results})")
    if FIRST is None:
        return
    if code == 0:
        mutations()

    browser = p.chromium.launch(headless=True)
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()

    # ---------- Entrée depuis Apprendre ----------
    page.goto(f"{BASE}/#/apprendre/lecons")
    ck.appears("[entrée] carte Tenir sous l'attaque", page, "button:has-text(\"Tenir sous l'attaque\")")
    check("[entrée] progression 0/N", page.locator("[data-testid='defense-card-progress']").inner_text() == f"0/{N} leçons")
    check("[entrée] carte des finales intacte", page.locator("[data-testid='course-card-progress']").inner_text() == f"0/{FINALES_N} leçons")
    check("[entrée] carte Démolir le roque intacte", page.locator("[data-testid='attack-card-progress']").inner_text() == f"0/{ROQUE_N} leçons")
    cards = page.locator("button:has([data-testid$='card-progress'])")
    order = [cards.nth(i).locator("[data-testid]").get_attribute("data-testid") for i in range(cards.count())]
    check("[entrée] tuile juste après Démolir le roque", "attack-card-progress" in order and order[order.index("attack-card-progress") + 1:][:1] == ["defense-card-progress"], f"({order})")
    shot(page, "defense_learn_home", full_page=True)
    page.locator("button", has_text="Tenir sous l'attaque").click()
    ck.appears("[sommaire] titre", page, "h1:has-text(\"Tenir sous l'attaque\")")
    check("[sommaire] URL", page.url.endswith("#/apprendre/defense"), f"({page.url})")
    check("[sommaire] chapitres", page.locator("main section h2").count() == len(COURSE["chapters"]))
    check("[sommaire] toutes les leçons listées", page.locator("[data-lesson]").count() == N)
    check("[sommaire] onglet Apprendre allumé", page.locator("nav a[aria-current]", has_text="Apprendre").count() >= 1)
    check("[sommaire] progression 0/N", page.locator("[data-testid='course-progress']").inner_text() == f"0/{N}")
    check("[sommaire] intro prudente (Stockfish)", "Stockfish" in page.locator("main").inner_text())
    shot(page, "defense_index", full_page=True)

    # ---------- Première leçon : diagramme, ligne, refus, indice, flèche, réponse ----------
    lesson = COURSE["lessons"][FIRST]
    total = len(lesson["steps"]) + 1
    first = lesson["steps"][0]
    page.locator(f"[data-lesson='{FIRST}']").click()
    ck.appears("[leçon] étape 1", page, f"[data-testid='lesson-step']:has-text('1/{total}')")
    check("[leçon] plein écran : nav recouverte", page.evaluate("() => !document.elementFromPoint(196, 840).closest('nav')"))
    check("[leçon] diagramme fléché", first["kind"] == "diagram" and page.locator(ARROWHEADS).count() == len(first.get("arrows", [])) > 0, f"({page.locator(ARROWHEADS).count()} flèches)")
    check("[leçon] diagramme vu du défenseur noir", page.locator("[data-square]").first.get_attribute("data-square") == "h1")
    shot(page, "defense_first_diagram")
    li, line = lines_of(FIRST)[0]
    for _ in range(li):
        advance(ck, page)
    ck.appears("[leçon] ligne ouverte", page, f"[data-testid='lesson-step']:has-text('{li + 1}/{total}')")
    check("[leçon] Continuer grisé tant que la ligne n'est pas jouée", not continue_btn(page).is_enabled())
    _, fen0, m0, uci0 = student_moves(line)[0]
    wrong = bad_move(fen0, m0)
    wrong_piece = piece_on(page, wrong[:2])
    red = f"() => [...document.querySelectorAll(\"[data-square='{wrong[2:4]}'] div\")].some((e) => getComputedStyle(e).backgroundColor.includes('235, 97, 80'))"
    with observe_dom(page, red) as red_seen:
        tap_move(page, wrong[:2], wrong[2:4], pause=120)
        fb = feedback(page)
        expected_bad = "ne tient pas" if line["result"] == "hold" else "laisse filer"
        check("[leçon] mauvais coup : refus prudent (Stockfish)", "Selon Stockfish" in fb and expected_bad in fb, f"({fb})")
        check("[leçon] indice du coup au premier échec", bool(m0.get("hint")) and "Indice" in fb and m0["hint"][:20] in fb, f"({fb})")
        check("[leçon] case du coup refusé en rouge", red_seen())
    wait_ready(ck, page)
    wait_piece(ck, page, wrong[:2], wrong_piece)
    check("[leçon] coup refusé repris", piece_on(page, wrong[:2]) is not None)
    check("[leçon] pas de flèche d'aide après un seul essai", page.locator(ARROWHEADS).count() == 0)
    tap_move(page, wrong[:2], wrong[2:4], pause=120)
    wait_ready(ck, page)
    wait_piece(ck, page, wrong[:2], wrong_piece)
    check("[leçon] flèche d'aide au 2e essai", page.locator(ARROWHEADS).count() == 1)
    piece = piece_on(page, uci0[:2])
    arrival = f"() => document.querySelector(\"[data-square='{uci0[2:4]}'] [data-piece]\")?.getAttribute('data-piece') === '{piece}'"
    with observe_dom(page, arrival) as arrived:
        drag_piece(page, uci0[:2], uci0[2:4])
        # Sous charge, le lâcher peut être traité après la fin du geste CDP : attendre le rendu, sans pause fixe.
        end = time.monotonic() + 5
        while not arrived() and time.monotonic() < end:
            page.wait_for_timeout(50)
        check("[leçon] pièce arrivée", arrived(), f"({piece} attendu en {uci0[2:4]}, {piece_on(page, uci0[2:4])} affiché)")
        check("[leçon] bon coup glissé au doigt, accepté et commenté", (m0.get("text") or "Bien joué")[:25] in feedback(page), f"({feedback(page)})")
    wait_ready(ck, page)
    if len(line["moves"]) > 1:
        reply = chess.Board(fen0)
        reply.push_uci(uci0)
        rmv = reply.parse_san(line["moves"][1]["san"])
        wait_piece(ck, page, rmv.uci()[:2], None)
        check("[leçon] réponse de l'attaquant jouée", piece_on(page, rmv.uci()[2:4]) is not None and piece_on(page, rmv.uci()[:2]) is None)
        check("[leçon] réponse annoncée dans la zone de retour", "répondent" in bubble(page))
    shot(page, "defense_first_line")
    clicks = finish_line(ck, page)
    check("[leçon] ligne jouée jusqu'au bout par Solution", continue_btn(page).is_enabled(), f"({clicks} clics)")
    check("[leçon] message de fin", line["end"][:30] in feedback(page), f"({feedback(page)})")
    shot(page, "defense_first_line_done")
    advance(ck, page)
    for s in lesson["steps"][li + 1:]:
        if s["kind"] == "line":
            finish_line(ck, page)
            check(f"[leçon] ligne « {s['text'][:30]} » jouée jusqu'au bout", continue_btn(page).is_enabled())
        advance(ck, page)
    ck.appears("[bilan] À retenir", page, "text=À retenir")
    check("[bilan] points clés affichés", all(k[:30] in page.inner_text("body") for k in lesson["keyPoints"]))
    check("[bilan] pas de S'entraîner (pas d'exercice de finale)", page.locator("button", has_text="S'entraîner").count() == 0)
    check("[bilan] Leçon suivante proposée", page.get_by_role("button", name="Leçon suivante").is_visible())
    shot(page, "defense_summary")
    wait_rows(ck, page, ROWS, "[progrès] ligne learnSessions defense écrite")
    check("[progrès] une ligne learnSessions defense", page.evaluate(ROWS) == [f"defense:{FIRST}"], f"({page.evaluate(ROWS)})")
    page.goto(f"{BASE}/#/apprendre/defense/{FIRST}?etape={total}")
    ck.appears("[progrès] bilan rouvert", page, "text=À retenir")
    wait_rows(ck, page, ROWS, "[progrès] ligne learnSessions defense relue")
    page.wait_for_timeout(400)  # Conserver la fenêtre de détection d’une écriture en double.
    check("[progrès] idempotent", page.evaluate(ROWS) == [f"defense:{FIRST}"], f"({page.evaluate(ROWS)})")

    # ---------- « Tient aussi » : un coup de keeps autre que celui de la leçon, dans une ligne hold ----------
    alt = None
    for lid in LESSONS:
        for si, s in lines_of(lid):
            for i, fen, m, uci in student_moves(s):
                others = [u for u in m["keeps"] if u != uci and not chess.Move.from_uci(u).promotion]
                if others and alt is None and s["result"] == "hold":
                    alt = (lid, si, i, others[0])
    check("[tient aussi] au moins un coup d'une ligne hold a une autre suite qui tient", alt is not None)
    if alt:
        lid, si, i, other = alt
        open_line_at(page, lid, si, i)
        tap_move(page, other[:2], other[2:4], pause=120)
        check("[tient aussi] message « tient aussi »", "tient aussi" in feedback(page), f"({lid} {other} : {feedback(page)})")
        wait_ready(ck, page)

    # ---------- Zone grise : un coup de `close` reçoit le message neutre ----------
    grey = None
    for lid in LESSONS:
        for si, s in lines_of(lid):
            for i, fen, m, uci in student_moves(s):
                if m.get("close") and grey is None:
                    grey = (lid, si, i, m["close"][0])
    check("[zone grise] au moins un coup du cours a une zone grise", grey is not None)
    if grey:
        lid, si, i, other = grey
        open_line_at(page, lid, si, i)
        tap_move(page, other[:2], other[2:4], pause=120)
        check("[zone grise] message « se défend moins bien »", "se défend moins bien" in feedback(page), f"({lid} {other} : {feedback(page)})")
        wait_ready(ck, page)

    # ---------- La prise hxg6 ouvre bien la colonne h ----------
    lid = "contre-la-tempete"
    si, storm = lines_of(lid)[0]
    open_line_at(page, lid, si, 0)
    tap_move(page, "h7", "g6", pause=120)
    board = chess.Board(storm["fen"])
    board.push_san("hxg6")
    check("[tempête] hxg6 ouvre la colonne h, sans pion sur cette colonne",
          not any(board.piece_at(chess.square(7, rank)) in
                  (chess.Piece(chess.PAWN, chess.WHITE), chess.Piece(chess.PAWN, chess.BLACK))
                  for rank in range(8)))
    check("[tempête] le commentaire explique que la colonne h s'ouvre",
          "colonne h s'ouvre" in feedback(page), f"({feedback(page)})")
    shot(page, "defense_storm_capture")

    # ---------- Id inconnu ----------
    page.goto(f"{BASE}/#/apprendre/defense/inconnue")
    ck.appears("[id inconnu] retour au sommaire", page, "h1:has-text(\"Tenir sous l'attaque\")")

    # ---------- Toutes les leçons se jouent jusqu'au bilan ----------
    for lid in LESSONS:
        if not open_lesson(ck, page, f"{BASE}/#/apprendre/defense/{lid}", COURSE["lessons"][lid]):
            continue
        ok = True
        for s in COURSE["lessons"][lid]["steps"]:
            if s["kind"] == "line":
                finish_line(ck, page)
                ok = ok and continue_btn(page).is_enabled()
            advance(ck, page)
        ok = ok and page.locator("text=À retenir").is_visible()
        check(f"[toutes] {lid} jouée jusqu'au bilan", ok)
    page.goto(f"{BASE}/#/apprendre/defense")
    ck.appears("[toutes] sommaire N/N", page, f"[data-testid='course-progress']:has-text('{N}/{N}')")
    page.goto(f"{BASE}/#/apprendre/lecons")
    ck.appears("[toutes] carte N/N", page, f"[data-testid='defense-card-progress']:has-text('{N}/{N} leçons')")
    check("[toutes] les finales restent à 0", page.locator("[data-testid='course-card-progress']").inner_text() == f"0/{FINALES_N} leçons")
    check("[toutes] Démolir le roque reste à 0", page.locator("[data-testid='attack-card-progress']").inner_text() == f"0/{ROQUE_N} leçons")
    rows = page.evaluate(ROWS)
    check("[toutes] lignes learnSessions toutes préfixées defense:", len(rows) == N and all(r.startswith("defense:") for r in rows), f"({rows})")
    ctx.close()

    # ---------- 393x660 : échiquier, bulle et Continuer dans l'écran ----------
    ctx = mobile_context(p, browser, ck)
    page = ctx.new_page()
    longest = max(
        ((lid, si) for lid in LESSONS for si, s in enumerate(COURSE["lessons"][lid]["steps"])),
        key=lambda x: len(COURSE["lessons"][x[0]]["steps"][x[1]]["text"]),
    )
    for lid, si in [(FIRST, 0), (FIRST, lines_of(FIRST)[0][0]), longest]:
        page.goto(f"{BASE}/#/apprendre/defense/{lid}?etape={si + 1}")
        if not ck.appears(f"[660] {lid} étape {si + 1} ouverte", page, "[id^='chessboard-']"):
            continue
        page.wait_for_timeout(500)
        board = page.locator("[id^='chessboard-']").first
        check(f"[660] {lid} étape {si + 1} : échiquier entier à l'écran", in_viewport(page, board), f"({board.bounding_box()})")
        check(f"[660] {lid} étape {si + 1} : Continuer à l'écran", in_viewport(page, continue_btn(page)))
        check(f"[660] {lid} étape {si + 1} : texte de l'étape visible", page.locator(".bg-white, [data-exercise-feedback]").first.is_visible())
        check(f"[660] {lid} étape {si + 1} : pas de défilement horizontal", overflow_x(page) == 0)
        shot(page, f"defense_660_{lid}_{si + 1}")
    ctx.close()

    # ---------- 1440x900 ----------
    ctx = desktop_context(browser, ck)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre/defense")
    ck.appears("[desktop] sommaire ouvert", page, "[data-lesson]")
    shot(page, "defense_desktop_index")
    page.goto(f"{BASE}/#/apprendre/defense/{FIRST}?etape={lines_of(FIRST)[0][0] + 1}")
    ck.appears("[desktop] ligne ouverte", page, "[id^='chessboard-']")
    page.wait_for_timeout(400)
    check("[desktop] Continuer à l'écran", in_viewport(page, continue_btn(page)))
    shot(page, "defense_desktop_line")
    ctx.close()
    browser.close()


ck.run(suite)
