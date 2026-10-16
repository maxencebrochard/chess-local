"""Génère `src/data/defenses.json`, la banque de positions de l'entraîneur de défense (/defense).

    python3 scripts/prepare-defenses.py [--per-category 25] [--max-fetch 6000] [--jobs 6] [--second-gap 150]
    python3 scripts/prepare-defenses.py --relabel

Source : les mêmes puzzles d'attaque que `scripts/prepare-attacks.py` (`public/puzzles.json`,
lichess, CC0 ; même filtre `wanted`, même catégorie calculée sur la position du puzzle, du point de
vue du camp qui résout) et leurs parties lichess (API publique `lichess.org/api/puzzle/<id>`, cache
partagé `data/lichess-puzzle-games.jsonl`). Le PGN s'arrête sur le coup d'amorce, celui du camp
qui va subir la combinaison : en reculant de 1, 3 puis 5 demi-coups (nombre impair), le DÉFENSEUR
est au trait, avant le coup qui a craqué. On garde la position la plus proche du puzzle qui passe
tous les critères (le défenseur pouvait encore tenir). Une position par partie, aucun doublon.

Résultats d'évaluation dans `data/defense-evals.jsonl` (non versionné), clés par puzzle, catégorie,
profondeur et signature des seuils : une relance reprend sans rien recalculer, un seuil modifié
recalcule. Une requête lichess par seconde, pause de 60 s sur un 429.

Critères, défenseur = camp au trait, attaquant = l'autre camp (attack_facts appelé avec `att`) :
- catégorie (roques opposés, même aile, roi au centre), la même sur la position du puzzle et sur la
  position retenue, pour le même attaquant ;
- pas d'échec, dernier coup qui n'est pas une prise, au moins 20 pièces, pas avant le 8e coup ;
- matériel : le défenseur n'a pas plus d'un pion de retard ;
- au moins deux pièces de l'attaquant (hors pions et roi) visent les abords du roi du défenseur,
  et un levier d'attaque (attack_facts.lever) ;
- tri rapide à profondeur 12 (entre -3,0 et +1,0 pour le défenseur, sans mat), puis profondeur
  `--depth` (18 par défaut, multipv 2, chaque recherche bornée en temps), du point de vue du
  défenseur : meilleur coup entre -2,0 et +0,3 (sous pression mais défendable), aucun mat annoncé
  sur les deux lignes, et le 2e coup au moins `--second-gap` centipions sous le 1er (150 par
  défaut) : il faut trouver le coup juste ;
- menace réelle : coup nul (`chess.Move.null()`, l'attaquant rejoue), position évaluée à
  profondeur 16 : l'attaquant y est à +3 ou mieux, ou mate.

Sortie non nulle si la banque a moins de 45 positions ou moins de 10 dans une catégorie. Le script
affiche, par catégorie, le nombre de positions rejetées par critère (une position candidate par
recul ; un puzzle sans position retenue compte pour chacun de ses reculs rejetés).

Calibrage : voir CALIBRAGE en fin de docstring, mis à jour à chaque génération de la banque.

CALIBRAGE (génération du 2026-10-16, `--per-category 25`, profondeur 18, seuils par défaut)
Aucun seuil élargi : les valeurs du cahier des charges suffisent (fenêtre -2,0 à +0,3, 2e coup
1,5 en dessous, menace +3 après le coup nul, un pion de retard au plus). Environ 4 % des puzzles
examinés donnent une position (opposes 25 sur 396, meme 25 sur 768, centre 25 sur 684), 3 050
parties lichess en cache. Banque : 25 positions par catégorie, 75 au total, 49 où les Noirs
défendent et 26 les Blancs ; recul 1 (40), 3 (22) ou 5 (13). Rejets les plus fréquents : dernier
coup qui prend, moins de deux attaquants, tri rapide, échec, puis « 2e coup qui tient aussi ». Le
critère de menace n'a rejeté aucune position qui passait les autres : il reste comme garde-fou.
Si une catégorie manquait de positions : `--per-category`, plus de téléchargements
(`--max-fetch`), puis `--second-gap 120`, en notant ici le choix.
"""
import argparse
import importlib.util
import io
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import chess
import chess.engine
import chess.pgn

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from attack_facts import CATEGORIES, category, lever, material  # noqa: E402
from defense_facts import attacker_of, defense_facts, defense_theme, goal, plan  # noqa: E402

# Téléchargement, cache lichess et filtre des puzzles : ceux de l'entraîneur d'attaque, partagés.
_spec = importlib.util.spec_from_file_location("prepare_attacks", os.path.join(HERE, "prepare-attacks.py"))
prepare_attacks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prepare_attacks)
wanted, load_cache, fetch, score_cp = prepare_attacks.wanted, prepare_attacks.load_cache, prepare_attacks.fetch, prepare_attacks.score_cp

ROOT = os.path.dirname(HERE)
EVAL_CACHE = os.path.join(ROOT, "data", "defense-evals.jsonl")  # résultats par puzzle, non versionné
OUT = os.path.join(ROOT, "src", "data", "defenses.json")
BACK_PLIES = (1, 3, 5)
MIN_TOTAL, MIN_PER_CATEGORY = 45, 10

EVAL_MIN, EVAL_MAX = -200, 30  # meilleur coup, défenseur
QUICK_MIN, QUICK_MAX = -300, 100  # tri rapide à profondeur 12
THREAT_MIN = 300  # attaquant après le coup nul
MAX_BEHIND = 1  # retard matériel maximal du défenseur, en pions


def signature(depth, gap):
    """Clé du cache d'évals : tout seuil qui change le verdict d'une position."""
    return f"d{depth}|e{EVAL_MIN}:{EVAL_MAX}|q{QUICK_MIN}:{QUICK_MAX}|g{gap}|t{THREAT_MIN}|m{MAX_BEHIND}|b{','.join(map(str, BACK_PLIES))}"


# ---------- Évaluation (processus de travail) ----------

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = chess.engine.SimpleEngine.popen_uci(os.environ.get("STOCKFISH", "stockfish"))
        _engine.configure({"Threads": 1, "Hash": 64})
    return _engine


def static_reject(board, last_move_capture, cat_expected):
    """Motif du rejet sans moteur, ou None si la position passe."""
    if board.is_check():
        return "échec"
    if last_move_capture:
        return "après une prise"
    if board.fullmove_number < 8 or len(board.piece_map()) < 20:
        return "trop tôt ou trop peu de pièces"
    att = attacker_of(board)
    if category(board, att) != cat_expected:
        return "catégorie changée"
    if material(board, att) - material(board, not att) > MAX_BEHIND:
        return "retard matériel"
    f = defense_facts(board)
    if len(f["attackers"]) < 2:
        return "moins de deux attaquants"
    if not lever(cat_expected, f):
        return "sans levier"
    return None


def engine_reject(board, depth, gap):
    """(motif du rejet ou None, éval du défenseur)."""
    engine = get_engine()
    dfn = board.turn
    game = object()  # nouvelle « partie » : ucinewgame, table vidée
    qcp, qmate = score_cp(engine.analyse(board, chess.engine.Limit(depth=12, time=10), game=game), dfn)
    if qmate is not None or qcp is None or not (QUICK_MIN <= qcp <= QUICK_MAX):
        return "tri rapide", None
    infos = engine.analyse(board, chess.engine.Limit(depth=depth, time=40), multipv=2, game=game)
    if len(infos) < 2:
        return "un seul coup légal", None
    cp, mate = score_cp(infos[0], dfn)
    cp2, mate2 = score_cp(infos[1], dfn)
    if mate is not None or mate2 is not None:
        return "mat annoncé", None
    if not (EVAL_MIN <= cp <= EVAL_MAX):
        return "éval hors fenêtre", None
    if cp - cp2 < gap:
        return "2e coup qui tient aussi", None
    # Coup nul (`chess.Move.null()`) sans historique : trait passé à l'attaquant, prise en passant
    # effacée. Même position, sans l'avertissement de python-chess sur un historique avec coup nul.
    b = board.copy(stack=False)
    b.push(chess.Move.null())
    b.clear_stack()
    tcp, tmate = score_cp(engine.analyse(b, chess.engine.Limit(depth=16, time=20), game=game), not dfn)
    if not ((tmate is not None and tmate > 0) or (tcp is not None and tcp >= THREAT_MIN)):
        return "menace trop faible", None
    return None, cp


def evaluate(pid, row, cat, depth, gap):
    """{entry, rejects} pour ce puzzle. Moteur tué de l'extérieur : relancé, puzzle repris de zéro."""
    global _engine
    for _ in range(3):
        try:
            return evaluate_once(pid, row, cat, depth, gap)
        except chess.engine.EngineTerminatedError:
            _engine = None
    raise RuntimeError(f"moteur arrêté trois fois sur {pid}")


def evaluate_once(pid, row, cat, depth, gap):
    game = chess.pgn.read_game(io.StringIO(row["pgn"]))
    moves = list(game.mainline_moves()) if game else []
    rejects = []
    if len(moves) < 12:
        return {"entry": None, "rejects": ["partie trop courte"]}
    for back in BACK_PLIES:
        n = len(moves) - back
        if n < 1:
            continue
        board = chess.Board()
        for m in moves[: n - 1]:
            board.push(m)
        last_capture = board.is_capture(moves[n - 1])
        board.push(moves[n - 1])
        why = static_reject(board, last_capture, cat)
        if why:
            rejects.append(why)
            continue
        why, cp = engine_reject(board, depth, gap)
        if why:
            rejects.append(why)
            continue
        f = defense_facts(board)
        return {
            "entry": {
                "id": f"def-{pid}",
                "fen": board.fen(),
                "defender": "w" if board.turn == chess.WHITE else "b",
                "category": cat,
                "theme": defense_theme(cat, f),
                "goal": goal(cat, f),
                "plan": plan(board, cat, f),
                "eval": cp,
                "source": {"puzzle": pid, "game": row["game"], "ply": n, "before": back},
            },
            "rejects": rejects,
        }
    return {"entry": None, "rejects": rejects}


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
                    evals[(row["pid"], row["cat"], row["sig"])] = row["result"]
    return evals


def relabel():
    bank = json.load(open(OUT, encoding="utf-8"))
    for e in bank:
        board = chess.Board(e["fen"])
        f = defense_facts(board)
        e["theme"], e["goal"], e["plan"] = defense_theme(e["category"], f), goal(e["category"], f), plan(board, e["category"], f)
    write_bank(bank)
    print("banque réétiquetée :", len(bank), "positions", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-category", type=int, default=25)
    ap.add_argument("--max-fetch", type=int, default=6000, help="téléchargements lichess au plus (0 : cache seul)")
    ap.add_argument("--depth", type=int, default=18)
    ap.add_argument("--second-gap", type=int, default=150, help="écart minimal du 2e coup, centipions")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--relabel", action="store_true", help="recalcule seulement thème, consigne et plan de la banque existante")
    args = ap.parse_args()
    if args.relabel:
        relabel()
        return
    sig = signature(args.depth, args.second_gap)

    puzzles = json.load(open(os.path.join(ROOT, "public", "puzzles.json"), encoding="utf-8"))
    # Une liste ordonnée (par id) par catégorie, calculée sur la position du puzzle (après le coup
    # d'amorce, camp qui résout = attaquant au trait), exactement comme pour l'attaque.
    lists = {c: [] for c in CATEGORIES}
    for pid, fen, moves, rating, themes in sorted(puzzles, key=lambda p: p[0]):
        if not wanted(set(themes.split())):
            continue
        b = chess.Board(fen)
        b.push_uci(moves.split()[0])
        cat = category(b)
        if cat:
            lists[cat].append(pid)
    print("candidats :", {c: len(v) for c, v in lists.items()}, "| seuils :", sig, flush=True)

    cache, evals = load_cache(), load_evals()
    fetched = 0
    started = time.time()
    accepted = {c: [] for c in CATEGORIES}
    rejects = {c: Counter() for c in CATEGORIES}
    examined = Counter()
    pool = ProcessPoolExecutor(max_workers=args.jobs)
    try:
        for c in CATEGORIES:
            i = 0
            while len(accepted[c]) < args.per_category and i < len(lists[c]):
                batch = lists[c][i : i + 2 * args.jobs]
                i += len(batch)
                todo = []
                for pid in batch:
                    if (pid, c, sig) in evals:
                        continue
                    if pid not in cache and fetched >= args.max_fetch:
                        continue
                    row, net = fetch(pid, cache)
                    fetched += net
                    if "error" in row:
                        evals[(pid, c, sig)] = {"entry": None, "rejects": ["partie introuvable"]}
                        continue
                    todo.append((pid, row))
                results = pool.map(evaluate, *zip(*[(pid, row, c, args.depth, args.second_gap) for pid, row in todo])) if todo else []
                for (pid, _), result in zip(todo, results):
                    evals[(pid, c, sig)] = result
                    with open(EVAL_CACHE, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"pid": pid, "cat": c, "sig": sig, "result": result}, ensure_ascii=False) + "\n")
                for pid in batch:
                    result = evals.get((pid, c, sig))
                    if result is None:
                        continue  # ni en cache ni téléchargeable (plafond atteint)
                    examined[c] += 1
                    rejects[c].update(result["rejects"])
                    entry = result["entry"]
                    if entry and len(accepted[c]) < args.per_category:
                        accepted[c].append(entry)
                        print(f"[{c} {len(accepted[c])}/{args.per_category}] {entry['id']} {entry['eval'] / 100:+.2f} -{entry['source']['before']} {entry['theme']} | {entry['goal']}", flush=True)
                print(f"  {c} : {i} parcourus, {examined[c]} examinés, {fetched} téléchargés, {time.time() - started:.0f} s", flush=True)
    finally:
        # Le moteur de chaque travailleur garde un fil actif : sans arrêt forcé, la fermeture du
        # pool attendrait indéfiniment (Stockfish quitte à la fermeture de son entrée standard).
        procs = list(pool._processes.values())
        pool.shutdown(wait=False, cancel_futures=True)
        for proc in procs:
            proc.kill()

    for c in CATEGORIES:
        print(f"rejets {c} ({examined[c]} puzzles examinés, {len(accepted[c])} retenus) :", dict(rejects[c].most_common()), flush=True)

    bank, seen_games, seen_boards = {c: [] for c in CATEGORIES}, set(), set()
    for c in CATEGORIES:
        for e in accepted[c]:
            board_key = " ".join(e["fen"].split()[:2])
            if e["source"]["game"] in seen_games or board_key in seen_boards or len(bank[c]) >= args.per_category:
                continue
            seen_games.add(e["source"]["game"])
            seen_boards.add(board_key)
            bank[c].append(e)

    # Les plus défendables d'abord (éval décroissante pour le défenseur).
    out = [e for c in CATEGORIES for e in sorted(bank[c], key=lambda e: (-e["eval"], e["id"]))]
    write_bank(out)
    relabel()  # thème, consigne et plan toujours recalculés : le cache d'évals ne fige pas les phrases
    counts = {c: len(bank[c]) for c in CATEGORIES}
    print("banque :", counts, "total", len(out), "->", os.path.relpath(OUT, ROOT), flush=True)
    if len(out) < MIN_TOTAL or min(counts.values()) < MIN_PER_CATEGORY:
        sys.exit(f"banque trop petite : il faut {MIN_TOTAL} positions et {MIN_PER_CATEGORY} par catégorie")


if __name__ == "__main__":
    main()
