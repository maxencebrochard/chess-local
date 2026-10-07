"""E2E cours « Démolir le roque » (Apprendre) : contrôle hors ligne et ses mutations, carte
d'entrée, sommaire, leçon du sacrifice grec coup par coup (refus prudents, indice, flèche,
« garde aussi », réponse adverse), roque de l'élève par un vrai glisser, réponse faible marquée,
toutes les leçons jouables, progression séparée des finales, mise en page 393x852, 393x660, 1440x900.

Usage : npm run test:e2e -- --suite cours_roque
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile

import chess

from helpers import BASE, Checker, desktop_context, drag_piece, mobile_context, piece_on, shot, tap_move

ck = Checker("cours_roque")
check = ck.check
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "src", "data", "attackCourse.json")
STAMP = os.path.join(ROOT, "scripts", "attack-course.verified")
# Absent sans la feature : la suite doit alors échouer par ses checks, pas planter au chargement.
RAW = open(DATA, encoding="utf-8").read() if os.path.exists(DATA) else ""
COURSE = json.loads(RAW) if RAW.strip() else {"chapters": [], "lessons": {}}
LESSONS = [lid for ch in COURSE["chapters"] for lid in ch["lessons"]]
N = len(LESSONS)
FINALES_N = sum(len(ch["lessons"]) for ch in json.load(open(os.path.join(ROOT, "src", "data", "endgameCourse.json"), encoding="utf-8"))["chapters"])

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
    return page.locator(".bg-white").first.inner_text()


def continue_btn(page):
    return page.get_by_role("button", name="Continuer", exact=True)


def solution_btn(page):
    return page.get_by_role("button", name="💡 Solution")


def wait_ready(page):
    page.wait_for_function(
        "() => [...document.querySelectorAll('button')].some((b) => (b.textContent.includes('Solution') || b.textContent.trim() === 'Continuer') && !b.disabled)",
        timeout=5000,
    )


def finish_line(page, max_moves=40):
    """Joue la ligne courante par « Solution » jusqu'au bout. Retourne le nombre de clics."""
    clicks = 0
    while not continue_btn(page).is_enabled() and clicks < max_moves:
        wait_ready(page)
        if continue_btn(page).is_enabled():
            break
        solution_btn(page).click()
        clicks += 1
        page.wait_for_timeout(120)
    page.wait_for_timeout(900)
    return clicks


def in_viewport(page, locator):
    box = locator.bounding_box()
    vp = page.viewport_size
    return box is not None and box["y"] >= 0 and box["y"] + box["height"] <= vp["height"] + 0.5 and box["x"] >= 0 and box["x"] + box["width"] <= vp["width"] + 0.5


def run_check(json_path=DATA, stamp_path=STAMP):
    res = subprocess.run(["node", "scripts/check-attack-course.mjs", json_path, stamp_path], cwd=ROOT, capture_output=True, text=True)
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
    """Un coup légal hors `keeps` et hors `close` : le contrôle exige donc un refus « échapper »."""
    b = chess.Board(fen)
    good = set(m.get("keeps", [])) | set(m.get("close", []))
    for mv in b.legal_moves:
        if mv.uci() not in good and not mv.promotion:
            return mv.uci()
    return None


# ---------- Mutations du contrôle : chaque copie est retamponnée, le message attendu est exigé ----------
def mutations():
    lesson = COURSE["lessons"]["grec-schema"]
    diag = next(i for i, s in enumerate(lesson["steps"]) if s["kind"] == "diagram")
    line = next(i for i, s in enumerate(lesson["steps"]) if s["kind"] == "line")

    def mut_fen(d):
        d["lessons"]["grec-schema"]["steps"][diag]["fen"] = "4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1"  # Noirs en échec, Blancs au trait
    def mut_move(d):
        d["lessons"]["grec-schema"]["steps"][line]["moves"][0]["san"] = "Bxa7"
    def mut_verdict(d):
        s = d["lessons"]["grec-schema"]["steps"][diag]
        s.pop("claim", None)
        s.pop("fails", None)
        s["text"] = "Ici, le sacrifice est décisif."
    def mut_dash(d):
        d["lessons"]["grec-schema"]["summary"] += " — vite"
    def mut_keeps(d):
        d["lessons"]["grec-schema"]["steps"][line]["moves"][0]["keeps"] = ["a2a3"]
    def mut_only(d):
        m = d["lessons"]["grec-schema"]["steps"][line]["moves"][0]
        m["only"] = True
        m["keeps"] = sorted(set(m["keeps"]) | {"a2a3"})
    def mut_absolute(d):
        d["lessons"]["grec-schema"]["keyPoints"][0] = "Le sacrifice gagne forcément."
    def mut_frozen(d):
        d["lessons"]["grec-schema-bis"] = d["lessons"].pop("grec-schema")
        for ch in d["chapters"]:
            ch["lessons"] = ["grec-schema-bis" if x == "grec-schema" else x for x in ch["lessons"]]
    def mut_forced(d):
        d["lessons"]["grec-schema"]["steps"][line]["moves"][0]["text"] = "Le mat devient forcé."
    def mut_mate(d):
        s = d["lessons"]["grec-schema"]["steps"][diag]
        s["text"] = "Les Blancs ont un mat en trois coups."
        s["eval"] = "+3.10"
    def mut_english(d):
        d["lessons"]["grec-schema"]["steps"][line]["moves"][0]["text"] = "Bxh7+ ouvre le roi."
    def mut_mate_end(d):
        d["lessons"]["grec-schema"]["steps"][line]["end"] = "Mat : la dame en h7, gardée par le cavalier."
    def mut_mate_move(d):
        d["lessons"]["grec-schema"]["steps"][line]["moves"][0]["text"] = "Mat. Le fou a tout pris."
    cases = [
        ("position illégale (le camp sans le trait est en échec)", mut_fen, "est en échec"),
        ("coup injouable", mut_move, "injouable"),
        ("verdict non tamponné", mut_verdict, "sans claim ni fails"),
        ("tiret cadratin", mut_dash, "tiret cadratin"),
        ("keeps sans le coup", mut_keeps, "keeps absent ou sans le coup"),
        ("only avec deux keeps", mut_only, "only mais"),
        ("formulation absolue", mut_absolute, "formulation absolue"),
        ("id figé renommé", mut_frozen, "supprimée ou renommée"),
        ("notation anglaise", mut_english, "notation anglaise"),
        ("« forcé » dans une ligne", mut_forced, "« forcé » sans mat"),
        ("mat annoncé sans mat moteur", mut_mate, "parle de mat sans mat"),
        ("fin de ligne « Mat » sans mat sur l'échiquier", mut_mate_end, "fin : annonce « Mat » sans mat"),
        ("texte de coup « Mat » sans mat sur l'échiquier", mut_mate_move, "coup 1 (Bxh7+) : annonce « Mat » sans mat"),
    ]
    tmp = tempfile.mkdtemp(prefix="cours-roque-")
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
            check(f"[mutation] {label} : contrôle en échec", code == 1 and expected in out, f"(code {code}, attendu « {expected} » : {out.strip()[-200:]})")
            check(f"[mutation] {label} : tampon accepté (le refus vient de la règle visée)", "a changé depuis" not in out, f"({out.strip()[:160]})")
        # Tampon périmé : le contenu change, le tampon non.
        path = os.path.join(tmp, "course.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(RAW.replace('"title": "', '"title": "x', 1))
        code, out = run_check(path, STAMP)
        check("[mutation] tampon périmé : contrôle en échec", code == 1 and "a changé depuis sa vérification" in out, f"(code {code})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def suite(p):
    # ---------- Données ----------
    code, out = run_check()
    check("[données] check-attack-course.mjs passe", code == 0, f"({out.strip()[-300:]})")
    check("[données] 8 chapitres, 16 leçons au moins", len(COURSE["chapters"]) == 8 and N >= 16, f"({len(COURSE['chapters'])} chapitres, {N} leçons)")
    check("[données] leçon grec-schema présente", "grec-schema" in COURSE["lessons"])
    if "grec-schema" not in COURSE["lessons"]:
        return
    if code == 0 and "grec-schema" in COURSE["lessons"]:
        mutations()

    browser = p.chromium.launch(headless=True)
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()

    # ---------- Entrée depuis Apprendre ----------
    page.goto(f"{BASE}/#/apprendre")
    ck.appears("[entrée] carte Démolir le roque", page, "button:has-text('Démolir le roque')")
    check("[entrée] progression 0/N", page.locator("[data-testid='attack-card-progress']").inner_text() == f"0/{N} leçons")
    check("[entrée] carte des finales intacte", page.locator("[data-testid='course-card-progress']").inner_text() == f"0/{FINALES_N} leçons")
    shot(page, "roque_learn_home")
    page.locator("button", has_text="Démolir le roque").click()
    ck.appears("[sommaire] titre", page, "h1:has-text('Démolir le roque')")
    check("[sommaire] URL", page.url.endswith("#/apprendre/roque"), f"({page.url})")
    check("[sommaire] 8 chapitres", page.locator("main section h2").count() == 8)
    check("[sommaire] toutes les leçons listées", page.locator("[data-lesson]").count() == N)
    check("[sommaire] onglet Apprendre allumé", page.locator("nav a[aria-current]", has_text="Apprendre").count() >= 1)
    check("[sommaire] progression 0/N", page.locator("[data-testid='course-progress']").inner_text() == f"0/{N}")
    check("[sommaire] intro prudente (Stockfish)", "Stockfish" in page.locator("main").inner_text())
    shot(page, "roque_index", full_page=True)

    # ---------- Leçon sacrifice grec : diagramme, ligne, refus, indice, flèche, réponse ----------
    lesson = COURSE["lessons"]["grec-schema"]
    total = len(lesson["steps"]) + 1
    first = lesson["steps"][0]
    page.locator("[data-lesson='grec-schema']").click()
    ck.appears("[grec] étape 1", page, f"[data-testid='lesson-step']:has-text('1/{total}')")
    check("[grec] plein écran : nav recouverte", page.evaluate("() => !document.elementFromPoint(196, 840).closest('nav')"))
    check("[grec] diagramme fléché", first["kind"] == "diagram" and page.locator(ARROWHEADS).count() == len(first.get("arrows", [])) > 0, f"({page.locator(ARROWHEADS).count()} flèches)")
    shot(page, "roque_grec_diagram")
    li, line = lines_of("grec-schema")[0]
    for _ in range(li):
        continue_btn(page).click()
        page.wait_for_timeout(200)
    ck.appears("[grec] ligne ouverte", page, f"[data-testid='lesson-step']:has-text('{li + 1}/{total}')")
    check("[grec] Continuer grisé tant que la ligne n'est pas jouée", not continue_btn(page).is_enabled())
    _, fen0, m0, uci0 = student_moves(line)[0]
    wrong = bad_move(fen0, m0)
    tap_move(page, wrong[:2], wrong[2:4], pause=120)
    fb = feedback(page)
    check("[grec] mauvais coup : refus prudent (Stockfish, avantage décisif)", "Selon Stockfish" in fb and "avantage décisif" in fb, f"({fb})")
    check("[grec] indice du coup au premier échec", bool(m0.get("hint")) and "Indice" in fb and m0["hint"][:20] in fb, f"({fb})")
    check("[grec] case du coup refusé en rouge", page.evaluate(f"() => [...document.querySelectorAll(\"[data-square='{wrong[2:4]}'] div\")].some((e) => getComputedStyle(e).backgroundColor.includes('235, 97, 80'))"))
    page.wait_for_timeout(900)
    check("[grec] coup refusé repris", piece_on(page, wrong[:2]) is not None)
    check("[grec] pas de flèche d'aide après un seul essai", page.locator(ARROWHEADS).count() == 0)
    tap_move(page, wrong[:2], wrong[2:4], pause=120)
    page.wait_for_timeout(1000)
    check("[grec] flèche d'aide au 2e essai", page.locator(ARROWHEADS).count() == 1)
    piece = piece_on(page, uci0[:2])
    tap_move(page, uci0[:2], uci0[2:4])
    check("[grec] bon coup accepté et commenté", (m0.get("text") or "Bien joué")[:25] in feedback(page), f"({feedback(page)})")
    check("[grec] pièce arrivée", piece_on(page, uci0[2:4]) == piece, f"({piece_on(page, uci0[2:4])})")
    page.wait_for_timeout(1100)
    reply = chess.Board(fen0)
    reply.push_uci(uci0)
    rmv = reply.parse_san(line["moves"][1]["san"])
    check("[grec] réponse adverse jouée", piece_on(page, rmv.uci()[2:4]) is not None and piece_on(page, rmv.uci()[:2]) is None)
    check("[grec] réponse annoncée dans la bulle", "répondent" in bubble(page))
    shot(page, "roque_grec_line")
    clicks = finish_line(page)
    check("[grec] ligne jouée jusqu'au bout par Solution", continue_btn(page).is_enabled(), f"({clicks} clics)")
    check("[grec] message de fin", line["end"][:30] in feedback(page), f"({feedback(page)})")
    shot(page, "roque_grec_line_done")
    continue_btn(page).click()
    page.wait_for_timeout(200)
    for s in lesson["steps"][li + 1:]:
        if s["kind"] == "line":
            finish_line(page)
            check(f"[grec] ligne « {s['text'][:30]} » jouée jusqu'au bout", continue_btn(page).is_enabled())
        continue_btn(page).click()
        page.wait_for_timeout(200)
    ck.appears("[bilan] À retenir", page, "text=À retenir")
    check("[bilan] points clés affichés", all(k[:30] in page.inner_text("body") for k in lesson["keyPoints"]))
    check("[bilan] pas de S'entraîner (pas d'exercice de finale)", page.locator("button", has_text="S'entraîner").count() == 0)
    check("[bilan] Leçon suivante proposée", page.get_by_role("button", name="Leçon suivante").is_visible())
    shot(page, "roque_summary")
    page.wait_for_timeout(300)
    check("[progrès] une ligne learnSessions roque", page.evaluate(ROWS) == ["roque:grec-schema"], f"({page.evaluate(ROWS)})")
    page.goto(f"{BASE}/#/apprendre/roque/grec-schema?etape={total}")
    ck.appears("[progrès] bilan rouvert", page, "text=À retenir")
    page.wait_for_timeout(400)
    check("[progrès] idempotent", page.evaluate(ROWS) == ["roque:grec-schema"], f"({page.evaluate(ROWS)})")

    # ---------- « Garde aussi » : un coup de keeps autre que celui de la leçon ----------
    alt = None
    for lid in LESSONS:
        for si, s in lines_of(lid):
            for i, fen, m, uci in student_moves(s):
                others = [u for u in m["keeps"] if u != uci and not chess.Move.from_uci(u).promotion]
                if others and alt is None:
                    alt = (lid, si, i, others[0])
    check("[garde aussi] au moins un coup du cours a une autre suite au palier", alt is not None)
    if alt:
        lid, si, i, other = alt
        page.goto(f"{BASE}/#/apprendre/roque/{lid}?etape={si + 1}")
        ck.appears("[garde aussi] ligne ouverte", page, f"[data-testid='lesson-step']:has-text('{si + 1}/')")
        for _ in range(i // 2):
            wait_ready(page)
            solution_btn(page).click()
            page.wait_for_timeout(1000)
        tap_move(page, other[:2], other[2:4], pause=120)
        check("[garde aussi] message « garde aussi »", "garde aussi" in feedback(page), f"({lid} {other} : {feedback(page)})")
        page.wait_for_timeout(900)

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
        page.goto(f"{BASE}/#/apprendre/roque/{lid}?etape={si + 1}")
        ck.appears("[zone grise] ligne ouverte", page, f"[data-testid='lesson-step']:has-text('{si + 1}/')")
        for _ in range(i // 2):
            wait_ready(page)
            solution_btn(page).click()
            page.wait_for_timeout(1000)
        tap_move(page, other[:2], other[2:4], pause=120)
        check("[zone grise] message « moins net »", "moins net" in feedback(page), f"({lid} {other} : {feedback(page)})")
        page.wait_for_timeout(900)

    # ---------- Roque de l'élève par un vrai glisser (Opéra : O-O-O) et réponse faible marquée ----------
    castle = None
    for lid in LESSONS:
        for si, s in lines_of(lid):
            for i, fen, m, uci in student_moves(s):
                if m["san"].startswith("O-O") and castle is None:
                    castle = (lid, si, i, uci)
    check("[roque] une ligne fait roquer l'élève", castle is not None)
    if castle:
        lid, si, i, uci = castle
        page.goto(f"{BASE}/#/apprendre/roque/{lid}?etape={si + 1}")
        ck.appears("[roque] ligne ouverte", page, f"[data-testid='lesson-step']:has-text('{si + 1}/')")
        weak_seen = False
        for _ in range(i // 2):
            wait_ready(page)
            solution_btn(page).click()
            page.wait_for_timeout(1000)
            weak_seen = weak_seen or re.search(r"répondent \S+ \?", bubble(page)) is not None
        wait_ready(page)
        drag_piece(page, uci[:2], uci[2:4])
        page.wait_for_timeout(300)
        check("[roque] grand roque joué au doigt", piece_on(page, "c1") == "wK" and piece_on(page, "d1") == "wR", f"({piece_on(page, 'c1')}, {piece_on(page, 'd1')})")
        weak_moves = [m for _, s in lines_of(lid) for m in s["moves"] if m.get("weak")]
        check("[faible] la ligne du roque a une réponse faible", bool(weak_moves))
        check("[faible] réponse faible marquée « ? » dans la bulle", weak_seen)
        shot(page, "roque_castle")

    # ---------- Id inconnu ----------
    page.goto(f"{BASE}/#/apprendre/roque/inconnue")
    ck.appears("[id inconnu] retour au sommaire", page, "h1:has-text('Démolir le roque')")

    # ---------- Toutes les leçons se jouent jusqu'au bilan ----------
    for lid in LESSONS:
        page.goto(f"{BASE}/#/apprendre/roque/{lid}")
        page.wait_for_selector("[data-testid='lesson-step']", timeout=10000)
        ok = True
        for s in COURSE["lessons"][lid]["steps"]:
            if s["kind"] == "line":
                finish_line(page)
                ok = ok and continue_btn(page).is_enabled()
            continue_btn(page).click()
            page.wait_for_timeout(150)
        ok = ok and page.locator("text=À retenir").is_visible()
        check(f"[toutes] {lid} jouée jusqu'au bilan", ok)
    page.goto(f"{BASE}/#/apprendre/roque")
    ck.appears("[toutes] sommaire N/N", page, f"[data-testid='course-progress']:has-text('{N}/{N}')")
    page.goto(f"{BASE}/#/apprendre")
    ck.appears("[toutes] carte N/N", page, f"[data-testid='attack-card-progress']:has-text('{N}/{N} leçons')")
    check("[toutes] les finales restent à 0", page.locator("[data-testid='course-card-progress']").inner_text() == f"0/{FINALES_N} leçons")
    page.goto(f"{BASE}/#/apprendre/finales")
    ck.appears("[toutes] sommaire des finales à 0", page, f"[data-testid='course-progress']:has-text('0/{FINALES_N}')")
    ctx.close()

    # ---------- 393x660 : échiquier, bulle et Continuer dans l'écran ----------
    ctx = mobile_context(p, browser, ck)
    page = ctx.new_page()
    longest = max(
        ((lid, si) for lid in LESSONS for si, s in enumerate(COURSE["lessons"][lid]["steps"])),
        key=lambda x: len(COURSE["lessons"][x[0]]["steps"][x[1]]["text"]),
    )
    for lid, si in [("grec-schema", 0), ("grec-schema", lines_of("grec-schema")[0][0]), longest]:
        page.goto(f"{BASE}/#/apprendre/roque/{lid}?etape={si + 1}")
        page.wait_for_selector("[id^='chessboard-']", timeout=10000)
        page.wait_for_timeout(500)
        board = page.locator("[id^='chessboard-']").first
        check(f"[660] {lid} étape {si + 1} : échiquier entier à l'écran", in_viewport(page, board), f"({board.bounding_box()})")
        check(f"[660] {lid} étape {si + 1} : Continuer à l'écran", in_viewport(page, continue_btn(page)))
        check(f"[660] {lid} étape {si + 1} : bulle visible", page.locator(".bg-white").first.is_visible())
        check(f"[660] {lid} étape {si + 1} : pas de défilement horizontal", page.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
        shot(page, f"roque_660_{lid}_{si + 1}")
    ctx.close()

    # ---------- 1440x900 ----------
    ctx = desktop_context(browser, ck)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre/roque")
    page.wait_for_selector("[data-lesson]", timeout=10000)
    shot(page, "roque_desktop_index")
    page.goto(f"{BASE}/#/apprendre/roque/grec-schema?etape={lines_of('grec-schema')[0][0] + 1}")
    page.wait_for_selector("[id^='chessboard-']", timeout=10000)
    page.wait_for_timeout(400)
    check("[desktop] Continuer à l'écran", in_viewport(page, continue_btn(page)))
    shot(page, "roque_desktop_line")
    ctx.close()
    browser.close()


ck.run(suite)
