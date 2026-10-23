"""E2E « Finales au chrono » (/finales/chrono) : finales théoriques à gagner ou à tenir nulle contre
Stockfish pleine force, avec très peu de temps.

Ce qui est vérifié :
- données : banque à jour avec ses sources et son tampon (`scripts/prepare-endgame-clock.py
  --check`), ids de familles figés (clés des records), positions légales, joueur au trait, objectif
  cohérent, lignes optimales légales, deux couleurs, aucune finale `chrono` dans endgames.json ;
- seuils de l'app : le Stockfish lite du repo, avec la recherche de verdict de l'app (VERDICT_NODES
  nœuds, table de hachage vidée, donc indépendante de la charge), sur chaque position des lignes
  optimales où le moteur a le trait : nulle à tenir => moteur sous HOLD_MAX_CP, gain => défenseur
  sous -WIN_DRAWN_CP (les constantes sont lues dans src/lib/endgameClock.ts bundlé), et même score
  pour une position rejugée après les autres ;
- logique pure (bundle rolldown sous Node) : fins par les règles avant la conversion, conversion
  par promotion ou matériel raflé, sous-promotion refusée, tenue de nulle, gain envolé, cadences,
  ordre des séries ;
- entrées : carte dans Apprendre, onglet Apprendre allumé, familles par thème, pas de débordement ;
- pendule sous horloge Playwright contrôlée : drapeau exact, incrément exact, pendule arrêtée et
  figée pendant la réponse du moteur (retenue à la frontière UCI), prémouvement débité de 100 ms
  puis incrément, drapeau au débit sans jouer ;
- parties réelles contre le Stockfish de l'app : gain (promotion) et nulle tenue avec les coups du
  Stockfish du repo, gain raté par une nulle ; UNE ligne `learnSessions` (domaine `endgame-clock`)
  par série, record relu après rechargement, aucune nouvelle version Dexie.

Usage : npm run test:e2e -- --suite finales_chrono
"""
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone

import chess

from helpers import BASE, HOLD_BESTMOVE, Checker, Solver, desktop_context, mobile_context, overflow_x, shot, tap_move

ck = Checker("finales_chrono")
check = ck.check
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLLDOWN = os.path.join(ROOT, "node_modules", ".bin", "rolldown")

# Clés des records (itemId `<famille>:<cadence>`) : une famille ne se renomme jamais.
FROZEN = [
    "kp-square", "kp-opposition-1", "kp-king-front", "opposition-distant", "two-pawns", "kp-defense-front",
    "active-king-draw", "lucena", "philidor", "r-vs-p", "q-vs-r", "q-vs-p7", "q-vs-p7-c", "q-vs-p7-a", "r-vs-b",
    "r-vs-n", "r-vs-n-win", "r-vs-p-draw",
]
GOALS = {"win": {"mate", "promote", "capture"}, "draw": {"hold"}}

# Schéma Dexie courant (src/lib/db.ts, version(3) donc 30 côté IndexedDB) : aucune version ni table en plus.
DB_VERSION = 30
DB_STORES = sorted(["games", "ratings", "puzzleAttempts", "rushScores", "mistakes", "learnSessions", "reviews"])

DB_JS = """async () => {
  const d = await new Promise((res, rej) => { const r = indexedDB.open('chess-local'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error) })
  const rows = await new Promise((res) => { const q = d.transaction('learnSessions').objectStore('learnSessions').getAll(); q.onsuccess = () => res(q.result) })
  const out = { version: d.version, stores: [...d.objectStoreNames].sort(), rows: rows.filter((r) => r.domain === 'endgame-clock') }
  d.close()
  return out
}"""


def read_json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def bundle_eval(js):
    """Exécute `js` sous Node avec `m` = src/lib/endgameClock.ts bundlé par rolldown ; rend son JSON."""
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "endgameClock.mjs")
        r = subprocess.run([ROLLDOWN, "src/lib/endgameClock.ts", "--format", "esm", "--file", out], cwd=ROOT, capture_output=True, text=True)
        if r.returncode != 0:
            ck.fail("[pur] bundle rolldown de endgameClock.ts", (r.stderr or r.stdout)[-300:])
            return None
        code = f"const m = await import(process.argv[1]);\n{js}"
        r = subprocess.run(["node", "--input-type=module", "-e", code, "file://" + out], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        ck.fail("[pur] script Node", r.stderr[-400:])
        return None
    return json.loads(r.stdout)


# ---------- données ----------

def data_suite():
    r = subprocess.run(["python3", "scripts/prepare-endgame-clock.py", "--check"], cwd=ROOT, capture_output=True, text=True)
    check("[données] banque à jour avec ses sources et son tampon", r.returncode == 0, f"({(r.stdout + r.stderr).strip()[-300:]})")
    data = read_json("src/data/endgameClock.json")
    fams = data["families"]
    check("[données] ids de familles figés (clés des records)", [f["id"] for f in fams] == FROZEN, f"({[f['id'] for f in fams]})")
    bad, colors, count, seen = [], set(), 0, set()
    for f in fams:
        if f["goal"] not in GOALS.get(f["objective"], set()) or not f["positions"] or not f["principle"]:
            bad.append(f"{f['id']} : objectif, goal ou principe")
        for p in f["positions"]:
            count += 1
            b = chess.Board(p["fen"])
            colors.add(b.turn)
            if not b.is_valid() or b.is_game_over() or len(b.piece_map()) > 7 or p["id"].split(".")[0] != f["id"] or p["id"] in seen:
                bad.append(p["id"])
                continue
            seen.add(p["id"])
            try:
                for m in p["line"]:
                    b.push_uci(m)
            except ValueError:
                bad.append(f"{p['id']} : ligne illégale")
            if not p["line"]:
                bad.append(f"{p['id']} : ligne vide")
    check(f"[données] {len(fams)} familles, {count} positions légales, lignes légales, objectifs cohérents", not bad and count >= 40, f"({bad[:4]})")
    check("[données] le joueur a tantôt les blancs, tantôt les noirs", colors == {chess.WHITE, chess.BLACK})
    ids = [e["id"] for e in read_json("src/data/endgames.json")]
    check("[données] aucune finale d'id `chrono` (route statique /finales/chrono)", "chrono" not in ids)
    return data


def thresholds_suite(data):
    consts = bundle_eval("console.log(JSON.stringify({ hold: m.HOLD_MAX_CP, drawn: m.WIN_DRAWN_CP, nodes: m.VERDICT_NODES }))")
    if not consts:
        return
    solver = Solver()
    worst_hold, worst_win, bad, first = -10**9, 10**9, [], None
    try:
        for f in data["families"]:
            for p in f["positions"]:
                b = chess.Board(p["fen"])
                player = b.turn
                for m in p["line"]:
                    b.push_uci(m)
                    if b.turn == player or b.is_game_over():
                        continue
                    s = solver.score(b.fen(), consts["nodes"])
                    first = first or (b.fen(), s)
                    if f["objective"] == "draw":
                        # Le camp fort ne doit voir ni mat ni +HOLD_MAX_CP sur une ligne nulle.
                        cp = 10**6 if s["mate"] is not None and s["mate"] > 0 else -(10**6) if s["mate"] is not None else s["cp"]
                        worst_hold = max(worst_hold, cp)
                        if cp >= consts["hold"]:
                            bad.append(f"{p['id']} nulle vue à {s}")
                    else:
                        # Le défenseur doit s'estimer sous -WIN_DRAWN_CP (ou mat contre lui) sur une ligne gagnante.
                        cp = -(10**6) if s["mate"] is not None and s["mate"] < 0 else 10**6 if s["mate"] is not None else s["cp"]
                        worst_win = min(worst_win, -cp)
                        if cp >= -consts["drawn"]:
                            bad.append(f"{p['id']} gain vu à {s}")
        again = solver.score(first[0], consts["nodes"])
    finally:
        solver.close()
    check(f"[seuils] verdict reproductible à {consts['nodes']} nœuds, quelle que soit la recherche précédente", again == first[1], f"({first[1]} puis {again})")
    check(f"[seuils] nulles sous +{consts['hold']} cp (pire {worst_hold}), gains au-dessus de +{consts['drawn']} cp (pire {worst_win})", not bad, f"({bad[:5]})")


PURE_JS = r"""
const { Chess } = await import('chess.js')
const j = (fen, player, objective, start) => m.judgeBoard(new Chess(fen), player, objective, start ?? fen, 3)
let seq = 0
const rnd = () => ((seq = (seq * 9301 + 49297) % 233280) / 233280)
console.log(JSON.stringify({
  // Promotion dame conservée, au trait du joueur : gain acquis.
  promoted: j('8/8/8/8/8/2k5/8/K2Q2n1 w - - 0 1', 'w', 'win', '8/8/8/8/8/2k5/3P4/K5n1 w - - 0 1'),
  // Sous-promotion en cavalier : matériel insuffisant, la règle passe avant la conversion.
  under: j('8/8/8/8/8/2k5/8/K2N4 b - - 0 1', 'w', 'win', '8/8/8/8/8/2k5/3P4/K7 w - - 0 1'),
  // Pion promu en dame juste après le coup, trait à l'adversaire : pas encore lu.
  notYet: j('8/8/8/8/8/2k5/8/K2Q4 b - - 0 1', 'w', 'win', '8/8/8/8/8/2k5/3P4/K7 w - - 0 1'),
  // Dame contre roi nu : matériel raflé.
  bare: j('8/8/8/8/8/2k5/8/K2Q4 w - - 0 1', 'w', 'win', '8/8/8/8/8/2k5/3p4/K2Q4 w - - 0 1'),
  // Tour contre tour : rien d'acquis.
  rr: j('8/8/8/8/8/2k1r3/8/K2R4 w - - 0 1', 'w', 'win', '8/8/8/8/8/2k1r3/3P4/K2R4 w - - 0 1'),
  // Pat : réussite si nulle à tenir, raté si gain.
  patHold: j('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1', 'b', 'draw'),
  patWin: j('7k/5Q2/6K1/8/8/8/8/8 b - - 0 1', 'w', 'win'),
  // Mat subi alors qu'il fallait tenir.
  matedHold: j('7k/6Q1/6K1/8/8/8/8/8 b - - 0 1', 'b', 'draw'),
  holdEarly: m.holdReached(m.HOLD_MOVES - 1, { cp: 0, mate: null }),
  holdOk: m.holdReached(m.HOLD_MOVES, { cp: m.HOLD_MAX_CP - 1, mate: null }),
  holdHigh: m.holdReached(m.HOLD_MOVES, { cp: m.HOLD_MAX_CP, mate: null }),
  holdMate: m.holdReached(m.HOLD_MOVES + 3, { cp: null, mate: 7 }),
  holdNone: m.holdReached(m.HOLD_MOVES, null),
  streak: [m.drawnStreak(0, { cp: -m.WIN_DRAWN_CP, mate: null }), m.drawnStreak(2, { cp: 10, mate: null }), m.drawnStreak(2, { cp: -m.WIN_DRAWN_CP - 1, mate: null }), m.drawnStreak(2, { cp: null, mate: -4 })],
  cadences: [m.cadenceLabel({ baseS: 15, incS: 0 }), m.cadenceLabel({ baseS: 30, incS: 1 }), m.cadenceLabel({ baseS: 60, incS: 2 })],
  keys: [m.recordKey('lucena', { baseS: 30, incS: 1 }), m.parseCadence('60+2'), m.parseCadence('45+0'), m.parseCadence('x')],
  seconds: m.secondsLabel(12345),
  family: m.seriesRound('philidor', rnd).map((p) => p.id).sort(),
  familyIds: m.familyById('philidor').positions.map((p) => p.id).sort(),
  mix: m.seriesRound('mix', rnd).map((p) => m.familyOf(p.id).difficulty),
  total: m.FAMILIES.reduce((n, f) => n + f.positions.length, 0),
}))
"""


def pure_suite():
    r = bundle_eval(PURE_JS)
    if r is None:
        return
    check("[pur] promotion dame conservée : gain acquis", r["promoted"] and r["promoted"]["success"] and "Promotion" in r["promoted"]["reason"], f"({r['promoted']})")
    check("[pur] sous-promotion en cavalier : nulle par la règle, objectif manqué", r["under"] and not r["under"]["success"] and r["under"]["end"]["kind"] == "insufficient", f"({r['under']})")
    check("[pur] conversion lue seulement au trait du joueur", r["notYet"] is None, f"({r['notYet']})")
    check("[pur] roi nu contre dame : matériel raflé", r["bare"] and r["bare"]["success"], f"({r['bare']})")
    check("[pur] tour contre tour : rien d'acquis", r["rr"] is None, f"({r['rr']})")
    check("[pur] pat : réussite pour tenir, raté pour gagner", r["patHold"]["success"] and not r["patWin"]["success"] and "Il fallait gagner" in r["patWin"]["reason"], f"({r['patHold']}, {r['patWin']})")
    check("[pur] mat subi : raté même à tenir", r["matedHold"] and not r["matedHold"]["success"], f"({r['matedHold']})")
    check("[pur] tenue : coups requis, seuil strict, mat du moteur refusé", not r["holdEarly"] and r["holdOk"] and not r["holdHigh"] and not r["holdMate"] and not r["holdNone"])
    check("[pur] gain envolé : série de réponses à l'équilibre", r["streak"] == [1, 3, 0, 0], f"({r['streak']})")
    check("[pur] libellés de cadence", r["cadences"] == ["15 s", "30 s | 1", "1 min | 2"], f"({r['cadences']})")
    check("[pur] clés de record et cadences valides", r["keys"] == ["lucena:30+1", {"baseS": 60, "incS": 2}, None, None], f"({r['keys']})")
    check("[pur] temps affiché", r["seconds"] == "12,3 s", f"({r['seconds']})")
    check("[pur] série d'une famille : toutes ses variantes", r["family"] == r["familyIds"] and len(r["family"]) >= 1, f"({r['family']})")
    check("[pur] mélange : toutes les positions, difficulté croissante", len(r["mix"]) == r["total"] and r["mix"] == sorted(r["mix"]), f"({r['mix'][:12]})")


# ---------- outils ----------

def attr(page, sel, name):
    loc = page.locator(sel)
    return loc.first.get_attribute(name) if loc.count() else None


def run_state(page):
    return page.evaluate("""() => {
      const r = document.querySelector('[data-run]')
      const t = r?.querySelector('[role=timer]')
      return r ? { fen: r.dataset.fen, phase: r.dataset.phase, pos: r.dataset.position, ms: t ? Number(t.dataset.ms) : null, running: t?.dataset.running ?? null } : null
    }""")


def rows(page, n=None, timeout=5000):
    end = time.time() + timeout / 1000
    while True:
        dump = page.evaluate(DB_JS)
        if n is None or len(dump["rows"]) >= n or time.time() > end:
            return dump
        page.wait_for_timeout(200)


def wait(page, expression, timeout=15000):
    try:
        page.wait_for_function(expression, timeout=timeout)
        return True
    except Exception:
        return False


def open_page(page, base_s, inc_label):
    page.goto(f"{BASE}/#/finales/chrono")
    ck.appears("[accueil] page chargée", page, "[data-serie='mix']", timeout=10000)
    page.get_by_role("radio", name=base_s, exact=True).click()
    page.get_by_role("radio", name=inc_label, exact=True).click()


def pawn_push(board):
    """Poussée d'une case du pion du joueur (camp au trait)."""
    for m in board.legal_moves:
        if board.piece_type_at(m.from_square) == chess.PAWN and abs(m.to_square - m.from_square) == 8:
            return m
    return None


def first_quiet(board):
    """Un coup légal de l'adversaire qui ne termine pas la partie et ne prend rien."""
    for m in board.legal_moves:
        if not board.is_capture(m):
            b = board.copy()
            b.push(m)
            if not b.is_game_over():
                return m
    return None


# ---------- parcours ----------

def entry_suite(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre")
    if ck.appears("[entrée] carte Finales au chrono dans Apprendre", page, "[data-testid='endgame-clock-card']", timeout=10000):
        shot(page, "finales_chrono_apprendre_393x852", full_page=True)
        page.locator("[data-testid='endgame-clock-card']").click()
        ck.appears("[entrée] Apprendre → /finales/chrono", page, "h1:has-text('Finales au chrono')", timeout=5000)
        check("[entrée] URL /finales/chrono", page.url.endswith("#/finales/chrono"), f"({page.url})")
    tab = page.locator("nav a[href='#/apprendre']").last
    check("[entrée] onglet Apprendre allumé", tab.get_attribute("aria-current") == "true", f"({tab.get_attribute('aria-current')})")
    fams = read_json("src/data/endgameClock.json")["families"]
    check("[accueil] une carte par famille, plus le mélange", page.locator("[data-serie]").count() == len(fams) + 1, f"({page.locator('[data-serie]').count()})")
    sections = page.locator("[data-section]").evaluate_all("els => els.map(e => e.dataset.section)")
    check("[accueil] familles groupées par thème", sections == ["pawns", "rooks", "queen", "other"] or sections == ["pawns", "rooks", "queen"], f"({sections})")
    check("[accueil] cadence par défaut 30 s sans incrément", page.get_by_role("radio", name="30 s", exact=True).get_attribute("aria-checked") == "true"
          and page.get_by_role("radio", name="Aucun", exact=True).get_attribute("aria-checked") == "true")
    check("[accueil] pas de débordement horizontal (393)", overflow_x(page) == 0)
    shot(page, "finales_chrono_accueil_393x852")
    shot(page, "finales_chrono_accueil_full_393x852", full_page=True)
    page.get_by_role("button", name="Retour à Apprendre").click()
    ck.appears("[entrée] retour à Apprendre", page, "[data-testid='endgame-clock-card']", timeout=5000)
    ctx.close()

    ctx = mobile_context(p, browser, ck)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/finales/chrono")
    ck.appears("[accueil 393x660] page chargée", page, "[data-serie='mix']", timeout=10000)
    check("[accueil 393x660] pas de débordement horizontal", overflow_x(page) == 0)
    shot(page, "finales_chrono_accueil_393x660")
    page.locator("[data-serie='lucena']").click()
    ck.appears("[série 393x660] série lancée", page, "[data-run='endgame-clock']", timeout=5000)
    check("[série 393x660] pas de débordement horizontal", overflow_x(page) == 0)
    shot(page, "finales_chrono_serie_393x660")
    page.get_by_role("button", name="Arrêter la série").click()
    ctx.close()


def clock_suite(p, browser):
    # 1. Drapeau exact : 15 s, sans incrément, aucune action.
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    open_page(page, "15 s", "Aucun")
    now = datetime.now(timezone.utc)
    page.clock.install(time=now)
    page.clock.pause_at(now + timedelta(seconds=1))
    page.locator("[data-serie='kp-square']").click()
    if not ck.appears("[pendule] série lancée", page, "[data-run='endgame-clock']", timeout=5000):
        ctx.close()
        return
    page.clock.run_for(14_900)
    s = run_state(page)
    check("[pendule] 14,9 s plus tard : 100 ms, toujours en jeu", s["ms"] == 100 and s["phase"] == "play" and s["running"] == "true", f"({s})")
    page.clock.run_for(200)
    s = run_state(page)
    check("[pendule] drapeau tombé à 15 s", s["phase"] == "over" and page.locator("text=Temps écoulé").count() == 1, f"({s})")
    dump = rows(page, 1)
    check("[pendule] série au drapeau enregistrée à 0", [(r["itemId"], r["score"]) for r in dump["rows"]] == [("kp-square:15+0", 0)], f"({dump['rows']})")
    shot(page, "finales_chrono_drapeau_393x852", full_page=True)
    ctx.close()

    # 2. Incrément, pendule figée pendant la réponse retenue, prémouvement débité puis incrémenté.
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(HOLD_BESTMOVE)
    page = ctx.new_page()
    open_page(page, "15 s", "+2 s")
    now = datetime.now(timezone.utc)
    page.clock.install(time=now)
    page.clock.pause_at(now + timedelta(seconds=1))
    page.locator("[data-serie='kp-square']").click()
    ck.appears("[incrément] série lancée", page, "[data-run='endgame-clock']", timeout=5000)
    board = chess.Board(run_state(page)["fen"])
    page.clock.run_for(3000)
    check("[incrément] 3 s consommées", run_state(page)["ms"] == 12_000, f"({run_state(page)})")
    page.evaluate("window.__heldUci = []")
    push = pawn_push(board)
    tap_move(page, chess.square_name(push.from_square), chess.square_name(push.to_square), pause=0)
    page.clock.run_for(50)
    s = run_state(page)
    check("[incrément] +2 s après le coup : 14 s, pendule arrêtée", s["ms"] == 14_000 and s["running"] == "false", f"({s})")
    held = wait(page, "window.__heldUci.length > 0")
    page.clock.run_for(1000)
    s = run_state(page)
    check("[incrément] réponse du moteur retenue : pendule figée", held and s["ms"] == 14_000 and s["running"] == "false", f"({held}, {s})")
    board.push(push)
    reply = first_quiet(board)
    after_reply = board.copy()
    after_reply.push(reply)
    pre = pawn_push(after_reply)
    tap_move(page, chess.square_name(pre.from_square), chess.square_name(pre.to_square), pause=0)
    page.clock.run_for(50)
    fen0 = run_state(page)["fen"]
    page.evaluate("uci => { for (const h of window.__heldUci) h[1] = 'bestmove ' + uci; window.__releaseUci() }", reply.uci())
    # Le coup n'apparaît qu'après la recherche de verdict, à nœuds fixes : en temps réel, hors horloge.
    wait(page, f"document.querySelector('[data-run]').dataset.fen !== {json.dumps(fen0)}")
    page.clock.run_for(50)
    after_reply.push(pre)
    s = run_state(page)
    actual = chess.Board(s["fen"])
    check("[prémouvement] exécuté après la réponse", actual.board_fen() == after_reply.board_fen(), f"({s['fen']} au lieu de {after_reply.fen()})")
    check("[prémouvement] 100 ms débitées puis +2 s : 15,9 s", s["ms"] == 15_900, f"({s})")
    page.evaluate("window.__heldUci = null")
    ctx.close()

    # 3. Drapeau au débit du prémouvement : 100 ms restantes, le prémouvement n'est pas joué.
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(HOLD_BESTMOVE)
    page = ctx.new_page()
    open_page(page, "15 s", "Aucun")
    now = datetime.now(timezone.utc)
    page.clock.install(time=now)
    page.clock.pause_at(now + timedelta(seconds=1))
    page.locator("[data-serie='kp-square']").click()
    ck.appears("[débit] série lancée", page, "[data-run='endgame-clock']", timeout=5000)
    board = chess.Board(run_state(page)["fen"])
    page.clock.run_for(14_900)
    page.evaluate("window.__heldUci = []")
    push = pawn_push(board)
    tap_move(page, chess.square_name(push.from_square), chess.square_name(push.to_square), pause=0)
    page.clock.run_for(50)
    held = wait(page, "window.__heldUci.length > 0")
    # Fin de l'animation du coup (horloge en pause) ; la pendule, arrêtée au trait du moteur, ne bouge pas.
    page.clock.run_for(1000)
    board.push(push)
    reply = first_quiet(board)
    board.push(reply)
    pre = pawn_push(board)
    tap_move(page, chess.square_name(pre.from_square), chess.square_name(pre.to_square), pause=0)
    page.clock.run_for(50)
    fen0 = run_state(page)["fen"]
    page.evaluate("uci => { for (const h of window.__heldUci) h[1] = 'bestmove ' + uci; window.__releaseUci() }", reply.uci())
    # Le coup n'apparaît qu'après la recherche de verdict, à nœuds fixes : en temps réel, hors horloge.
    wait(page, f"document.querySelector('[data-run]').dataset.fen !== {json.dumps(fen0)}")
    page.clock.run_for(50)
    s = run_state(page)
    actual = chess.Board(s["fen"])
    check("[débit] 100 ms restantes : drapeau à zéro sans jouer le prémouvement",
          held and s["phase"] == "over" and s["ms"] == 0 and actual.board_fen() == board.board_fen() and page.locator("text=Temps écoulé").count() == 1, f"({held}, {s})")
    ctx.close()


def play_out(page, me_moves, max_moves=40):
    """Joue, au trait du joueur, le coup que donne `me_moves(board)` jusqu'à la fin de la position.
    Rend la phase atteinte : 'won', 'over', 'next' (position suivante déjà chargée) ou 'play'."""
    s0 = run_state(page)
    start, me = s0["pos"], chess.Board(s0["fen"]).turn
    played = 0
    deadline = time.time() + 180
    while time.time() < deadline:
        s = run_state(page)
        if s["pos"] != start:
            return "next"
        if s["phase"] != "play":
            return s["phase"]
        board = chess.Board(s["fen"])
        if board.turn != me or s["running"] != "true":
            page.wait_for_timeout(50)
            continue
        if played >= max_moves:
            return "play"
        move = me_moves(board)
        played += 1
        tap_move(page, chess.square_name(move.from_square), chess.square_name(move.to_square), pause=60)
        if move.promotion:
            page.get_by_role("button", name="Dame", exact=True).first.click()
        wait(page, f"(() => {{ const r = document.querySelector('[data-run]'); return !r || r.dataset.fen !== {json.dumps(s['fen'])} || r.dataset.phase !== 'play' }})()", timeout=5000)
    return run_state(page)["phase"]


PLACEMENT_JS = """() => {
  const rows = []
  for (let r = 8; r >= 1; r--) {
    let row = '', empty = 0
    for (const f of 'abcdefgh') {
      const el = document.querySelector(`[data-board] [data-square='${f}${r}'] [data-piece]`)
      const pc = el ? el.getAttribute('data-piece') : null
      if (!pc) { empty++; continue }
      if (empty) { row += empty; empty = 0 }
      row += pc[0] === 'w' ? pc[1] : pc[1].toLowerCase()
    }
    if (empty) row += empty
    rows.push(row)
  }
  return rows.join('/')
}"""


def summary_round_trip(page, before):
    """Bilan d'une série close : « Analyser avec Stockfish » ouvre la dernière position jouée, et
    « Retour au bilan » rend le même bilan (position, motif), pendule arrêtée, sans écriture."""
    if not ck.appears("[analyse] bouton du bilan", page, "[data-run-over] button:has-text('Analyser avec Stockfish')", timeout=3000):
        return
    state = run_state(page)
    reason = page.locator("[data-run-over]").inner_text()
    page.locator("[data-run-over] button", has_text="Analyser avec Stockfish").click()
    if not ck.appears("[analyse] « Retour au bilan » dans l'analyseur", page, "button:has-text('Retour au bilan')", timeout=10000):
        return
    check("[analyse] analyseur ouvert", page.evaluate("() => location.hash") == "#/analyse")
    target = chess.Board(state["fen"]).board_fen()
    check("[analyse] dernière position de la série transmise", wait(page, f"({PLACEMENT_JS})() === {json.dumps(target)}", timeout=5000),
          f"({page.evaluate(PLACEMENT_JS)} vs {target})")
    page.get_by_role("button", name="Retour au bilan").click()
    if not ck.appears("[analyse] retour : bilan restauré", page, "[data-run='endgame-clock'][data-phase='over'] [data-run-over]", timeout=10000):
        return
    after = run_state(page)
    check("[analyse] retour : même position et même pendule", (after["fen"], after["pos"], after["ms"]) == (state["fen"], state["pos"], state["ms"]),
          f"({after} vs {state})")
    check("[analyse] retour : même bilan", page.locator("[data-run-over]").inner_text() == reason)
    page.wait_for_timeout(1200)
    check("[analyse] retour : pendule arrêtée", run_state(page)["ms"] == state["ms"] and run_state(page)["running"] == "false", f"({run_state(page)})")
    got = rows(page)["rows"]
    check("[analyse] retour : aucune écriture de plus", len(got) == len(before), f"({got} vs {before})")


def games_suite(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    open_page(page, "1 min", "+2 s")
    solver = Solver()
    try:
        # Gain réel : pion qui court, promotion conservée.
        page.locator("[data-serie='kp-square']").click()
        ck.appears("[gain] série lancée", page, "[data-run='endgame-clock']", timeout=5000)
        check("[gain] objectif affiché : Gagner", attr(page, "[data-run]", "data-objective") == "win" and page.locator("[data-run] >> text=Gagner").count() >= 1)
        first = run_state(page)["pos"]
        shot(page, "finales_chrono_serie_393x852")
        phase = play_out(page, lambda b: chess.Move.from_uci(solver.best(b.fen(), 10)))
        won = phase == "won"
        check("[gain] promotion conservée : objectif atteint", won, f"({phase}, {run_state(page)})")
        if won:
            status = page.locator("[data-status]").inner_text()
            check("[gain] temps de réussite affiché", status.startswith("✓ Objectif atteint en ") and status.endswith(" s"), f"({status})")
            check("[gain] motif : promotion", page.locator("[data-run] >> text=Promotion réussie").count() == 1)
            check("[gain] score 1", attr(page, "[data-score]", "data-score") == "1")
            dump = rows(page, 1)
            check("[gain] série enregistrée dès la première réussite", [(r["itemId"], r["score"]) for r in dump["rows"]] == [("kp-square:60+2", 1)], f"({dump['rows']})")
            check("[gain] position suivante de la famille, pendule pleine",
                  wait(page, f"(() => {{ const r = document.querySelector('[data-run]'); return r.dataset.phase === 'play' && r.dataset.position !== {json.dumps(first)} }})()", timeout=4000)
                  and (attr(page, "[data-run]", "data-position") or "").startswith("kp-square") and run_state(page)["ms"] > 58_000, f"({run_state(page)})")
        page.get_by_role("button", name="Arrêter la série").click()
        ck.appears("[gain] bilan de série", page, "[data-run-over]", timeout=3000)
        if won:
            ck.appears("[gain] nouveau record annoncé", page, "text=Nouveau record", timeout=3000)
            check("[gain] unité du bilan", page.locator("[data-run-over] >> text=finale réussie").count() == 1)
        check("[gain] méthode de la famille au bilan", page.locator("[data-principle]").count() == 1)
        shot(page, "finales_chrono_bilan_393x852", full_page=True)
        dump = rows(page)
        check("[gain] UNE ligne pour la série", len(dump["rows"]) == 1, f"({dump['rows']})")

        # Gain raté : le roi s'éloigne du pion, Stockfish le rattrape.
        page.get_by_role("button", name="Menu").click()
        page.locator("[data-serie='kp-square']").click()
        ck.appears("[raté] série lancée", page, "[data-run='endgame-clock'][data-phase='play']", timeout=5000)

        def wander(b):
            pawn = next(sq for sq, pc in b.piece_map().items() if pc.piece_type == chess.PAWN)
            kings = [m for m in b.legal_moves if b.piece_type_at(m.from_square) == chess.KING]
            return max(kings, key=lambda m: chess.square_distance(m.to_square, pawn)) if kings else next(iter(b.legal_moves))

        phase = play_out(page, wander)
        reason = page.locator("[data-run-over]").inner_text() if page.locator("[data-run-over]").count() else ""
        check("[raté] gain manqué : la série s'arrête sur la nulle", phase == "over" and ("Il fallait gagner" in reason or "Le gain s'est envolé" in reason), f"({phase}, {reason[:160]})")
        shot(page, "finales_chrono_rate_393x852", full_page=True)
        summary_round_trip(page, rows(page, 2)["rows"])

        # Nulle tenue : défense devant le pion.
        page.get_by_role("button", name="Menu").click()
        page.locator("[data-serie='kp-defense-front']").click()
        ck.appears("[nulle] série lancée", page, "[data-run='endgame-clock'][data-objective='draw']", timeout=5000)
        check("[nulle] consigne : coups à tenir", page.locator("[data-status]:has-text('tiens encore 15 coups')").count() == 1, f"({attr(page, '[data-status]', 'class')})")
        phase = play_out(page, lambda b: chess.Move.from_uci(solver.best(b.fen(), 12)))
        check("[nulle] nulle tenue contre Stockfish : objectif atteint", phase == "won", f"({phase}, {run_state(page)})")
        shot(page, "finales_chrono_nulle_393x852")
        page.get_by_role("button", name="Arrêter la série").click()
        ck.appears("[nulle] bilan", page, "[data-run-over]", timeout=3000)
    finally:
        solver.close()
    dump = rows(page, 3)
    keys = sorted((r["itemId"], r["score"]) for r in dump["rows"])
    check("[séries] trois séries, trois lignes", keys == [("kp-defense-front:60+2", 1), ("kp-square:60+2", 0), ("kp-square:60+2", 1)], f"({keys})")
    check("[données] pas de nouvelle version ni table Dexie", dump["version"] == DB_VERSION and dump["stores"] == DB_STORES, f"({dump['version']}, {dump['stores']})")

    # Record relu après rechargement, cadence mémorisée.
    # Attendre chaque rendu : sous CPU ralenti, Apprendre encore en montage ramènerait l'URL à
    # #/apprendre après le second goto, et le rechargement ne rouvrirait pas les finales au chrono.
    page.goto(f"{BASE}/#/apprendre")
    ck.appears("[records] Apprendre affiché", page, "[data-testid='endgame-clock-card']", timeout=10000)
    page.goto(f"{BASE}/#/finales/chrono")
    ck.appears("[records] retour aux finales au chrono", page, "[data-serie='mix']", timeout=10000)
    page.reload()
    ck.appears("[records] page rechargée", page, "[data-serie='mix']", timeout=10000)
    check("[records] cadence mémorisée (1 min | 2)", page.get_by_role("radio", name="1 min", exact=True).get_attribute("aria-checked") == "true"
          and page.get_by_role("radio", name="+2 s", exact=True).get_attribute("aria-checked") == "true")
    ck.appears("[records] record de la carte relu", page, "[data-serie='kp-square'] [data-record='1']", timeout=5000)
    page.get_by_role("radio", name="15 s", exact=True).click()
    check("[records] record propre à la cadence", page.locator("[data-serie='kp-square'] [data-record]").count() == 0)
    ctx.close()


def desktop_suite(p, browser):
    ctx = desktop_context(browser, ck)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/finales/chrono")
    ck.appears("[desktop] accueil", page, "[data-serie='mix']", timeout=10000)
    check("[desktop] pas de débordement horizontal", overflow_x(page) == 0)
    shot(page, "finales_chrono_accueil_1440x900")
    page.locator("[data-serie='philidor']").click()
    ck.appears("[desktop] série lancée", page, "[data-run='endgame-clock']", timeout=5000)
    check("[desktop] série : pas de débordement horizontal", overflow_x(page) == 0)
    shot(page, "finales_chrono_serie_1440x900")
    page.get_by_role("button", name="Arrêter la série").click()
    ctx.close()


def suite(p):
    data = data_suite()
    pure_suite()
    thresholds_suite(data)
    browser = p.chromium.launch(headless=True)
    entry_suite(p, browser)
    clock_suite(p, browser)
    games_suite(p, browser)
    desktop_suite(p, browser)
    browser.close()


ck.run(suite)
