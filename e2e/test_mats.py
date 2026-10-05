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
import time

try:
    import chess
except ImportError:
    sys.exit("python-chess manquant : pip install -r e2e/requirements.txt")

from helpers import BASE, Checker, click_square, desktop_context, mobile_context, overflow_x, shot

ck = Checker("mats")
check = ck.check
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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

    src = read("src/lib/mates.ts") if os.path.exists(os.path.join(ROOT, "src/lib/mates.ts")) else ""
    fens = re.findall(r"'([1-8pnbrqkPNBRQK/]{15,}) ([wb]) - - 0 1'", src)
    not_mate = [f for f, t in fens if not chess.Board(f"{f} {t} - - 0 1").is_checkmate()]
    check(f"[données] {len(fens)} positions types des fiches, toutes des mats", len(fens) >= 14 and not not_mate, f"({not_mate})")

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

DB_JS = """async () => {
  const d = await new Promise((res, rej) => { const r = indexedDB.open('chess-local'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error) })
  const rows = await new Promise((res) => { const q = d.transaction('learnSessions').objectStore('learnSessions').getAll(); q.onsuccess = () => res(q.result) })
  const out = { version: d.version, stores: [...d.objectStoreNames].sort(), rows: rows.filter((r) => r.domain === 'mats') }
  d.close()
  return out
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
        glyph = {"q": "♕♛", "r": "♖♜", "b": "♗♝", "n": "♘♞"}[uci[4]]
        page.locator("button", has_text=re.compile(f"^[{glyph}]$")).first.click()
        page.wait_for_timeout(150)


class Solver:
    """Le camp fort de la suite : le Stockfish du repo (node_modules, build lite mono-thread) lancé
    sous Node, en UCI. Le joueur simulé mate donc vraiment, quelle que soit la défense de l'app."""

    def __init__(self):
        self.proc = subprocess.Popen(
            ["node", "node_modules/stockfish/bin/stockfish-18-lite-single.js"],
            cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        self._send("uci")
        self._until("uciok")

    def _send(self, cmd):
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()

    def _until(self, prefix):
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("Stockfish (Node) s'est arrêté")
            if line.startswith(prefix):
                return line.strip()

    def best(self, fen):
        self._send(f"position fen {fen}")
        self._send("go depth 14")
        return self._until("bestmove").split()[1]

    def close(self):
        try:
            self._send("quit")
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


# ---------- parcours ----------

def entry_suite(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre")
    ok = ck.appears("[entrée] carte Mats éclair dans Apprendre", page, "main button:has-text('Mats éclair')", timeout=10000)
    if ok:
        page.locator("main button", has_text="Mats éclair").click()
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
    for name in ["Dame", "Tour", "Deux tours", "Dame + tour", "Fou + cavalier", "Deux fous", "Dame + pion", "Promotion puis mat"]:
        check(f"[accueil] carte « {name} »", page.locator("[data-section='chrono'] [data-drill]", has_text=re.compile(f"^.*{re.escape(name)}")).count() > 0)
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
        # Sans attente après le coup : la réponse du moteur (150 ms) doit être observée.
        play_uci(page, move.uci(), after=0)
        board.push(move)
        if board.is_checkmate() or move.promotion:
            page.wait_for_timeout(300)
            continue
        # Pendant la réponse de Stockfish, le chrono du joueur est arrêté et ne bouge plus.
        samples = []
        end = time.time() + 8
        while time.time() < end and attr(page, "[data-run]", "data-phase") == "play":
            running, ms, turn_fen = page.evaluate("""() => {
              const t = document.querySelector('[role=timer]'), r = document.querySelector('[data-run]')
              return [t.dataset.running, Number(t.dataset.ms), r.dataset.fen]
            }""")
            if chess.Board(turn_fen).turn == me:
                break
            samples.append((running, ms))
            page.wait_for_timeout(10)
        frozen = [ms for running, ms in samples if running == "false"]
        if len(frozen) >= 2:
            frozen_seen += 1
            stopped_ok = stopped_ok and max(frozen) - min(frozen) < 50
        stopped_ok = stopped_ok and all(running == "false" for running, _ in samples)
    solver.close()
    check("[chrono] mat contre Stockfish (deux tours)", won, f"(phase {attr(page, '[data-run]', 'data-phase')}, {attr(page, '[data-run]', 'data-fen')})")
    check("[chrono] chrono arrêté et figé pendant chaque réponse de Stockfish", stopped_ok and frozen_seen >= 1, f"({frozen_seen} réponses observées)")
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
    check("[données] pas de nouvelle version ni table Dexie", dump["version"] == 20 and "learnSessions" in dump["stores"] and len(dump["stores"]) == 6, f"({dump['version']}, {dump['stores']})")

    # Rechargement : records relus depuis IndexedDB.
    page.goto(f"{BASE}/#/mats")
    page.reload()
    if won:
        ck.appears("[records] record de la carte relu", page, "[data-drill='chrono-krr']:has-text('Record 1')", timeout=8000)
        check("[records] total des mats", page.locator("[data-total-mates]").inner_text() == "1")
    ctx.close()


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
    check("[mat en 1] puzzle mat en 1, 12 pièces au plus", pz is not None and "mateIn1" in pz[4].split() and len(re.sub(r"[^a-zA-Z]", "", pz[1].split()[0])) <= 12, f"({pid})")
    shot(page, "mats_rush_393x660")
    if pz:
        page.wait_for_timeout(900)
        play_uci(page, pz[2].split()[1])
        ck.appears("[mat en 1] réseau affiché après le mat", page, "[data-run][data-phase='net']", timeout=3000)
        ms1 = int(attr(page, "[role=timer]", "data-ms"))
        check("[mat en 1] score 1", attr(page, "[data-score]", "data-score") == "1")
        check("[mat en 1] légende du réseau", page.locator("[data-net-piece]").count() >= 1)
        shot(page, "mats_rush_reseau_393x660")
        page.wait_for_timeout(800)
        ms2 = int(attr(page, "[role=timer]", "data-ms"))
        check("[mat en 1] chrono suspendu pendant le réseau", attr(page, "[data-run]", "data-phase") == "net" and abs(ms1 - ms2) < 150, f"({ms1} → {ms2})")
        ck.appears("[mat en 1] puzzle suivant", page, "[data-run][data-phase='play']", timeout=3000)
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
    page.locator("button:has-text('Voir la solution')").click()
    page.wait_for_timeout(1500)
    check("[mat en 1] solution ouverte dans l'analyse", "#/analyse" in page.url, f"({page.url})")
    back = page.get_by_role("button", name=re.compile("Retour"))
    if ck.appears("[mat en 1] bouton retour de l'analyse", page, "button:has-text('Retour')", timeout=5000):
        back.first.click()
        ck.appears("[mat en 1] retour sur la fiche Mat en 1", page, "[data-sheet='mate-1']", timeout=5000)

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
