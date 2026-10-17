#!/usr/bin/env python3
"""Génère la banque de l'entraîneur « Calcul et visualisation » (src/data/visualisation.json) depuis
les puzzles lichess de public/puzzles.json, vérifie chaque meilleur coup avec Stockfish 18 natif,
puis tamponne le fichier (scripts/visualisation.verified).

Usage :
    python3 scripts/prepare-visualisation.py   (Stockfish : variable STOCKFISH, sinon `stockfish` du PATH)
Puis committer le JSON ET le tampon. Le contrôle hors ligne (scripts/check-visualisation.mjs, lancé
par la suite E2E `visualisation`) échoue si le JSON ne correspond plus au tampon.

Construction d'un item de niveau N (N demi-coups, pair) à partir d'un puzzle [id, fen, moves, ...] :
- position montrée = FEN du puzzle après l'amorce moves[0] (le camp du puzzle a le trait) ;
- ligne annoncée = moves[1..N] (coups lichess : ceux du camp du puzzle sont les seuls coups gagnants,
  ceux de l'adversaire les défenses retenues par lichess) ;
- meilleur coup de la position finale = moves[N + 1], coup du camp du puzzle, CONFIRMÉ par Stockfish :
  recherche MultiPV 2 à profondeur DEPTH (mono-thread, hachage vidé), le coup doit être le premier de
  Stockfish, et soit le seul coup légal, soit un mat quand le second coup n'en est pas un, soit
  au moins GAP points de win% (formule lichess) au-dessus du second. Sinon le puzzle est écarté.
Un `best` en sous-promotion est écarté (l'app compte une promotion en dame).
Sélection déterministe : candidats classés entre RATING_MIN et RATING_MAX, triés par sha1 de l'id,
niveaux remplis du plus long au plus court (les longues lignes sont rares), un puzzle dans un seul
niveau, PER_LEVEL items par niveau, puis des items supplémentaires dont la position finale a un mat
en 1 jusqu'à MIN_MATE (la question « mat en 1 » est tirée moitié Oui, moitié Non par l'app).
Au plus WORKERS Stockfish mono-thread pour tout le script ; le cache sert de reprise.
Analyses en cache hors dépôt : ~/.cache/chess-local/visualisation-eval.json.
"""
import hashlib
import json
import math
import os
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import chess
import chess.engine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUZZLES = os.path.join(ROOT, "public", "puzzles.json")
DATA = os.path.join(ROOT, "src", "data", "visualisation.json")
STAMP = os.path.join(ROOT, "scripts", "visualisation.verified")
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "chess-local", "visualisation-eval.json")

LEVELS = [2, 4, 6, 8]
PER_LEVEL = 150
RATING_MIN = 600
RATING_MAX = 2600
DEPTH = 18
HASH_MB = 64
GAP = 15.0  # points de win%
WORKERS = 2  # au plus deux Stockfish mono-thread : la machine sert aussi aux autres travaux
MIN_MATE = 25  # items par niveau dont la position finale a un mat en 1 (question « mate » équilibrée)

ENGINE_PATH = os.environ.get("STOCKFISH") or shutil.which("stockfish")

_local = threading.local()
_engines = []
_lock = threading.Lock()


def engine():
    if not hasattr(_local, "engine"):
        eng = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
        eng.configure({"Threads": 1, "Hash": HASH_MB})
        _local.engine = eng
        with _lock:
            _engines.append(eng)
    return _local.engine


def has_mate_in_1(board):
    for m in board.legal_moves:
        board.push(m)
        mate = board.is_checkmate()
        board.pop()
        if mate:
            return True
    return False


def win_pct(cp):
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def score_of(pov):
    """PovScore du point de vue du trait -> [mat (n signé) ou None, cp ou None]."""
    if pov.is_mate():
        return [pov.mate(), None]
    return [None, pov.score()]


def analyse(fen):
    """MultiPV 2 à profondeur fixe, hachage vidé : [[uci, mate, cp], ...] du point de vue du trait."""
    infos = engine().analyse(chess.Board(fen), chess.engine.Limit(depth=DEPTH), multipv=2, game=object())
    if isinstance(infos, dict):
        infos = [infos]
    out = []
    for info in infos:
        if "pv" not in info or not info["pv"]:
            continue
        out.append([info["pv"][0].uci(), *score_of(info["score"].relative)])
    return out


def wp(line):
    mate, cp = line[1], line[2]
    if mate is not None:
        return 100.0 if mate > 0 else 0.0
    return win_pct(cp)


def verdict(board, best, lines):
    """None si `best` est confirmé, sinon la raison du rejet."""
    if not lines:
        return "aucune ligne moteur"
    if lines[0][0] != best:
        return f"Stockfish préfère {lines[0][0]}"
    if board.legal_moves.count() == 1:
        return None
    if len(lines) < 2:
        return "une seule ligne moteur pour plusieurs coups légaux"
    first, second = lines[0], lines[1]
    first_mates = first[1] is not None and first[1] > 0
    second_mates = second[1] is not None and second[1] > 0
    if first_mates and not second_mates:
        return None
    if first_mates and second_mates:
        return "deux coups matent"
    if wp(first) - wp(second) >= GAP:
        return None
    return f"écart {wp(first) - wp(second):.1f} < {GAP}"


def main():
    if not ENGINE_PATH:
        sys.exit("Stockfish introuvable : variable STOCKFISH ou `stockfish` dans le PATH")
    with open(PUZZLES) as f:
        puzzles = json.load(f)
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            cache = json.load(f)
    key_prefix = f"d{DEPTH}:"

    def sha(pid):
        return hashlib.sha1(pid.encode()).hexdigest()

    candidates = sorted(
        (p for p in puzzles if RATING_MIN <= p[3] <= RATING_MAX),
        key=lambda p: sha(p[0]),
    )
    used = set()
    levels = {}
    ex = ThreadPoolExecutor(WORKERS)
    rejected = {}
    for n in sorted(LEVELS, reverse=True):
        pool = [p for p in candidates if len(p[2].split()) >= n + 2 and p[0] not in used]
        items = []
        idx = 0

        def want(board):
            if len(items) < PER_LEVEL:
                return True
            return sum(1 for it in items if it["mate"]) < MIN_MATE and has_mate_in_1(board)

        while (len(items) < PER_LEVEL or sum(1 for it in items if it["mate"]) < MIN_MATE) and idx < len(pool):
            batch = pool[idx: idx + 64]
            idx += len(batch)
            prepared = []
            for pid, fen, moves, rating, _themes in batch:
                mv = moves.split()
                board = chess.Board(fen)
                board.push_uci(mv[0])
                start = board.fen()
                for u in mv[1: n + 1]:
                    board.push_uci(u)
                prepared.append((pid, start, mv, rating, board))

            def run(entry):
                board = entry[4]
                k = key_prefix + board.fen()
                if k not in cache:
                    cache[k] = analyse(board.fen())
                return cache[k]

            todo = [e for e in prepared if want(e[4])]
            results = list(ex.map(run, todo))
            for (pid, start, mv, rating, board), lines in zip(todo, results):
                if not want(board):
                    continue
                best = mv[n + 1]
                why = "sous-promotion" if len(best) == 5 and best[4] != "q" else verdict(board, best, lines)
                if why:
                    rejected[why.split(" ")[0]] = rejected.get(why.split(" ")[0], 0) + 1
                    continue
                items.append({"id": pid, "fen": start, "last": mv[0], "line": mv[1: n + 1], "best": best, "rating": rating, "mate": has_mate_in_1(board)})
                used.add(pid)
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            with open(CACHE, "w") as f:
                json.dump(cache, f)
        n_mate = sum(1 for it in items if it["mate"])
        if len(items) < PER_LEVEL or n_mate < MIN_MATE:
            sys.exit(f"niveau {n} : {len(items)} items dont {n_mate} avec mat en 1, il en faut {PER_LEVEL} et {MIN_MATE}")
        for it in items:
            del it["mate"]  # recalculé par l'app (chess.js) et par l'oracle de la suite E2E
        levels[str(n)] = items
        print(f"niveau {n} : {len(items)} items dont {n_mate} avec mat en 1 ({idx} candidats examinés)")
    ex.shutdown()
    for eng in _engines:
        eng.quit()

    data = {"version": 1, "levels": {str(n): levels[str(n)] for n in LEVELS}}
    # Une ligne par item : diff lisible, fichier compact.
    parts = []
    for n in LEVELS:
        rows = ",\n".join("    " + json.dumps(it, ensure_ascii=False, separators=(",", ":")) for it in levels[str(n)])
        parts.append(f'  "{n}": [\n{rows}\n  ]')
    text = '{"version":1,"levels":{\n' + ",\n".join(parts) + "\n}}\n"
    assert json.loads(text) == data
    with open(DATA, "w") as f:
        f.write(text)
    digest = hashlib.sha256(text.encode()).hexdigest()
    with open(os.path.abspath(__file__), "rb") as f:
        verifier = hashlib.sha256(f.read()).hexdigest()
    with open(STAMP, "w") as f:
        f.write(f"{digest} {verifier}\n")
    eng = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)
    name = eng.id.get("name", "?")
    eng.quit()
    print(f"OK : {sum(len(v) for v in levels.values())} items vérifiés par {name} (profondeur {DEPTH}, MultiPV 2, écart {GAP}). Rejets : {rejected}. Tampon {digest[:12]}.")


if __name__ == "__main__":
    main()
