"""E2E « Calcul et visualisation » (/visualisation) : ligne annoncée sans bouger les pièces, question
sur la position finale imaginée.

Ce qui est vérifié :
- données : `node scripts/check-visualisation.mjs` passe (tampon Stockfish à jour, lignes légales,
  meilleur coup légal, mats en 1 en nombre) et échoue sur des banques mutées, même retamponnées ;
- logique : src/lib/visualisation.ts bundlé par rolldown et exécuté sous Node sur toute la banque et
  sur des lignes construites (roque, prise en passant, promotion), comparé à un oracle python-chess
  indépendant (notation numérotée en figurines, suivi des pièces, pièce demandée, pièces en prise,
  mats en 1, réponse au meilleur coup, roque roi puis tour) ; des copies mutées du bundle doivent
  diverger de l'oracle ; tirage de « mat en un » équilibré entre Oui et Non ;
- entrée : tuile dans Apprendre, onglet Apprendre allumé sur /visualisation ;
- série mobile (393x852) : chaque question affichée est résolue par l'oracle, ligne affichée = oracle,
  bonne réponse par toucher → ✓, score ; position finale révélée lue dans le DOM = oracle ; mauvaise
  réponse → ✗, case touchée en rouge, erreurs comptées ; trois erreurs → bilan ; lignes
  `learnSessions` (une par question, une par série) ; record relu après rechargement ;
- mode « Un par un » : coups montrés un à un, ligne cachée pendant la question, série arrêtée à zéro
  non enregistrée ;
- aucune nouvelle table ni version Dexie ; captures 393x852, 393x660, 1440x900 sans débordement.

Usage : npm run test:e2e -- --suite visualisation
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile

try:
    import chess
except ImportError:
    sys.exit("python-chess manquant : pip install -r e2e/requirements.txt")

from helpers import BASE, Checker, mobile_context, desktop_context, overflow_x, shot

ck = Checker("visualisation")
check = ck.check
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLLDOWN = os.path.join(ROOT, "node_modules", ".bin", "rolldown")
BANK_PATH = os.path.join(ROOT, "src", "data", "visualisation.json")
CHECKER = os.path.join(ROOT, "scripts", "check-visualisation.mjs")
GENERATOR = os.path.join(ROOT, "scripts", "prepare-visualisation.py")

DB_VERSION = 30  # src/lib/db.ts version(3) : l'entraîneur n'ajoute ni version ni table
DB_STORES = sorted(["games", "ratings", "puzzleAttempts", "rushScores", "mistakes", "learnSessions", "reviews"])
DB_JS = """async () => {
  const d = await new Promise((res, rej) => { const r = indexedDB.open('chess-local'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error) })
  const rows = await new Promise((res) => { const q = d.transaction('learnSessions').objectStore('learnSessions').getAll(); q.onsuccess = () => res(q.result) })
  const out = { version: d.version, stores: [...d.objectStoreNames].sort(), rows: rows.filter((r) => r.domain === 'visualisation') }
  d.close()
  return out
}"""
BOARD_JS = """() => {
  const out = {}
  for (const el of document.querySelectorAll('[data-board] [data-square]')) {
    const p = el.querySelector('[data-piece]')
    if (p) out[el.getAttribute('data-square')] = p.getAttribute('data-piece')
  }
  return out
}"""

FIG = {chess.WHITE: {"K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘"}, chess.BLACK: {"K": "♚", "Q": "♛", "R": "♜", "B": "♝", "N": "♞"}}
VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}

# Lignes construites : roque des deux côtés (tour suivie), prise en passant (pion pris absent),
# promotion (pièce promue jamais demandée).
SYNTHETIC = [
    {"id": "syn-roque", "fen": "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", "last": "a1a1", "line": ["e1g1", "e8c8", "f1f7", "d8d2"], "best": "f7f8", "rating": 0},
    {"id": "syn-ep", "fen": "4k3/8/8/8/3p4/8/4P3/4K3 w - - 0 1", "last": "a1a1", "line": ["e2e4", "d4e3", "e1e2", "e8d7"], "best": "e2e3", "rating": 0},
    {"id": "syn-promo", "fen": "8/P5k1/8/8/8/8/6K1/8 w - - 0 1", "last": "a1a1", "line": ["a7a8q", "g7h7", "g2f3", "h7g7"], "best": "a8a7", "rating": 0},
    {"id": "syn-noirs", "fen": "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2", "last": "g1f3", "line": ["b8c6", "f1b5", "g8f6", "e1g1"], "best": "f6e4", "rating": 0},
]


def read_bank():
    with open(BANK_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------- oracle python-chess ----------

def oracle(item):
    b = chess.Board(item["fen"])
    labels, numbered = [], []
    at = {sq: sq for sq in b.piece_map()}
    info = {}
    for i, u in enumerate(item["line"]):
        m = chess.Move.from_uci(u)
        color = b.turn
        num = b.fullmove_number
        san = b.san(m)
        fig = "".join(FIG[color].get(ch, ch) for ch in san)
        nb = f"{num}. {fig}" if color == chess.WHITE else f"{num}… {fig}"
        numbered.append(nb)
        labels.append(nb if color == chess.WHITE or i == 0 else fig)

        def bump(frm, to, promoted=False):
            pid = at.pop(frm)
            at[to] = pid
            s = info.get(pid, {"moves": 0, "last": 0, "promoted": False})
            info[pid] = {"moves": s["moves"] + 1, "last": i + 1, "promoted": s["promoted"] or promoted}

        if b.is_en_passant(m):
            at.pop(chess.square(chess.square_file(m.to_square), chess.square_rank(m.from_square)))
        elif b.is_capture(m):
            at.pop(m.to_square)
        castle = b.is_castling(m)
        kingside = b.is_kingside_castling(m)
        bump(m.from_square, m.to_square, m.promotion is not None)
        if castle:
            rank = chess.square_rank(m.from_square)
            rf, rt = (7, 5) if kingside else (0, 3)
            bump(chess.square(rf, rank), chess.square(rt, rank))
        b.push(m)
    start = chess.Board(item["fen"])
    tracked = []
    for end, pid in at.items():
        s = info.get(pid)
        if not s or s["promoted"]:
            continue
        tracked.append({"start": chess.square_name(pid), "end": chess.square_name(end), "moves": s["moves"], "lastPly": s["last"],
                        "type": start.piece_at(pid).symbol().lower(), "color": "w" if start.piece_at(pid).color else "b"})
    tracked.sort(key=lambda t: t["start"])
    n = len(item["line"])
    cutoff = n - 1 if n >= 4 else n
    ok = [t for t in tracked if t["lastPly"] < cutoff]
    where = []
    if ok:
        bm = max(t["moves"] for t in ok)
        bl = min(t["lastPly"] for t in ok if t["moves"] == bm)
        where = sorted(t["start"] for t in ok if t["moves"] == bm and t["lastPly"] == bl)
    hanging = set()
    mates = []
    for m in list(b.legal_moves):
        if b.is_capture(m) and not b.is_en_passant(m):
            victim = b.piece_at(m.to_square)
            mover = b.piece_at(m.from_square)
            if victim.piece_type != chess.KING:
                if VALUE[mover.piece_type] < VALUE[victim.piece_type]:
                    hanging.add(chess.square_name(m.to_square))
                else:
                    b.push(m)
                    if not any(r.to_square == m.to_square for r in b.legal_moves):
                        hanging.add(chess.square_name(m.to_square))
                    b.pop()
        b.push(m)
        if b.is_checkmate():
            mates.append(m.uci())
        b.pop()
    # Roque : roi puis tour accepté en plus de la case d'arrivée du roi.
    best = chess.Move.from_uci(item["best"])
    best_alts = [item["best"][2:4]]
    if b.is_castling(best):
        best_alts.append(("h" if b.is_kingside_castling(best) else "a") + item["best"][1])
    placement = {}
    for sq, p in b.piece_map().items():
        placement[chess.square_name(sq)] = ("w" if p.color else "b") + p.symbol().upper()
    return {
        "labels": labels, "numbered": numbered, "final": b.fen(), "tracked": tracked, "where": where,
        "hanging": sorted(hanging), "mates": sorted(mates), "bestFrom": item["best"][:2], "bestTo": best_alts,
        "placement": placement, "turn": "w" if b.turn else "b",
    }


# ---------- données ----------

def run_checker(json_path=None, stamp_path=None):
    args = ["node", CHECKER] + ([json_path, stamp_path] if json_path else [])
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True)


def data_suite():
    r = run_checker()
    check("[données] banque contrôlée et tamponnée (check-visualisation.mjs)", r.returncode == 0, (r.stdout + r.stderr)[-600:])
    bank = read_bank()
    with open(GENERATOR, "rb") as f:
        gen_sha = hashlib.sha256(f.read()).hexdigest()

    def mutant(name, mutate):
        data = json.loads(json.dumps(bank))
        mutate(data)
        with tempfile.TemporaryDirectory() as d:
            jp, sp = os.path.join(d, "bank.json"), os.path.join(d, "stamp")
            raw = json.dumps(data, ensure_ascii=False)
            with open(jp, "w", encoding="utf-8") as f:
                f.write(raw)
            # Retamponné : seul le contenu peut faire échouer le contrôle.
            with open(sp, "w") as f:
                f.write(f"{hashlib.sha256(raw.encode()).hexdigest()} {gen_sha}\n")
            res = run_checker(jp, sp)
        check(f"[données] mutation détectée : {name}", res.returncode != 0, (res.stdout or "")[:200])

    def illegal_line(d):
        it = d["levels"]["4"][0]
        it["line"][2] = it["line"][2][:2] + ("a1" if it["line"][2][2:4] != "a1" else "h8")

    def short_line(d):
        d["levels"]["6"][3]["line"] = d["levels"]["6"][3]["line"][:5]

    def illegal_best(d):
        it = d["levels"]["2"][5]
        it["best"] = it["best"][:2] + ("a1" if it["best"][2:4] != "a1" else "h8")

    def underpromo(d):
        it = d["levels"]["8"][7]
        it["best"] = it["best"][:4] + "n"

    def dup_id(d):
        d["levels"]["2"][1]["id"] = d["levels"]["4"][1]["id"]

    def too_few(d):
        d["levels"]["8"] = d["levels"]["8"][:120]

    def bad_last(d):
        it = d["levels"]["4"][9]
        it["last"] = it["line"][0][:2] + it["line"][0][:2]

    for name, fn in [("coup illégal dans la ligne", illegal_line), ("ligne trop courte", short_line), ("meilleur coup illégal", illegal_best),
                     ("sous-promotion", underpromo), ("id en double", dup_id), ("niveau incomplet", too_few), ("amorce incohérente", bad_last)]:
        mutant(name, fn)
    r_stale = run_checker(BANK_PATH, os.path.join(ROOT, "e2e", "fixtures", "chesscom.json"))
    check("[données] tampon périmé refusé", r_stale.returncode != 0)
    return bank


# ---------- logique sous Node ----------

NODE_JS = r"""
// review.ts (figurines) importe engine.ts, qui lit `location` au chargement.
globalThis.location = { href: '' }
const lib = await import(process.argv[1])
const items = JSON.parse(await (await import('node:fs')).promises.readFile(process.argv[2], 'utf8'))
const out = {}
for (const it of items) {
  const final = lib.finalPosition(it)
  const moves = lib.lineMoves(it)
  const best = [it.best.slice(0, 2), it.best.slice(2, 4)]
  const q = { kind: 'best', item: it, level: it.line.length, side: final.turn(), text: '', answers: best }
  const rook = { 'e1g1': 'h1', 'e1c1': 'a1', 'e8g8': 'h8', 'e8c8': 'a8' }[it.best.slice(0, 4)]
  out[it.id] = {
    labels: moves.map((m) => m.label), numbered: moves.map((m) => m.numbered), final: final.fen(),
    tracked: lib.trackPieces(it).map((t) => ({ start: t.start, end: t.end, moves: t.moves, lastPly: t.lastPly, type: t.type, color: t.color })),
    where: lib.whereCandidates(it).map((t) => t.start).sort(),
    hanging: lib.hangingSquares(final), mates: lib.mateMoves(final).sort(),
    bestOk: lib.checkSquares(q, best), bestWrong: lib.checkSquares(q, [best[0], ['a1', 'b1', 'c1'].find((s) => s !== best[0] && s !== best[1] && s !== rook)]),
    rookOk: rook ? lib.checkSquares(q, [best[0], rook]) : null,
  }
}
// Tirage : proportion de « Oui » parmi les questions « mat en un » (niveau 6, 4000 tirages).
let yes = 0, mate = 0
const lv = JSON.parse(await (await import('node:fs')).promises.readFile(process.argv[3], 'utf8')).levels['6']
for (let i = 0; i < 4000; i++) {
  const q = lib.pickQuestion(lv, 6, new Set())
  if (q && q.kind === 'mate') { mate += 1; if (q.mate.length > 0) yes += 1 }
}
out.__draw = { yes, mate }
out.__exhausted = []
const levels = JSON.parse(await (await import('node:fs')).promises.readFile(process.argv[3], 'utf8')).levels
for (const [level, pool] of Object.entries(levels)) {
  const groups = [false, true].map(yes => pool.filter(it => (lib.mateMoves(lib.finalPosition(it)).length > 0) === yes))
  for (const consumed of [[], groups[0], groups[1], pool]) {
    const used = new Set(consumed.map(it => it.id))
    const fresh = pool.filter(it => !used.has(it.id))
    const size = fresh.length || pool.length
    for (const wantYes of [false, true]) {
      let call = 0
      const rng = () => {
        const n = call++
        return n === size - 1 ? 0 : n === size + 2 ? (wantYes ? 0.25 : 0.75) : 0.999
      }
      const q = lib.pickQuestion(pool, Number(level), used, rng)
      const available = groups[Number(wantYes)].some(it => !used.has(it.id))
      out.__exhausted.push({ level, consumed: consumed.length, wantYes,
        correct: q?.kind === 'mate' && (q.mate.length > 0) === wantYes,
        fresh: !available || !used.has(q?.item.id) })
    }
  }
}
console.log(JSON.stringify(out))
"""


def bundle(dest):
    r = subprocess.run([ROLLDOWN, "src/lib/visualisation.ts", "--format", "esm", "--file", dest, "--no-codeSplitting"], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0, (r.stderr or r.stdout)[-300:]


def node_eval(bundle_path, items_path):
    r = subprocess.run(["node", "--input-type=module", "-e", NODE_JS, "file://" + bundle_path, items_path, BANK_PATH], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        return None, r.stderr[-300:]
    return json.loads(r.stdout), ""


def compare(items, got, expected):
    """Nombre de divergences entre la lib et l'oracle, et la première."""
    bad, first = 0, ""
    for it in items:
        g, e = got.get(it["id"]), expected[it["id"]]
        diffs = []
        if g is None:
            diffs.append("absent")
        else:
            for k in ["labels", "numbered", "final", "tracked", "where", "hanging", "mates"]:
                if g[k] != e[k]:
                    diffs.append(f"{k}: {g[k]} != {e[k]}")
            if not g["bestOk"] or g["bestWrong"]:
                diffs.append("réponse au meilleur coup")
            if len(e["bestTo"]) > 1 and g["rookOk"] is not True:
                diffs.append("roque roi puis tour refusé")
        if diffs:
            bad += 1
            first = first or f"{it['id']} : {diffs[0]}"
    return bad, first


def logic_suite(bank):
    items = [it for n in ["2", "4", "6", "8"] for it in bank["levels"][n]] + SYNTHETIC
    expected = {it["id"]: oracle(it) for it in items}
    with tempfile.TemporaryDirectory() as d:
        bp = os.path.join(d, "vis.mjs")
        ok, err = bundle(bp)
        if not check("[logique] bundle rolldown de visualisation.ts", ok, err):
            return
        ip = os.path.join(d, "items.json")
        with open(ip, "w") as f:
            json.dump(items, f)
        got, err = node_eval(bp, ip)
        if not check("[logique] exécution sous Node", got is not None, err):
            return
        bad, first = compare(items, got, expected)
        check(f"[logique] {len(items)} lignes : lib = oracle python-chess", bad == 0, f"({bad} divergence(s), {first})")
        syn = {it["id"]: expected[it["id"]] for it in SYNTHETIC}
        check("[logique] roque : tour h1 suivie jusqu'en f7", any(t["start"] == "h1" and t["end"] == "f7" for t in syn["syn-roque"]["tracked"]))
        check("[logique] prise en passant : pion e2 retiré", not any(t["start"] == "e2" for t in syn["syn-ep"]["tracked"]))
        check("[logique] promotion : pion promu jamais demandé", not any(t["start"] == "a7" for t in syn["syn-promo"]["tracked"]))
        check("[logique] numérotation quand les Noirs commencent", syn["syn-noirs"]["labels"][:2] == ["2… ♞c6", "3. ♗b5"], f"({syn['syn-noirs']['labels']})")
        # La case demandée ne se lit jamais dans le dernier coup annoncé.
        leak = 0
        for it in items:
            last_dest = it["line"][-1][2:4]
            if any(t["end"] == last_dest and t["start"] in expected[it["id"]]["where"] for t in expected[it["id"]]["tracked"]):
                leak += 1
        check("[logique] pièce demandée jamais celle du dernier coup", leak == 0, f"({leak})")
        draw = got.get("__draw", {})
        ratio = draw.get("yes", 0) / max(1, draw.get("mate", 0))
        check("[logique] « mat en un » tiré environ moitié Oui", draw.get("mate", 0) > 500 and 0.42 <= ratio <= 0.58, f"({draw})")
        exhausted = got["__exhausted"]
        check("[logique] Oui/Non conservé après épuisement, aux quatre longueurs",
              len(exhausted) == 32 and all(r["correct"] and r["fresh"] for r in exhausted),
              str([r for r in exhausted if not r["correct"] or not r["fresh"]]))
        # Mutations du bundle : l'oracle doit les voir.
        with open(bp, encoding="utf-8") as f:
            src = f.read()
        mutations = [
            ("roque : tour non suivie", "bump(`${rf}${rank}`, `${rt}${rank}`);", ""),
            ("prise en passant ignorée", "if (m.isEnPassant()) at.delete(`${m.to[0]}${m.from[1]}`);\n\t\telse if", "if"),
            ("en prise : valeur égale comptée", "if (VALUE[m.piece] < VALUE[m.captured]) {", "if (VALUE[m.piece] <= VALUE[m.captured]) {"),
            ("dernier coup non exclu", "n >= 4 ? n - 1 : n", "n + 1"),
            ("numérotation", "`${num}… ${fig}`", "`${num}. ${fig}`"),
        ]
        for name, old, new in mutations:
            mp = os.path.join(d, "mutant.mjs")
            with open(mp, "w", encoding="utf-8") as f:
                f.write(src.replace(old, new))
            mg, _ = node_eval(mp, ip)
            mbad = len(items) if mg is None else compare(items, mg, expected)[0]
            check(f"[logique] mutation détectée : {name}", mbad > 0, f"({mbad} divergence(s))")


# ---------- interface ----------

def item_of(bank, level, item_id):
    for it in bank["levels"][str(level)]:
        if it["id"] == item_id:
            return it
    return None


def vis_rows(page, n=None, timeout=5000):
    import time
    end = time.time() + timeout / 1000
    while True:
        dump = page.evaluate(DB_JS)
        if n is None or len(dump["rows"]) >= n or time.time() > end:
            return dump
        page.wait_for_timeout(200)


def board_settled(page, expected, timeout=3000):
    """Placement lu dans le DOM, une fois l'animation des pièces terminée (attente bornée)."""
    try:
        page.wait_for_function(
            f"(e) => {{ const b = ({BOARD_JS})(); const k = Object.keys(b); return k.length === Object.keys(e).length && k.every((s) => b[s] === e[s]) }}",
            arg=expected, timeout=timeout)
    except Exception:
        pass
    return page.evaluate(BOARD_JS)


def run_attr(page, name):
    return page.locator("[data-vis-run]").first.get_attribute(name)


def current(page, bank):
    level = int(run_attr(page, "data-level"))
    it = item_of(bank, level, run_attr(page, "data-item"))
    return it, run_attr(page, "data-kind"), run_attr(page, "data-target"), (oracle(it) if it else None)


def give_answer(page, kind, target, o, right):
    """Répond juste (right) ou faux ; retourne les cases touchées (toucher sur mobile, clic sur ordinateur)."""
    touch = page.evaluate("() => navigator.maxTouchPoints > 0")

    def tap_square(page, sq):
        loc = page.locator(f"[data-board] [data-square='{sq}']").first
        loc.tap() if touch else loc.click()

    if kind == "mate":
        yes = bool(o["mates"]) == right
        page.get_by_role("button", name="Oui" if yes else "Non", exact=True).click()
        return []
    if kind == "where":
        end = next(t["end"] for t in o["tracked"] if t["start"] == target)
        sq = end if right else next(s for s in ["a1", "h8", "a8", "h1", "d4"] if s != end)
        tap_square(page, sq)
        return [sq]
    if kind == "hanging":
        sq = o["hanging"][0] if right else next(s for s in chess.SQUARE_NAMES if s not in o["hanging"])
        tap_square(page, sq)
        return [sq]
    frm = o["bestFrom"]
    to = o["bestTo"][0] if right else next(s for s in chess.SQUARE_NAMES if s not in o["bestTo"] and s != frm)
    tap_square(page, frm)
    page.wait_for_timeout(150)
    tap_square(page, to)
    return [frm, to]


def ui_suite(p, browser, bank):
    ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block")
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre")
    tile = page.get_by_role("link", name="Calcul et visualisation")
    ck.appears("[entrée] tuile dans Apprendre", page, "a[href='#/visualisation']", timeout=15000)
    tile.click()
    ck.appears("[entrée] accueil de l'entraîneur", page, "[data-vis-hub]", timeout=15000)
    check("[entrée] onglet Apprendre allumé", page.locator("nav a[aria-current='true']", has_text="Apprendre").count() >= 1)
    ck.appears("[accueil] banque chargée", page, "button:has-text('Commencer'):not([disabled])", timeout=15000)
    check("[accueil] pas de débordement horizontal", overflow_x(page) == 0)
    page.wait_for_timeout(300)  # fin de la transition d'opacité du bouton activé
    shot(page, "visualisation_hub_393x852")
    page.locator("[data-level='4']").click()
    check("[accueil] niveau 4 choisi", page.locator("[data-level='4']").get_attribute("aria-checked") == "true")
    page.get_by_role("button", name="Commencer").click()
    ck.appears("[série] question affichée", page, "[data-vis-run][data-phase='question']", timeout=10000)

    score = 0
    errors = 0
    seen_kinds = set()
    rounds = 0
    shots_done = set()
    while rounds < 30 and errors < 3:
        rounds += 1
        it, kind, target, o = current(page, bank)
        if not check(f"[série] tour {rounds} : position de la banque (niveau 4)", it is not None):
            break
        seen_kinds.add(kind)
        line = page.locator("[data-line-text] [data-ply]").all_inner_texts()
        check(f"[série] tour {rounds} : ligne affichée = oracle", line == o["labels"], f"({line} / {o['labels']})")
        start_place = {chess.square_name(sq): ("w" if pc.color else "b") + pc.symbol().upper() for sq, pc in chess.Board(it["fen"]).piece_map().items()}
        board = board_settled(page, start_place)
        check(f"[série] tour {rounds} : échiquier figé sur la position de départ", board == start_place)
        if kind == "where":
            check(f"[série] tour {rounds} : pièce demandée parmi les candidates de l'oracle", target in o["where"], f"({target} / {o['where']})")
        if kind == "hanging":
            check(f"[série] tour {rounds} : question en prise posée sur une position qui en a", len(o["hanging"]) > 0)
        if f"q-{kind}" not in shots_done:
            shots_done.add(f"q-{kind}")
            shot(page, f"visualisation_question_{kind}_393x852")
        right = score < 4  # quatre bonnes réponses, puis trois fausses
        touched = give_answer(page, kind, target, o, right)
        verdict = "ok" if right else "ko"
        ck.appears(f"[série] tour {rounds} ({kind}) : verdict {verdict}", page, f"[data-vis-run][data-phase='reveal'][data-verdict='{verdict}']", timeout=5000)
        if right:
            score += 1
        else:
            errors += 1
        check(f"[série] tour {rounds} : score {score}", page.locator(f"[data-score='{score}']").count() == 1)
        check(f"[série] tour {rounds} : erreurs {errors}", page.locator(f"[data-errors='{errors}']").count() == 1)
        board = board_settled(page, o["placement"])
        check(f"[série] tour {rounds} : position finale révélée = oracle", board == o["placement"])
        if not right and touched:
            # react-chessboard pose `squareStyles` sur le div intérieur de la case.
            html = page.locator(f"[data-board] [data-square='{touched[-1]}']").first.evaluate("(e) => e.innerHTML")
            check(f"[série] tour {rounds} : case touchée fausse en rouge", "220, 50, 50" in html, f"({html[:160]})")
        if f"r-{verdict}" not in shots_done:
            shots_done.add(f"r-{verdict}")
            shot(page, f"visualisation_reveal_{verdict}_393x852")
        page.get_by_role("button", name="Bilan" if errors >= 3 else "Suivant").click()
        if errors < 3:
            ck.appears(f"[série] tour {rounds} : question suivante", page, "[data-vis-run][data-phase='question']", timeout=5000)
    check("[série] trois erreurs atteintes", errors == 3, f"({errors} en {rounds} tours)")
    ck.appears("[série] bilan", page, "[data-run-over]", timeout=5000)
    big = page.locator("[data-run-over] p.text-5xl")
    check("[série] bilan : score affiché", big.count() == 1 and big.inner_text().strip() == str(score), f"({big.all_inner_texts()})")
    shot(page, "visualisation_bilan_393x852")
    dump = vis_rows(page, rounds + 1)
    q_rows = [r for r in dump["rows"] if r["itemId"].startswith("q:4:")]
    s_rows = [r for r in dump["rows"] if r["itemId"] == "serie:4:visible"]
    check("[persistance] une ligne par question", len(q_rows) == rounds and sum(r["success"] for r in q_rows) == score, f"({len(q_rows)} lignes, {rounds} tours)")
    check("[persistance] une ligne de série avec le score", len(s_rows) == 1 and s_rows[0].get("score") == score, f"({s_rows})")
    check("[persistance] lignes hors Elo", all(r["ratingAfter"] is None for r in dump["rows"]))
    check("[persistance] pas de nouvelle version ni table Dexie", dump["version"] == DB_VERSION and dump["stores"] == DB_STORES, f"({dump['version']}, {dump['stores']})")

    page.reload()
    ck.appears("[persistance] accueil après rechargement", page, "[data-vis-hub]", timeout=10000)
    page.wait_for_function("() => document.querySelector('[data-answered]')?.textContent !== '…'", timeout=5000)
    check("[persistance] record relu", (page.locator("[data-record]").inner_text() or "").strip() == str(score), f"({page.locator('[data-record]').inner_text()})")
    check("[persistance] questions répondues relues", page.locator("[data-answered]").inner_text().strip() == str(rounds))
    check("[accueil] taux par type affichés", page.locator("[data-rate]").count() == 4)

    # Mode « Un par un ».
    page.locator("[data-mode='flash']").click()
    page.get_by_role("button", name="Commencer").click()
    ck.appears("[un par un] phase de ligne", page, "[data-vis-run][data-phase='line']", timeout=5000)
    it, kind, target, o = current(page, bank)
    first = page.locator("[data-flash-move]").inner_text().strip()
    check("[un par un] premier coup seul, numéroté", first == o["numbered"][0], f"({first} / {o['numbered'][0]})")
    check("[un par un] ligne entière absente", page.locator("[data-line-text]").count() == 0)
    shot(page, "visualisation_flash_393x852")
    try:
        page.wait_for_function(f"() => document.querySelector('[data-flash-move]')?.textContent.trim() === {json.dumps(o['numbered'][1])}", timeout=4000)
        second = o["numbered"][1]
    except Exception:
        second = page.locator("[data-flash-move]").inner_text().strip() if page.locator("[data-flash-move]").count() else None
    check("[un par un] deuxième coup affiché ensuite, seul", second == o["numbered"][1] and page.locator("[data-line-text]").count() == 0, f"({second})")
    ck.appears("[un par un] question après le dernier coup", page, "[data-vis-run][data-phase='question']", timeout=10000)
    check("[un par un] ligne cachée pendant la question", page.locator("[data-line-text]").count() == 0 and "Ligne cachée" in page.locator("[data-line]").inner_text())
    page.get_by_role("button", name="Arrêter la série").first.click()
    ck.appears("[un par un] bilan après arrêt", page, "[data-run-over]", timeout=5000)
    page.wait_for_timeout(400)
    dump = vis_rows(page)
    check("[un par un] série arrêtée à zéro non enregistrée", not any(r["itemId"] == "serie:4:flash" for r in dump["rows"]))
    ctx.close()


def layout_suite(p, browser, bank):
    for label, make in [
        ("393x660", lambda: mobile_context(p, browser, ck, standalone=False, service_workers="block")),
        ("1440x900", lambda: desktop_context(browser, ck, service_workers="block")),
    ]:
        ctx = make()
        page = ctx.new_page()
        page.goto(f"{BASE}/#/visualisation")
        ck.appears(f"[{label}] accueil", page, "button:has-text('Commencer'):not([disabled])", timeout=15000)
        check(f"[{label}] accueil sans débordement", overflow_x(page) == 0)
        page.wait_for_timeout(300)
        shot(page, f"visualisation_hub_{label}")
        page.get_by_role("button", name="Commencer").click()
        ck.appears(f"[{label}] question", page, "[data-vis-run][data-phase='question']", timeout=10000)
        check(f"[{label}] série sans débordement", overflow_x(page) == 0)
        # La question tient dans l'écran sans défiler : bas du panneau au-dessus du bas de <main>.
        geo = page.evaluate("""() => {
          const q = document.querySelector('[data-question]').getBoundingClientRect()
          const m = document.querySelector('main').getBoundingClientRect()
          return { q: Math.round(q.bottom), m: Math.round(m.bottom) }
        }""")
        check(f"[{label}] question visible sans défiler", geo["q"] <= geo["m"], f"({geo})")
        shot(page, f"visualisation_question_{label}")
        it, kind, target, o = current(page, bank)
        give_answer(page, kind, target, o, True)
        ck.appears(f"[{label}] révélation", page, "[data-vis-run][data-phase='reveal']", timeout=5000)
        geo = page.evaluate("""() => {
          const q = document.querySelector('[data-reveal]').getBoundingClientRect()
          const m = document.querySelector('main').getBoundingClientRect()
          return { q: Math.round(q.bottom), m: Math.round(m.bottom) }
        }""")
        check(f"[{label}] correction visible sans défiler", geo["q"] <= geo["m"], f"({geo})")
        check(f"[{label}] position finale révélée = oracle", board_settled(page, o["placement"]) == o["placement"])
        shot(page, f"visualisation_reveal_{label}")
        ctx.close()


def reset_prefs_suite(p, browser):
    ctx = mobile_context(p, browser, ck, service_workers="block")
    page = ctx.new_page()
    page.goto(f"{BASE}/#/visualisation")
    page.locator('[data-level="8"]').click()
    page.locator('[data-mode="flash"]').click()
    page.reload()
    ck.appears("[préférences] longueur conservée", page, '[data-level="8"][aria-checked="true"]')
    ck.appears("[préférences] mode conservé", page, '[data-mode="flash"][aria-checked="true"]')
    page.goto(f"{BASE}/#/stats")
    with page.expect_download() as download:
        page.locator('[data-testid="export-btn"]').click()
    with open(download.value.path(), encoding="utf-8") as f:
        exported = json.load(f)
    check("[préférences] visualisation hors sauvegarde",
          "chess-local-visualisation" not in exported and "visualisation" not in json.loads(exported["settings"])["state"])
    page.locator('[data-testid="reset-btn"]').click()
    page.locator('[data-testid="reset-confirm"]').click()
    with page.expect_event("load"):
        page.locator('[data-testid="reset-final-confirm"]').click()
    check("[préférences] clé effacée par la réinitialisation",
          page.evaluate("() => localStorage.getItem('chess-local-visualisation')") is None)
    page.goto(f"{BASE}/#/visualisation")
    ck.appears("[préférences] longueur par défaut après réinitialisation", page, '[data-level="4"][aria-checked="true"]')
    ck.appears("[préférences] mode par défaut après réinitialisation", page, '[data-mode="visible"][aria-checked="true"]')
    ctx.close()


def suite(p):
    bank = data_suite()
    logic_suite(bank)
    browser = p.chromium.launch(headless=True)
    ui_suite(p, browser, bank)
    layout_suite(p, browser, bank)
    reset_prefs_suite(p, browser)
    browser.close()


ck.run(suite)
