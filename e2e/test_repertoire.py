"""E2E « Mon répertoire » (F20) : où je sors de la théorie dans mes parties chess.com.

Trois volets :
- banc Node (src/lib/myRepertoire.ts bundlé par rolldown, sans Dexie) : toutes les parties de la
  fixture chess.com plus des cas construits (bilans cohérents, bilan d'une autre partie, bilan
  abîmé, PGN illisible, partie depuis une position, doublon), confrontés à un oracle python-chess
  indépendant (positions d'openings.json : sortie, camp qui sort, coups théoriques, compteurs, coût,
  verdicts, priorité, coup typique, cadence) et lignes de séance réécrites depuis la partie ;
- UI avec bilans semés (IndexedDB natif, table `reviews`) : la page se construit sans réseau, puis
  « Charger » lit la fixture (pseudo `repertoire_qa`, requêtes comptées), fusion, filtres camp et
  cadence, séance « Prochain coup » (tentatives `opening-drill` comme l'entraîneur), états
  Corrigée / À revoir, Analyse de la partie au bon demi-coup avec retour, tuile d'Apprendre ;
- pseudo absent, invalide ou inconnu : jamais mémorisé.

Fondée sur la fixture e2e/fixtures/chesscom.json : ignorée en --live.
Usage : npm run test:e2e -- --suite repertoire
"""
import io
import json
import os
import subprocess
import sys
import tempfile

import chess
import chess.pgn

from helpers import BASE, LIVE, SHOTS, Checker, desktop_context, mobile_context, overflow_x, tap_move

if LIVE:
    print("[repertoire] suite fondée sur la fixture chess.com : ignorée en --live")
    sys.exit(0)

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(E2E_DIR)
ROLLDOWN = os.path.join(ROOT, "node_modules", ".bin", "rolldown")
ck = Checker("repertoire")
check = ck.check

USER = "repertoire_qa"
START_FEN = chess.STARTING_FEN
STORES = 7  # games, ratings, puzzleAttempts, rushScores, mistakes, learnSessions, reviews
COSTLY = 7

with open(os.path.join(E2E_DIR, "fixtures", "chesscom.json"), encoding="utf-8") as f:
    FIXTURE = json.load(f)["routes"]
with open(os.path.join(ROOT, "src", "data", "openings.json"), encoding="utf-8") as f:
    OPENINGS = json.load(f)


# ---------------------------------------------------------------- oracle (python-chess)
def pkey(board):
    """Placement, trait, roques : la clé de position du module (prise en passant ignorée)."""
    return " ".join(board.fen().split(" ")[:3])


THROUGH = {}  # clé de position -> [(ligne, demi-coups jusqu'à la position)]
NAMED = {}  # clé de position -> première ligne d'openings.json qui s'y termine
for _line in OPENINGS:
    _b = chess.Board()
    THROUGH.setdefault(pkey(_b), []).append((_line, 0))
    for _i, _u in enumerate(_line["uci"].split(" ")):
        _b.push_uci(_u)
        THROUGH.setdefault(pkey(_b), []).append((_line, _i + 1))
    NAMED.setdefault(pkey(_b), _line)


def family_of(name):
    if "London System" in name:
        return "London System"
    k = name.split(":")[0].split(",")[0].strip()
    for suf in (" Accepted", " Declined"):
        if k.endswith(suf):
            k = k[: -len(suf)]
    return k


def book_moves(key):
    out = {}
    for line, at in THROUGH.get(key, []):
        mv = line["uci"].split(" ")
        if at < len(mv):
            cur = out.get(mv[at])
            if cur is None:
                out[mv[at]] = {"uci": mv[at], "lines": 1, "name": line["name"], "len": len(line["uci"])}
            else:
                cur["lines"] += 1
                if len(line["uci"]) < cur["len"]:
                    cur["name"], cur["len"] = line["name"], len(line["uci"])
    return sorted(out.values(), key=lambda m: (-m["lines"], m["uci"]))


def parse(pgn):
    """Coups UCI d'une partie standard, ou None (illisible, départ non standard, sans coup)."""
    try:
        game = chess.pgn.read_game(io.StringIO(pgn))
    except Exception:
        return None
    if game is None or game.errors:
        return None
    fen = game.headers.get("FEN")
    if fen and fen != START_FEN:
        return None
    moves = [m.uci() for m in game.mainline_moves()]
    return moves or None


def exit_of(moves, color):
    b = chess.Board()
    keys = [pkey(b)]
    for u in moves[:40]:
        b.push_uci(u)
        keys.append(pkey(b))
    d = 0
    while d < len(moves) and d + 1 < len(keys) and keys[d + 1] in THROUGH:
        d += 1
    opening = None
    for n in range(min(d, len(keys) - 1), 0, -1):
        if keys[n] in NAMED:
            opening = NAMED[keys[n]]
            break
    name = opening["name"] if opening else "?"
    fam = family_of(name) if opening else "?"
    if d >= len(moves) or d + 1 >= len(keys):
        return "inBook", None, None, fam, name
    if not book_moves(keys[d]):
        return "end", None, None, fam, name
    mine = (d % 2 == 0) == (color == "w")
    return ("mine" if mine else "theirs"), d, keys[d], fam, name


def san_at(prefix, uci):
    b = chess.Board()
    for u in prefix:
        b.push_uci(u)
    return b.san(chess.Move.from_uci(uci))


def drop_of(review, moves, ply):
    if not isinstance(review, dict) or not isinstance(review.get("moves"), list):
        return None
    if review.get("startFen", START_FEN) != START_FEN:
        return None
    if ply >= len(review["moves"]):
        return None
    m = review["moves"][ply]
    if not isinstance(m, dict) or m.get("uci") != moves[ply]:
        return None
    try:
        before, after = float(m["winPctBefore"]), float(m["winPctAfter"])
    except (TypeError, ValueError, KeyError):
        return None
    if before != before or after != after:
        return None
    return max(0.0, before - after)


def low_median(xs):
    if not xs:
        return None
    s = sorted(xs)
    return s[(len(s) - 1) // 2]


def oracle(games, time_class="all"):
    out = {"games": 0, "skipped": 0, "reviewed": 0, "byColor": {c: {"games": 0, "openings": {}, "devs": {}} for c in "wb"}}
    seen = set()
    for g in games:
        if g["key"] in seen:
            continue
        seen.add(g["key"])
        if time_class != "all" and g["timeClass"] != time_class:
            continue
        moves = parse(g["pgn"]) if isinstance(g["pgn"], str) else None
        if not moves:
            out["skipped"] += 1
            continue
        color = g["playerColor"]
        kind, ply, key, fam, name = exit_of(moves, color)
        out["games"] += 1
        if g.get("review"):
            out["reviewed"] += 1
        cr = out["byColor"][color]
        cr["games"] += 1
        op = cr["openings"].setdefault(fam, {"games": 0, "wins": 0, "draws": 0, "losses": 0, "mine": 0, "theirs": 0, "end": 0, "inBook": 0})
        op["games"] += 1
        op[{"win": "wins", "draw": "draws", "loss": "losses"}[g["result"]]] += 1
        op[kind] += 1
        if kind != "mine":
            continue
        did = f"{color}|{key}"
        d = cr["devs"].get(did)
        if d is None:
            d = cr["devs"][did] = {"id": did, "family": fam, "opening": name, "games": 0, "wins": 0, "draws": 0, "losses": 0,
                                    "played": {}, "drops": [], "moves": [], "last": None, "lastDate": -1, "expected": [m["uci"] for m in book_moves(key)[:3]]}
        d["games"] += 1
        d[{"win": "wins", "draw": "draws", "loss": "losses"}[g["result"]]] += 1
        d["played"][moves[ply]] = d["played"].get(moves[ply], 0) + 1
        d["moves"].append(ply // 2 + 1)
        if g["date"] > d["lastDate"]:
            d["lastDate"], d["last"], d["prefix"], d["ply"] = g["date"], g["key"], moves[:ply], ply
        dr = drop_of(g.get("review"), moves, ply)
        if dr is not None:
            d["drops"].append(dr)
    for c in "wb":
        cr = out["byColor"][c]
        devs = []
        for d in cr["devs"].values():
            d["avgDrop"] = sum(d["drops"]) / len(d["drops"]) if d["drops"] else None
            d["verdict"] = "unknown" if d["avgDrop"] is None else ("costly" if d["avgDrop"] >= COSTLY else "ok")
            devs.append(d)

        def prio(d):
            rank = {"costly": 0, "unknown": 1, "ok": 2}[d["verdict"]]
            if d["verdict"] == "costly":
                k = (-d["avgDrop"] * d["games"], 0)
            elif d["verdict"] == "unknown":
                k = (-d["games"], -d["losses"])
            else:
                k = (-d["games"], 0)
            return (rank, k, d["ply"], d["id"])

        devs.sort(key=prio)
        cr["order"] = [d["id"] for d in devs]
        cr["mine"] = sum(len(d["moves"]) for d in devs)
        cr["typicalMove"] = low_median([m for d in devs for m in d["moves"]])
        for fam, op in cr["openings"].items():
            op["typicalMove"] = low_median([m for d in devs if d["family"] == fam for m in d["moves"]])
            op["order"] = [d["id"] for d in devs if d["family"] == fam]
        cr["openingOrder"] = [f for f, _ in sorted(cr["openings"].items(), key=lambda kv: (-kv[1]["games"], kv[0]))]
    return out


# ---------------------------------------------------------------- jeu de parties
def fixture_games():
    """Toutes les parties de la fixture, telles que toGame les rend (variantes écartées)."""
    out = []
    for url, entry in FIXTURE.items():
        body = entry.get("body") or {}
        if "/games/" not in url or url.endswith("/archives") or not isinstance(body, dict):
            continue
        user = url.split("/player/")[1].split("/")[0]
        for g in body.get("games", []):
            if not g.get("pgn") or g.get("rules") != "chess":
                continue
            color = "w" if g["white"]["username"].lower() == user else "b" if g["black"]["username"].lower() == user else None
            if color is None:
                continue
            me = g["white"] if color == "w" else g["black"]
            res = "win" if me["result"] == "win" else "draw" if me["result"] in ("agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient") else "loss"
            gid = g["url"].rstrip("/").split("/")[-1]
            out.append({"key": f"{user}:chesscom:{gid}", "user": user, "id": int(gid), "pgn": g["pgn"], "playerColor": color, "result": res,
                        "timeClass": g["time_class"], "date": g["end_time"] * 1000, "opponent": (g["black"] if color == "w" else g["white"])["username"], "review": None})
    return out


def synthetic_review(moves, drops):
    """Bilan valide (validRow d'insights.ts) : tous les coups à 50 %, sauf `drops` {ply: chute}."""
    b = chess.Board()
    out = []
    for i, u in enumerate(moves):
        mv = chess.Move.from_uci(u)
        san = b.san(mv)
        b.push(mv)
        dr = drops.get(i, 0)
        out.append({"san": san, "uci": u, "class": "mistake" if dr >= 10 else "good", "evalAfterCp": 0, "mateAfter": None,
                    "bestMoveUci": u, "winPctBefore": 55.0, "winPctAfter": 55.0 - dr})
    zero = {k: 0 for k in ("brilliant", "great", "best", "excellent", "good", "book", "inaccuracy", "mistake", "miss", "missedWin", "blunder")}
    return {"moves": out, "startFen": START_FEN, "startTurn": "w", "accuracyWhite": 80.0, "accuracyBlack": 80.0,
            "counts": {"w": dict(zero), "b": dict(zero)}, "gameRatingWhite": 1000, "gameRatingBlack": 1000, "winPctSeries": [50.0] * (len(moves) + 1)}


def san_pgn(sans, white, black, result="1-0"):
    b = chess.Board()
    for s in sans.split():
        b.push_san(s)
    game = chess.pgn.Game.from_board(b)
    game.headers.clear()
    game.headers["White"], game.headers["Black"], game.headers["Result"] = white, black, result
    return str(game)


REP = {g["id"]: g for g in fixture_games() if g["user"] == USER}
# Partie seulement présente dans le cache des bilans (plus ancienne que les 3 mois chargés) :
# même sortie que 304 (Deux cavaliers, 4. De2), bilan à -20 %.
OLD_399 = {"key": "chesscom:399", "pgn": san_pgn("e4 e5 Nf3 Nc6 Bc4 Nf6 Qe2 Bc5 c3 O-O", USER, "QaOld"), "playerColor": "w", "result": "loss",
           "timeClass": "blitz", "date": 1781100000000, "opponent": "QaOld"}
# Chutes des bilans semés : 301 et 302 (Italienne, 4. h3 par deux ordres de coups), 308 (Sicilienne, 5... Db6).
DROPS = {301: {6: 15.0}, 302: {6: 9.0}, 308: {9: 2.0}, 399: {6: 20.0}}


def rep_game(gid):
    g = dict(REP[gid]) if gid in REP else dict(OLD_399)
    g["key"] = f"chesscom:{gid}"
    return g


def with_review(g, gid):
    g = dict(g)
    g["review"] = synthetic_review(parse(g["pgn"]), DROPS[gid])
    return g


def bench_cases():
    allg = fixture_games()
    cached = [with_review(rep_game(i), i) for i in (301, 302, 308, 399)]
    loaded = cached + [rep_game(i) for i in sorted(REP) if i not in (301, 302, 308)]
    bad = dict(rep_game(304), key="cas:autre-bilan")
    bad["review"] = synthetic_review(parse(rep_game(301)["pgn"]), {6: 30.0})  # bilan d'une autre partie
    nan = dict(rep_game(308), key="cas:nan")
    nan["review"] = dict(synthetic_review(parse(nan["pgn"]), {9: 12.0}))
    nan["review"]["moves"] = [dict(m) for m in nan["review"]["moves"]]
    nan["review"]["moves"][9]["winPctAfter"] = "NaN"
    custom = dict(rep_game(308), key="cas:depart-perso")
    custom["review"] = dict(synthetic_review(parse(custom["pgn"]), {9: 40.0}), startFen="4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
    short = dict(rep_game(308), key="cas:revue-courte")
    short["review"] = dict(synthetic_review(parse(short["pgn"])[:5], {}))
    junk = [dict(rep_game(301), key="cas:illisible", pgn="1. e4 e5 2. Ke3 *"), dict(rep_game(301), key="cas:vide", pgn='[White "a"]\n\n*'),
            dict(rep_game(301), key="cas:doublon")] + [dict(rep_game(301), key="cas:doublon", result="win")]
    return {
        "fixture": {"games": allg, "tc": "all"},
        "fixture:blitz": {"games": allg, "tc": "blitz"},
        "fixture:bullet": {"games": allg, "tc": "bullet"},
        "cache": {"games": cached, "tc": "all"},
        "charge": {"games": loaded, "tc": "all"},
        "charge:rapid": {"games": loaded, "tc": "rapid"},
        "abimes": {"games": [bad, nan, custom, short] + junk, "tc": "all"},
    }


BENCH_JS = r"""
import { readFileSync } from 'node:fs'
const mod = await import(process.argv[2])
const data = JSON.parse(readFileSync(process.argv[3], 'utf8'))
const t0 = performance.now()
mod.bookIndex()
const indexMs = performance.now() - t0
const out = { indexMs, cases: {}, drill: {} }
for (const [name, c] of Object.entries(data.cases)) out.cases[name] = mod.computeRepertoire(c.games, c.tc)
for (const [name, d] of Object.entries(data.drill)) out.drill[name] = mod.drillLines(d.prefix, d.opening)
console.log(JSON.stringify(out))
"""

DRILL_CASES = {
    # 302 : Italienne atteinte par 2. Fc4 puis 3. Cf3 (transposition).
    "transpose": {"prefix": parse(REP[302]["pgn"])[:6], "opening": "Italian Game"},
    "sicilienne": {"prefix": parse(REP[308]["pgn"])[:9], "opening": "Sicilian Defense"},
}


def node_bench(cases):
    src = os.path.join(ROOT, "src", "lib", "myRepertoire.ts")
    if not os.path.exists(src):
        ck.fail("[banc] src/lib/myRepertoire.ts existe", "(fichier absent)")
        return None
    with tempfile.TemporaryDirectory() as d:
        bundle = os.path.join(d, "rep.mjs")
        r = subprocess.run([ROLLDOWN, src, "--format", "esm", "--file", bundle], cwd=ROOT, capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            ck.fail("[banc] bundle rolldown de myRepertoire.ts", (r.stderr or r.stdout)[-300:])
            return None
        with open(bundle, encoding="utf-8") as f:
            code = f.read()
        check("[banc] module pur : ni Dexie ni IndexedDB dans le bundle", "dexie" not in code.lower() and "indexeddb" not in code.lower())
        script = os.path.join(d, "bench.mjs")
        data = os.path.join(d, "cases.json")
        with open(script, "w", encoding="utf-8") as f:
            f.write(BENCH_JS)
        with open(data, "w", encoding="utf-8") as f:
            json.dump({"cases": cases, "drill": DRILL_CASES}, f)
        r = subprocess.run(["node", script, "file://" + bundle, data], cwd=ROOT, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        ck.fail("[banc] computeRepertoire sous Node", r.stderr.strip()[-400:])
        return None
    return json.loads(r.stdout.strip().splitlines()[-1])


def close(a, b, tol=1e-6):
    return (a is None and b is None) or (a is not None and b is not None and abs(a - b) < tol)


def compare(name, got, exp):
    tag = f"[banc {name}]"
    check(f"{tag} parties, ignorées, avec bilan", (got["games"], got["skipped"], got["reviewed"]) == (exp["games"], exp["skipped"], exp["reviewed"]),
          f"({got['games']}, {got['skipped']}, {got['reviewed']} contre {exp['games']}, {exp['skipped']}, {exp['reviewed']})")
    for c in "wb":
        g, e = got["byColor"][c], exp["byColor"][c]
        t = f"{tag} {c}"
        check(f"{t} : parties, sorties du joueur, coup typique", (g["games"], g["mine"], g["typicalMove"]) == (e["games"], e["mine"], e["typicalMove"]),
              f"({g['games']}, {g['mine']}, {g['typicalMove']} contre {e['games']}, {e['mine']}, {e['typicalMove']})")
        check(f"{t} : ouvertures dans l'ordre (parties puis nom)", [o["family"] for o in g["openings"]] == e["openingOrder"], f"({[o['family'] for o in g['openings']]} contre {e['openingOrder']})")
        bad = []
        for o in g["openings"]:
            eo = e["openings"].get(o["family"])
            keys = ("games", "wins", "draws", "losses", "mine", "theirs", "end", "inBook", "typicalMove")
            if eo is None or any(o[k] != eo[k] for k in keys) or [d["id"] for d in o["deviations"]] != eo["order"]:
                bad.append((o["family"], {k: o[k] for k in keys}, eo))
        check(f"{t} : compteurs par ouverture (V/N/D, sorties, adverses, fin de théorie, dans la théorie)", not bad, f"({bad[:2]})")
        check(f"{t} : sorties dans l'ordre de priorité", [d["id"] for d in g["deviations"]] == e["order"], f"({[d['id'][-30:] for d in g['deviations']]} contre {[x[-30:] for x in e['order']]})")
        bad = []
        for d in g["deviations"]:
            ed = e["devs"].get(d["id"])
            if ed is None:
                bad.append((d["id"], "absente de l'oracle"))
                continue
            played = {m["uci"]: m["games"] for m in d["played"]}
            sans_ok = all(m["san"] == san_at(ed["prefix"], m["uci"]) for m in d["played"]) and all(x["san"] == san_at(ed["prefix"], x["uci"]) for x in d["expected"])
            fields = (d["family"], d["opening"], d["games"], d["wins"], d["draws"], d["losses"], d["reviewed"], d["verdict"], d["prefix"], d["ply"], d["moveNumber"], d["last"]["key"])
            efields = (ed["family"], ed["opening"], ed["games"], ed["wins"], ed["draws"], ed["losses"], len(ed["drops"]), ed["verdict"], ed["prefix"], ed["ply"], ed["ply"] // 2 + 1, ed["last"])
            if fields != efields or played != ed["played"] or [x["uci"] for x in d["expected"]] != ed["expected"] or not close(d["avgDrop"], ed["avgDrop"]) or not sans_ok:
                bad.append((d["id"][-40:], fields, efields, played, ed["played"], d["avgDrop"], ed["avgDrop"]))
        check(f"{t} : chaque sortie (coups joués, théorie attendue, SAN, résultats, coût, verdict, partie la plus récente)", not bad, f"({bad[:2]})")
    return True


def find_dev(report, color, prefix_sans):
    b = chess.Board()
    for s in prefix_sans.split():
        b.push_san(s)
    did = f"{color}|{pkey(b)}"
    return next((d for d in report["byColor"][color]["deviations"] if d["id"] == did), None), did


def bench_checks(out, cases):
    print(f"[info] index des positions théoriques construit en {out['indexMs']:.0f} ms")
    exp = {name: oracle(c["games"], c["tc"]) for name, c in cases.items()}
    for name in cases:
        compare(name, out["cases"][name], exp[name])
    got = out["cases"]
    # Ancres littérales sur le jeu repertoire_qa chargé (en plus de l'oracle).
    tag = "[banc ancres]"
    ch = got["charge"]
    it, _ = find_dev(ch, "w", "e4 e5 Nf3 Nc6 Bc4 Bc5")
    check(f"{tag} Italienne 4. h3 (deux ordres de coups) et 4. a3 : une seule sortie, 3 parties, deux ordres de coups",
          it is not None and it["games"] == 3 and sorted(it["prefixes"]) == sorted(["e2e4 e7e5 f1c4 b8c6 g1f3 f8c5", "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5"])
          and [(m["san"], m["games"]) for m in it["played"]] == [("h3", 2), ("a3", 1)], f"({it and (it['games'], it['prefixes'], it['played'])})")
    check(f"{tag} Italienne : coût moyen (15 + 9) / 2 = 12 % sur 2 bilans, coûteuse, théorie b4, c3, O-O",
          it is not None and close(it["avgDrop"], 12.0) and it["reviewed"] == 2 and it["verdict"] == "costly" and [x["san"] for x in it["expected"]] == ["b4", "c3", "O-O"],
          f"({it and (it['avgDrop'], it['reviewed'], it['verdict'], [x['san'] for x in it['expected']])})")
    check(f"{tag} Italienne : la séance part de la partie la plus récente (303, 4. a3)", it is not None and it["last"]["key"] == "chesscom:303" and it["prefix"] == parse(REP[303]["pgn"])[:6])
    tk, _ = find_dev(ch, "w", "e4 e5 Nf3 Nc6 Bc4 Nf6")
    order_w = [d["id"] for d in ch["byColor"]["w"]["deviations"]]
    check(f"{tag} Deux cavaliers 4. De2 : 2 parties, 1 bilan (-20 %), en tête de file (20 x 2 > 12 x 3)",
          tk is not None and tk["games"] == 2 and tk["reviewed"] == 1 and close(tk["avgDrop"], 20.0) and order_w[:2] == [tk["id"], it["id"]], f"({tk and (tk['games'], tk['avgDrop'])}, {len(order_w)})")
    ca = got["cache"]
    order_cache = [d["id"] for d in ca["byColor"]["w"]["deviations"]]
    check(f"{tag} avant chargement : l'Italienne passe devant (12 x 2 > 20 x 1)", order_cache[:2] == [it["id"], tk["id"]], f"({len(order_cache)})")
    sic, _ = find_dev(ch, "b", "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3")
    sc, _ = find_dev(ch, "b", "e4 d5 exd5 Qxd5 Nc3 Qd8 d4")
    check(f"{tag} Noirs : Sicilienne 5... Db6 sans dommage (2 %, 1 bilan sur 2 parties), Scandinave 4... h6 sans bilan avant elle",
          sic is not None and sic["verdict"] == "ok" and sic["games"] == 2 and sc is not None and sc["verdict"] == "unknown"
          and [d["id"] for d in ch["byColor"]["b"]["deviations"]] == [sc["id"], sic["id"]])
    fam = {o["family"]: o for o in ch["byColor"]["w"]["openings"]}
    check(f"{tag} Blancs : 1.d4 d5 2.Ff4 Cf6 sortie adverse ; 3.Fb5 a6 finie dans la théorie ; Evans Hein 5. exd5 fin de théorie connue",
          sum(o["theirs"] for o in fam.values()) == 1 and sum(o["inBook"] for o in fam.values()) == 1 and sum(o["end"] for o in fam.values()) == 1,
          f"({[(k, o['theirs'], o['inBook'], o['end']) for k, o in fam.items()]})")
    check(f"{tag} partie « depuis une position » (en-tête FEN) ignorée et comptée", ch["skipped"] == 1, f"({ch['skipped']})")
    ab = got["abimes"]
    check(f"{tag} bilan d'une autre partie, win% illisible, départ non standard, bilan trop court : aucun coût",
          all(d["reviewed"] == 0 and d["verdict"] == "unknown" for c in "wb" for d in ab["byColor"][c]["deviations"]), "")
    check(f"{tag} PGN illisible et sans coup ignorés, doublon de clé compté une fois", ab["skipped"] == 2 and ab["games"] == 5, f"({ab['skipped']}, {ab['games']})")
    # Lignes de séance : réécrites depuis les coups réels, mêmes coups théoriques que la position.
    for name, d in DRILL_CASES.items():
        lines = out["drill"][name]
        head = " ".join(d["prefix"])
        b = chess.Board()
        for u in d["prefix"]:
            b.push_uci(u)
        nexts = {l["uci"].split(" ")[len(d["prefix"])] for l in lines if len(l["uci"].split(" ")) > len(d["prefix"])}
        exp_moves = {m["uci"] for m in book_moves(pkey(b))}
        legal = True
        for l in lines:
            bb = chess.Board()
            for u in l["uci"].split(" "):
                mv = chess.Move.from_uci(u)
                if mv not in bb.legal_moves:
                    legal = False
                    break
                bb.push(mv)
        check(f"[banc séance {name}] lignes réécrites depuis la partie : toutes partent de ses coups, sont légales, ligne nommée de la position présente",
              all(l["uci"] == head or l["uci"].startswith(head + " ") for l in lines) and legal and any(l["uci"] == head for l in lines), f"({len(lines)} lignes)")
        check(f"[banc séance {name}] coups suivants = coups théoriques de la position (transpositions comprises)", nexts == exp_moves, f"({sorted(nexts)} contre {sorted(exp_moves)})")


# ---------------------------------------------------------------- UI
OPEN_DB = f"""
() => new Promise((res, rej) => {{
  const r = indexedDB.open('chess-local')
  r.onsuccess = () => {{
    const db = r.result
    if (db.objectStoreNames.length !== {STORES}) {{ db.close(); rej(new Error('schéma inattendu : ' + db.objectStoreNames.length + ' stores')); return }}
    res(db)
  }}
  r.onerror = () => rej(r.error)
}})
"""


def wait_schema(page, tries=60):
    for _ in range(tries):
        n = page.evaluate(
            """() => new Promise((res) => {
              indexedDB.databases().then((list) => {
                if (!list.some((d) => d.name === 'chess-local')) return res(0)
                const r = indexedDB.open('chess-local')
                r.onsuccess = () => { const n = r.result.objectStoreNames.length; r.result.close(); res(n) }
                r.onerror = () => res(-1)
              })
            })"""
        )
        if n == STORES:
            return True
        page.wait_for_timeout(250)
    return False


def seed_db(page, data):
    page.evaluate(
        "async (data) => {"
        f"  const db = await ({OPEN_DB})()"
        """
          const tx = db.transaction(Object.keys(data), 'readwrite')
          for (const [t, rows] of Object.entries(data)) for (const r of rows) tx.objectStore(t).put(r)
          await new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = () => rej(tx.error); tx.onabort = () => rej(tx.error) })
          db.close()
        }""",
        data,
    )


def rows_of(page, store):
    return page.evaluate(
        "async (store) => {"
        f"  const db = await ({OPEN_DB})()"
        """
          const rows = await new Promise((res, rej) => { const q = db.transaction(store).objectStore(store).getAll(); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error) })
          db.close()
          return rows
        }""",
        store,
    )


def review_row(g, gid, username=USER, key=None):
    return {
        "key": key or f"chesscom:{gid}", "source": "chesscom", "username": username, "date": g["date"], "timeClass": g["timeClass"],
        "timeControl": "180", "playerColor": g["playerColor"], "playerRating": 1010, "opponent": g["opponent"], "opponentRating": 1000,
        "result": g["result"], "termination": "abandon", "lostOnTime": False, "pgn": g["pgn"], "depth": 10,
        "review": synthetic_review(parse(g["pgn"]), DROPS.get(gid, {})),
    }


def seeded_rows():
    rows = [review_row(rep_game(i), i) for i in (301, 302, 308, 399)]
    # Ignorées : autre compte, partie ChessLocal, bilan abîmé.
    rows.append(review_row(rep_game(304), 304, username="someone_else", key="chesscom:398"))
    local = review_row(rep_game(304), 304, key="local:1")
    rows.append(dict(local, source="local", username=None))
    broken = review_row(rep_game(309), 309, key="chesscom:397")
    broken["review"] = dict(broken["review"], moves="x")
    rows.append(broken)
    return rows


def count_api_calls(ctx):
    box = {"n": 0, "urls": []}

    def on_req(req):
        if "api.chess.com" in req.url:
            box["n"] += 1
            box["urls"].append(req.url)

    ctx.on("request", on_req)
    return box


def attr(page, selector, name):
    el = page.locator(selector)
    return el.first.get_attribute(name) if el.count() else None


def ui_cards(page):
    """(famille, parties) des cartes affichées, dans l'ordre."""
    return page.evaluate("() => [...document.querySelectorAll('[data-opening]')].map((e) => [e.getAttribute('data-opening'), Number(e.querySelector('[data-opening-games]').getAttribute('data-opening-games'))])")


def ui_devs(page):
    return page.evaluate("() => [...document.querySelectorAll('[data-deviation]')].map((e) => [e.getAttribute('data-deviation'), e.getAttribute('data-verdict'), e.getAttribute('data-state')])")


def pick(page, group, option):
    page.get_by_role("group", name=group).get_by_role("button", name=option, exact=True).click()
    try:
        page.wait_for_function(
            """([g, o]) => [...document.querySelectorAll(`[role=group][aria-label="${g}"] button`)]
                 .some((b) => b.textContent.trim() === o && b.getAttribute('aria-pressed') === 'true')""",
            arg=[group, option], timeout=3000,
        )
    except Exception:
        pass
    page.wait_for_timeout(200)


def expected_cards(rep, color):
    cr = rep["byColor"][color]
    # Toutes les sorties d'une ouverture ne sont pas affichées (3 premières) : cartes + ordre global.
    return [[f, cr["openings"][f]["games"]] for f in cr["openingOrder"]]


def shown_dev_ids(rep, color):
    cr = rep["byColor"][color]
    out = []
    for f in cr["openingOrder"]:
        out += cr["openings"][f]["order"][:3]
    return out


def wait_rows(page, n, timeout=8000):
    for _ in range(timeout // 200):
        rows = [r for r in rows_of(page, "learnSessions") if r["domain"] == "opening-drill"]
        if len(rows) >= n:
            return rows
        page.wait_for_timeout(200)
    return [r for r in rows_of(page, "learnSessions") if r["domain"] == "opening-drill"]


def legal_off_book(prefix):
    b = chess.Board()
    for u in prefix:
        b.push_uci(u)
    book = {m["uci"] for m in book_moves(pkey(b))}
    prefixes = set()
    for line in OPENINGS:
        mv = line["uci"].split(" ")
        for n in range(1, len(mv) + 1):
            prefixes.add(" ".join(mv[:n]))
    for mv in sorted(b.legal_moves, key=lambda m: m.uci()):
        nb = b.copy()
        nb.push(mv)
        if mv.uci() not in book and pkey(nb) not in THROUGH and " ".join(prefix + [mv.uci()]) not in prefixes and not mv.promotion:
            return mv.uci()
    return None


def seeded_page(p, browser):
    tag = "[ui]"
    ctx = mobile_context(p, browser, ck, settings={"chesscomUsername": USER}, standalone=True, service_workers="block")
    calls = count_api_calls(ctx)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre")
    ck.appears(f"{tag} Apprendre chargé", page, "main a:has-text('Mon répertoire')", timeout=20000)
    if not check(f"{tag} base Dexie en version 3 ({STORES} stores)", wait_schema(page)):
        ctx.close()
        return
    seed_db(page, {"reviews": seeded_rows()})
    cached = oracle([with_review(rep_game(i), i) for i in (301, 302, 308, 399)])

    # Tuile d'Apprendre, juste après l'entraîneur d'ouvertures.
    tiles = page.locator("main a").all_inner_texts()
    idx = next((i for i, t in enumerate(tiles) if "Entraîneur d'ouvertures" in t), -1)
    check(f"{tag} tuile « Mon répertoire » juste après l'entraîneur d'ouvertures", idx >= 0 and idx + 1 < len(tiles) and "Mon répertoire" in tiles[idx + 1], f"({tiles})")
    page.locator("main a", has_text="Mon répertoire").click()
    ck.appears(f"{tag} page ouverte", page, "main h1:has-text('Mon répertoire')", timeout=10000)
    check(f"{tag} route #/repertoire", page.evaluate("() => location.hash").startswith("#/repertoire"))
    tab = page.locator("nav a", has_text="Apprendre").last
    check(f"{tag} onglet Apprendre allumé", tab.get_attribute("aria-current") is not None)

    # Sans réseau : les bilans en cache de ce compte seulement (autre compte, ChessLocal, abîmé exclus).
    ck.appears(f"{tag} cartes d'ouvertures depuis le cache", page, "[data-opening]", timeout=15000)
    check(f"{tag} cache : 4 parties, 4 avec bilan", (attr(page, "[data-games-count]", "data-games-count"), attr(page, "[data-reviewed-count]", "data-reviewed-count")) == ("4", "4"),
          f"({attr(page, '[data-games-count]', 'data-games-count')}, {attr(page, '[data-reviewed-count]', 'data-reviewed-count')})")
    check(f"{tag} cache : aucune requête chess.com avant le tap", calls["n"] == 0, f"({calls['urls']})")
    check(f"{tag} cache : cartes Blancs = oracle", ui_cards(page) == expected_cards(cached, "w"), f"({ui_cards(page)} contre {expected_cards(cached, 'w')})")
    devs = ui_devs(page)
    check(f"{tag} cache : sorties affichées et verdicts = oracle (Italienne coûteuse en tête)",
          [d[0] for d in devs] == shown_dev_ids(cached, "w") and all(d[1] == cached["byColor"]["w"]["devs"][d[0]]["verdict"] for d in devs), f"({devs})")
    it_id = cached["byColor"]["w"]["order"][0]
    row = page.locator(f"[data-deviation='{it_id}']")
    played = row.locator("[data-played]").inner_text() if row.count() else ""
    theory = row.locator("[data-theory]").inner_text() if row.count() else ""
    cost = row.locator("[data-cost]").inner_text().replace("\xa0", " ") if row.count() else ""
    check(f"{tag} Italienne : « 4.♙h3 », théorie « ♙b4, ♙c3, O-O », « −12 % de gain »", "4.h3" in played and "b4, c3, O-O" in theory and cost == "−12 % de gain", f"({played!r}, {theory!r}, {cost!r})")
    summary = page.locator("[data-summary]").inner_text().replace("\xa0", " ")
    check(f"{tag} résumé Blancs : 3 parties, 3 sorties, coup 4", "3 parties" in summary and "dans 3" in summary and "coup 4" in summary, f"({summary!r})")
    check(f"{tag} pas de débordement horizontal (393x852)", overflow_x(page) == 0, f"({overflow_x(page)} px)")
    page.screenshot(path=f"{SHOTS}/repertoire_cache_852.png", full_page=True)

    # Chargement : liste des archives + 3 mois, une seule fois, puis fusion sans doublon.
    page.locator("[data-load]").click()
    ck.appears(f"{tag} chargement terminé", page, "[data-load]:has-text('Recharger')", timeout=20000)
    page.wait_for_timeout(300)
    check(f"{tag} chargement : 4 requêtes, toutes dans la fixture (archives + 3 mois)", calls["n"] == 4 and all(USER in u for u in calls["urls"]), f"({calls['urls']})")
    loaded_games = [with_review(rep_game(i), i) for i in (301, 302, 308, 399)] + [rep_game(i) for i in sorted(REP) if i not in (301, 302, 308)]
    loaded = oracle(loaded_games)
    check(f"{tag} fusion : 13 parties (4 en cache + 9 chargées, 3 doublons, variante écartée), 4 bilans",
          (attr(page, "[data-games-count]", "data-games-count"), attr(page, "[data-reviewed-count]", "data-reviewed-count")) == ("13", "4"),
          f"({attr(page, '[data-games-count]', 'data-games-count')})")
    check(f"{tag} chargé : cartes Blancs = oracle", ui_cards(page) == expected_cards(loaded, "w"), f"({ui_cards(page)} contre {expected_cards(loaded, 'w')})")
    check(f"{tag} chargé : sorties Blancs dans l'ordre de l'oracle (Deux cavaliers passe en tête)", [d[0] for d in ui_devs(page)] == shown_dev_ids(loaded, "w"), f"({ui_devs(page)})")
    check(f"{tag} partie depuis une position signalée comme ignorée", page.locator("main", has_text="1 partie ignorée").count() == 1)
    page.screenshot(path=f"{SHOTS}/repertoire_loaded_852.png", full_page=True)

    # Camp et cadence (URL, remplacement d'historique).
    pick(page, "Camp", "Noirs")
    check(f"{tag} Noirs : cartes = oracle", ui_cards(page) == expected_cards(loaded, "b"), f"({ui_cards(page)} contre {expected_cards(loaded, 'b')})")
    check(f"{tag} Noirs : Scandinave sans bilan avant Sicilienne sans dommage", [(d[0], d[1]) for d in ui_devs(page)] == [(i, loaded["byColor"]["b"]["devs"][i]["verdict"]) for i in shown_dev_ids(loaded, "b")], f"({ui_devs(page)})")
    pick(page, "Cadence", "Bullet")
    bullet = oracle(loaded_games, "bullet")
    check(f"{tag} Noirs bullet : cartes = oracle (Scandinave seule)", ui_cards(page) == expected_cards(bullet, "b"), f"({ui_cards(page)})")
    check(f"{tag} camp et cadence dans l'URL", "camp=b" in page.evaluate("() => location.hash") and "cadence=bullet" in page.evaluate("() => location.hash"))
    pick(page, "Cadence", "Rapide")
    pick(page, "Camp", "Blancs")
    rapid = oracle(loaded_games, "rapid")
    check(f"{tag} Blancs rapide : finie dans la théorie, aucune sortie", ui_cards(page) == expected_cards(rapid, "w") and page.locator("[data-start]").is_disabled(), f"({ui_cards(page)})")
    pick(page, "Cadence", "Toutes")

    # Séance : la file des Blancs, dans l'ordre de priorité.
    order = loaded["byColor"]["w"]["order"]
    first, second = loaded["byColor"]["w"]["devs"][order[0]], loaded["byColor"]["w"]["devs"][order[1]]
    start = page.locator("[data-start]")
    check(f"{tag} CTA « S'entraîner sur mes sorties ({len(order)}) »", f"({len(order)})" in start.inner_text(), f"({start.inner_text()!r})")
    start.click()
    if ck.appears(f"{tag} séance : drill « Prochain coup » ouvert", page, "[data-drill][data-mode='next']", timeout=8000):
        check(f"{tag} séance : 1re sortie = position de la partie la plus récente (Deux cavaliers, 304)", attr(page, "[data-drill]", "data-uci") == " ".join(first["prefix"]), f"({attr(page, '[data-drill]', 'data-uci')})")
        check(f"{tag} séance : titre « Sortie 1/{len(order)} »", page.locator("[data-drill] h1", has_text=f"Sortie 1/{len(order)}").count() == 1)
        page.screenshot(path=f"{SHOTS}/repertoire_drill_852.png")
        wrong = legal_off_book(first["prefix"])
        tap_move(page, wrong[:2], wrong[2:4])
        ck.appears(f"{tag} séance : coup hors théorie -> flèches de la théorie", page, "[data-drill][data-hint]", timeout=5000)
        rows = wait_rows(page, 1)
        check(f"{tag} séance : échec enregistré comme l'entraîneur (opening-drill, next:w:<UCI>, 0)",
              [(r["itemId"], r["success"], r["ratingAfter"]) for r in rows] == [(f"next:w:{' '.join(first['prefix'])}", 0, None)], f"({rows})")
        hint = attr(page, "[data-drill]", "data-hint")
        check(f"{tag} séance : coup attendu = premier coup théorique de l'oracle", hint == first["expected"][0], f"({hint} contre {first['expected']})")
        tap_move(page, hint[:2], hint[2:4])
        page.wait_for_timeout(600)
        if ck.appears(f"{tag} séance : verdict", page, "[data-result]", timeout=5000):
            page.locator("[data-result] button", has_text="Réessayer").click()
            page.wait_for_timeout(400)
            tap_move(page, hint[:2], hint[2:4])
            ck.appears(f"{tag} séance : réessai réussi", page, "[data-result='ok']", timeout=5000)
            page.wait_for_timeout(500)
            check(f"{tag} séance : « Réessayer » n'écrit rien", len(wait_rows(page, 2, 1200)) == 1)
            page.locator("[data-result] button", has_text="Sortie suivante").click()
            ck.appears(f"{tag} séance : sortie 2", page, f"[data-drill] h1:has-text('Sortie 2/{len(order)}')", timeout=5000)
            check(f"{tag} séance : 2e sortie = Italienne depuis la partie la plus récente (303)", attr(page, "[data-drill]", "data-uci") == " ".join(second["prefix"]), f"({attr(page, '[data-drill]', 'data-uci')})")
            good = second["expected"][1]
            tap_move(page, good[:2], good[2:4])
            ck.appears(f"{tag} séance : un autre coup théorique (♙c3) est accepté du premier coup", page, "[data-result='ok']", timeout=5000)
            page.screenshot(path=f"{SHOTS}/repertoire_drill_ok_852.png")
            rows = wait_rows(page, 2)
            check(f"{tag} séance : réussite enregistrée (next:w:<UCI de 303>, 1)", len(rows) == 2 and (rows[-1]["itemId"], rows[-1]["success"]) == (f"next:w:{' '.join(second['prefix'])}", 1), f"({rows})")
        page.locator("[data-drill] button[aria-label='Fermer le drill']").click()
        page.wait_for_timeout(500)
        states = {d[0]: d[2] for d in ui_devs(page)}
        check(f"{tag} retour : Deux cavaliers « À revoir », Italienne « Corrigée »", states.get(order[0]) == "review" and states.get(order[1]) == "fixed", f"({states})")
        page.screenshot(path=f"{SHOTS}/repertoire_states_852.png", full_page=True)

    # « Partie » : l'Analyse s'ouvre sur le coup de sortie de la partie la plus récente, avec retour.
    it_row = page.locator(f"[data-deviation='{second['id']}']")
    if it_row.count():
        it_row.locator("button", has_text="Partie").click()
        if ck.appears(f"{tag} Analyse ouverte", page, "main [data-square]", timeout=20000):
            page.wait_for_timeout(800)
            pa3 = page.evaluate("() => document.querySelector(\"[data-square='a3'] [data-piece]\")?.getAttribute('data-piece')")
            check(f"{tag} Analyse : position après 4. a3 (pion blanc en a3)", pa3 == "wP", f"({pa3})")
            back = page.locator("main button", has_text="Retour au répertoire")
            if check(f"{tag} Analyse : bouton « Retour au répertoire »", back.count() == 1):
                back.click()
                ck.appears(f"{tag} retour au répertoire", page, "[data-opening]", timeout=10000)
                check(f"{tag} retour : parties chargées conservées (13)", attr(page, "[data-games-count]", "data-games-count") == "13")
                check(f"{tag} retour : aucune requête de plus", calls["n"] == 4, f"({calls['n']})")
    ctx.close()


def layouts(p, browser):
    """Captures et débordement : iPhone Safari 393x660 et ordinateur 1440x900."""
    for name, make in (("660", lambda: mobile_context(p, browser, ck, settings={"chesscomUsername": USER}, service_workers="block")),
                       ("1440", lambda: desktop_context(browser, ck, settings={"chesscomUsername": USER}, service_workers="block"))):
        ctx = make()
        page = ctx.new_page()
        page.goto(f"{BASE}/#/repertoire")
        if not ck.appears(f"[{name}] page", page, "main h1:has-text('Mon répertoire')", timeout=20000):
            ctx.close()
            continue
        page.locator("[data-load]").click()
        ck.appears(f"[{name}] parties chargées", page, "[data-opening]", timeout=20000)
        page.wait_for_timeout(300)
        check(f"[{name}] pas de débordement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
        page.screenshot(path=f"{SHOTS}/repertoire_{name}.png")
        page.locator("[data-start]").click()
        if ck.appears(f"[{name}] séance ouverte", page, "[data-drill]", timeout=8000):
            check(f"[{name}] séance : pas de débordement horizontal", overflow_x(page) == 0)
            page.screenshot(path=f"{SHOTS}/repertoire_drill_{name}.png")
        ctx.close()


def no_username(p, browser):
    tag = "[pseudo]"
    ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block")
    calls = count_api_calls(ctx)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/repertoire")
    if not ck.appears(f"{tag} champ pseudo sans pseudo enregistré", page, "#rep-user", timeout=20000):
        ctx.close()
        return
    check(f"{tag} bouton désactivé tant que le champ est vide", page.locator("[data-load]").is_disabled())
    check(f"{tag} état vide expliqué", page.locator("[data-empty='none']").count() == 1)
    page.screenshot(path=f"{SHOTS}/repertoire_nouser_852.png")
    page.fill("#rep-user", "Éric_59")
    page.locator("[data-load]").click()
    ck.appears(f"{tag} pseudo invalide refusé", page, "[role=alert]:has-text('Pseudo invalide')", timeout=3000)
    check(f"{tag} pseudo invalide : aucune requête", calls["n"] == 0)
    page.fill("#rep-user", "zz_qa_nobody_98765")
    page.locator("[data-load]").click()
    ck.appears(f"{tag} pseudo inconnu : « Joueur introuvable »", page, "[role=alert]:has-text('Joueur introuvable')", timeout=10000)
    stored = page.evaluate("() => JSON.parse(localStorage.getItem('chess-local-settings')).state.chesscomUsername")
    check(f"{tag} pseudo inconnu non mémorisé", stored == "", f"({stored!r})")
    page.fill("#rep-user", "  Repertoire_QA ")
    page.locator("[data-load]").click()
    ck.appears(f"{tag} pseudo valide : parties chargées", page, "[data-opening]", timeout=20000)
    stored = page.evaluate("() => JSON.parse(localStorage.getItem('chess-local-settings')).state.chesscomUsername")
    check(f"{tag} pseudo normalisé mémorisé après le chargement", stored == USER, f"({stored!r})")
    check(f"{tag} 12 parties chargées (variante écartée, aucun bilan en cache)", attr(page, "[data-games-count]", "data-games-count") == "12",
          f"({attr(page, '[data-games-count]', 'data-games-count')})")
    ctx.close()


def suite(p):
    cases = bench_cases()
    out = node_bench(cases)
    if out is not None:
        bench_checks(out, cases)
    browser = p.chromium.launch(headless=True)
    try:
        seeded_page(p, browser)
        layouts(p, browser)
        no_username(p, browser)
    finally:
        browser.close()


ck.run(suite)
