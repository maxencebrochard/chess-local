#!/usr/bin/env python3
"""Génère src/data/mateDrills.json : positions de départ des mats « contre la montre » (/mats).

Pour chaque schéma, des positions légales sont tirées au hasard (python-chess), puis vérifiées
une à une sur les tables de finales de lichess (https://tablebase.lichess.ovh, Syzygy + DTM) :
seules les positions GAGNÉES pour le camp qui a le trait, avec un mat le plus court (DTM) dans
la plage du schéma, sont gardées. Le DTM est stocké : l'app peut dire « mat en N au mieux ».

Usage (réseau requis, quelques minutes) :
    python3 scripts/prepare-mates.py            # tous les schémas
    python3 scripts/prepare-mates.py kq kbn     # seulement ceux-là (les autres sont conservés)
"""
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request

import chess

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "data", "mateDrills.json")
API = "https://tablebase.lichess.ovh/standard?fen="
PER_PATTERN = 40

# Pièces du camp fort (en plus du roi), plage de « mat en N » (coups du camp fort) visée : des
# positions de bullet, déjà engagées (fou + cavalier : la phase finale vers le bon coin).
PATTERNS = {
    "kq": ("Q", (4, 9)),
    "kr": ("R", (5, 12)),
    "krr": ("RR", (3, 7)),
    "kqr": ("QR", (3, 6)),
    "kbb": ("BB", (6, 12)),
    "kbn": ("BN", (8, 15)),
    "kqp": ("QP", (4, 9)),
    "kp": ("P", (8, 20)),
}


def random_position(pieces, rng):
    """Position légale au hasard : camp fort au trait (couleur tirée au sort), aucun roi en échec."""
    strong = rng.choice([chess.WHITE, chess.BLACK])
    while True:
        board = chess.Board(None)
        board.turn = strong
        squares = rng.sample(range(64), 2 + len(pieces))
        board.set_piece_at(squares[0], chess.Piece(chess.KING, strong))
        board.set_piece_at(squares[1], chess.Piece(chess.KING, not strong))
        ok = True
        for sq, sym in zip(squares[2:], pieces):
            piece = chess.Piece.from_symbol(sym if strong == chess.WHITE else sym.lower())
            if piece.piece_type == chess.PAWN and chess.square_rank(sq) in (0, 7):
                ok = False
            board.set_piece_at(sq, piece)
        if not ok:
            continue
        # Deux fous : de couleurs opposées, sinon le mat est impossible.
        bishops = [sq for sq in squares[2:] if board.piece_type_at(sq) == chess.BISHOP]
        if len(bishops) == 2 and (chess.square_rank(bishops[0]) + chess.square_file(bishops[0])) % 2 == (
            chess.square_rank(bishops[1]) + chess.square_file(bishops[1])
        ) % 2:
            continue
        if not board.is_valid() or board.is_check() or board.is_game_over():
            continue
        return board


def probe(fen):
    url = API + urllib.parse.quote(fen.replace(" ", "_"), safe="/_")
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "chess-local/prepare-mates"}), timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(60)
                continue
            raise
        except OSError:
            time.sleep(2 + attempt * 3)
    raise RuntimeError(f"tablebase injoignable pour {fen}")


def generate(key, rng):
    pieces, (lo, hi) = PATTERNS[key]
    kept, seen, tries = [], set(), 0
    while len(kept) < PER_PATTERN:
        tries += 1
        if tries > 4000:
            raise RuntimeError(f"{key} : pas assez de positions dans la plage {lo}-{hi}")
        board = random_position(pieces, rng)
        fen = board.fen()
        if fen in seen:
            continue
        seen.add(fen)
        res = probe(fen)
        time.sleep(0.25)
        dtm = res.get("dtm")
        if res.get("category") != "win" or not isinstance(dtm, int) or dtm <= 0:
            continue
        mate_in = (dtm + 1) // 2  # DTM en demi-coups jusqu'au mat, camp fort au trait
        if not lo <= mate_in <= hi:
            continue
        kept.append({"fen": fen, "mateIn": mate_in})
        print(f"{key} {len(kept)}/{PER_PATTERN} mat en {mate_in} : {fen}", flush=True)
    kept.sort(key=lambda p: p["mateIn"])
    return kept


def main():
    keys = sys.argv[1:] or list(PATTERNS)
    unknown = [k for k in keys if k not in PATTERNS]
    if unknown:
        sys.exit(f"schéma inconnu : {', '.join(unknown)}")
    data = {"source": "tablebase.lichess.ovh (Syzygy, DTM), scripts/prepare-mates.py", "patterns": {}}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            data["patterns"] = json.load(f).get("patterns", {})
    rng = random.Random(20261005)
    for key in keys:
        data["patterns"][key] = generate(key, rng)
    data["patterns"] = {k: data["patterns"][k] for k in PATTERNS if k in data["patterns"]}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"écrit : {OUT}")


if __name__ == "__main__":
    main()
