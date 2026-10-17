"""E2E « Plans par structure de pions » : détecteur, cours, structures de mes parties.

1. Détecteur (src/lib/structures.ts, bundlé sous Node par rolldown) comparé à un oracle python-chess
   indépendant (e2e/structures_oracle.py) : positions écrites à la main (attendus fixes, les deux
   camps, témoins négatifs), toutes les positions des lignes d'ouvertures, un échantillon fixe de
   puzzles ; repérage dans une partie (milieu de partie, série stable, trait du joueur) sur les
   parties de la fixture chess.com et des parties écrites à la main.
2. Cours « Structures de pions » : contrôle hors ligne et ses mutations (tampon Stockfish), contrôle
   croisé cours / détecteur (départ de chaque ligne et premier diagramme reconnus comme la
   structure du chapitre, par le bundle ET par l'oracle), carte d'Apprendre, sommaire, une leçon
   coup par coup (refus, indice, solution), toutes les leçons jouables, progression `structures:<id>`.
3. « Dans mes parties » (/structures) : parties semées dans IndexedDB (games contre un bot, bilans
   chess.com d'Insights), structures les plus fréquentes, résultats exacts, positions de mes parties
   jouées contre Stockfish (PositionGame), tentative notée dans learnSessions (`structure-play`).
4. Mise en page : 393x852, 393x660 et 1440x900, sans débordement horizontal.

Usage : npm run test:e2e -- --suite structures
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile

import chess
import chess.pgn

import logging

import structures_oracle as oracle
from helpers import BASE, E2E_DIR, Checker, desktop_context, mobile_context, overflow_x, shot, tap_move

# Les parties Chess960 de la fixture font crier le lecteur PGN de python-chess : elles sont écartées
# des deux côtés (chess.js refuse aussi leur PGN), sans bruit dans le journal.
logging.getLogger("chess.pgn").setLevel(logging.CRITICAL)
ck = Checker("structures")
check = ck.check
ROOT = os.path.dirname(E2E_DIR)
ROLLDOWN = os.path.join(ROOT, "node_modules", ".bin", "rolldown")
DATA = os.path.join(ROOT, "src", "data", "structuresCourse.json")
STAMP = os.path.join(ROOT, "scripts", "structures-course.verified")
RAW = open(DATA, encoding="utf-8").read() if os.path.exists(DATA) else ""
COURSE = json.loads(RAW) if RAW.strip() else {"chapters": [], "lessons": {}}
LESSONS = [lid for ch in COURSE["chapters"] for lid in ch["lessons"]]
N = len(LESSONS)
STRUCTURE_IDS = oracle.IDS
START = chess.STARTING_FEN

with open(os.path.join(E2E_DIR, "fixtures", "chesscom.json"), encoding="utf-8") as f:
    FIXTURE_GAMES = [g for e in json.load(f)["routes"].values() for g in e.get("body", {}).get("games", []) if g.get("pgn")]


def after(moves, fen=START):
    """FEN après une suite de coups SAN (python-chess vérifie leur légalité)."""
    b = chess.Board(fen)
    for san in moves.split():
        b.push_san(san)
    return b.fen()


# ---------- 1. Positions écrites à la main : attendus fixes ----------
HAND = [
    ("départ", START, []),
    ("française pas encore fermée", after("e4 e6 d4 d5"), []),
    ("Panov : pion isolé blanc", after("e4 c6 d4 d5 exd5 cxd5 c4 Nf6 Nc3 e6 Nf3 Be7 cxd5 Nxd5"), [("iqp", "w")]),
    ("Tarrasch : pion isolé noir", after("d4 d5 c4 e6 Nc3 c5 cxd5 exd5 Nf3 Nc6 g3 Nf6 Bg2 Be7 O-O O-O dxc5 Bxc5"), [("iqp", "b")]),
    ("pions pendants blancs", "r2q1rk1/p3bppp/1p2pn2/8/2PP4/5N2/P4PPP/R2Q1RK1 w - - 0 15", [("pendants", "w")]),
    ("pions pendants noirs", "r2q1rk1/p4ppp/5n2/2pp4/8/1P2PN2/P4PPP/R2Q1RK1 w - - 0 15", [("pendants", "b")]),
    ("Carlsbad (gambit dame, échange)", after("d4 d5 c4 e6 Nc3 Nf6 cxd5 exd5 Bg5 c6 e3"), [("carlsbad", "w")]),
    ("Carlsbad inversé (Caro-Kann, échange)", after("e4 c6 d4 d5 exd5 cxd5"), [("carlsbad", "b")]),
    ("étau de Maroczy", after("e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 g6 c4"), [("maroczy", "w")]),
    ("hérisson (le Maroczy de l'autre camp est retiré)", "r1bq1rk1/4bppp/pp1ppn2/8/2P1P3/2N2N2/PP2BPPP/R2Q1RK1 w - - 0 11", [("herisson", "b")]),
    ("chaîne française", after("e4 e6 d4 d5 e5"), [("francaise", "w")]),
    ("chaîne est-indienne", after("d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O Nc6 d5"), [("est-indienne", "w")]),
    ("Stonewall hollandais (noir)", after("d4 f5 c4 Nf6 g3 e6 Bg2 d5"), [("stonewall", "b")]),
    ("Stonewall blanc", after("d4 d5 e3 Nf6 Bd3 c5 c3 Nc6 f4"), [("stonewall", "w")]),
    ("Caro-Kann classique", after("e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Ng3 Bg6 Nf3 e6"), [("caro-slave", "b")]),
    ("slave (e3 sans pion c)", "rn1qkb1r/pp3ppp/2p1pn2/5b2/P1BP4/2N1PN2/1P3PPP/R1BQK2R b KQkq - 0 7", [("caro-slave", "b")]),
    ("majorité noire à l'aile dame", "r4rk1/pp3ppp/8/2p5/3PP3/8/PP3PPP/R4RK1 w - - 0 20", [("majorite", "b")]),
    # Témoins : chacun ressortirait si sa règle sautait.
    ("pion d isolé mais colonne d bouchée (pas un IQP)", "4k3/pp3ppp/3p4/8/3P4/8/PP3PPP/4K3 w - - 0 1", []),
    ("Caro sans pion c ni e blanc : c'est un IQP, pas un Caro", "4k3/pp3ppp/2p1p3/8/3P4/8/PP3PPP/4K3 w - - 0 1", [("iqp", "w")]),
    ("Stonewall incomplet (pas de f4)", "4k3/pppppppp/8/8/3P4/4P3/PPP2PPP/4K3 w - - 0 1", []),
]


# ---------- Bundle Node de structures.ts ----------
NODE_JS = r"""
const fs = await import('node:fs')
const mod = await import(process.argv[2])
const { fens, games } = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'))
const detect = fens.map((f) => mod.detectStructures(f).map((m) => [m.id, m.side]))
const scans = games.map(([pgn, color]) => mod.structuresInGame(pgn, color).map((s) => [s.id, s.side, s.ply, s.fen]))
const meta = Object.fromEntries(mod.STRUCTURE_IDS.map((id) => [id, mod.STRUCTURES[id]]))
const stats = mod.structureStats(games.map(([pgn, color, result], i) => ({ game: { key: `g${i}`, playerColor: color, result }, sightings: mod.structuresInGame(pgn, color) })))
  .map((s) => [s.id, s.games, s.wins, s.draws, s.losses, s.owner])
const mirrored = mod.squaresFor('Cd5, b4-b5 et Fxh7', 'b')
console.log(JSON.stringify({ ids: mod.STRUCTURE_IDS, detect, scans, meta, stats, mirrored }))
"""


def node_run(fens, games):
    src = os.path.join(ROOT, "src", "lib", "structures.ts")
    if not os.path.exists(src):
        ck.fail("[détecteur] src/lib/structures.ts existe")
        return None
    with tempfile.TemporaryDirectory() as d:
        bundle = os.path.join(d, "structures.mjs")
        r = subprocess.run([ROLLDOWN, src, "--format", "esm", "--file", bundle], cwd=ROOT, capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            ck.fail("[détecteur] bundle rolldown de structures.ts", (r.stderr or r.stdout)[-300:])
            return None
        script = os.path.join(d, "run.mjs")
        data = os.path.join(d, "data.json")
        with open(script, "w", encoding="utf-8") as f:
            f.write(NODE_JS)
        with open(data, "w", encoding="utf-8") as f:
            json.dump({"fens": fens, "games": games}, f)
        r = subprocess.run(["node", script, "file://" + bundle, data], cwd=ROOT, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        ck.fail("[détecteur] structures.ts sous Node", r.stderr.strip()[-400:])
        return None
    return json.loads(r.stdout.strip().splitlines()[-1])


def opening_fens():
    """Toutes les positions des lignes de src/data/openings.json (sans doublon, ordre stable)."""
    seen = {}
    for line in json.load(open(os.path.join(ROOT, "src", "data", "openings.json"), encoding="utf-8")):
        b = chess.Board()
        for u in line["uci"].split():
            b.push_uci(u)
            seen.setdefault(b.fen(), None)
    return list(seen)


def course_fens():
    """Toutes les positions du cours : diagrammes et chaque position des lignes."""
    out = []
    for lesson in COURSE["lessons"].values():
        for st in lesson["steps"]:
            b = chess.Board(st["fen"])
            out.append(b.fen())
            for m in st.get("moves", []):
                b.push_san(m["san"])
                out.append(b.fen())
    return out


def puzzle_fens(step=15):
    rows = json.load(open(os.path.join(ROOT, "public", "puzzles.json"), encoding="utf-8"))
    return [r[1] for r in rows[::step]]


# Parties écrites à la main pour le repérage : structure qui apparaît, puis qui dure.
HAND_GAMES = [
    # Gambit dame, variante d'échange : Carlsbad installé dès 6.e3, attaque de minorité ensuite.
    ("carlsbad", "1. d4 d5 2. c4 e6 3. Nc3 Nf6 4. cxd5 exd5 5. Bg5 c6 6. e3 Be7 7. Bd3 O-O 8. Qc2 Nbd7 9. Nf3 Re8 10. O-O Nf8 11. Rab1 Ne4 12. Bxe7 Qxe7 13. b4 a6 14. a4 Bf5 15. b5 axb5 16. axb5 Rec8 *"),
    # Panov : pion isolé blanc dès 7...Nxd5, puis milieu de partie classique.
    ("panov", "1. e4 c6 2. d4 d5 3. exd5 cxd5 4. c4 Nf6 5. Nc3 e6 6. Nf3 Be7 7. cxd5 Nxd5 8. Bd3 Nc6 9. O-O O-O 10. Re1 Nf6 11. a3 b6 12. Bc2 Bb7 13. Qd3 Rc8 14. Bg5 g6 *"),
    # Française avance : chaîne bloquée, puis la base attaquée.
    ("francaise", "1. e4 e6 2. d4 d5 3. e5 c5 4. c3 Nc6 5. Nf3 Qb6 6. a3 Nh6 7. b4 cxd4 8. cxd4 Nf5 9. Bb2 Be7 10. Bd3 O-O 11. O-O f6 12. Bxf5 exf5 13. Nc3 Be6 *"),
    # Partie courte : structure trop tôt (avant MIN_PLY) puis disparue : rien.
    ("courte", "1. e4 e6 2. d4 d5 3. exd5 exd5 4. Nf3 Nf6 *"),
]


def oracle_section():
    tag = "[détecteur]"
    hand_fens = [f for _, f, _ in HAND]
    corpus = opening_fens()
    puzzles = puzzle_fens()
    fens = hand_fens + corpus + puzzles + course_fens()
    games = []
    for g in FIXTURE_GAMES:
        for color in ("w", "b"):
            games.append([g["pgn"], color, "win" if color == "w" else "loss"])
    for _, pgn in HAND_GAMES:
        for color in ("w", "b"):
            games.append([pgn, color, "draw"])
    out = node_run(fens, games)
    if out is None:
        return
    check(f"{tag} ordre des structures identique à l'oracle", out["ids"] == STRUCTURE_IDS, f"({out['ids']})")
    # Attendus écrits à la main : le bundle ET l'oracle.
    for (label, fen, expected), got in zip(HAND, out["detect"]):
        exp = [list(x) for x in expected]
        check(f"{tag} {label} : structures.ts", got == exp, f"(obtenu {got}, attendu {exp})")
        check(f"{tag} {label} : oracle", [list(x) for x in oracle.detect(chess.Board(fen))] == exp, f"({oracle.detect(chess.Board(fen))})")
    # Corpus : égalité exacte, position par position.
    diffs = []
    counts = {}
    for fen, got in zip(fens, out["detect"]):
        exp = [list(x) for x in oracle.detect(chess.Board(fen))]
        for sid, side in exp:
            counts[(sid, side)] = counts.get((sid, side), 0) + 1
        if got != exp:
            diffs.append((fen, got, exp))
    check(f"{tag} {len(fens)} positions (ouvertures, puzzles, cours, main) : verdicts identiques à l'oracle", not diffs, f"({len(diffs)} écarts, ex. {diffs[:2]})")
    # Le corpus exerce chaque règle : sinon l'égalité ne prouverait rien.
    for sid in STRUCTURE_IDS:
        n = counts.get((sid, "w"), 0) + counts.get((sid, "b"), 0)
        check(f"{tag} corpus : {sid} reconnu au moins 3 fois", n >= 3, f"({counts.get((sid, 'w'), 0)} blancs, {counts.get((sid, 'b'), 0)} noirs)")
    for sid in ("iqp", "carlsbad", "stonewall", "majorite"):
        check(f"{tag} corpus : {sid} vu des deux côtés", counts.get((sid, "w"), 0) > 0 and counts.get((sid, "b"), 0) > 0, f"({counts.get((sid, 'w'), 0)}/{counts.get((sid, 'b'), 0)})")
    # Repérage dans les parties.
    sdiffs = []
    for (pgn, color, _), got in zip(games, out["scans"]):
        exp = [list(x) for x in oracle.scan(pgn, color)]
        if got != exp:
            sdiffs.append((pgn[:60], color, got, exp))
    check(f"{tag} repérage dans {len(games)} parties (fixture + main, deux couleurs) : identique à l'oracle", not sdiffs, f"({len(sdiffs)} écarts, ex. {sdiffs[:1]})")
    found = sum(1 for s in out["scans"] if s)
    check(f"{tag} repérage : au moins 6 parties avec une structure", found >= 6, f"({found})")
    hand = {name: [out["scans"][len(FIXTURE_GAMES) * 2 + i * 2], out["scans"][len(FIXTURE_GAMES) * 2 + i * 2 + 1]] for i, (name, _) in enumerate(HAND_GAMES)}
    cw = hand["carlsbad"][0]
    check(f"{tag} gambit dame d'échange : Carlsbad blanc vu, position au trait des Blancs, après le 10e demi-coup",
          bool(cw) and cw[0][0] == "carlsbad" and cw[0][1] == "w" and cw[0][2] >= oracle.MIN_PLY and cw[0][3].split()[1] == "w", f"({cw})")
    cb = hand["carlsbad"][1]
    check(f"{tag} même partie vue des Noirs : même structure, position au trait des Noirs",
          bool(cb) and cb[0][0] == "carlsbad" and cb[0][3].split()[1] == "b" and abs(cb[0][2] - cw[0][2]) == 1 if cw else False, f"({cb})")
    check(f"{tag} Panov : pion isolé blanc repéré", any(s[0] == "iqp" and s[1] == "w" for s in hand["panov"][0]), f"({hand['panov'][0]})")
    check(f"{tag} française : chaîne repérée", any(s[0] == "francaise" for s in hand["francaise"][0]), f"({hand['francaise'][0]})")
    check(f"{tag} partie trop courte : aucune structure", hand["courte"] == [[], []], f"({hand['courte']})")
    # Bilan : parties, gains, porteur.
    st = {s[0]: s[1:] for s in out["stats"]}
    if "carlsbad" in st:
        check(f"{tag} bilan : Carlsbad compté dans les parties semées", st["carlsbad"][0] >= 2, f"({st['carlsbad']})")
    check(f"{tag} fiches : une par structure, plans des deux camps non vides",
          all(out["meta"].get(sid, {}).get("planOwner") and out["meta"][sid].get("planOpponent") and out["meta"][sid].get("name") for sid in STRUCTURE_IDS))
    check(f"{tag} fiche retournée pour un porteur noir", out["mirrored"] == "Cd4, b5-b4 et Fxh2", f"({out['mirrored']})")
    lessons = set(COURSE["lessons"])
    check(f"{tag} chaque fiche renvoie à une leçon du cours", all(out["meta"][sid]["lesson"] in lessons for sid in STRUCTURE_IDS),
          f"({[out['meta'][s]['lesson'] for s in STRUCTURE_IDS if out['meta'][s]['lesson'] not in lessons]})")
    for sid in STRUCTURE_IDS:
        for k in ("planOwner", "planOpponent"):
            t = out["meta"][sid][k]
            check(f"{tag} fiche {sid} {k} : pas de tiret cadratin ni de notation anglaise",
                  "—" not in t and "–" not in t and not re.search(r"\b[KQNB][a-h]?[1-8]?x?[a-h][1-8]\b", t), f"({t})")


# ---------- 2. Cours ----------
def run_check(json_path=DATA, stamp_path=STAMP):
    res = subprocess.run(["node", "scripts/check-structures-course.mjs", json_path, stamp_path], cwd=ROOT, capture_output=True, text=True)
    return res.returncode, res.stdout + res.stderr


def lines_of(lesson_id):
    return [(i, s) for i, s in enumerate(COURSE["lessons"][lesson_id]["steps"]) if s["kind"] == "line"]


def chapter_of(lesson_id):
    return next(ch["id"] for ch in COURSE["chapters"] if lesson_id in ch["lessons"])


def anchor_fens():
    """[(leçon, étape, fen)] : départ de chaque ligne et premier diagramme de chaque leçon, qui
    doivent montrer la structure du chapitre (une rupture, plus loin, peut la dissoudre)."""
    out = []
    for lid in LESSONS:
        steps = COURSE["lessons"][lid]["steps"]
        first = next((i for i, s in enumerate(steps) if s["kind"] == "diagram"), None)
        for i, s in enumerate(steps):
            if s["kind"] == "line" or i == first:
                out.append((lid, i, s["fen"]))
    return out


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
    """Un coup légal hors `keeps` et hors `close` : le contrôle exige donc un refus."""
    b = chess.Board(fen)
    good = set(m.get("keeps", [])) | set(m.get("close", []))
    for mv in b.legal_moves:
        if mv.uci() not in good and not mv.promotion:
            return mv.uci()
    return None


def write_stamped(tmp, d):
    text = json.dumps(d, ensure_ascii=False, indent=2) + "\n"
    path = os.path.join(tmp, "course.json")
    stamp = os.path.join(tmp, "course.verified")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    with open(stamp, "w") as f:
        # Mêmes sha des vérificateurs que le vrai tampon : seul le contenu diffère.
        f.write(hashlib.sha256(text.encode()).hexdigest() + " " + " ".join(open(STAMP).read().split()[1:]) + "\n")
    return path, stamp


def mutations():
    lid = "carlsbad"
    lesson = COURSE["lessons"][lid]
    diag = next(i for i, s in enumerate(lesson["steps"]) if s["kind"] == "diagram")
    line = next(i for i, s in enumerate(lesson["steps"]) if s["kind"] == "line")

    def mut_fen(d):
        d["lessons"][lid]["steps"][diag]["fen"] = "4k3/8/8/8/8/8/4Q3/4K3 w - - 0 1"
    def mut_move(d):
        d["lessons"][lid]["steps"][line]["moves"][0]["san"] = "Qh8"
    def mut_verdict(d):
        s = d["lessons"][lid]["steps"][diag]
        s.pop("claim", None)
        s.pop("fails", None)
        s["text"] = "Ici, l'attaque de minorité gagne."
    def mut_line_verdict(d):
        d["lessons"][lid]["steps"][line]["end"] = "Les Blancs gagnent."
    def mut_dash(d):
        d["lessons"][lid]["summary"] += " — vite"
    def mut_keeps(d):
        d["lessons"][lid]["steps"][line]["moves"][0]["keeps"] = ["a2a3"]
    def mut_result(d):
        d["lessons"][lid]["steps"][line]["result"] = "win"
    def mut_frozen(d):
        d["lessons"]["carlsbad-bis"] = d["lessons"].pop(lid)
        for ch in d["chapters"]:
            ch["lessons"] = ["carlsbad-bis" if x == lid else x for x in ch["lessons"]]
    def mut_chapter(d):
        d["chapters"][0]["id"] = "isole"
    def mut_english(d):
        d["lessons"][lid]["steps"][line]["moves"][0]["text"] = "Le cavalier vise e5, puis Nd2 prépare la poussée."
    cases = [
        ("position illégale", mut_fen, "est en échec"),
        ("coup injouable", mut_move, "injouable"),
        ("verdict non tamponné dans un diagramme", mut_verdict, "sans claim ni fails"),
        ("verdict dans une ligne de plan", mut_line_verdict, "qu'une ligne de plan n'établit pas"),
        ("tiret cadratin", mut_dash, "tiret cadratin"),
        ("keeps sans le coup", mut_keeps, "keeps absent ou sans le coup"),
        ("résultat autre que plan", mut_result, "result invalide"),
        ("id figé renommé", mut_frozen, "supprimée ou renommée"),
        ("chapitre qui n'est pas une structure", mut_chapter, "un par structure"),
        ("notation anglaise", mut_english, "notation anglaise"),
    ]
    tmp = tempfile.mkdtemp(prefix="cours-structures-")
    try:
        for label, fn, expected in cases:
            d = json.loads(RAW)
            fn(d)
            path, stamp = write_stamped(tmp, d)
            code, out = run_check(path, stamp)
            check(f"[mutation] {label} : contrôle en échec", code == 1 and expected in out, f"(code {code}, attendu « {expected} » : {out.strip()[-200:]})")
            check(f"[mutation] {label} : tampon accepté (le refus vient de la règle visée)", "a changé depuis" not in out, f"({out.strip()[:160]})")
        path = os.path.join(tmp, "course.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(RAW.replace('"title": "', '"title": "x', 1))
        code, out = run_check(path, STAMP)
        check("[mutation] tampon périmé : contrôle en échec", code == 1 and "a changé depuis sa vérification" in out, f"(code {code})")
        # Tampon d'un autre vérificateur : le sha de la plomberie réutilisée est contrôlé.
        d = json.loads(RAW)
        path, stamp = write_stamped(tmp, d)
        words = open(stamp).read().split()
        with open(stamp, "w") as f:
            f.write(" ".join(words[:2] + ["0" * 64]) + "\n")
        code, out = run_check(path, stamp)
        check("[mutation] sha de verify-attack-course.py périmé : contrôle en échec", code == 1 and "plomberie moteur" in out, f"(code {code} : {out.strip()[-160:]})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cross_check():
    """Départs de lignes et premiers diagrammes : structure du chapitre, pour le bundle ET l'oracle."""
    anchors = anchor_fens()
    out = node_run([f for _, _, f in anchors], [])
    if out is None:
        return
    bad_ts, bad_py = [], []
    for (lid, si, fen), got in zip(anchors, out["detect"]):
        want = chapter_of(lid)
        if not any(sid == want for sid, _ in got):
            bad_ts.append((lid, si + 1, got))
        if not any(sid == want for sid, _ in oracle.detect(chess.Board(fen))):
            bad_py.append((lid, si + 1))
    check(f"[croisé] {len(anchors)} positions clés du cours reconnues par structures.ts comme la structure de leur chapitre", not bad_ts, f"({bad_ts[:3]})")
    check("[croisé] mêmes positions reconnues par l'oracle python-chess", not bad_py, f"({bad_py[:3]})")
    # Mutation : un départ de ligne remplacé par une position d'une autre structure est refusé.
    lid = "carlsbad"
    si, step = lines_of(lid)[0]
    french = after("e4 e6 d4 d5 e5")
    got = node_run([french], [])
    check("[croisé] mutation : une position française dans le chapitre Carlsbad n'y est pas reconnue",
          got is not None and not any(sid == "carlsbad" for sid, _ in got["detect"][0]), f"({got and got['detect'][0]})")


def feedback(page):
    return page.locator("[data-testid='line-feedback']").inner_text()


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


ROWS = """(domain) => new Promise((resolve) => {
  const req = indexedDB.open('chess-local')
  req.onsuccess = () => {
    const tx = req.result.transaction('learnSessions', 'readonly')
    const all = tx.objectStore('learnSessions').getAll()
    all.onsuccess = () => { resolve(all.result.filter((r) => r.domain === domain)); req.result.close() }
  }
})"""


def course_ui(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre")
    ck.appears("[entrée] carte Structures de pions", page, "button:has-text('Structures de pions')")
    check("[entrée] progression 0/N", page.locator("[data-testid='structures-card-progress']").inner_text() == f"0/{N} leçons")
    check("[entrée] tuile Mes structures de pions", page.locator("[data-testid='my-structures-tile']").count() == 1)
    page.locator("button", has_text="Structures de pions").click()
    ck.appears("[sommaire] titre", page, "h1:has-text('Structures de pions')")
    check("[sommaire] URL", page.url.endswith("#/apprendre/structures"), f"({page.url})")
    check("[sommaire] un chapitre par structure", page.locator("main section h2").count() == len(STRUCTURE_IDS), f"({page.locator('main section h2').count()})")
    check("[sommaire] toutes les leçons listées", page.locator("[data-lesson]").count() == N)
    check("[sommaire] onglet Apprendre allumé", page.locator("nav a[aria-current]", has_text="Apprendre").count() >= 1)
    check("[sommaire] carte « Dans mes parties »", page.locator("[data-testid='my-structures-card']").count() == 1)
    shot(page, "structures_index", full_page=True)

    lid = "carlsbad"
    lesson = COURSE["lessons"][lid]
    total = len(lesson["steps"]) + 1
    page.locator(f"[data-lesson='{lid}']").click()
    ck.appears("[carlsbad] étape 1", page, f"[data-testid='lesson-step']:has-text('1/{total}')")
    shot(page, "structures_carlsbad_diagram")
    li, line = lines_of(lid)[0]
    for _ in range(li):
        continue_btn(page).click()
        page.wait_for_timeout(200)
    ck.appears("[carlsbad] ligne ouverte", page, f"[data-testid='lesson-step']:has-text('{li + 1}/{total}')")
    check("[carlsbad] Continuer grisé tant que la ligne n'est pas jouée", not continue_btn(page).is_enabled())
    _, fen0, m0, uci0 = student_moves(line)[0]
    wrong = bad_move(fen0, m0)
    tap_move(page, wrong[:2], wrong[2:4], pause=120)
    fb = feedback(page)
    check("[carlsbad] mauvais coup : refus prudent (Stockfish, plan)", "Selon Stockfish" in fb and "abîme" in fb, f"({wrong} : {fb})")
    check("[carlsbad] indice du coup au premier échec", bool(m0.get("hint")) and "Indice" in fb, f"({fb})")
    page.wait_for_timeout(900)
    tap_move(page, uci0[:2], uci0[2:4])
    check("[carlsbad] bon coup accepté et commenté", (m0.get("text") or "Bien joué")[:25] in feedback(page), f"({feedback(page)})")
    page.wait_for_timeout(1100)
    shot(page, "structures_carlsbad_line")
    finish_line(page)
    check("[carlsbad] ligne jouée jusqu'au bout", continue_btn(page).is_enabled())
    check("[carlsbad] message de fin", line["end"][:30] in feedback(page), f"({feedback(page)})")
    continue_btn(page).click()
    page.wait_for_timeout(200)
    for s in lesson["steps"][li + 1:]:
        if s["kind"] == "line":
            finish_line(page)
        continue_btn(page).click()
        page.wait_for_timeout(200)
    ck.appears("[bilan] À retenir", page, "text=À retenir")
    page.wait_for_timeout(300)
    rows = [r["itemId"] for r in page.evaluate(ROWS, "course")]
    check("[progrès] une ligne learnSessions structures:carlsbad", rows == ["structures:carlsbad"], f"({rows})")
    shot(page, "structures_summary")

    # « Se défend aussi » : un coup de keeps autre que celui de la leçon.
    alt = None
    for l2 in LESSONS:
        for si, s in lines_of(l2):
            for i, fen, m, uci in student_moves(s):
                others = [u for u in m["keeps"] if u != uci and not chess.Move.from_uci(u).promotion]
                if others and alt is None:
                    alt = (l2, si, i, others[0])
    check("[se défend aussi] au moins un coup du cours a une autre suite dans le plan", alt is not None)
    if alt:
        l2, si, i, other = alt
        page.goto(f"{BASE}/#/apprendre/structures/{l2}?etape={si + 1}")
        ck.appears("[se défend aussi] ligne ouverte", page, f"[data-testid='lesson-step']:has-text('{si + 1}/')")
        for _ in range(i // 2):
            wait_ready(page)
            solution_btn(page).click()
            page.wait_for_timeout(1000)
        tap_move(page, other[:2], other[2:4], pause=120)
        check("[se défend aussi] message dédié", "se défend aussi" in feedback(page), f"({l2} {other} : {feedback(page)})")
        page.wait_for_timeout(900)

    # Toutes les leçons se jouent jusqu'au bilan.
    for l2 in LESSONS:
        page.goto(f"{BASE}/#/apprendre/structures/{l2}")
        page.wait_for_selector("[data-testid='lesson-step']", timeout=10000)
        ok = True
        for s in COURSE["lessons"][l2]["steps"]:
            if s["kind"] == "line":
                finish_line(page)
                ok = ok and continue_btn(page).is_enabled()
            continue_btn(page).click()
            page.wait_for_timeout(150)
        ok = ok and page.locator("text=À retenir").is_visible()
        check(f"[toutes] {l2} jouée jusqu'au bilan", ok)
    page.goto(f"{BASE}/#/apprendre")
    ck.appears("[toutes] carte N/N", page, f"[data-testid='structures-card-progress']:has-text('{N}/{N} leçons')")
    check("[toutes] le cours d'attaque reste à 0", page.locator("[data-testid='attack-card-progress']").inner_text().startswith("0/"))
    ctx.close()

    # 393x660 : échiquier, bulle et Continuer dans l'écran.
    ctx = mobile_context(p, browser, ck)
    page = ctx.new_page()
    longest = max(((l2, si) for l2 in LESSONS for si, s in enumerate(COURSE["lessons"][l2]["steps"])),
                  key=lambda x: len(COURSE["lessons"][x[0]]["steps"][x[1]]["text"]))
    for l2, si in [("carlsbad", 0), ("carlsbad", lines_of("carlsbad")[0][0]), longest]:
        page.goto(f"{BASE}/#/apprendre/structures/{l2}?etape={si + 1}")
        page.wait_for_selector("[id^='chessboard-']", timeout=10000)
        page.wait_for_timeout(500)
        board = page.locator("[id^='chessboard-']").first
        check(f"[660] {l2} étape {si + 1} : échiquier entier à l'écran", in_viewport(page, board), f"({board.bounding_box()})")
        check(f"[660] {l2} étape {si + 1} : Continuer à l'écran", in_viewport(page, continue_btn(page)))
        check(f"[660] {l2} étape {si + 1} : pas de défilement horizontal", overflow_x(page) == 0)
        shot(page, f"structures_660_{l2}_{si + 1}")
    ctx.close()


# ---------- 3. Dans mes parties ----------
T0 = 1760000000000
HAND_PGN = dict(HAND_GAMES)
# (clé, source, couleur du joueur, résultat PGN, partie) : les résultats du joueur se déduisent.
SEED = [
    ("local:1", "local", "w", "1-0", "carlsbad"),
    ("chesscom:9001", "chesscom", "b", "1-0", "carlsbad"),
    ("local:2", "local", "b", "1/2-1/2", "panov"),
    ("chesscom:9002", "chesscom", "w", "0-1", "francaise"),
    ("local:3", "local", "w", "1-0", "courte"),
]


def player_result(color, res):
    if res == "1/2-1/2":
        return "draw"
    return "win" if (res == "1-0") == (color == "w") else "loss"


def seed_rows():
    games, reviews = [], []
    for i, (key, source, color, res, name) in enumerate(SEED):
        pgn = HAND_PGN[name].replace(" *", f" {res}")
        if source == "local":
            games.append({"id": int(key.split(":")[1]), "date": T0 + i * 60000, "mode": "bot", "botId": "iris", "playerColor": color,
                          "timeControl": "5+0", "timeClass": "blitz", "pgn": pgn, "result": res, "termination": "abandon"})
        else:
            reviews.append({"key": key, "source": "chesscom", "username": "qa", "date": T0 + i * 60000, "timeClass": "blitz", "timeControl": "180",
                            "playerColor": color, "playerRating": 1500, "opponent": "Rival", "opponentRating": 1520, "result": player_result(color, res),
                            "termination": "abandon", "lostOnTime": False, "pgn": pgn, "depth": 12, "review": {}})
    # Témoins : une partie à deux joueurs (couleur inconnue) et le bilan Insights d'une partie locale
    # (doublon de `games`) : ni l'un ni l'autre ne compte.
    games.append({"id": 4, "date": T0 + 9 * 60000, "mode": "local", "playerColor": "w", "timeControl": "illimité", "timeClass": "unlimited",
                  "pgn": HAND_PGN["panov"].replace(" *", " 1-0"), "result": "1-0", "termination": "mat"})
    reviews.append(dict(reviews[0], key="local:1", source="local", username=None))
    return games, reviews


def expected_stats():
    st = {}
    for key, source, color, res, name in SEED:
        for sid, side, ply, fen in oracle.scan(HAND_PGN[name].replace(" *", f" {res}"), color):
            e = st.setdefault(sid, {"games": 0, "w": 0, "d": 0, "l": 0, "owner": 0, "pos": []})
            r = player_result(color, res)
            e["games"] += 1
            e[r[0]] += 1
            e["owner"] += side == color
            e["pos"].append((f"{key}@{ply}", fen))
    return st


SEED_JS = """([games, reviews]) => new Promise((resolve, reject) => {
  const req = indexedDB.open('chess-local')
  req.onerror = () => reject(req.error)
  req.onsuccess = () => {
    const db = req.result
    if (!db.objectStoreNames.contains('reviews')) { db.close(); reject(new Error('base non initialisée')); return }
    const tx = db.transaction(['games', 'reviews'], 'readwrite')
    for (const g of games) tx.objectStore('games').put(g)
    for (const r of reviews) tx.objectStore('reviews').put(r)
    tx.oncomplete = () => { db.close(); resolve(true) }
    tx.onerror = () => { db.close(); reject(tx.error) }
  }
})"""

GAME = "[data-testid='position-game']"


def my_structures(p, browser):
    tag = "[mes parties]"
    exp = expected_stats()
    order = sorted(exp, key=lambda s: (-exp[s]["games"], STRUCTURE_IDS.index(s)))
    check(f"{tag} jeu semé : Carlsbad, pion isolé et chaîne française attendus", {"carlsbad", "iqp", "francaise"} <= set(exp), f"({sorted(exp)})")

    # État vide.
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/structures")
    ck.appears(f"{tag} état vide", page, "[data-testid='structures-empty']")
    check(f"{tag} vide : toutes les structures « pas encore vues »", page.locator("[data-testid='structure-unseen']").count() == len(STRUCTURE_IDS))
    shot(page, "structures_mine_empty")

    # Parties semées.
    games, reviews = seed_rows()
    page.evaluate(SEED_JS, [games, reviews])
    page.goto(f"{BASE}/#/apprendre")
    page.locator("[data-testid='my-structures-tile']").click()
    ck.appears(f"{tag} cartes affichées", page, "[data-testid='structure-card']")
    check(f"{tag} URL", page.url.endswith("#/structures"), f"({page.url})")
    check(f"{tag} onglet Apprendre allumé", page.locator("nav a[aria-current]", has_text="Apprendre").count() >= 1)
    cards = page.locator("[data-testid='structure-card']")
    got_order = [cards.nth(i).get_attribute("data-id") for i in range(cards.count())]
    check(f"{tag} structures triées par fréquence (oracle)", got_order == order, f"({got_order}, attendu {order})")
    summary = page.locator("[data-testid='structures-summary']").inner_text()
    check(f"{tag} résumé : 5 parties lues (témoins écartés) et structure la plus fréquente", summary.startswith("Sur 5 parties") and "Carlsbad" in summary, f"({summary})")
    for sid in order:
        e = exp[sid]
        card = page.locator(f"[data-testid='structure-card'][data-id='{sid}']")
        rec = card.locator("[data-testid='structure-record']").inner_text()
        want = f"{e['games']} partie{'s' if e['games'] > 1 else ''} · {e['w']} V · {e['d']} N · {e['l']} D · {round((e['w'] + e['d'] / 2) / e['games'] * 100)} %"
        check(f"{tag} {sid} : bilan exact", rec == want, f"({rec!r}, attendu {want!r})")
        sides = card.locator("[data-testid='structure-sides']").inner_text()
        check(f"{tag} {sid} : avec / contre", sides.endswith(f": {e['owner']} · contre : {e['games'] - e['owner']}"), f"({sides})")
        keys = [card.locator("[data-testid='structure-position']").nth(i).get_attribute("data-key") for i in range(card.locator("[data-testid='structure-position']").count())]
        check(f"{tag} {sid} : positions de mes parties (clé partie@demi-coup)", sorted(keys) == sorted(k for k, _ in e["pos"]), f"({keys})")
    check(f"{tag} structures absentes listées à part", page.locator("[data-testid='structure-unseen']").count() == len(STRUCTURE_IDS) - len(exp))
    check(f"{tag} pas de débordement horizontal (852)", overflow_x(page) == 0, f"({overflow_x(page)} px)")
    shot(page, "structures_mine", full_page=True)

    # Lien vers la leçon.
    page.locator("[data-testid='structure-card'][data-id='carlsbad'] [data-testid='structure-lesson']").click()
    ck.appears(f"{tag} lien Leçon : leçon Carlsbad ouverte", page, "[data-testid='lesson-step']")
    check(f"{tag} lien Leçon : URL", page.url.endswith("#/apprendre/structures/carlsbad"), f"({page.url})")
    page.go_back()

    # Partie depuis une position de ma partie.
    key, fen = next((k, f) for k, f in exp["carlsbad"]["pos"] if k.startswith("local:1@"))
    ck.appears(f"{tag} retour à la liste", page, f"[data-testid='structure-position'][data-key='{key}']")
    page.locator(f"[data-testid='structure-position'][data-key='{key}']").click()
    ck.appears(f"{tag} partie ouverte", page, GAME)
    check(f"{tag} position de départ = apparition de la structure (oracle)", page.locator(GAME).get_attribute("data-fen") == fen, f"({page.locator(GAME).get_attribute('data-fen')} / {fen})")
    check(f"{tag} objectif : jouer le plan", "joue le plan" in page.locator("[data-testid='objective']").inner_text())
    check(f"{tag} puce du niveau de Stockfish", page.locator("[data-testid='level-chip']").count() == 1)
    shot(page, "structures_play")
    b = chess.Board(fen)
    mv = next(m for m in b.legal_moves if not m.promotion and not b.is_capture(m))
    tap_move(page, mv.uci()[:2], mv.uci()[2:4], pause=150)
    page.wait_for_function(f"() => {{ const g = document.querySelector(\"{GAME}\"); return g && g.dataset.thinking === '0' && g.dataset.fen.split(' ')[1] === '{'w' if b.turn else 'b'}' && g.dataset.fen !== {json.dumps(fen)} }}", timeout=30000)
    check(f"{tag} Stockfish a répondu", page.locator(GAME).get_attribute("data-fen") != fen)
    page.get_by_role("button", name="Recommencer").first.click()
    page.wait_for_timeout(600)
    rows = page.evaluate(ROWS, "structure-play")
    check(f"{tag} Recommencer : tentative notée (structure-play, clé, FEN, abandon)",
          len(rows) == 1 and rows[0]["itemId"] == key and rows[0]["fen"] == fen and rows[0]["outcome"] == "abandon" and rows[0]["success"] == 0 and rows[0]["ratingAfter"] is None,
          f"({rows})")
    page.goto(f"{BASE}/#/structures")
    ck.appears(f"{tag} essai affiché dans la liste", page, f"[data-testid='structure-position'][data-key='{key}'] [data-testid='structure-attempts']")

    # Une autre position remplace la tentative en cours : elle compte comme un abandon.
    page.locator(f"[data-testid='structure-position'][data-key='{key}']").click()
    ck.appears(f"{tag} nouvelle tentative ouverte", page, GAME)
    tap_move(page, mv.uci()[:2], mv.uci()[2:4], pause=150)
    page.wait_for_function(f"() => {{ const g = document.querySelector(\"{GAME}\"); return g && g.dataset.thinking === '0' && g.dataset.fen !== {json.dumps(fen)} }}", timeout=30000)
    other_key, other_fen = exp["iqp"]["pos"][0]
    page.goto(f"{BASE}/#/structures/{other_key.replace(':', '%3A').replace('@', '%40')}")
    ck.appears(f"{tag} autre position ouverte", page, GAME)
    other_move = next(m for m in chess.Board(other_fen).legal_moves if not m.promotion)
    tap_move(page, other_move.uci()[:2], other_move.uci()[2:4], pause=150)
    page.wait_for_timeout(600)
    replaced = [r for r in page.evaluate(ROWS, "structure-play") if r["itemId"] == key]
    check(f"{tag} remplacement : ancienne tentative notée une seule fois comme abandon",
          len(replaced) == 2 and all(r["outcome"] == "abandon" and r["success"] == 0 for r in replaced), f"({replaced})")

    # Clé inconnue.
    page.goto(f"{BASE}/#/structures/local%3A99%4012")
    ck.appears(f"{tag} position inconnue : message", page, "[data-testid='structure-missing']")
    ctx.close()

    # 393x660 et 1440x900.
    for name, make in (("660", lambda: mobile_context(p, browser, ck)), ("desktop", lambda: desktop_context(browser, ck))):
        ctx = make()
        page = ctx.new_page()
        page.goto(f"{BASE}/#/structures")
        page.wait_for_selector("[data-testid='structures-summary']", timeout=15000)
        page.evaluate(SEED_JS, [games, reviews])
        page.reload()
        ck.appears(f"{tag} [{name}] cartes", page, "[data-testid='structure-card']")
        check(f"{tag} [{name}] pas de débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
        shot(page, f"structures_mine_{name}", full_page=True)
        page.goto(f"{BASE}/#/structures/{key.replace(':', '%3A').replace('@', '%40')}")
        ck.appears(f"{tag} [{name}] partie", page, GAME)
        page.wait_for_timeout(500)
        check(f"{tag} [{name}] partie : pas de débordement horizontal", overflow_x(page) == 0)
        shot(page, f"structures_play_{name}")
        page.goto(f"{BASE}/#/apprendre/structures")
        page.wait_for_selector("[data-lesson]", timeout=10000)
        shot(page, f"structures_index_{name}", full_page=True)
        ctx.close()


def suite(p):
    oracle_section()
    code, out = run_check()
    check("[données] check-structures-course.mjs passe", code == 0, f"({out.strip()[-400:]})")
    check("[données] un chapitre par structure, 11 leçons au moins", [c["id"] for c in COURSE["chapters"]] == STRUCTURE_IDS and N >= 11,
          f"({len(COURSE['chapters'])} chapitres, {N} leçons)")
    if "carlsbad" not in COURSE["lessons"]:
        check("[données] leçon carlsbad présente", False)
        return
    if code == 0:
        mutations()
    cross_check()
    browser = p.chromium.launch(headless=True)
    try:
        course_ui(p, browser)
        my_structures(p, browser)
    finally:
        browser.close()


if __name__ == "__main__":
    ck.run(suite)
