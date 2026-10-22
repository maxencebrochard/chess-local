#!/usr/bin/env python3
"""Génère src/data/endgameClock.json : la banque des « Finales au chrono » (/finales/chrono).

Familles : des finales théoriques reprises par id de src/data/endgames.json (FEN, titre, objectif
lus là-bas : une correction s'y propage) et quelques autres écrites ici. Chaque famille donne au
plus quatre variantes : la position, son miroir a-h, couleurs inversées, et les deux.

Chaque variante est sondée sur les tables de finales de lichess (https://tablebase.lichess.ovh,
Syzygy + DTM, réponses en cache dans ~/.cache/chess-local/tablebase.json, partagé avec
verify-endgame-course.py) ; elle n'est gardée que si :
- le verdict pour le camp au trait (le joueur) est exactement `win` (objectif gain) ou `draw`
  (objectif nulle) : `cursed-win` et `blessed-loss` (règle des 50 coups) sont refusés ;
- au moins un coup légal du joueur change ce verdict : la position demande de savoir quoi faire.
Une famille sans variante gardée fait échouer le script.

Couleurs inversées = `chess.Board.mirror()` (miroir vertical, échange des couleurs et du trait).
Chaque position garde une ligne optimale des tables (LINE_PLIES demi-coups au plus : le joueur
joue le coup qui conserve le verdict au plus court, l'adversaire le plus tenace) : la suite E2E
y vérifie que les seuils d'évaluation de l'app (src/lib/endgameClock.ts) séparent bien les cas.

Le JSON écrit est tamponné (sha256) dans scripts/endgame-clock.verified.

Usage :
    python3 scripts/prepare-endgame-clock.py          # régénère (réseau requis sauf cache complet)
    python3 scripts/prepare-endgame-clock.py --check  # hors ligne : JSON à jour avec ses sources et le tampon
"""
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request

import chess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENDGAMES = os.path.join(ROOT, "src", "data", "endgames.json")
OUT = os.path.join(ROOT, "src", "data", "endgameClock.json")
STAMP = os.path.join(ROOT, "scripts", "endgame-clock.verified")
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "chess-local", "tablebase.json")
API = "https://tablebase.lichess.ovh/standard?fen="

# Familles reprises de endgames.json : id -> principe (une phrase de méthode, sans nom de case,
# vraie aussi pour le miroir et les couleurs inversées).
FROM_ENDGAMES = {
    "kp-square": "Le roi adverse est hors du carré du pion : pousse-le sans t'arrêter.",
    "kp-opposition-1": "Prends l'opposition : rois face à face, une case entre eux, trait à l'adversaire.",
    "kp-king-front": "Roi devant le pion : un coup d'attente rend le trait à l'adversaire, puis contourne.",
    "opposition-distant": "Opposition à distance : même colonne, un nombre impair de cases entre les rois.",
    "two-pawns": "Deux pions liés en escalier se protègent : avance-les une case à la fois.",
    "kp-defense-front": "Roi devant le pion : recule tout droit et prends l'opposition au dernier moment.",
    "active-king-draw": "Réti : ton roi poursuit deux buts à la fois sur la diagonale.",
    "lucena": "Le pont : tour sur la 4e rangée, sors le roi, puis abrite-le derrière ta tour.",
    "philidor": "Ta tour tient la rangée devant le roi adverse ; quand le pion y arrive, échecs par derrière.",
    "r-vs-p": "Ramène ton roi par le plus court chemin : la tour seule n'arrête pas le pion soutenu.",
    "q-vs-r": "Approche ton roi, zugzwang, puis fourchette de dame sur le roi et la tour.",
}

# Familles écrites ici (vérifiées comme les autres).
OWN = [
    {
        "id": "q-vs-p7", "title": "Dame contre pion central sur la 7e", "objective": "win", "goal": "capture",
        "fen": "K7/6Q1/8/8/8/8/3kp3/8 w - - 0 1", "difficulty": 1300,
        "principle": "Échecs et clouages jusqu'à forcer le roi devant son pion, puis rapproche ton roi d'un pas.",
    },
    {
        "id": "q-vs-p7-c", "title": "Pion fou sur la 7e contre dame", "objective": "draw", "goal": "hold",
        "fen": "7K/8/8/8/4Q3/8/1kp5/8 b - - 0 1", "difficulty": 1400,
        "principle": "Pion fou : va dans le coin à côté, le pat te sauve si la dame prend le pion.",
    },
    {
        "id": "q-vs-p7-a", "title": "Pion tour sur la 7e contre dame", "objective": "draw", "goal": "hold",
        "fen": "7K/8/8/8/8/6Q1/pk6/8 b - - 0 1", "difficulty": 1300,
        "principle": "Pion tour : ton roi s'enferme devant lui, la dame n'a que le pat à offrir.",
    },
    {
        "id": "r-vs-b", "title": "Tour contre fou, le bon coin", "objective": "draw", "goal": "hold",
        "fen": "7k/4R3/5K2/8/8/8/8/7b b - - 0 1", "difficulty": 1300,
        "principle": "Roi dans le coin que ton fou ne contrôle pas ; le fou reste sur la grande diagonale.",
    },
    {
        "id": "r-vs-n", "title": "Tour contre cavalier, collés", "objective": "draw", "goal": "hold",
        "fen": "6k1/5n2/4K3/8/8/8/R7/8 b - - 0 1", "difficulty": 1600,
        "principle": "Le cavalier ne quitte jamais son roi : échec ou retour à côté de lui, jamais seul.",
    },
    {
        "id": "r-vs-n-win", "title": "Tour contre cavalier séparé", "objective": "win", "goal": "capture",
        "fen": "5k2/8/4K3/8/8/8/R7/2n5 w - - 0 1", "difficulty": 1600,
        "principle": "Coupe le cavalier de son roi avec la tour, puis traque-le avec ton roi.",
    },
    {
        "id": "r-vs-p-draw", "title": "Pion contre tour : la nulle", "objective": "draw", "goal": "hold",
        "fen": "8/8/8/8/1pk5/8/8/6KR b - - 0 1", "difficulty": 1400,
        "principle": "Pion et roi côte à côte, le roi devant ou à côté : le roi adverse arrive trop tard.",
    },
]

_cache = {}


def load_cache():
    global _cache
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            _cache = json.load(f)


def save_cache():
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_cache, f)
    os.replace(tmp, CACHE)


def probe(board):
    key = " ".join(board.fen().split()[:4])
    if key not in _cache:
        url = API + urllib.parse.quote(key.replace(" ", "_"))
        for attempt in range(8):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "chess-local/prepare-endgame-clock"}), timeout=30) as r:
                    _cache[key] = json.load(r)
                break
            except Exception as e:  # 429 ou réseau : on attend et on réessaie
                if attempt == 7:
                    raise RuntimeError(f"tables injoignables pour {key} : {e}")
                time.sleep(2 + 3 * attempt)
        save_cache()
        time.sleep(0.25)
    return _cache[key]


def mirror_files(board):
    return board.transform(chess.flip_horizontal)


def families():
    """Familles dans l'ordre d'écriture, FEN de base comprise (sans sondage)."""
    with open(ENDGAMES, encoding="utf-8") as f:
        endgames = {e["id"]: e for e in json.load(f)}
    out = []
    for id_, principle in FROM_ENDGAMES.items():
        e = endgames.get(id_)
        if e is None:
            raise SystemExit(f"{id_} absent de endgames.json")
        out.append({"id": id_, "title": e["title"], "objective": e["objective"], "goal": e["goal"], "fen": e["fen"], "difficulty": e["difficulty"], "principle": principle})
    return out + OWN


def variants(fam):
    """Variantes (id, FEN) dédoublonnées : position, miroir (`.m`), couleurs inversées (`.c`), les
    deux (`.mc`). Le point sépare sans ambiguïté : les ids de familles n'en contiennent pas."""
    base = chess.Board(fam["fen"])
    base.clear_stack()
    seen, out = set(), []
    for suffix, board in (("", base), (".m", mirror_files(base)), (".c", base.mirror()), (".mc", mirror_files(base.mirror()))):
        board.halfmove_clock, board.fullmove_number = 0, 1
        fen = board.fen()
        if fen in seen:
            continue
        seen.add(fen)
        out.append((fam["id"] + suffix, fen))
    return out


FLIP = {"loss": "win", "win": "loss", "draw": "draw", "cursed-win": "blessed-loss", "blessed-loss": "cursed-win"}


def verify(fen, objective):
    """None si la variante est gardée, sinon la raison du refus."""
    board = chess.Board(fen)
    if not board.is_valid() or board.is_game_over() or len(board.piece_map()) > 7:
        return "position illégale, terminée ou de plus de 7 pièces"
    res = probe(board)
    want = "win" if objective == "win" else "draw"
    if res.get("category") != want:
        return f"verdict {res.get('category')} au lieu de {want}"
    # Catégorie du coup vue par le joueur (les tables la donnent du point de vue de l'adversaire).
    after = [FLIP.get(m["category"], m["category"]) for m in res.get("moves", [])]
    if all(c == want for c in after):
        return "tous les coups conservent le verdict (position triviale)"
    return None


LINE_PLIES = 8


def dist(m):
    """Distance au mat (DTM, sinon DTZ) d'un coup, du point de vue du camp qui aura le trait."""
    return m.get("dtm") if m.get("dtm") is not None else (m.get("dtz") or 0)


def best_line(fen, objective):
    """Ligne optimale des tables : demi-coups UCI, jusqu'à LINE_PLIES ou la fin de partie."""
    board = chess.Board(fen)
    player = board.turn
    want = "win" if objective == "win" else "draw"
    line = []
    while len(line) < LINE_PLIES and not board.is_game_over():
        moves = probe(board).get("moves", [])
        if not moves:
            break
        if board.turn == player:
            keep = [m for m in moves if FLIP.get(m["category"], m["category"]) == want]
            # Gain : le mat le plus court (DTM du coup, négatif = perte adverse) ; nulle : le premier.
            keep.sort(key=lambda m: -dist(m) if want == "win" else 0)
        else:
            # Adversaire : la meilleure catégorie pour lui, puis la défense la plus longue.
            rank = {"win": 0, "cursed-win": 1, "draw": 2, "blessed-loss": 3, "loss": 4}
            keep = sorted(moves, key=lambda m: (rank.get(FLIP.get(m["category"], m["category"]), 5), -dist(m)))
        if not keep:
            break
        move = chess.Move.from_uci(keep[0]["uci"])
        line.append(move.uci())
        board.push(move)
    return line


def build():
    load_cache()
    out = []
    for fam in families():
        kept = []
        for vid, fen in variants(fam):
            why = verify(fen, fam["objective"])
            if why:
                print(f"écartée {vid} : {why} ({fen})", flush=True)
                continue
            kept.append({"id": vid, "fen": fen, "line": best_line(fen, fam["objective"])})
        if not kept:
            raise SystemExit(f"famille {fam['id']} : aucune variante vérifiée")
        print(f"{fam['id']} : {len(kept)} variante(s)", flush=True)
        out.append({k: fam[k] for k in ("id", "title", "objective", "goal", "difficulty", "principle")} | {"positions": kept})
    return {"source": "tablebase.lichess.ovh (Syzygy, DTM), scripts/prepare-endgame-clock.py", "families": out}


def serialize(data):
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check():
    """Hors ligne : le JSON correspond aux sources (familles, FEN des variantes) et au tampon."""
    errors = []
    try:
        with open(OUT, encoding="utf-8") as f:
            text = f.read()
        data = json.loads(text)
    except (OSError, ValueError) as e:
        sys.exit(f"{OUT} illisible : {e}")
    stamp = open(STAMP).read().strip() if os.path.exists(STAMP) else ""
    if stamp != digest(text):
        errors.append("tampon absent ou périmé : relancer scripts/prepare-endgame-clock.py")
    expected = {f["id"]: f for f in families()}
    got = {f["id"]: f for f in data.get("families", [])}
    if list(expected) != list(got):
        errors.append(f"familles {list(got)} au lieu de {list(expected)}")
    for id_, fam in expected.items():
        g = got.get(id_)
        if not g:
            continue
        for k in ("title", "objective", "goal", "difficulty", "principle"):
            if g.get(k) != fam[k]:
                errors.append(f"{id_} : {k} périmé")
        allowed = dict(variants(fam))
        for p in g.get("positions", []):
            if allowed.get(p.get("id")) != p.get("fen"):
                errors.append(f"{id_} : variante {p.get('id')} inattendue ou FEN périmée")
        if not g.get("positions"):
            errors.append(f"{id_} : aucune position")
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print(f"endgameClock.json à jour : {len(got)} familles, {sum(len(f['positions']) for f in got.values())} positions")


def main():
    if "--check" in sys.argv[1:]:
        check()
        return
    text = serialize(build())
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    with open(STAMP, "w") as f:
        f.write(digest(text) + "\n")
    print(f"écrit : {OUT} et {STAMP}")


if __name__ == "__main__":
    main()
