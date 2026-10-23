"""E2E « Mats éclair » (/mats) : entraînement aux schémas de mat pour le bullet.

Ce qui est vérifié :
- données : positions « contre la montre » légales, matériel du schéma, camp fort au trait, deux
  couleurs représentées, fous de couleurs opposées ; positions types des fiches = mats (python-chess) ;
  index de géométrie à jour (`node scripts/prepare-mates-index.mjs --check`) et finissant sur des mats ;
- entrées : carte dans Apprendre, bouton dans Puzzles, onglet Apprendre allumé sur /mats ;
- accueil : quatre familles, cartes, pas de débordement horizontal ;
- fiche : principe nommé, réseau dessiné (flèches, légende par pièce), cadences ;
- contre la montre : mat réel contre Stockfish (deux tours, coups du joueur choisis par le
  Stockfish du repo lancé sous Node), chrono qui ne tourne qu'au trait du joueur, réseau affiché après le mat, drapeau
  qui tombe, UNE ligne `learnSessions` (domaine `mats`) par série, record relu après rechargement ;
- mat en 1 : solution jouée, réseau affiché chrono suspendu, coup faux compté, mats manqués ;
- géométrie (escalier) : le puzzle servi vient de l'index et le réseau nomme l'escalier ;
- aucune nouvelle table ni version Dexie.

Usage : npm run test:e2e -- --suite mats
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time

try:
    import chess
except ImportError:
    sys.exit("python-chess manquant : pip install -r e2e/requirements.txt")

from helpers import BASE, Checker, Solver, click_square, desktop_context, mobile_context, overflow_x, scroll_state, shot

ck = Checker("mats")
check = ck.check
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLLDOWN = os.path.join(ROOT, "node_modules", ".bin", "rolldown")

PATTERN_MATERIAL = {
    "kq": "Q", "kr": "R", "krr": "RR", "kqr": "QR", "kbb": "BB", "kbn": "BN", "kqp": "PQ", "kp": "P",
}


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


# ---------- données ----------

def load_json(rel, default):
    try:
        return json.loads(read(rel))
    except (OSError, ValueError) as e:
        ck.fail(f"[données] {rel} lisible", f"({type(e).__name__})")
        return default


def lesson_fens():
    """`lessonFen` des fiches, lus dans `DRILLS` tel que l'app l'exporte (src/lib/mates.ts bundlé par rolldown, exécuté sous Node)."""
    with tempfile.TemporaryDirectory() as d:
        bundle = os.path.join(d, "mates.mjs")
        r = subprocess.run([ROLLDOWN, "src/lib/mates.ts", "--format", "esm", "--file", bundle], cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            ck.fail("[données] bundle rolldown de mates.ts", (r.stderr or r.stdout)[-300:])
            return {}
        js = "const { DRILLS } = await import(process.argv[1]); console.log(JSON.stringify(Object.fromEntries(DRILLS.filter((d) => d.lessonFen).map((d) => [d.id, d.lessonFen]))))"
        r = subprocess.run(["node", "--input-type=module", "-e", js, "file://" + bundle], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        ck.fail("[données] DRILLS lisible sous Node", r.stderr[-300:])
        return {}
    return json.loads(r.stdout)


def data_suite():
    drills = load_json("src/data/mateDrills.json", {"patterns": {}})["patterns"]
    check("[données] les 8 schémas contre la montre", sorted(drills) == sorted(PATTERN_MATERIAL), f"({sorted(drills)})")
    colors = set()
    for key, positions in drills.items():
        bad = []
        for p in positions:
            b = chess.Board(p["fen"])
            strong = b.turn
            colors.add(strong)
            mine = "".join(sorted(pc.symbol().upper() for pc in b.piece_map().values() if pc.color == strong and pc.piece_type != chess.KING))
            theirs = [pc for pc in b.piece_map().values() if pc.color != strong and pc.piece_type != chess.KING]
            ok = b.is_valid() and not b.is_check() and not b.is_game_over() and mine == PATTERN_MATERIAL[key] and not theirs
            ok = ok and isinstance(p.get("mateIn"), int) and 1 <= p["mateIn"] <= 30
            if key == "kbb":
                sq = [s for s, pc in b.piece_map().items() if pc.piece_type == chess.BISHOP]
                ok = ok and (chess.square_file(sq[0]) + chess.square_rank(sq[0])) % 2 != (chess.square_file(sq[1]) + chess.square_rank(sq[1])) % 2
            if not ok:
                bad.append(p["fen"])
        check(f"[données] {key} : {len(positions)} positions légales, matériel juste, camp fort au trait", len(positions) >= 30 and not bad, f"({bad[:2]})")
    check("[données] le camp fort a tantôt les blancs, tantôt les noirs", colors == {chess.WHITE, chess.BLACK})

    lessons = lesson_fens()
    not_mate = [i for i, f in lessons.items() if not chess.Board(f).is_checkmate()]
    check(f"[données] {len(lessons)} positions types des fiches, toutes des mats", len(lessons) >= 14 and not not_mate, f"({not_mate})")

    res = subprocess.run(["node", "--no-warnings", "scripts/prepare-mates-index.mjs", "--check"], cwd=ROOT, capture_output=True, text=True)
    check("[données] index de géométrie à jour avec le classement de l'app", res.returncode == 0, f"({(res.stdout + res.stderr)[-300:]})")
    index = load_json("src/data/mateIndex.json", {"escalier": []})
    puzzles = {p[0]: p for p in json.loads(read("public/puzzles.json"))}
    missing = [i for ids in index.values() for i in ids if i not in puzzles]
    check("[données] index : tous les puzzles existent", not missing, f"({missing[:3]})")
    small = {t: len(ids) for t, ids in index.items() if len(ids) < 40}
    check("[données] index : au moins 40 positions par géométrie", not small, f"({small})")
    return index, puzzles


# ---------- outils ----------

# Schéma Dexie courant (src/lib/db.ts, version(3) donc 30 côté IndexedDB) : Mats éclair n'y ajoute ni version ni table.
DB_VERSION = 30
DB_STORES = sorted(["games", "ratings", "puzzleAttempts", "rushScores", "mistakes", "learnSessions", "reviews"])

DB_JS = """async () => {
  const d = await new Promise((res, rej) => { const r = indexedDB.open('chess-local'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error) })
  const rows = await new Promise((res) => { const q = d.transaction('learnSessions').objectStore('learnSessions').getAll(); q.onsuccess = () => res(q.result) })
  const out = { version: d.version, stores: [...d.objectStoreNames].sort(), rows: rows.filter((r) => r.domain === 'mats') }
  d.close()
  return out
}"""


# Journal des états du chrono : un observateur de mutations dans la page note l'état du DOM (trait,
# phase, chrono en marche, temps restant) après chaque commit React. La réponse de Stockfish peut tenir
# en 10 ms quand le roi n'a qu'un coup légal : un sondage depuis Playwright la rate, l'observateur non.
CLOCK_LOG_JS = """() => {
  const run = document.querySelector('[data-run]')
  const log = (window.__clockLog = [])
  const snap = () => {
    const t = run.querySelector('[role=timer]')
    log.push({ fen: run.dataset.fen, phase: run.dataset.phase, running: t ? t.dataset.running : null, ms: t ? Number(t.dataset.ms) : null })
  }
  new MutationObserver(snap).observe(run, { attributes: true, subtree: true, attributeFilter: ['data-fen', 'data-phase', 'data-running', 'data-ms'] })
  snap()
}"""


def mats_rows(page, n=None, timeout=5000):
    end = time.time() + timeout / 1000
    while True:
        dump = page.evaluate(DB_JS)
        if n is None or len(dump["rows"]) >= n or time.time() > end:
            return dump
        page.wait_for_timeout(200)


def attr(page, sel, name):
    loc = page.locator(sel)
    return loc.first.get_attribute(name) if loc.count() else None


def play_uci(page, uci, after=150):
    click_square(page, uci[:2])
    page.wait_for_timeout(120)
    click_square(page, uci[2:4])
    page.wait_for_timeout(after)
    if len(uci) == 5:
        name = {"q": "Dame", "r": "Tour", "b": "Fou", "n": "Cavalier"}[uci[4]]
        page.get_by_role("button", name=name, exact=True).first.click()
        page.wait_for_timeout(150)


# ---------- parcours ----------

def entry_suite(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre")
    ok = ck.appears("[entrée] carte Mats éclair dans Apprendre", page, "main a:has-text('Mats éclair')", timeout=10000)
    if ok:
        page.locator("main a", has_text="Mats éclair").click()
        ck.appears("[entrée] Apprendre → /mats", page, "h1:has-text('Mats éclair')", timeout=5000)
        check("[entrée] URL /mats", "#/mats" in page.url, f"({page.url})")
    page.goto(f"{BASE}/#/puzzles")
    if ck.appears("[entrée] bouton Mats éclair dans Puzzles", page, "main button:has-text('Mats éclair')", timeout=15000):
        page.locator("main button", has_text="Mats éclair").click()
        page.wait_for_timeout(500)
        check("[entrée] Puzzles → /mats", "#/mats" in page.url, f"({page.url})")
    page.goto(f"{BASE}/#/mats")
    ck.appears("[accueil] titre", page, "h1:has-text('Mats éclair')", timeout=10000)
    cur = page.locator("nav a[aria-current]").last
    check("[accueil] onglet Apprendre allumé", cur.count() > 0 and "Apprendre" in cur.inner_text(), f"({cur.inner_text() if cur.count() else '-'})")
    sections = page.locator("[data-section]").evaluate_all("els => els.map(e => e.dataset.section)")
    check("[accueil] quatre familles d'exercices", sections == ["chrono", "mateIn", "geo", "motif"], f"({sections})")
    n = {s: page.locator(f"[data-section='{s}'] [data-drill]").count() for s in sections}
    check("[accueil] cartes : 9 contre la montre, 4 mat en N, 5 géométrie, 14 motifs", n == {"chrono": 9, "mateIn": 4, "geo": 5, "motif": 14}, f"({n})")
    titles = page.locator("[data-section='chrono'] [data-drill] span.font-bold").all_inner_texts()
    check("[accueil] titres exacts des cartes contre la montre (dame + pion nommé contre roi)",
          titles == ["Dame", "Tour", "Deux tours", "Dame + tour", "Deux fous", "Fou + cavalier", "Dame + pion contre roi", "Promotion puis mat", "Mélange"], f"({titles})")
    for name in ["Mat du couloir", "Mat étouffé", "Anastasie", "Boden", "Mat arabe", "Damiano", "épaulettes"]:
        check(f"[accueil] motif « {name} »", page.locator("[data-section='motif'] [data-drill]", has_text=name).count() > 0)
    check("[accueil] pas de débordement horizontal (393 px)", overflow_x(page) == 0, f"({overflow_x(page)})")
    shot(page, "mats_hub_393x852")
    shot(page, "mats_hub_393x852_full", full_page=True)

    # Fiche « Deux tours » : principe, réseau, cadences.
    page.locator("[data-drill='chrono-krr']").click()
    ck.appears("[fiche] fiche Deux tours", page, "[data-sheet='chrono-krr']", timeout=5000)
    check("[fiche] URL ?d= (retour arrière = accueil)", "d=chrono-krr" in page.url, f"({page.url})")
    check("[fiche] principe nommé (escalier)", "Escalier" in (page.locator("[data-principle]").inner_text() or ""))
    check("[fiche] réseau calculé : escalier", "escalier" in (attr(page, "[data-net]", "data-net") or ""), f"({attr(page, '[data-net]', 'data-net')})")
    legend = page.locator("[data-net-piece]").all_inner_texts()
    check("[fiche] légende : une phrase par pièce, lignes nommées", len(legend) == 2 and any("7e rangée" in t for t in legend) and any("donne l'échec" in t for t in legend), f"({legend})")
    arrows = page.locator("[data-sheet] svg line, [data-sheet] svg path").count()
    check("[fiche] flèches dessinées sur l'échiquier", arrows >= 2, f"({arrows})")
    radios = page.get_by_role("radio").all_inner_texts()
    check("[fiche] cadences 15 s, 30 s, 1 min, 2 min", radios == ["15 s", "30 s", "1 min", "2 min"], f"({radios})")
    check("[fiche] DTM des positions affiché", page.locator("text=vérifiées sur les tables de finales").count() > 0)
    shot(page, "mats_fiche_krr_393x852", full_page=True)
    page.go_back()
    page.wait_for_timeout(400)
    check("[fiche] retour arrière → accueil", page.locator("[data-section]").count() == 4)

    # Fiche ouverte depuis le hub DÉFILÉ : seule la requête change (`?d=`), la coquille doit
    # quand même remettre <main> en haut. Damiano : carte du bas, fiche avec échiquier (lessonFen),
    # donc plus haute que la fenêtre : sans correctif, le défilement du hub reste.
    page.evaluate("() => { document.querySelector('main').scrollTop = 9999 }")
    page.wait_for_timeout(200)
    st = scroll_state(page)
    check("[fiche défilée] précondition : hub défilé", st["mainScrollable"] and st["mainScrollTop"] > 0, f"({st})")
    page.locator("[data-drill='motif-damiano']").click()
    ck.appears("[fiche défilée] fiche Damiano ouverte", page, "[data-sheet='motif-damiano'] [data-square='g1']", timeout=5000)
    page.wait_for_timeout(300)
    st = scroll_state(page)
    check("[fiche défilée] précondition : la fiche défile (sinon scrollTop vaudrait 0 par construction)", st["mainScrollable"], f"({st})")
    check("[fiche défilée] fiche ouverte en haut (<main> remis à zéro sur changement de requête)", st["mainScrollTop"] == 0, f"({st})")
    ctx.close()


def chrono_suite(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/mats?d=chrono-krr")
    ck.appears("[chrono] fiche", page, "[data-sheet='chrono-krr']", timeout=10000)
    page.get_by_role("radio", name="2 min").click()
    page.get_by_role("button", name="Commencer").click()
    if not ck.appears("[chrono] série lancée", page, "[data-run='chrono']", timeout=5000):
        ctx.close()
        return
    fen0 = attr(page, "[data-run]", "data-fen")
    me = chess.Board(fen0).turn
    page.wait_for_timeout(1200)
    ms1 = int(attr(page, "[role=timer]", "data-ms"))
    page.wait_for_timeout(1000)
    ms2 = int(attr(page, "[role=timer]", "data-ms"))
    check("[chrono] le chrono tourne au trait du joueur", 700 <= ms1 - ms2 <= 1500, f"({ms1} → {ms2})")
    shot(page, "mats_chrono_393x852")

    solver = Solver()
    won = False
    stopped_ok = True
    frozen_seen = 0
    page.evaluate(CLOCK_LOG_JS)
    replies = []
    for _ in range(40):
        phase = attr(page, "[data-run]", "data-phase")
        if phase != "play":
            won = phase == "won"
            break
        fen = attr(page, "[data-run]", "data-fen")
        board = chess.Board(fen)
        if board.turn != me:
            page.wait_for_timeout(150)
            continue
        move = chess.Move.from_uci(solver.best(fen))
        play_uci(page, move.uci(), after=0)
        board.push(move)
        if board.is_checkmate() or move.promotion:
            page.wait_for_timeout(300)
            continue
        # Pendant la réponse de Stockfish, le chrono du joueur est arrêté et ne bouge plus : chaque état
        # du DOM au trait du moteur doit montrer le chrono à l'arrêt, au même temps restant.
        end = time.time() + 8
        while time.time() < end:
            phase, turn_fen = page.evaluate("() => { const r = document.querySelector('[data-run]'); return [r?.dataset.phase, r?.dataset.fen] }")
            if phase != "play" or not turn_fen or chess.Board(turn_fen).turn == me:
                break
            page.wait_for_timeout(20)
        snaps = page.evaluate("() => window.__clockLog.splice(0)")
        engine_turn = [s for s in snaps if s["phase"] == "play" and s["fen"] and chess.Board(s["fen"]).turn != me]
        if engine_turn:
            frozen_seen += 1
            ms = [s["ms"] for s in engine_turn]
            stopped_ok = stopped_ok and all(s["running"] == "false" for s in engine_turn) and max(ms) - min(ms) < 50
        frozen = [s for s in engine_turn if s["running"] == "false"]
        replies.append(f"{len(engine_turn)} éch. dont {len(frozen)} arrêtés")
    solver.close()
    check("[chrono] mat contre Stockfish (deux tours)", won, f"(phase {attr(page, '[data-run]', 'data-phase')}, {attr(page, '[data-run]', 'data-fen')})")
    check("[chrono] chrono arrêté et figé pendant chaque réponse de Stockfish", stopped_ok and frozen_seen >= 1,
          f"({frozen_seen} réponses observées, arrêté={stopped_ok}, par réponse : {replies})")
    if won:
        check("[chrono] score 1", attr(page, "[data-score]", "data-score") == "1")
        check("[chrono] réseau du mat affiché (légende)", page.locator("[data-net-piece]").count() >= 1)
        check("[chrono] temps du mat affiché", page.locator("text=/✓ Mat en \\d+,\\d s/").count() == 1)
        shot(page, "mats_chrono_mat_393x852", full_page=True)
        rows = mats_rows(page, 1)["rows"]
        check("[chrono] série enregistrée dès le premier mat", len(rows) == 1 and rows[0]["score"] == 1 and rows[0]["itemId"] == "chrono-krr:120s", f"({rows})")
        page.wait_for_timeout(1800)
        check("[chrono] position suivante, chrono plein", attr(page, "[data-run]", "data-phase") == "play" and int(attr(page, "[role=timer]", "data-ms")) > 115_000)
    page.get_by_role("button", name="Arrêter la série").click()
    ck.appears("[chrono] bilan de série", page, "[data-run-over]", timeout=3000)
    if won:
        ck.appears("[chrono] nouveau record annoncé", page, "text=Nouveau record", timeout=3000)
    dump = mats_rows(page)
    check("[chrono] UNE ligne pour la série (mise à jour, pas de doublon)", len(dump["rows"]) == 1, f"({dump['rows']})")
    shot(page, "mats_chrono_bilan_393x852", full_page=True)
    summary_round_trip(page, "[chrono:analyse]", "chrono-krr", won, 1)

    # Drapeau : 15 s sans jouer.
    page.get_by_role("button", name="Menu").click()
    page.get_by_role("radio", name="15 s").click()
    page.get_by_role("button", name="Commencer").click()
    page.wait_for_timeout(500)
    ck.appears("[chrono] drapeau tombé après 15 s", page, "[data-run-over]", timeout=18000)
    check("[chrono] raison : temps écoulé", page.locator("text=Temps écoulé").count() == 1)
    dump = mats_rows(page, 2)
    keys = sorted(r["itemId"] for r in dump["rows"])
    check("[chrono] deux séries, deux lignes", keys == ["chrono-krr:120s", "chrono-krr:15s"], f"({keys})")
    check("[données] pas de nouvelle version ni table Dexie", dump["version"] == DB_VERSION and dump["stores"] == DB_STORES, f"({dump['version']}, {dump['stores']})")

    # Rechargement : records relus depuis IndexedDB.
    page.goto(f"{BASE}/#/mats")
    page.reload()
    if won:
        ck.appears("[records] record de la carte relu", page, "[data-drill='chrono-krr']:has-text('Record 1')", timeout=8000)
        check("[records] total des mats", page.locator("[data-total-mates]").inner_text() == "1")
    ctx.close()


def summary_round_trip(page, tag, drill_id, record, n_rows):
    """Bilan d'une série contre la montre close : « Analyser avec Stockfish » ouvre la dernière
    position, « Retour au bilan » rend le même bilan (position, score, record), pendule arrêtée,
    sans nouvelle ligne `mats`."""
    if not ck.appears(f"{tag} bouton du bilan", page, "[data-run-over] button:has-text('Analyser avec Stockfish')", timeout=3000):
        return
    fen = attr(page, "[data-run]", "data-fen")
    score = attr(page, "[data-score]", "data-score")
    ms = attr(page, "[role=timer]", "data-ms")
    page.locator("[data-run-over] button", has_text="Analyser avec Stockfish").click()
    if not ck.appears(f"{tag} « Retour au bilan » dans l'analyseur", page, "button:has-text('Retour au bilan')", timeout=10000):
        return
    check(f"{tag} analyseur ouvert", page.evaluate("() => location.hash") == "#/analyse")
    page.get_by_role("button", name="Retour au bilan").click()
    if not ck.appears(f"{tag} retour : bilan restauré", page, "[data-run][data-phase='over'] [data-run-over]", timeout=10000):
        return
    check(f"{tag} retour : fiche du schéma dans l'URL", f"d={drill_id}" in page.url, f"({page.url})")
    check(f"{tag} retour : même position", attr(page, "[data-run]", "data-fen") == fen, f"({attr(page, '[data-run]', 'data-fen')} vs {fen})")
    check(f"{tag} retour : même score", attr(page, "[data-score]", "data-score") == score)
    check(f"{tag} retour : même annonce de record", (page.locator("text=Nouveau record").count() == 1) == bool(record))
    page.wait_for_timeout(1200)
    check(f"{tag} retour : pendule arrêtée au même temps", attr(page, "[role=timer]", "data-ms") == ms, f"({attr(page, '[role=timer]', 'data-ms')} vs {ms})")
    dump = mats_rows(page)
    check(f"{tag} retour : aucune écriture de plus", len(dump["rows"]) == n_rows, f"({dump['rows']})")


def puzzle_suite(p, browser, index, puzzles):
    ctx = mobile_context(p, browser, ck, standalone=False)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/mats?d=mate-1")
    ck.appears("[mat en 1] fiche", page, "[data-sheet='mate-1']", timeout=10000)
    ck.appears("[mat en 1] puzzles chargés", page, "button:has-text('Commencer'):not([disabled])", timeout=30000)
    page.get_by_role("radio", name="3 min").click()
    page.get_by_role("button", name="Commencer").click()
    ck.appears("[mat en 1] série lancée", page, "[data-run='puzzle']", timeout=5000)
    pid = attr(page, "[data-run]", "data-puzzle")
    pz = puzzles.get(pid)
    pz2 = None
    check("[mat en 1] puzzle mat en 1, 12 pièces au plus", pz is not None and "mateIn1" in pz[4].split() and len(re.sub(r"[^a-zA-Z]", "", pz[1].split()[0])) <= 12, f"({pid})")
    shot(page, "mats_rush_393x660")
    if pz:
        page.wait_for_timeout(900)
        # Chaque rendu (phase, chrono, légende) est journalisé dans la page : sous charge, une
        # capture ou une attente côté Playwright peut dépasser les 1,5 s du réseau et lire le
        # puzzle suivant, où le chrono a légitimement repris.
        page.evaluate("""() => {
            window.__netLog = []
            const rec = () => {
                const run = document.querySelector('[data-run]'), timer = document.querySelector('[role=timer]')
                if (run && timer) window.__netLog.push([run.dataset.phase, +timer.dataset.ms, performance.now(),
                    document.querySelectorAll('[data-net-piece]').length])
            }
            rec()
            window.__netObs = new MutationObserver(rec)
            window.__netObs.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['data-ms', 'data-phase'] })
        }""")
        play_uci(page, pz[2].split()[1])
        ck.appears("[mat en 1] réseau affiché après le mat", page, "[data-run][data-phase='net']", timeout=3000)
        check("[mat en 1] score 1", attr(page, "[data-score]", "data-score") == "1")
        shot(page, "mats_rush_reseau_393x660")
        ck.appears("[mat en 1] puzzle suivant", page, "[data-run][data-phase='play']", timeout=3000)
        log = page.evaluate("() => { window.__netObs.disconnect(); return window.__netLog }")
        net = [e for e in log if e[0] == "net"]
        check("[mat en 1] légende du réseau", any(e[3] >= 1 for e in net), f"({len(net)} rendus du réseau)")
        net_ms = sorted({e[1] for e in net})
        after = [e for e in log if net and e[2] > net[-1][2]]
        # Durée du réseau : du premier rendu « net » au premier rendu qui le remplace.
        shown = after[0][2] - net[0][2] if after else 0
        check("[mat en 1] chrono suspendu pendant le réseau",
              len(net_ms) == 1 and bool(after) and after[0][0] == "play" and shown >= 1000,
              f"(chrono pendant le réseau : {net_ms}, réseau affiché {round(shown)} ms)")
        pid2 = attr(page, "[data-run]", "data-puzzle")
        check("[mat en 1] nouveau puzzle", pid2 and pid2 != pid)
        pz2 = puzzles.get(pid2)
        if pz2:
            page.wait_for_timeout(900)
            b = chess.Board(pz2[1])
            b.push_uci(pz2[2].split()[0])
            wrong = None
            for m in b.legal_moves:
                b.push(m)
                mate = b.is_checkmate()
                b.pop()
                if not mate and not m.promotion:
                    wrong = m.uci()
                    break
            play_uci(page, wrong)
            page.wait_for_timeout(300)
            check("[mat en 1] coup faux compté", page.locator("[aria-label='1 erreur sur 3']").count() == 1)
            page.wait_for_timeout(900)
    page.get_by_role("button", name="Arrêter la série").click()
    ck.appears("[mat en 1] bilan", page, "[data-run-over]", timeout=3000)
    check("[mat en 1] mat manqué listé", page.locator("button:has-text('Voir la solution')").count() == 1)
    rows = mats_rows(page, 1)["rows"]
    check("[mat en 1] série enregistrée", any(r["itemId"] == "mate-1:3min" and r["score"] == 1 for r in rows), f"({rows})")
    shot(page, "mats_rush_bilan_393x660", full_page=True)
    missed_before = page.locator("button:has-text('Voir la solution')").inner_text()
    page.locator("button:has-text('Voir la solution')").click()
    if ck.appears("[mat en 1] « Retour au bilan » dans l'analyseur", page, "button:has-text('Retour au bilan')", timeout=10000):
        check("[mat en 1] solution ouverte dans l'analyse", "#/analyse" in page.url, f"({page.url})")
        page.get_by_role("button", name="Retour au bilan").click()
        # Série close : le retour rend son bilan (pas la fiche), sans relancer de chrono.
        if ck.appears("[mat en 1] retour : bilan restauré", page, "[data-run='puzzle'][data-phase='over'] [data-run-over]", timeout=30000):
            check("[mat en 1] retour : même mat manqué listé", page.locator("button:has-text('Voir la solution')").count() == 1
                  and page.locator("button:has-text('Voir la solution')").inner_text() == missed_before)
            check("[mat en 1] retour : même score", attr(page, "[data-score]", "data-score") == "1")
            check("[mat en 1] retour : même erreur comptée", page.locator("[aria-label='1 erreur sur 3']").count() == 1)
            page.wait_for_timeout(600)
            rows = mats_rows(page)["rows"]
            check("[mat en 1] retour : aucune écriture de plus", len([r for r in rows if r["itemId"] == "mate-1:3min"]) == 1, f"({rows})")
            page.get_by_role("button", name="Menu").click()
            ck.appears("[mat en 1] Menu : fiche Mat en 1", page, "[data-sheet='mate-1']", timeout=5000)

    # Géométrie : escalier, en survie.
    page.goto(f"{BASE}/#/mats?d=geo-escalier")
    ck.appears("[géométrie] puzzles chargés", page, "button:has-text('Commencer'):not([disabled])", timeout=30000)
    check("[géométrie] fiche : réseau escalier", "escalier" in (attr(page, "[data-net]", "data-net") or ""))
    page.get_by_role("radio", name="Survie").click()
    page.get_by_role("button", name="Commencer").click()
    ck.appears("[géométrie] série lancée", page, "[data-run='puzzle']", timeout=5000)
    gid = attr(page, "[data-run]", "data-puzzle")
    check("[géométrie] puzzle tiré de l'index escalier", gid in index["escalier"], f"({gid})")
    gz = puzzles.get(gid)
    if gz:
        moves = gz[2].split()
        b = chess.Board(gz[1])
        b.push_uci(moves[0])
        page.wait_for_timeout(900)
        for i in range(1, len(moves), 2):
            play_uci(page, moves[i])
            b.push_uci(moves[i])
            if i + 1 < len(moves):
                b.push_uci(moves[i + 1])
                page.wait_for_timeout(700)
        ck.appears("[géométrie] réseau après le mat", page, "[data-run][data-phase='net']", timeout=3000)
        text = page.locator("[data-run]").inner_text()
        check("[géométrie] principe : escalier nommé", "Escalier" in text, f"({text[:200]})")
        shot(page, "mats_geo_escalier_393x660")
    page.get_by_role("button", name="Arrêter la série").click()
    ctx.close()


def desktop_suite(p, browser):
    ctx = desktop_context(browser, ck)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/mats")
    ck.appears("[desktop] accueil", page, "[data-section='motif']", timeout=10000)
    check("[desktop] pas de débordement horizontal", overflow_x(page) == 0)
    shot(page, "mats_hub_1440x900")
    page.goto(f"{BASE}/#/mats?d=motif-smotheredMate")
    ck.appears("[desktop] fiche motif : diagramme tiré d'un puzzle", page, "[data-net]", timeout=30000)
    check("[desktop] fiche motif : le diagramme est un mat", (attr(page, "[data-net]", "data-net") or "aucun") != "aucun")
    shot(page, "mats_fiche_motif_1440x900")
    ctx.close()


def suite(p):
    index, puzzles = data_suite()
    browser = p.chromium.launch(headless=True)
    entry_suite(p, browser)
    chrono_suite(p, browser)
    puzzle_suite(p, browser, index, puzzles)
    desktop_suite(p, browser)
    browser.close()


ck.run(suite)
