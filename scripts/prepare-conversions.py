"""Génère `src/data/conversions.json`, la banque de l'entraîneur « Convertir l'avantage » (/convertir).

    python3 scripts/prepare-conversions.py [--per-category 20] [--max-candidates 3000] [--jobs 2]

Source : les puzzles de `public/puzzles.json` (lichess, CC0, positions de vraies parties) au thème
`advantage` (la solution gagne un avantage net, pas le mat), sans thème de mat. On joue la
solution du puzzle : la combinaison est faite, il reste à convertir. Stockfish joue ensuite la
suite (profondeur 12) jusqu'à une position calme au trait du gagnant : pas d'échec, dernier coup
qui n'est pas une prise (pas au milieu d'un échange), au plus 6 demi-coups ajoutés. Aucun appel
réseau. Une position par puzzle, aucune position en double.

Critères (joueur = camp au trait), mesurés avec Stockfish 18 natif (`STOCKFISH`, par défaut
`stockfish` du PATH ; même version que le WASM de l'app : seul le choix des positions en dépend).
Un moteur mono-thread par processus, table vidée avant chaque position : le résultat ne dépend pas
de l'ordre de traitement.
- au moins 7 unités (pions et pièces hors rois), au moins une pièce ou deux pions au défenseur ;
- pas de fous de couleurs opposées (un fou de chaque côté, sans cavalier : conseil d'échange
  incertain), pas de matériel en moins hors finale (compensation : une attaque, pas une
  conversion), un levier (conversion_facts.lever) ;
- tri rapide à profondeur 12 (entre +1,5 et +5,5), puis profondeur `--depth` (18 par défaut,
  multipv 2) : entre +2 et +4,5 pour le joueur, aucun mat annoncé, 2e coup encore à +1 au moins
  (pas un coup unique de puzzle) ;
- suite : Stockfish joue 2 coups de chaque camp (profondeur 14, prolongée de 2 demi-coups au plus
  tant que le dernier coup est une prise), position réévaluée à profondeur 16. Le joueur n'y gagne pas 2 points de matériel ou plus (pas de tactique qui rafle tout), et
  la position reste entre +1,2 et +7 sans mat : l'avantage tient, mais la partie n'est pas jouée.

Résultats d'évaluation en cache dans `data/conversion-evals.jsonl` (non versionné) : une relance
reprend sans rien recalculer ; la clé porte la version des critères (`CRITERIA`).
Les coups ajoutés après la solution sont gardés (`source.uci`) : la suite E2E rejoue puzzle,
solution et coups ajoutés, et doit retrouver la FEN. `--relabel` recalcule seulement thème, consigne et plan.
Sortie non nulle si la banque a moins de 45 positions ou moins de 12 dans une catégorie.
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import chess
import chess.engine

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conversion_facts import CATEGORIES, category, facts, goal, lever, material, plan, theme  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_CACHE = os.path.join(ROOT, "data", "conversion-evals.jsonl")
OUT = os.path.join(ROOT, "src", "data", "conversions.json")
MIN_TOTAL, MIN_PER_CATEGORY = 45, 12
QUIET_PLIES = 6
EVAL_MIN, EVAL_MAX = 200, 450
SECOND_MIN = 100
AFTER_MIN, AFTER_MAX = 120, 700
MIN_UNITS = 7
# Version des critères, dans la clé du cache : changer un seuil ou une profondeur oblige à la changer.
CRITERIA = f"v1:q12:{EVAL_MIN}-{EVAL_MAX}:{SECOND_MIN}:{AFTER_MIN}-{AFTER_MAX}:{QUIET_PLIES}:{MIN_UNITS}"


def wanted(tags):
    return "advantage" in tags and not any(t.startswith("mate") for t in tags)


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


def static_ok(board):
    units = [p for p in board.piece_map().values() if p.piece_type != chess.KING]
    if len(units) < MIN_UNITS:
        return None
    op = not board.turn
    op_units = [p for p in units if p.color == op]
    if not any(p.piece_type != chess.PAWN for p in op_units) and len(op_units) < 2:
        return None
    f = facts(board)
    cat = category(board)
    # Matériel en moins hors finale : une compensation (attaque), pas une conversion.
    if cat == "positionnel" and f["diff"] < 0:
        return None
    if not lever(cat, f):
        return None
    return cat, f


def engine_ok(board, depth, game):
    """Éval (cp, joueur) si la position passe les critères moteur, sinon None."""
    engine = get_engine()
    pl = board.turn
    qcp, qmate = score_cp(engine.analyse(board, chess.engine.Limit(depth=12, time=10), game=game), pl)
    if qmate is not None or qcp is None or not (EVAL_MIN - 50 <= qcp <= EVAL_MAX + 100):
        return None
    infos = engine.analyse(board, chess.engine.Limit(depth=depth, time=40), multipv=2, game=game)
    cp, mate = score_cp(infos[0], pl)
    if mate is not None or cp is None or not (EVAL_MIN <= cp <= EVAL_MAX) or len(infos) < 2:
        return None
    cp2, mate2 = score_cp(infos[1], pl)
    if mate2 is not None or cp2 is None or cp2 < SECOND_MIN:
        return None
    mat0 = material(board, pl) - material(board, not pl)
    # Suite de 4 demi-coups, prolongée de 2 au plus tant que le dernier coup est une prise : le
    # matériel se compte sur une position calme, pas au milieu d'un échange.
    b = board.copy()
    last_capture = False
    for i in range(6):
        if i >= 4 and not last_capture:
            break
        if b.is_game_over():
            return None
        move = engine.play(b, chess.engine.Limit(depth=14, time=10), game=game).move
        last_capture = b.is_capture(move)  # avant le push : après, le test vise le mauvais camp
        b.push(move)
    if material(b, pl) - material(b, not pl) - mat0 >= 2:
        return None
    acp, amate = score_cp(engine.analyse(b, chess.engine.Limit(depth=16, time=20), game=game), pl)
    if amate is not None or acp is None or not (AFTER_MIN <= acp <= AFTER_MAX):
        return None
    return cp


def evaluate(pid, fen, moves, depth, skip):
    """Position retenue pour ce puzzle (dict) ou None. Moteur tué de l'extérieur : relancé, et
    le puzzle repris de zéro (table vidée à chaque position, le résultat ne change pas)."""
    global _engine
    for _ in range(3):
        try:
            return evaluate_once(pid, fen, moves, depth, skip)
        except chess.engine.EngineTerminatedError:
            _engine = None
    raise RuntimeError(f"moteur arrêté trois fois sur {pid}")


def evaluate_once(pid, fen, moves, depth, skip):
    """`skip` : catégories déjà pleines, rendues {"skip": cat} sans évaluation (jamais en cache)."""
    board = chess.Board(fen)
    for m in moves.split():
        board.push_uci(m)
    player = not board.turn  # le camp qui vient de jouer la solution
    engine = get_engine()
    game = object()  # nouvelle « partie » : ucinewgame, table vidée
    added = []
    while len(added) < QUIET_PLIES:
        if board.is_game_over():
            return None
        move = engine.play(board, chess.engine.Limit(depth=12, time=10), game=game).move
        capture = board.is_capture(move)
        board.push(move)
        added.append(move.uci())
        if board.turn == player and not capture and not board.is_check():
            break
    else:
        return None
    ok = static_ok(board)
    if not ok:
        return None
    cat, f = ok
    if cat in skip:
        return {"skip": cat}
    cp = engine_ok(board, depth, game)
    if cp is None:
        return None
    return {
        "id": f"conv-{pid}",
        "fen": board.fen(),
        "player": "w" if board.turn == chess.WHITE else "b",
        "category": cat,
        "theme": theme(cat, f),
        "goal": goal(cat, f),
        "plan": plan(board, cat, f),
        "eval": cp,
        "source": {"puzzle": pid, "uci": added},
    }


# ---------- Orchestration ----------

def write_bank(bank):
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("[\n" + ",\n".join(json.dumps(e, ensure_ascii=False) for e in bank) + "\n]\n")


def load_evals():
    evals = {}
    if os.path.exists(EVAL_CACHE):
        with open(EVAL_CACHE, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    row = json.loads(line)
                    if row.get("criteria") == CRITERIA:
                        evals[(row["pid"], row["depth"])] = row["entry"]
    return evals


def relabel(e):
    """Entrée aux textes recalculés, ou None si la position n'a plus de levier."""
    board = chess.Board(e["fen"])
    f = facts(board)
    cat = category(board)
    if not lever(cat, f):
        return None
    e["category"], e["theme"], e["goal"], e["plan"] = cat, theme(cat, f), goal(cat, f), plan(board, cat, f)
    return e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-category", type=int, default=20)
    ap.add_argument("--max-candidates", type=int, default=3000)
    ap.add_argument("--depth", type=int, default=18)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--relabel", action="store_true", help="recalcule seulement catégorie, thème, consigne et plan de la banque existante")
    args = ap.parse_args()

    if args.relabel:
        bank = [e for e in (relabel(x) for x in json.load(open(OUT, encoding="utf-8"))) if e]
        write_bank(sorted(bank, key=lambda e: (CATEGORIES.index(e["category"]), e["eval"], e["id"])))
        print("banque réétiquetée :", len(bank), "positions", flush=True)
        return

    puzzles = json.load(open(os.path.join(ROOT, "public", "puzzles.json"), encoding="utf-8"))
    cands = [(pid, fen, moves) for pid, fen, moves, rating, themes in sorted(puzzles, key=lambda p: p[0]) if wanted(set(themes.split()))]
    cands = cands[: args.max_candidates]
    print("candidats :", len(cands), flush=True)

    evals = load_evals()
    started = time.time()
    accepted = {c: [] for c in CATEGORIES}
    seen = set()
    pool = ProcessPoolExecutor(max_workers=args.jobs)

    def full():
        return all(len(v) >= args.per_category for v in accepted.values())

    try:
        i = 0
        while not full() and i < len(cands):
            # Lot dans l'ordre des ids : évalué en parallèle, résultats en cache, dépouillé dans l'ordre.
            batch = cands[i : i + 4 * args.jobs]
            i += len(batch)
            todo = [c for c in batch if (c[0], args.depth) not in evals]
            skip = frozenset(c for c, v in accepted.items() if len(v) >= args.per_category)
            if todo:
                results = pool.map(evaluate, *zip(*[(pid, fen, moves, args.depth, skip) for pid, fen, moves in todo]))
                for (pid, _, _), entry in zip(todo, results):
                    if entry and "skip" in entry:
                        continue
                    evals[(pid, args.depth)] = entry
                    with open(EVAL_CACHE, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"pid": pid, "depth": args.depth, "criteria": CRITERIA, "entry": entry}, ensure_ascii=False) + "\n")
            for pid, _, _ in batch:
                entry = evals.get((pid, args.depth))
                if not entry:
                    continue
                entry = relabel(dict(entry))  # faits recalculés : le cache ne fige pas les textes
                if not entry:
                    continue
                key = " ".join(entry["fen"].split()[:2])
                c = entry["category"]
                if key in seen or len(accepted[c]) >= args.per_category:
                    continue
                seen.add(key)
                accepted[c].append(entry)
                print(f"[{c} {len(accepted[c])}/{args.per_category}] {entry['id']} +{entry['eval'] / 100:.2f} {entry['theme']} | {entry['goal']}", flush=True)
            print(f"  {i} examinés, {time.time() - started:.0f} s, " + ", ".join(f"{c} {len(v)}" for c, v in accepted.items()), flush=True)
    finally:
        # Le moteur de chaque travailleur garde un fil actif : sans arrêt forcé, la fermeture du
        # pool attendrait indéfiniment (Stockfish quitte à la fermeture de son entrée standard).
        procs = list(pool._processes.values())
        pool.shutdown(wait=False, cancel_futures=True)
        for proc in procs:
            proc.kill()

    out = [e for c in CATEGORIES for e in sorted(accepted[c], key=lambda e: (e["eval"], e["id"]))]
    write_bank(out)
    counts = {c: len(accepted[c]) for c in CATEGORIES}
    print("banque :", counts, "total", len(out), "->", os.path.relpath(OUT, ROOT), flush=True)
    if len(out) < MIN_TOTAL or min(counts.values()) < MIN_PER_CATEGORY:
        sys.exit(f"banque trop petite : il faut {MIN_TOTAL} positions et {MIN_PER_CATEGORY} par catégorie")


if __name__ == "__main__":
    main()
