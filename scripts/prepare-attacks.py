"""Génère `src/data/attacks.json`, la banque de positions de l'entraîneur d'attaque (/attaque).

    python3 scripts/prepare-attacks.py [--per-category 30] [--max-fetch 4000] [--jobs 6]

Source : les puzzles de `public/puzzles.json` (lichess, CC0) des thèmes kingsideAttack,
queensideAttack, attackingF2F7 et exposedKing, ou sacrifice/attraction associés à l'un d'eux ou
à un mat. Pour chacun, la partie lichess d'origine est lue sur l'API publique
`https://lichess.org/api/puzzle/<id>` (champ `game.pgn`, qui s'arrête sur le coup d'amorce de
l'adversaire, juste avant la solution). On recule de 10, 8, 6, 4 puis 2 demi-coups dans cette
partie (nombre pair : l'attaquant reste au trait) et on garde la position la plus ancienne qui
passe tous les critères : l'attaque se construit, la combinaison n'est pas encore là. Le puzzle
lui-même n'est jamais retenu. Une position par partie, aucune position en double.

Réponses de l'API en cache dans `data/lichess-puzzle-games.jsonl`, résultats d'évaluation dans
`data/attack-evals.jsonl` (non versionnés) : une relance reprend sans rien retélécharger ni
recalculer. Une requête par seconde, pause de 60 s sur un 429.

Critères (attaquant = camp au trait), mesurés avec Stockfish 18 natif (`STOCKFISH`, par défaut
`stockfish` du PATH ; même version que le WASM de l'app, gros réseau NNUE : seul le choix des
positions en dépend). Un moteur mono-thread par processus, table vidée avant chaque position :
le résultat ne dépend pas de l'ordre de traitement.
- catégorie (scripts/attack_facts.py) : roques opposés, même aile, roi au centre ; elle doit être
  la même sur la position du puzzle et sur la position retenue ;
- pas d'échec, dernier coup qui n'est pas une prise (pas de position au milieu d'un échange),
  au moins 20 pièces, pas avant le 8e coup ;
- matériel : l'attaquant n'a pas plus d'un pion d'avance (il peut être en retard) ;
- au moins deux pièces de l'attaquant (hors pions et roi) visent les abords du roi adverse, et un
  levier (attack_facts.lever) : roi au centre, tempête de pions, colonne ouverte ou semi-ouverte
  près du roi, bouclier de pions entamé ;
- tri rapide à profondeur 12 (entre +0,7 et +6,5), puis profondeur `--depth` (18 par défaut, multipv 2 ; chaque recherche est aussi bornée en temps) : entre
  +1,5 et +5 pour l'attaquant, aucun mat annoncé (donc pas de mat en 3 ou moins), 2e coup encore à
  +0,6 au moins (pas un coup unique de puzzle), et au moins +1,2 au-delà de l'avance matérielle ;
- construction : Stockfish joue 2 coups de chaque camp (profondeur 14), position réévaluée à profondeur 16. L'attaquant n'y gagne pas
  2 points de matériel ou plus (pas une tactique qui rafle du matériel), et la position reste
  entre +1 et +6 sans mat : l'avantage tient, mais il faut encore plusieurs coups pour conclure.

Sortie non nulle si la banque a moins de 60 positions ou moins de 15 dans une catégorie.
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ProcessPoolExecutor

import chess
import chess.engine
import chess.pgn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attack_facts import CATEGORIES, category, facts, goal, lever, material, plan, theme  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATTACK_THEMES = {"kingsideAttack", "queensideAttack", "attackingF2F7", "exposedKing"}
COMBO_THEMES = {"sacrifice", "attraction"}
CACHE = os.path.join(ROOT, "data", "lichess-puzzle-games.jsonl")
EVAL_CACHE = os.path.join(ROOT, "data", "attack-evals.jsonl")  # résultats par puzzle, non versionné
OUT = os.path.join(ROOT, "src", "data", "attacks.json")
BACK_PLIES = (10, 8, 6, 4, 2)
MIN_TOTAL, MIN_PER_CATEGORY = 60, 15

EVAL_MIN, EVAL_MAX = 150, 500
SECOND_MIN = 60
EDGE_MIN = 120  # avance d'éval sur l'avance matérielle, en centipions
AFTER_MIN, AFTER_MAX = 100, 600


def wanted(tags):
    if "endgame" in tags:
        return False
    if tags & ATTACK_THEMES:
        return True
    return bool(tags & COMBO_THEMES) and any(t.startswith("mate") for t in tags)


# ---------- API lichess ----------

def load_cache():
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    cache[row["id"]] = row
    return cache


def fetch(pid, cache):
    """(ligne, téléchargée ?)."""
    if pid in cache:
        return cache[pid], False
    url = f"https://lichess.org/api/puzzle/{pid}"
    while True:
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "chess-local prepare-attacks"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.load(r)
            row = {"id": pid, "game": data["game"]["id"], "pgn": data["game"]["pgn"]}
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print("  429 : pause de 60 s", flush=True)
                time.sleep(60)
                continue
            row = {"id": pid, "error": e.code}
            break
        except Exception as e:  # réseau : on note et on passe
            row = {"id": pid, "error": str(e)[:80]}
            break
    time.sleep(1)
    cache[pid] = row
    with open(CACHE, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return row, True


# ---------- Évaluation (processus de travail) ----------

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = chess.engine.SimpleEngine.popen_uci(os.environ.get("STOCKFISH", "stockfish"))
        _engine.configure({"Threads": 1, "Hash": 64})
    return _engine


def score_cp(info, pov):
    s = info["score"].pov(pov)
    return (None, s.mate()) if s.is_mate() else (s.score(), None)


def static_ok(board, last_move_capture, cat_expected):
    if board.is_check() or last_move_capture or board.fullmove_number < 8 or len(board.piece_map()) < 20:
        return None
    cat = category(board)
    if cat != cat_expected:
        return None
    att = board.turn
    if material(board, att) - material(board, not att) > 1:
        return None
    f = facts(board)
    if len(f["attackers"]) < 2 or not lever(cat, f):
        return None
    return f


def engine_ok(board, key, depth):
    """Retourne l'éval (cp, attaquant) si la position passe les critères moteur, sinon None."""
    engine = get_engine()
    att = board.turn
    game = object()  # nouvelle « partie » : ucinewgame, table vidée
    qcp, qmate = score_cp(engine.analyse(board, chess.engine.Limit(depth=12, time=10), game=game), att)
    if qmate is not None or qcp is None or not (EVAL_MIN - 80 <= qcp <= EVAL_MAX + 150):
        return None
    infos = engine.analyse(board, chess.engine.Limit(depth=depth, time=40), multipv=2, game=game)
    cp, mate = score_cp(infos[0], att)
    if mate is not None or cp is None or not (EVAL_MIN <= cp <= EVAL_MAX):
        return None
    if len(infos) < 2:
        return None
    cp2, mate2 = score_cp(infos[1], att)
    if mate2 is not None or cp2 is None or cp2 < SECOND_MIN:
        return None
    mat0 = material(board, att) - material(board, not att)
    if cp - 100 * mat0 < EDGE_MIN:
        return None
    b = board.copy()
    for _ in range(4):
        if b.is_game_over():
            return None
        b.push(engine.play(b, chess.engine.Limit(depth=14, time=10), game=game).move)
    if material(b, att) - material(b, not att) - mat0 >= 2:
        return None
    acp, amate = score_cp(engine.analyse(b, chess.engine.Limit(depth=16, time=20), game=game), att)
    if amate is not None or acp is None or not (AFTER_MIN <= acp < AFTER_MAX):
        return None
    return cp


def evaluate(pid, row, cat, depth):
    """Position retenue pour ce puzzle (dict) ou None. Moteur tué de l'extérieur : relancé, et
    le puzzle repris de zéro (table vidée à chaque position, le résultat ne change pas)."""
    global _engine
    for _ in range(3):
        try:
            return evaluate_once(pid, row, cat, depth)
        except chess.engine.EngineTerminatedError:
            _engine = None
    raise RuntimeError(f"moteur arrêté trois fois sur {pid}")


def evaluate_once(pid, row, cat, depth):
    game = chess.pgn.read_game(io.StringIO(row["pgn"]))
    moves = list(game.mainline_moves()) if game else []
    if len(moves) < 12:
        return None
    for back in BACK_PLIES:
        n = len(moves) - back
        if n < 1:
            continue
        board = chess.Board()
        for m in moves[: n - 1]:
            board.push(m)
        last_capture = board.is_capture(moves[n - 1])
        board.push(moves[n - 1])
        f = static_ok(board, last_capture, cat)
        if not f:
            continue
        cp = engine_ok(board, f"{pid}-{back}", depth)
        if cp is None:
            continue
        return {
            "id": f"att-{pid}",
            "fen": board.fen(),
            "attacker": "w" if board.turn == chess.WHITE else "b",
            "category": cat,
            "theme": theme(cat, f),
            "goal": goal(cat, f),
            "plan": plan(board, cat, f),
            "eval": cp,
            "source": {"puzzle": pid, "game": row["game"], "ply": n, "before": back},
        }
    return None


# ---------- Orchestration ----------

def write_bank(bank):
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(json.dumps(e, ensure_ascii=False) for e in bank) + "\n]\n")


def load_evals():
    evals = {}
    if os.path.exists(EVAL_CACHE):
        with open(EVAL_CACHE, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    evals[(row["pid"], row["cat"], row["depth"])] = row["entry"]
    return evals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-category", type=int, default=30)
    ap.add_argument("--max-fetch", type=int, default=4000)
    ap.add_argument("--depth", type=int, default=18)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--relabel", action="store_true", help="recalcule seulement thème, consigne et plan de la banque existante")
    args = ap.parse_args()

    if args.relabel:
        bank = json.load(open(OUT, encoding="utf-8"))
        for e in bank:
            board = chess.Board(e["fen"])
            f = facts(board)
            e["theme"], e["goal"], e["plan"] = theme(e["category"], f), goal(e["category"], f), plan(board, e["category"], f)
        write_bank(bank)
        print("banque réétiquetée :", len(bank), "positions", flush=True)
        return

    puzzles = json.load(open(os.path.join(ROOT, "public", "puzzles.json"), encoding="utf-8"))
    # Une liste ordonnée (par id) par catégorie, calculée sur la position du puzzle (après le coup
    # d'amorce). La position retenue doit garder cette catégorie : la banque d'une catégorie = ses
    # N premiers puzzles acceptés, dans l'ordre de sa liste.
    lists = {c: [] for c in CATEGORIES}
    for pid, fen, moves, rating, themes in sorted(puzzles, key=lambda p: p[0]):
        if not wanted(set(themes.split())):
            continue
        b = chess.Board(fen)
        b.push_uci(moves.split()[0])
        cat = category(b)
        if cat:
            lists[cat].append(pid)
    print("candidats :", {c: len(v) for c, v in lists.items()}, flush=True)

    cache, evals = load_cache(), load_evals()
    fetched = 0
    started = time.time()
    accepted = {c: [] for c in CATEGORIES}
    pool = ProcessPoolExecutor(max_workers=args.jobs)
    try:
        for c in CATEGORIES:
            i = 0
            while len(accepted[c]) < args.per_category and i < len(lists[c]):
                # Lot de puzzles dans l'ordre de la liste : évalués en parallèle, résultats en cache
                # (relance sans recalcul), dépouillés dans l'ordre.
                batch = lists[c][i : i + 2 * args.jobs]
                i += len(batch)
                todo = []
                for pid in batch:
                    if (pid, c, args.depth) in evals:
                        continue
                    if fetched >= args.max_fetch:
                        break
                    row, net = fetch(pid, cache)
                    fetched += net
                    if "error" in row:
                        evals[(pid, c, args.depth)] = None
                        continue
                    todo.append((pid, row))
                for (pid, _), entry in zip(todo, pool.map(evaluate, *zip(*[(pid, row, c, args.depth) for pid, row in todo])) if todo else []):
                    evals[(pid, c, args.depth)] = entry
                    with open(EVAL_CACHE, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"pid": pid, "cat": c, "depth": args.depth, "entry": entry}, ensure_ascii=False) + "\n")
                for pid in batch:
                    entry = evals.get((pid, c, args.depth))
                    if entry and len(accepted[c]) < args.per_category:
                        accepted[c].append(entry)
                        print(f"[{c} {len(accepted[c])}/{args.per_category}] {entry['id']} +{entry['eval'] / 100:.2f} -{entry['source']['before']} {entry['theme']} | {entry['goal']}", flush=True)
                print(f"  {c} : {i} examinés, {fetched} téléchargés, {time.time() - started:.0f} s", flush=True)
                if fetched >= args.max_fetch:
                    break
    finally:
        # Le moteur de chaque travailleur garde un fil actif : sans arrêt forcé, la fermeture du
        # pool attendrait indéfiniment (Stockfish quitte à la fermeture de son entrée standard).
        procs = list(pool._processes.values())
        pool.shutdown(wait=False, cancel_futures=True)
        for proc in procs:
            proc.kill()

    def accepted_prefix(c):
        return accepted[c]

    bank, seen_games, seen_boards = {c: [] for c in CATEGORIES}, set(), set()
    for c in CATEGORIES:
        for e in accepted_prefix(c):
            board_key = " ".join(e["fen"].split()[:2])
            if e["source"]["game"] in seen_games or board_key in seen_boards or len(bank[c]) >= args.per_category:
                continue
            seen_games.add(e["source"]["game"])
            seen_boards.add(board_key)
            bank[c].append(e)

    out = [e for c in CATEGORIES for e in sorted(bank[c], key=lambda e: (e["eval"], e["id"]))]
    write_bank(out)
    counts = {c: len(bank[c]) for c in CATEGORIES}
    print("banque :", counts, "total", len(out), "->", os.path.relpath(OUT, ROOT), flush=True)
    if len(out) < MIN_TOTAL or min(counts.values()) < MIN_PER_CATEGORY:
        sys.exit(f"banque trop petite : il faut {MIN_TOTAL} positions et {MIN_PER_CATEGORY} par catégorie")


if __name__ == "__main__":
    main()
